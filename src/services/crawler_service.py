"""
CrawlerService - Service métier pour le crawling GitHub avec persistence PostgreSQL.

Ce service orchestre le crawling des serveurs MCP depuis GitHub et leur
stockage dans PostgreSQL (mcp_servers + mcp_content).
"""

from typing import Dict, Set, Optional
from datetime import datetime, timedelta
import structlog

from src.database.db_manager import DatabaseManager
from src.database.repositories.servers_repository import ServersRepository
from src.database.repositories.content_repository import ContentRepository
from src.github_crawler import GitHubCrawler

logger = structlog.get_logger(__name__)


class CrawlerService:
    """
    Service pour crawler les serveurs GitHub et les stocker dans PostgreSQL.

    Workflow:
    1. Vérifie si le serveur existe déjà (par github_url)
    2. Si récent (<7 jours), skip
    3. Sinon, crawle GitHub (fetch metadata + files)
    4. Insert/Update dans mcp_servers
    5. Extrait README et insère dans mcp_content
    """

    def __init__(self, db_manager: DatabaseManager, github_token: str):
        """
        Initialise le CrawlerService.

        Args:
            db_manager: Gestionnaire de base de données
            github_token: Token GitHub pour l'API
        """
        self.db_manager = db_manager
        self.servers_repo = ServersRepository(db_manager)
        self.content_repo = ContentRepository(db_manager)
        self.crawler = GitHubCrawler(github_token)

        logger.info("crawler_service_initialized")

    def process_server(self, server_input: dict, force_update: bool = False) -> dict:
        """
        Crawle un serveur GitHub et l'enregistre dans la DB.

        Args:
            server_input: Dict avec github_url, slug, name, etc.
                Exemple: {
                    'github_url': 'https://github.com/user/repo',
                    'slug': 'my-server',
                    'name': 'My MCP Server'
                }
            force_update: Si True, force le re-crawl même si récent

        Returns:
            Dict avec:
                - status: 'success', 'skipped', ou 'error'
                - server_id: UUID du serveur (si success)
                - message: Message descriptif
                - error: Message d'erreur (si status='error')
        """
        github_url = server_input.get('github_url')
        slug = server_input.get('slug', '')

        if not github_url:
            return {
                'status': 'error',
                'error': 'Missing github_url in server_input'
            }

        logger.info("processing_server", github_url=github_url, slug=slug)

        try:
            # 1. Vérifier si le serveur existe déjà
            existing_server = self.servers_repo.get_server_by_github_url(github_url)

            if existing_server and not force_update:
                # Vérifier la date de dernière mise à jour
                updated_at = existing_server.get('updated_at')
                if updated_at:
                    # Si mis à jour il y a moins de 7 jours, skip
                    if isinstance(updated_at, str):
                        updated_at = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))

                    days_since_update = (datetime.now(updated_at.tzinfo) - updated_at).days

                    if days_since_update < 7:
                        logger.info(
                            "server_recently_updated",
                            github_url=github_url,
                            days_since_update=days_since_update
                        )
                        return {
                            'status': 'skipped',
                            'server_id': existing_server['id'],
                            'message': f'Server updated {days_since_update} days ago (skip)'
                        }

            # 2. Crawler GitHub pour obtenir les données
            logger.info("crawling_github", github_url=github_url)
            repo_data = self.crawler.fetch_repo_data_with_retry(github_url)

            # Vérifier si erreur de crawl
            if 'error' in repo_data:
                logger.error("crawl_failed", github_url=github_url, error=repo_data['error'])

                # Si le serveur existe déjà, on le garde tel quel
                if existing_server:
                    return {
                        'status': 'error',
                        'server_id': existing_server['id'],
                        'error': repo_data['error'],
                        'message': 'Crawl failed but server already exists'
                    }
                else:
                    # Insérer quand même le serveur avec status='rejected'
                    server_data = self._build_server_data_from_input(server_input, repo_data)
                    server_data['status'] = 'rejected'
                    server_id = self.servers_repo.insert_server(server_data)

                    return {
                        'status': 'error',
                        'server_id': server_id,
                        'error': repo_data['error'],
                        'message': 'Server inserted with status=rejected'
                    }

            # 3. Construire les données du serveur depuis repo_data
            server_data = self._build_server_data_from_crawl(server_input, repo_data)

            # 4. Insérer ou mettre à jour le serveur
            if existing_server:
                # Update
                server_id = existing_server['id']
                self.servers_repo.update_server(server_id, server_data)
                logger.info("server_updated", server_id=server_id, github_url=github_url)
            else:
                # Insert
                server_id = self.servers_repo.insert_server(server_data)
                logger.info("server_inserted", server_id=server_id, github_url=github_url)

            # 5. Extraire et stocker le README
            readme_inserted = self._extract_and_store_readme(server_id, repo_data)

            return {
                'status': 'success',
                'server_id': server_id,
                'message': f'Server crawled and stored (README: {readme_inserted})',
                'files_count': repo_data.get('files_count', 0),
                'readme_stored': readme_inserted
            }

        except Exception as e:
            logger.error("process_server_failed", github_url=github_url, error=str(e), exc_info=True)
            return {
                'status': 'error',
                'error': str(e),
                'message': 'Unexpected error during processing'
            }

    def _build_server_data_from_input(self, server_input: dict, repo_data: dict) -> dict:
        """
        Construit server_data depuis server_input (quand crawl a échoué).

        Args:
            server_input: Données d'entrée du serveur
            repo_data: Données du crawl (avec erreur)

        Returns:
            Dict pour insertion dans mcp_servers
        """
        return {
            'slug': server_input.get('slug', ''),
            'name': server_input.get('name', ''),
            'github_url': server_input['github_url'],
            'github_owner': self._extract_owner_from_url(server_input['github_url']),
            'github_repo': self._extract_repo_from_url(server_input['github_url']),
            'status': 'pending'
        }

    def _build_server_data_from_crawl(self, server_input: dict, repo_data: dict) -> dict:
        """
        Construit server_data depuis repo_data (crawl réussi).

        Args:
            server_input: Données d'entrée (slug, name)
            repo_data: Données du crawl GitHub

        Returns:
            Dict pour insertion/update dans mcp_servers
        """
        metadata = repo_data.get('metadata', {})

        # Extraire owner et repo depuis l'URL
        github_url = repo_data['github_url']
        owner = self._extract_owner_from_url(github_url)
        repo_name = self._extract_repo_from_url(github_url)

        return {
            'slug': server_input.get('slug', repo_name),
            'name': server_input.get('name', metadata.get('name', repo_name)),
            'display_name': metadata.get('name', server_input.get('name', repo_name)),
            'description': metadata.get('description', ''),
            'github_url': github_url,
            'github_owner': owner,
            'github_repo': repo_name,
            'github_stars': metadata.get('stars', 0),
            'github_forks': metadata.get('forks', 0),
            'github_last_commit': self._parse_datetime(metadata.get('updated_at')),
            'primary_language': metadata.get('language'),
            'homepage_url': metadata.get('homepage'),
            'status': 'approved'  # Par défaut approved si crawl réussi
        }

    def _extract_and_store_readme(self, server_id: str, repo_data: dict) -> bool:
        """
        Extrait le README depuis repo_data et le stocke dans mcp_content.

        Args:
            server_id: UUID du serveur
            repo_data: Données du crawl contenant files

        Returns:
            True si README trouvé et inséré, False sinon
        """
        files = repo_data.get('files', {})

        # Chercher le README parmi les fichiers
        readme_content = None
        for file_name, content in files.items():
            if 'README' in file_name.upper():
                readme_content = content
                break

        if not readme_content:
            logger.info("no_readme_found", server_id=server_id)
            return False

        # Vérifier si un README existe déjà pour ce serveur
        existing_readme = self.content_repo.get_content_by_type(server_id, 'readme')

        if existing_readme:
            # Update
            self.content_repo.update_content(existing_readme['id'], readme_content)
            logger.info("readme_updated", server_id=server_id)
        else:
            # Insert
            self.content_repo.insert_content(server_id, 'readme', readme_content)
            logger.info("readme_inserted", server_id=server_id)

        return True

    def _extract_owner_from_url(self, github_url: str) -> str:
        """Extrait le owner depuis l'URL GitHub."""
        # https://github.com/owner/repo -> owner
        parts = github_url.rstrip('/').split('/')
        if len(parts) >= 2:
            return parts[-2]
        return ''

    def _extract_repo_from_url(self, github_url: str) -> str:
        """Extrait le nom du repo depuis l'URL GitHub."""
        # https://github.com/owner/repo -> repo
        parts = github_url.rstrip('/').split('/')
        if len(parts) >= 1:
            return parts[-1]
        return ''

    def _parse_datetime(self, dt_string: Optional[str]) -> Optional[datetime]:
        """Parse une chaîne datetime ISO."""
        if not dt_string:
            return None
        try:
            return datetime.fromisoformat(dt_string.replace('Z', '+00:00'))
        except Exception:
            return None

    def get_processed_urls(self) -> Set[str]:
        """
        Retourne l'ensemble des URLs GitHub déjà crawlées.

        Returns:
            Set des github_url déjà présentes dans mcp_servers
        """
        all_servers = self.servers_repo.get_all_servers()
        urls = {server['github_url'] for server in all_servers if 'github_url' in server}

        logger.info("processed_urls_retrieved", count=len(urls))
        return urls

    def get_crawl_statistics(self) -> dict:
        """
        Calcule les statistiques du crawling.

        Returns:
            Dict avec:
                - total_servers: Nombre total de serveurs
                - by_status: Dict {status: count}
                - with_readme: Nombre de serveurs avec README
                - avg_stars: Moyenne des étoiles GitHub
        """
        all_servers = self.servers_repo.get_all_servers()

        # Count par status
        by_status = {}
        total_stars = 0
        stars_count = 0

        for server in all_servers:
            status = server.get('status', 'unknown')
            by_status[status] = by_status.get(status, 0) + 1

            stars = server.get('github_stars', 0)
            if stars > 0:
                total_stars += stars
                stars_count += 1

        # Count serveurs avec README
        readme_query = """
            SELECT COUNT(DISTINCT server_id)
            FROM mcp_content
            WHERE content_type = 'readme'
        """
        with_readme = self.db_manager.fetch_value(readme_query) or 0

        stats = {
            'total_servers': len(all_servers),
            'by_status': by_status,
            'with_readme': with_readme,
            'avg_stars': round(total_stars / stars_count, 2) if stars_count > 0 else 0
        }

        logger.info("crawl_statistics_computed", stats=stats)
        return stats
