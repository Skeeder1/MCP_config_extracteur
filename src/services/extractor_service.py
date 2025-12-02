"""
ExtractorService - Service métier pour l'extraction LLM avec persistence PostgreSQL.

Ce service orchestre l'extraction des configurations MCP via LLM et leur
stockage dans PostgreSQL (mcp_configs + mise à jour de mcp_servers.status).
"""

from typing import Dict, List, Optional
import structlog

from src.database.db_manager import DatabaseManager
from src.database.repositories.servers_repository import ServersRepository
from src.database.repositories.configs_repository import ConfigsRepository
from src.database.repositories.content_repository import ContentRepository
from src.llm_extractor import LLMExtractor
from src.llm_validator import LLMValidator
from src.prompt_builder import PromptBuilder

logger = structlog.get_logger(__name__)


class ExtractorService:
    """
    Service pour extraire les configurations MCP via LLM et les stocker dans PostgreSQL.

    Workflow:
    1. Récupère les serveurs qui n'ont pas encore de config
    2. Pour chaque serveur, extrait la config via LLM
    3. Valide la config par batch
    4. Insère dans mcp_configs
    5. Met à jour mcp_servers.status selon validation
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        extractor: LLMExtractor,
        validator: LLMValidator,
        prompt_builder: PromptBuilder
    ):
        """
        Initialise l'ExtractorService.

        Args:
            db_manager: Gestionnaire de base de données
            extractor: Extracteur LLM
            validator: Validateur LLM
            prompt_builder: Constructeur de prompts
        """
        self.db_manager = db_manager
        self.servers_repo = ServersRepository(db_manager)
        self.configs_repo = ConfigsRepository(db_manager)
        self.content_repo = ContentRepository(db_manager)
        self.extractor = extractor
        self.validator = validator
        self.prompt_builder = prompt_builder

        logger.info("extractor_service_initialized")

    def get_servers_to_process(self, limit: Optional[int] = None) -> List[dict]:
        """
        Récupère les serveurs qui n'ont pas encore de config.

        Args:
            limit: Nombre maximum de serveurs à retourner

        Returns:
            Liste de dicts avec server_id, github_url, metadata, README content
        """
        query = """
            SELECT
                s.id as server_id,
                s.slug,
                s.name,
                s.github_url,
                s.github_owner,
                s.github_repo,
                s.github_stars,
                s.github_forks,
                s.primary_language,
                s.description,
                c.content as readme_content
            FROM mcp_servers s
            LEFT JOIN mcp_configs cfg ON cfg.server_id = s.id
            LEFT JOIN mcp_content c ON c.server_id = s.id AND c.content_type = 'readme'
            WHERE cfg.id IS NULL  -- Pas encore de config
            AND s.status != 'rejected'  -- Pas les serveurs rejetés
        """

        if limit:
            query += f" LIMIT {limit}"

        servers = self.db_manager.fetch_all(query)

        logger.info("servers_to_process_retrieved", count=len(servers))
        return servers

    async def process_server(self, server: dict) -> dict:
        """
        Extrait la config d'un serveur via LLM.

        Args:
            server: Dict avec server_id, github_url, README content, etc.

        Returns:
            Dict avec:
                - server_id: UUID du serveur
                - github_url: URL GitHub
                - config: Config extraite (ou None si échec)
                - extraction: Métadonnées d'extraction (model, tokens, etc.)
                - error: Message d'erreur (si échec)
        """
        server_id = server['server_id']
        github_url = server['github_url']

        logger.info("processing_server_extraction", server_id=server_id, github_url=github_url)

        try:
            # 1. Construire le contexte (simuler repo_data comme avant)
            repo_data = self._build_repo_data_from_server(server)

            # 2. Construire le prompt (files et metadata séparément)
            prompt = self.prompt_builder.build_prompt(
                files=repo_data['files'],
                metadata=repo_data['metadata']
            )

            # 3. Extraire la config via LLM
            extraction_result = await self.extractor.extract_config(prompt)

            # Vérifier si l'extraction a réussi
            if extraction_result.get('error'):
                logger.error(
                    "extraction_failed",
                    server_id=server_id,
                    error=extraction_result['error']
                )
                return {
                    'server_id': server_id,
                    'github_url': github_url,
                    'config': None,
                    'extraction': {'error': extraction_result['error']},
                    'error': extraction_result['error']
                }

            # extraction_result IS the config (with _llm_metadata inside)
            config = extraction_result

            # Extract metadata for tracking
            llm_metadata = config.pop('_llm_metadata', {})

            return {
                'server_id': server_id,
                'github_url': github_url,
                'slug': server.get('slug'),
                'name': server.get('name'),
                'config': config,
                'extraction': llm_metadata,  # Store LLM metadata separately
                'github_metadata': {
                    'name': server.get('name'),
                    'stars': server.get('github_stars', 0),
                    'language': server.get('primary_language')
                }
            }

        except Exception as e:
            logger.error(
                "process_server_exception",
                server_id=server_id,
                error=str(e),
                exc_info=True
            )
            return {
                'server_id': server_id,
                'github_url': github_url,
                'config': None,
                'extraction': {'error': str(e)},
                'error': str(e)
            }

    async def process_batch(
        self,
        servers: List[dict],
        start_index: int = 0,
        total: int = None
    ) -> List[dict]:
        """
        Traite un batch de serveurs avec extraction et validation.

        Args:
            servers: Liste de serveurs à traiter
            start_index: Index de départ pour l'affichage
            total: Nombre total de serveurs (pour l'affichage)

        Returns:
            Liste de résultats avec configs extraites et validées
        """
        import asyncio

        if total is None:
            total = len(servers)

        logger.info("processing_batch", count=len(servers))

        # Step 1: Extract all configs in parallel
        tasks = [self.process_server(server) for server in servers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter exceptions
        valid_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error("batch_task_failed", error=str(result))
            else:
                valid_results.append(result)

        if not valid_results:
            return []

        # Step 2: Validate all configs in one LLM call
        configs_to_validate = [r["config"] for r in valid_results if r.get("config")]

        if configs_to_validate:
            try:
                validations = await self.validator.validate_batch(configs_to_validate)

                # Merge validation results back
                validation_idx = 0
                for result in valid_results:
                    if result.get("config"):
                        validation = validations[validation_idx]

                        # Add validation data to extraction
                        result["extraction"]["status"] = validation["status"]
                        result["extraction"]["score"] = validation["score"]
                        result["extraction"]["confidence"] = validation["confidence"]
                        result["extraction"]["issues"] = validation["issues"]
                        result["extraction"]["warnings"] = validation["warnings"]

                        # Nullify config if rejected
                        if validation["status"] == "rejected":
                            result["config"] = None

                        validation_idx += 1

                    else:
                        # No config extracted (error case)
                        result["extraction"]["status"] = "rejected"
                        result["extraction"]["score"] = 0.0
                        result["extraction"]["confidence"] = 0.0
                        result["extraction"]["issues"] = ["Extraction failed"]
                        result["extraction"]["warnings"] = []

            except Exception as e:
                logger.error("batch_validation_failed", error=str(e))
                # Fallback: mark all as needs_review
                for result in valid_results:
                    if result.get("config"):
                        result["extraction"]["status"] = "needs_review"
                        result["extraction"]["score"] = -1.0
                        result["extraction"]["confidence"] = 0.5
                        result["extraction"]["issues"] = [f"Validation failed: {str(e)}"]
                        result["extraction"]["warnings"] = ["Needs manual review"]

        # Step 3: Store configs in PostgreSQL and update server status
        for result in valid_results:
            server_id = result['server_id']
            config = result.get('config')
            extraction = result.get('extraction', {})
            status = extraction.get('status', 'pending')
            score = extraction.get('score', 0.0)

            if config:
                # Insert config dans mcp_configs
                try:
                    # Déduire le config_type depuis le command
                    config_type = self._infer_config_type(config)

                    config_data = {
                        'config_type': config_type,
                        'config_json': config
                    }

                    self.configs_repo.insert_config(server_id, config_data)
                    logger.info("config_stored", server_id=server_id, config_type=config_type)

                except Exception as e:
                    logger.error("config_insert_failed", server_id=server_id, error=str(e))

            # Update server status
            self.update_server_status(server_id, status, score)

        return valid_results

    def update_server_status(self, server_id: str, validation_status: str, score: float):
        """
        Met à jour le status du serveur après validation.

        Mapping:
        - approved (score >= 7.0) → status='approved'
        - needs_review (5.0 <= score < 7.0) → status='pending'
        - rejected (score < 5.0) → status='rejected'

        Args:
            server_id: UUID du serveur
            validation_status: Status de validation ('approved', 'needs_review', 'rejected')
            score: Score de validation (0-10)
        """
        # Mapper validation_status vers server status
        status_mapping = {
            'approved': 'approved',
            'needs_review': 'pending',
            'rejected': 'rejected'
        }

        new_status = status_mapping.get(validation_status, 'pending')

        # Mise à jour
        self.servers_repo.update_server(server_id, {'status': new_status})

        logger.info(
            "server_status_updated",
            server_id=server_id,
            status=new_status,
            validation_status=validation_status,
            score=score
        )

    def get_extraction_statistics(self) -> dict:
        """
        Calcule les statistiques d'extraction depuis PostgreSQL.

        Returns:
            Dict avec:
                - total_servers: Nombre total de serveurs
                - with_config: Nombre de serveurs avec config
                - without_config: Nombre de serveurs sans config
                - by_status: Dict {status: count}
                - avg_stars_with_config: Moyenne des étoiles pour serveurs avec config
        """
        # Total serveurs
        total_servers = len(self.servers_repo.get_all_servers())

        # Serveurs avec config
        with_config_query = """
            SELECT COUNT(DISTINCT server_id)
            FROM mcp_configs
        """
        with_config = self.db_manager.fetch_value(with_config_query) or 0
        without_config = total_servers - with_config

        # Count par status
        all_servers = self.servers_repo.get_all_servers()
        by_status = {}
        total_stars_with_config = 0
        stars_count = 0

        for server in all_servers:
            status = server.get('status', 'unknown')
            by_status[status] = by_status.get(status, 0) + 1

        # Moyenne étoiles pour serveurs avec config
        avg_stars_query = """
            SELECT AVG(s.github_stars)
            FROM mcp_servers s
            JOIN mcp_configs c ON c.server_id = s.id
            WHERE s.github_stars > 0
        """
        avg_stars_with_config = self.db_manager.fetch_value(avg_stars_query) or 0

        stats = {
            'total_servers': total_servers,
            'with_config': with_config,
            'without_config': without_config,
            'by_status': by_status,
            'avg_stars_with_config': round(float(avg_stars_with_config), 2) if avg_stars_with_config else 0
        }

        logger.info("extraction_statistics_computed", stats=stats)
        return stats

    def _build_repo_data_from_server(self, server: dict) -> dict:
        """
        Construit un repo_data au format attendu par PromptBuilder depuis un server dict.

        Args:
            server: Dict depuis get_servers_to_process()

        Returns:
            Dict au format repo_data (metadata, files, etc.)
        """
        # Réconstruire la structure files
        files = {}
        readme_content = server.get('readme_content')
        if readme_content:
            files['README.md'] = readme_content

        return {
            'github_url': server['github_url'],
            'metadata': {
                'name': server.get('name', ''),
                'full_name': f"{server.get('github_owner', '')}/{server.get('github_repo', '')}",
                'description': server.get('description', ''),
                'language': server.get('primary_language'),
                'stars': server.get('github_stars', 0),
                'forks': server.get('github_forks', 0)
            },
            'files': files,
            'files_count': len(files)
        }

    def _infer_config_type(self, config: dict) -> str:
        """
        Infère le config_type depuis le command de la config.

        Args:
            config: Config dict avec 'command', 'args', etc.

        Returns:
            Type de config ('npm', 'python', 'docker', 'binary', 'other')
        """
        command = config.get('command', '').lower()

        if 'npx' in command or 'node' in command or 'npm' in command:
            return 'npm'
        elif 'python' in command or 'uvx' in command:
            return 'python'
        elif 'docker' in command:
            return 'docker'
        elif command in ['go', 'cargo', 'dotnet', 'java']:
            return 'binary'
        else:
            return 'other'
