"""
ContentRepository - Gestion du contenu MCP (table mcp_content).

Repository pour les opérations CRUD sur le contenu (README, about, FAQ, etc.).
"""

from typing import Optional, List, Dict
import structlog

logger = structlog.get_logger(__name__)


class ContentRepository:
    """
    Repository pour la table mcp_content.

    Gère le contenu textuel associé aux serveurs (README, about, FAQ, changelog).
    Relation 1:N avec mcp_servers.
    """

    def __init__(self, db_manager):
        """
        Initialise le repository.

        Args:
            db_manager: Instance de DatabaseManager
        """
        self.db = db_manager

    def insert_content(
        self,
        server_id: str,
        content_type: str,
        content: str
    ) -> str:
        """
        Insère un nouveau contenu pour un serveur.

        Args:
            server_id: UUID du serveur
            content_type: Type de contenu (readme/about/faq/changelog)
            content: Texte du contenu (markdown)

        Returns:
            UUID du contenu créé

        Example:
            content_id = repo.insert_content(
                server_id,
                'readme',
                '# Brave Search MCP Server\\n\\n## Installation...'
            )
        """
        query = """
            INSERT INTO mcp_content (
                server_id, content_type, content
            ) VALUES (
                %s, %s, %s
            )
            RETURNING id
        """

        with self.db.get_cursor(dict_cursor=False) as cursor:
            cursor.execute(query, (server_id, content_type, content))
            content_id = cursor.fetchone()[0]

        logger.info(
            "content_inserted",
            content_id=str(content_id),
            server_id=server_id,
            content_type=content_type,
            content_length=len(content)
        )
        return str(content_id)

    def get_content_by_id(self, content_id: str) -> Optional[Dict]:
        """
        Récupère un contenu par son ID.

        Args:
            content_id: UUID du contenu

        Returns:
            Dict contenant le contenu ou None
        """
        query = "SELECT * FROM mcp_content WHERE id = %s"
        return self.db.fetch_one(query, (content_id,))

    def get_content_by_server(self, server_id: str) -> List[Dict]:
        """
        Récupère tous les contenus d'un serveur.

        Args:
            server_id: UUID du serveur

        Returns:
            Liste de contenus (readme, about, etc.)
        """
        query = """
            SELECT * FROM mcp_content
            WHERE server_id = %s
            ORDER BY content_type
        """
        return self.db.fetch_all(query, (server_id,))

    def get_content_by_type(
        self,
        server_id: str,
        content_type: str
    ) -> Optional[Dict]:
        """
        Récupère un type de contenu spécifique pour un serveur.

        Args:
            server_id: UUID du serveur
            content_type: Type de contenu (readme/about/faq/changelog)

        Returns:
            Dict contenant le contenu ou None

        Example:
            readme = repo.get_content_by_type(server_id, 'readme')
        """
        query = """
            SELECT * FROM mcp_content
            WHERE server_id = %s AND content_type = %s
        """
        return self.db.fetch_one(query, (server_id, content_type))

    def update_content(self, content_id: str, content: str) -> bool:
        """
        Met à jour le texte d'un contenu.

        Args:
            content_id: UUID du contenu
            content: Nouveau texte

        Returns:
            True si mis à jour
        """
        query = """
            UPDATE mcp_content
            SET content = %s
            WHERE id = %s
        """

        self.db.execute_query(query, (content, content_id))
        logger.info("content_updated", content_id=content_id, length=len(content))
        return True

    def upsert_content(
        self,
        server_id: str,
        content_type: str,
        content: str
    ) -> str:
        """
        Insert ou Update un contenu (si existe déjà).

        Args:
            server_id: UUID du serveur
            content_type: Type de contenu
            content: Texte du contenu

        Returns:
            UUID du contenu (existant ou créé)

        Note:
            Utilise ON CONFLICT pour gérer les doublons
        """
        # Vérifier si existe
        existing = self.get_content_by_type(server_id, content_type)

        if existing:
            # Update
            self.update_content(existing['id'], content)
            return existing['id']
        else:
            # Insert
            return self.insert_content(server_id, content_type, content)

    def delete_content(self, content_id: str) -> bool:
        """
        Supprime un contenu.

        Args:
            content_id: UUID du contenu

        Returns:
            True si supprimé
        """
        query = "DELETE FROM mcp_content WHERE id = %s"
        self.db.execute_query(query, (content_id,))
        logger.info("content_deleted", content_id=content_id)
        return True

    def delete_content_by_type(self, server_id: str, content_type: str) -> bool:
        """
        Supprime un type de contenu spécifique pour un serveur.

        Args:
            server_id: UUID du serveur
            content_type: Type de contenu à supprimer

        Returns:
            True si supprimé
        """
        query = """
            DELETE FROM mcp_content
            WHERE server_id = %s AND content_type = %s
        """
        self.db.execute_query(query, (server_id, content_type))
        logger.info("content_type_deleted", server_id=server_id, content_type=content_type)
        return True

    def search_in_content(self, search_term: str, limit: int = 20) -> List[Dict]:
        """
        Recherche dans le contenu (full-text search).

        Args:
            search_term: Terme à rechercher
            limit: Nombre maximum de résultats

        Returns:
            Liste de contenus correspondants

        Note:
            Utilise l'index full-text (to_tsvector)
        """
        query = """
            SELECT c.*, s.name as server_name, s.slug
            FROM mcp_content c
            JOIN mcp_servers s ON s.id = c.server_id
            WHERE to_tsvector('english', c.content) @@ plainto_tsquery('english', %s)
            ORDER BY ts_rank(to_tsvector('english', c.content), plainto_tsquery('english', %s)) DESC
            LIMIT %s
        """
        return self.db.fetch_all(query, (search_term, search_term, limit))

    def get_readme_for_server(self, server_id: str) -> Optional[str]:
        """
        Récupère uniquement le texte du README d'un serveur.

        Args:
            server_id: UUID du serveur

        Returns:
            Texte du README ou None

        Utile pour:
            Construire les prompts LLM sans charger tout l'objet
        """
        content = self.get_content_by_type(server_id, 'readme')
        return content['content'] if content else None
