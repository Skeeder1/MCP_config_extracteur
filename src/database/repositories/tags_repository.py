"""
TagsRepository - Gestion des tags (table mcp_tags).

Repository pour les opérations CRUD sur les tags (référentiel).
"""

from typing import Optional, List, Dict
import structlog

logger = structlog.get_logger(__name__)


class TagsRepository:
    """
    Repository pour la table mcp_tags.

    Gère le référentiel des tags utilisés pour étiqueter les serveurs.
    """

    def __init__(self, db_manager):
        """
        Initialise le repository.

        Args:
            db_manager: Instance de DatabaseManager
        """
        self.db = db_manager

    def insert_tag(
        self,
        slug: str,
        name: str,
        color: Optional[str] = None
    ) -> str:
        """
        Insère un nouveau tag.

        Args:
            slug: Identifiant unique URL-friendly
            name: Nom d'affichage
            color: Couleur hexadécimale (optionnel)

        Returns:
            UUID du tag créé

        Example:
            tag_id = repo.insert_tag('typescript', 'TypeScript', '#3178C6')
        """
        query = """
            INSERT INTO mcp_tags (
                slug, name, color
            ) VALUES (
                %s, %s, %s
            )
            RETURNING id
        """

        with self.db.get_cursor(dict_cursor=False) as cursor:
            cursor.execute(query, (slug, name, color))
            tag_id = cursor.fetchone()[0]

        logger.info("tag_inserted", tag_id=str(tag_id), slug=slug)
        return str(tag_id)

    def get_tag_by_id(self, tag_id: str) -> Optional[Dict]:
        """
        Récupère un tag par son ID.

        Args:
            tag_id: UUID du tag

        Returns:
            Dict contenant le tag ou None
        """
        query = "SELECT * FROM mcp_tags WHERE id = %s"
        return self.db.fetch_one(query, (tag_id,))

    def get_tag_by_slug(self, slug: str) -> Optional[Dict]:
        """
        Récupère un tag par son slug.

        Args:
            slug: Slug du tag

        Returns:
            Dict contenant le tag ou None
        """
        query = "SELECT * FROM mcp_tags WHERE slug = %s"
        return self.db.fetch_one(query, (slug,))

    def get_all_tags(self) -> List[Dict]:
        """
        Récupère tous les tags.

        Returns:
            Liste de tous les tags (triés par nom)
        """
        query = "SELECT * FROM mcp_tags ORDER BY name"
        return self.db.fetch_all(query)

    def update_tag(self, tag_id: str, updates: dict) -> bool:
        """
        Met à jour un tag.

        Args:
            tag_id: UUID du tag
            updates: Dict des champs à mettre à jour

        Returns:
            True si mis à jour

        Example:
            repo.update_tag(tag_id, {'color': '#FF0000'})
        """
        if not updates:
            return False

        set_clauses = []
        params = {}

        for key, value in updates.items():
            set_clauses.append(f"{key} = %({key})s")
            params[key] = value

        params['tag_id'] = tag_id

        query = f"""
            UPDATE mcp_tags
            SET {', '.join(set_clauses)}
            WHERE id = %(tag_id)s
        """

        self.db.execute_query(query, params)
        logger.info("tag_updated", tag_id=tag_id)
        return True

    def delete_tag(self, tag_id: str) -> bool:
        """
        Supprime un tag.

        Args:
            tag_id: UUID du tag

        Returns:
            True si supprimé

        Note:
            Les références dans mcp_servers.tags restent (UUID[])
            mais ne pointent plus vers rien.
        """
        query = "DELETE FROM mcp_tags WHERE id = %s"
        self.db.execute_query(query, (tag_id,))
        logger.info("tag_deleted", tag_id=tag_id)
        return True

    def tag_exists(self, slug: str) -> bool:
        """
        Vérifie si un tag existe déjà.

        Args:
            slug: Slug du tag

        Returns:
            True si existe
        """
        query = "SELECT EXISTS(SELECT 1 FROM mcp_tags WHERE slug = %s)"
        return self.db.fetch_value(query, (slug,))

    def get_or_create_tag(
        self,
        slug: str,
        name: str,
        color: Optional[str] = None
    ) -> str:
        """
        Récupère ou crée un tag.

        Args:
            slug: Slug du tag
            name: Nom d'affichage
            color: Couleur (optionnel)

        Returns:
            UUID du tag (existant ou créé)
        """
        existing = self.get_tag_by_slug(slug)

        if existing:
            return existing['id']
        else:
            return self.insert_tag(slug, name, color)

    def get_tags_for_server(self, server_id: str) -> List[Dict]:
        """
        Récupère tous les tags d'un serveur.

        Args:
            server_id: UUID du serveur

        Returns:
            Liste des tags du serveur

        Note:
            Fait un JOIN avec mcp_servers via l'array tags
        """
        query = """
            SELECT t.*
            FROM mcp_tags t
            JOIN mcp_servers s ON t.id = ANY(s.tags)
            WHERE s.id = %s
            ORDER BY t.name
        """
        return self.db.fetch_all(query, (server_id,))

    def count_servers_by_tag(self) -> List[Dict]:
        """
        Compte le nombre de serveurs par tag.

        Returns:
            Liste de dicts avec tag_name et server_count

        Example:
            [
                {'name': 'TypeScript', 'slug': 'typescript', 'server_count': 120},
                {'name': 'Python', 'slug': 'python', 'server_count': 85}
            ]
        """
        query = """
            SELECT
                t.id,
                t.slug,
                t.name,
                t.color,
                COUNT(s.id) as server_count
            FROM mcp_tags t
            LEFT JOIN mcp_servers s ON t.id = ANY(s.tags)
            GROUP BY t.id, t.slug, t.name, t.color
            ORDER BY server_count DESC, t.name
        """
        return self.db.fetch_all(query)

    def bulk_insert_tags(self, tags: List[Dict]) -> List[str]:
        """
        Insère plusieurs tags en une seule transaction.

        Args:
            tags: Liste de dicts avec slug, name, color

        Returns:
            Liste des UUIDs créés

        Example:
            tag_ids = repo.bulk_insert_tags([
                {'slug': 'free', 'name': 'Free', 'color': '#10B981'},
                {'slug': 'paid', 'name': 'Paid', 'color': '#EF4444'}
            ])
        """
        if not tags:
            return []

        query = """
            INSERT INTO mcp_tags (slug, name, color)
            VALUES (%s, %s, %s)
            RETURNING id
        """

        tag_ids = []

        with self.db.get_cursor(dict_cursor=False) as cursor:
            for tag in tags:
                cursor.execute(query, (
                    tag['slug'],
                    tag['name'],
                    tag.get('color')
                ))
                tag_id = cursor.fetchone()[0]
                tag_ids.append(str(tag_id))

        logger.info("bulk_tags_inserted", count=len(tag_ids))
        return tag_ids
