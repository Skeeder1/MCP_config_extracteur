"""
ServersRepository - Gestion des serveurs MCP (table mcp_servers).

Repository pour toutes les opérations CRUD sur la table centrale mcp_servers.
"""

from typing import Optional, List, Dict
from datetime import datetime
import structlog

logger = structlog.get_logger(__name__)


class ServersRepository:
    """
    Repository pour la table mcp_servers.

    Gère toutes les opérations sur les serveurs MCP : création, lecture,
    mise à jour, recherche, etc.
    """

    def __init__(self, db_manager):
        """
        Initialise le repository.

        Args:
            db_manager: Instance de DatabaseManager
        """
        self.db = db_manager

    def insert_server(self, server_data: dict) -> str:
        """
        Insère un nouveau serveur dans la base de données.

        Args:
            server_data: Dict contenant les données du serveur
                Champs obligatoires: slug, name, display_name, github_url,
                                    github_owner, github_repo

        Returns:
            UUID du serveur créé (string)

        Example:
            server_id = repo.insert_server({
                'slug': 'brave-search',
                'name': 'brave-search',
                'display_name': 'Brave Search MCP Server',
                'github_url': 'https://github.com/brave/brave-search-mcp',
                'github_owner': 'brave',
                'github_repo': 'brave-search-mcp',
                'github_stars': 856,
                'primary_language': 'TypeScript'
            })
        """
        query = """
            INSERT INTO mcp_servers (
                slug, name, display_name, tagline, description,
                logo_url, homepage_url,
                github_url, github_owner, github_repo,
                github_stars, github_forks, github_last_commit,
                primary_language, license,
                install_count, favorite_count, tools_count,
                categories, tags,
                status, creator_username
            ) VALUES (
                %(slug)s, %(name)s, %(display_name)s, %(tagline)s, %(description)s,
                %(logo_url)s, %(homepage_url)s,
                %(github_url)s, %(github_owner)s, %(github_repo)s,
                %(github_stars)s, %(github_forks)s, %(github_last_commit)s,
                %(primary_language)s, %(license)s,
                %(install_count)s, %(favorite_count)s, %(tools_count)s,
                %(categories)s, %(tags)s,
                %(status)s, %(creator_username)s
            )
            RETURNING id
        """

        # Valeurs par défaut
        defaults = {
            'display_name': server_data.get('name', ''),  # Use name as display_name by default
            'tagline': '',
            'description': '',
            'logo_url': None,
            'homepage_url': None,
            'github_stars': 0,
            'github_forks': 0,
            'github_last_commit': None,
            'primary_language': None,
            'license': None,
            'install_count': 0,
            'favorite_count': 0,
            'tools_count': 0,
            'categories': [],
            'tags': [],
            'status': 'approved',
            'creator_username': None
        }

        # Fusionner avec les valeurs fournies
        params = {**defaults, **server_data}

        # S'assurer que display_name existe
        if 'display_name' not in params or not params['display_name']:
            params['display_name'] = params.get('name', '')

        with self.db.get_cursor(dict_cursor=False) as cursor:
            cursor.execute(query, params)
            server_id = cursor.fetchone()[0]

        logger.info("server_inserted", server_id=str(server_id), slug=params['slug'])
        return str(server_id)

    def get_server_by_id(self, server_id: str) -> Optional[Dict]:
        """
        Récupère un serveur par son ID.

        Args:
            server_id: UUID du serveur

        Returns:
            Dict contenant les données du serveur ou None
        """
        query = "SELECT * FROM mcp_servers WHERE id = %s"
        return self.db.fetch_one(query, (server_id,))

    def get_server_by_github_url(self, github_url: str) -> Optional[Dict]:
        """
        Récupère un serveur par son URL GitHub.

        Args:
            github_url: URL GitHub du repository

        Returns:
            Dict contenant les données du serveur ou None
        """
        query = "SELECT * FROM mcp_servers WHERE github_url = %s"
        return self.db.fetch_one(query, (github_url,))

    def get_server_by_slug(self, slug: str) -> Optional[Dict]:
        """
        Récupère un serveur par son slug.

        Args:
            slug: Slug unique du serveur

        Returns:
            Dict contenant les données du serveur ou None
        """
        query = "SELECT * FROM mcp_servers WHERE slug = %s"
        return self.db.fetch_one(query, (slug,))

    def update_server(self, server_id: str, updates: dict) -> bool:
        """
        Met à jour un serveur existant.

        Args:
            server_id: UUID du serveur
            updates: Dict des champs à mettre à jour

        Returns:
            True si mis à jour, False sinon

        Example:
            repo.update_server(server_id, {
                'github_stars': 900,
                'status': 'approved'
            })
        """
        if not updates:
            return False

        # Construire la clause SET dynamiquement
        set_clauses = []
        params = {}

        for key, value in updates.items():
            set_clauses.append(f"{key} = %({key})s")
            params[key] = value

        params['server_id'] = server_id

        query = f"""
            UPDATE mcp_servers
            SET {', '.join(set_clauses)}
            WHERE id = %(server_id)s
        """

        self.db.execute_query(query, params)
        logger.info("server_updated", server_id=server_id, fields=list(updates.keys()))
        return True

    def get_all_servers(self, status: Optional[str] = None, limit: Optional[int] = None) -> List[Dict]:
        """
        Récupère tous les serveurs, optionnellement filtrés par status.

        Args:
            status: Filtrer par status (approved/pending/rejected) ou None pour tous
            limit: Limiter le nombre de résultats

        Returns:
            Liste de dicts contenant les serveurs
        """
        if status:
            query = "SELECT * FROM mcp_servers WHERE status = %s ORDER BY github_stars DESC"
            params = (status,)
        else:
            query = "SELECT * FROM mcp_servers ORDER BY github_stars DESC"
            params = None

        if limit:
            query += f" LIMIT {limit}"

        return self.db.fetch_all(query, params)

    def server_exists(self, github_url: str) -> bool:
        """
        Vérifie si un serveur existe déjà (par URL GitHub).

        Args:
            github_url: URL GitHub du repository

        Returns:
            True si le serveur existe, False sinon
        """
        query = "SELECT EXISTS(SELECT 1 FROM mcp_servers WHERE github_url = %s)"
        return self.db.fetch_value(query, (github_url,))

    def get_processed_urls(self) -> set:
        """
        Récupère l'ensemble de toutes les URLs GitHub déjà crawlées.

        Returns:
            Set d'URLs GitHub

        Utile pour:
            La déduplication lors du crawling
        """
        query = "SELECT github_url FROM mcp_servers"
        results = self.db.fetch_all(query)
        return {row['github_url'] for row in results}

    def get_servers_updated_before(self, days: int = 7) -> List[Dict]:
        """
        Récupère les serveurs non mis à jour depuis X jours.

        Args:
            days: Nombre de jours

        Returns:
            Liste de serveurs à re-crawler
        """
        query = """
            SELECT * FROM mcp_servers
            WHERE updated_at < NOW() - INTERVAL '%s days'
            ORDER BY github_stars DESC
        """
        return self.db.fetch_all(query, (days,))

    def get_servers_without_config(self, limit: Optional[int] = None) -> List[Dict]:
        """
        Récupère les serveurs qui n'ont pas encore de configuration.

        Args:
            limit: Limiter le nombre de résultats

        Returns:
            Liste de serveurs sans config

        Utile pour:
            Identifier les serveurs à traiter par l'extractor
        """
        query = """
            SELECT s.*
            FROM mcp_servers s
            LEFT JOIN mcp_configs c ON c.server_id = s.id
            WHERE c.id IS NULL
            ORDER BY s.github_stars DESC
        """

        if limit:
            query += f" LIMIT {limit}"

        return self.db.fetch_all(query)

    def get_statistics(self) -> Dict:
        """
        Récupère les statistiques globales sur les serveurs.

        Returns:
            Dict avec les stats (total, par status, moyennes, etc.)
        """
        query = "SELECT * FROM v_global_statistics"
        stats = self.db.fetch_one(query)

        if stats:
            # Convertir les Decimal en float pour la sérialisation JSON
            return {
                key: float(value) if isinstance(value, (int, float)) and value is not None else value
                for key, value in stats.items()
            }

        return {}

    def delete_server(self, server_id: str) -> bool:
        """
        Supprime un serveur (et ses configs/content via CASCADE).

        Args:
            server_id: UUID du serveur

        Returns:
            True si supprimé

        Note:
            Supprime également les configs et content associés (CASCADE)
        """
        query = "DELETE FROM mcp_servers WHERE id = %s"
        self.db.execute_query(query, (server_id,))
        logger.info("server_deleted", server_id=server_id)
        return True

    def search_servers(self, search_term: str, limit: int = 20) -> List[Dict]:
        """
        Recherche des serveurs par nom, description ou slug.

        Args:
            search_term: Terme de recherche
            limit: Nombre maximum de résultats

        Returns:
            Liste de serveurs correspondants
        """
        query = """
            SELECT * FROM mcp_servers
            WHERE
                name ILIKE %s OR
                display_name ILIKE %s OR
                slug ILIKE %s OR
                description ILIKE %s
            ORDER BY github_stars DESC
            LIMIT %s
        """
        pattern = f"%{search_term}%"
        return self.db.fetch_all(query, (pattern, pattern, pattern, pattern, limit))
