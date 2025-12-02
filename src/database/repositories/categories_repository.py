"""
CategoriesRepository - Gestion des catégories (table mcp_categories).

Repository pour les opérations CRUD sur les catégories (référentiel).
"""

from typing import Optional, List, Dict
import structlog

logger = structlog.get_logger(__name__)


class CategoriesRepository:
    """
    Repository pour la table mcp_categories.

    Gère le référentiel des catégories utilisées pour classer les serveurs.
    """

    def __init__(self, db_manager):
        """
        Initialise le repository.

        Args:
            db_manager: Instance de DatabaseManager
        """
        self.db = db_manager

    def insert_category(
        self,
        slug: str,
        name: str,
        icon: Optional[str] = None,
        color: Optional[str] = None
    ) -> str:
        """
        Insère une nouvelle catégorie.

        Args:
            slug: Identifiant unique URL-friendly
            name: Nom d'affichage
            icon: Emoji ou nom d'icône (optionnel)
            color: Couleur hexadécimale (optionnel)

        Returns:
            UUID de la catégorie créée

        Example:
            category_id = repo.insert_category(
                'search-web',
                'Search & Web',
                '🔍',
                '#10B981'
            )
        """
        query = """
            INSERT INTO mcp_categories (
                slug, name, icon, color
            ) VALUES (
                %s, %s, %s, %s
            )
            RETURNING id
        """

        with self.db.get_cursor(dict_cursor=False) as cursor:
            cursor.execute(query, (slug, name, icon, color))
            category_id = cursor.fetchone()[0]

        logger.info("category_inserted", category_id=str(category_id), slug=slug)
        return str(category_id)

    def get_category_by_id(self, category_id: str) -> Optional[Dict]:
        """
        Récupère une catégorie par son ID.

        Args:
            category_id: UUID de la catégorie

        Returns:
            Dict contenant la catégorie ou None
        """
        query = "SELECT * FROM mcp_categories WHERE id = %s"
        return self.db.fetch_one(query, (category_id,))

    def get_category_by_slug(self, slug: str) -> Optional[Dict]:
        """
        Récupère une catégorie par son slug.

        Args:
            slug: Slug de la catégorie

        Returns:
            Dict contenant la catégorie ou None
        """
        query = "SELECT * FROM mcp_categories WHERE slug = %s"
        return self.db.fetch_one(query, (slug,))

    def get_all_categories(self) -> List[Dict]:
        """
        Récupère toutes les catégories.

        Returns:
            Liste de toutes les catégories (triées par nom)
        """
        query = "SELECT * FROM mcp_categories ORDER BY name"
        return self.db.fetch_all(query)

    def update_category(self, category_id: str, updates: dict) -> bool:
        """
        Met à jour une catégorie.

        Args:
            category_id: UUID de la catégorie
            updates: Dict des champs à mettre à jour

        Returns:
            True si mis à jour

        Example:
            repo.update_category(category_id, {
                'name': 'Web Search',
                'color': '#00FF00'
            })
        """
        if not updates:
            return False

        set_clauses = []
        params = {}

        for key, value in updates.items():
            set_clauses.append(f"{key} = %({key})s")
            params[key] = value

        params['category_id'] = category_id

        query = f"""
            UPDATE mcp_categories
            SET {', '.join(set_clauses)}
            WHERE id = %(category_id)s
        """

        self.db.execute_query(query, params)
        logger.info("category_updated", category_id=category_id)
        return True

    def delete_category(self, category_id: str) -> bool:
        """
        Supprime une catégorie.

        Args:
            category_id: UUID de la catégorie

        Returns:
            True si supprimé

        Note:
            Les références dans mcp_servers.categories restent (UUID[])
            mais ne pointent plus vers rien.
        """
        query = "DELETE FROM mcp_categories WHERE id = %s"
        self.db.execute_query(query, (category_id,))
        logger.info("category_deleted", category_id=category_id)
        return True

    def category_exists(self, slug: str) -> bool:
        """
        Vérifie si une catégorie existe déjà.

        Args:
            slug: Slug de la catégorie

        Returns:
            True si existe
        """
        query = "SELECT EXISTS(SELECT 1 FROM mcp_categories WHERE slug = %s)"
        return self.db.fetch_value(query, (slug,))

    def get_or_create_category(
        self,
        slug: str,
        name: str,
        icon: Optional[str] = None,
        color: Optional[str] = None
    ) -> str:
        """
        Récupère ou crée une catégorie.

        Args:
            slug: Slug de la catégorie
            name: Nom d'affichage
            icon: Emoji (optionnel)
            color: Couleur (optionnel)

        Returns:
            UUID de la catégorie (existante ou créée)
        """
        existing = self.get_category_by_slug(slug)

        if existing:
            return existing['id']
        else:
            return self.insert_category(slug, name, icon, color)

    def get_categories_for_server(self, server_id: str) -> List[Dict]:
        """
        Récupère toutes les catégories d'un serveur.

        Args:
            server_id: UUID du serveur

        Returns:
            Liste des catégories du serveur

        Note:
            Fait un JOIN avec mcp_servers via l'array categories
        """
        query = """
            SELECT c.*
            FROM mcp_categories c
            JOIN mcp_servers s ON c.id = ANY(s.categories)
            WHERE s.id = %s
            ORDER BY c.name
        """
        return self.db.fetch_all(query, (server_id,))

    def count_servers_by_category(self) -> List[Dict]:
        """
        Compte le nombre de serveurs par catégorie.

        Returns:
            Liste de dicts avec category_name et server_count

        Example:
            [
                {'name': 'Search & Web', 'slug': 'search-web', 'server_count': 15},
                {'name': 'Data Analysis', 'slug': 'data-analysis', 'server_count': 8}
            ]
        """
        query = """
            SELECT
                c.id,
                c.slug,
                c.name,
                c.icon,
                c.color,
                COUNT(s.id) as server_count
            FROM mcp_categories c
            LEFT JOIN mcp_servers s ON c.id = ANY(s.categories)
            GROUP BY c.id, c.slug, c.name, c.icon, c.color
            ORDER BY server_count DESC, c.name
        """
        return self.db.fetch_all(query)
