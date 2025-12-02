"""
DatabaseManager - Gestionnaire de connexions PostgreSQL.

Gère le pool de connexions, les transactions et fournit des méthodes
utilitaires pour exécuter des requêtes SQL.
"""

import os
from typing import Any, Optional, List, Tuple, Dict
from contextlib import contextmanager
import psycopg2
from psycopg2 import pool, sql
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import structlog

# Charger les variables d'environnement
load_dotenv()

logger = structlog.get_logger(__name__)


class DatabaseManager:
    """
    Gestionnaire de connexions PostgreSQL avec pool de connexions.

    Utilise un pool de connexions pour optimiser les performances et
    fournit des méthodes de haut niveau pour les opérations CRUD.

    Exemple:
        db = DatabaseManager()
        result = db.fetch_one("SELECT * FROM mcp_servers WHERE slug = %s", ("test",))
        db.close_pool()
    """

    _instance = None
    _pool = None

    def __new__(cls):
        """Singleton pattern pour réutiliser le pool de connexions."""
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialise le pool de connexions PostgreSQL."""
        if self._pool is None:
            self._initialize_pool()

    def _initialize_pool(self):
        """Crée le pool de connexions à partir des variables d'environnement."""
        try:
            self._pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=int(os.getenv('DB_POOL_MIN_SIZE', 1)),
                maxconn=int(os.getenv('DB_POOL_MAX_SIZE', 10)),
                host=os.getenv('DB_HOST', 'localhost'),
                port=int(os.getenv('DB_PORT', 5432)),
                database=os.getenv('DB_NAME', 'mydb'),
                user=os.getenv('DB_USER', 'postgres'),
                password=os.getenv('DB_PASSWORD', 'postgres')
            )
            logger.info(
                "database_pool_created",
                host=os.getenv('DB_HOST'),
                database=os.getenv('DB_NAME'),
                min_connections=os.getenv('DB_POOL_MIN_SIZE', 1),
                max_connections=os.getenv('DB_POOL_MAX_SIZE', 10)
            )
        except psycopg2.Error as e:
            logger.error("database_pool_creation_failed", error=str(e))
            raise

    def get_connection(self):
        """
        Récupère une connexion du pool.

        Returns:
            connection: Connexion PostgreSQL

        Note:
            N'oubliez pas de retourner la connexion au pool avec putconn()
        """
        if self._pool is None:
            self._initialize_pool()
        return self._pool.getconn()

    def put_connection(self, conn):
        """
        Retourne une connexion au pool.

        Args:
            conn: Connexion à retourner au pool
        """
        if self._pool:
            self._pool.putconn(conn)

    @contextmanager
    def get_cursor(self, dict_cursor=True, commit=True):
        """
        Context manager pour obtenir un cursor.

        Args:
            dict_cursor: Si True, utilise RealDictCursor (rows as dicts)
            commit: Si True, commit automatiquement à la fin

        Yields:
            cursor: Cursor PostgreSQL

        Example:
            with db.get_cursor() as cursor:
                cursor.execute("SELECT * FROM mcp_servers")
                results = cursor.fetchall()
        """
        conn = self.get_connection()
        cursor = None

        try:
            cursor_factory = RealDictCursor if dict_cursor else None
            cursor = conn.cursor(cursor_factory=cursor_factory)
            yield cursor

            if commit:
                conn.commit()

        except Exception as e:
            conn.rollback()
            logger.error("database_operation_failed", error=str(e))
            raise

        finally:
            if cursor:
                cursor.close()
            self.put_connection(conn)

    def execute_query(self, query: str, params: Optional[Tuple] = None, commit: bool = True) -> int:
        """
        Exécute une requête SQL sans retour de résultat (INSERT, UPDATE, DELETE).

        Args:
            query: Requête SQL à exécuter
            params: Paramètres de la requête (tuple)
            commit: Si True, commit automatiquement

        Returns:
            int: Nombre de lignes affectées

        Example:
            rows_affected = db.execute_query(
                "UPDATE mcp_servers SET status = %s WHERE id = %s",
                ('approved', server_id)
            )
        """
        with self.get_cursor(dict_cursor=False, commit=commit) as cursor:
            cursor.execute(query, params)
            logger.debug("query_executed", query=query[:100], rows_affected=cursor.rowcount)
            return cursor.rowcount

    def execute_many(self, query: str, params_list: List[Tuple], commit: bool = True) -> None:
        """
        Exécute une requête plusieurs fois avec différents paramètres.

        Args:
            query: Requête SQL à exécuter
            params_list: Liste de tuples de paramètres
            commit: Si True, commit automatiquement

        Example:
            db.execute_many(
                "INSERT INTO mcp_tags (slug, name, color) VALUES (%s, %s, %s)",
                [('tag1', 'Tag 1', '#FF0000'), ('tag2', 'Tag 2', '#00FF00')]
            )
        """
        with self.get_cursor(dict_cursor=False, commit=commit) as cursor:
            cursor.executemany(query, params_list)
            logger.debug("batch_query_executed", query=query[:100], rows_affected=cursor.rowcount)

    def fetch_one(self, query: str, params: Optional[Tuple] = None) -> Optional[Dict]:
        """
        Exécute une requête et retourne une seule ligne.

        Args:
            query: Requête SQL SELECT
            params: Paramètres de la requête

        Returns:
            Dict ou None si aucun résultat

        Example:
            server = db.fetch_one(
                "SELECT * FROM mcp_servers WHERE slug = %s",
                ('brave-search',)
            )
        """
        with self.get_cursor(dict_cursor=True, commit=False) as cursor:
            cursor.execute(query, params)
            result = cursor.fetchone()
            return dict(result) if result else None

    def fetch_all(self, query: str, params: Optional[Tuple] = None) -> List[Dict]:
        """
        Exécute une requête et retourne toutes les lignes.

        Args:
            query: Requête SQL SELECT
            params: Paramètres de la requête

        Returns:
            Liste de dicts (peut être vide)

        Example:
            servers = db.fetch_all(
                "SELECT * FROM mcp_servers WHERE status = %s",
                ('approved',)
            )
        """
        with self.get_cursor(dict_cursor=True, commit=False) as cursor:
            cursor.execute(query, params)
            results = cursor.fetchall()
            return [dict(row) for row in results]

    def fetch_value(self, query: str, params: Optional[Tuple] = None) -> Any:
        """
        Exécute une requête et retourne une seule valeur.

        Args:
            query: Requête SQL SELECT
            params: Paramètres de la requête

        Returns:
            La première valeur de la première ligne (ou None)

        Example:
            count = db.fetch_value("SELECT COUNT(*) FROM mcp_servers")
        """
        with self.get_cursor(dict_cursor=False, commit=False) as cursor:
            cursor.execute(query, params)
            result = cursor.fetchone()
            return result[0] if result else None

    @contextmanager
    def transaction(self):
        """
        Context manager pour une transaction manuelle.

        Yields:
            connection: Connexion PostgreSQL

        Example:
            with db.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO ...")
                cursor.execute("UPDATE ...")
                # Commit automatique si pas d'exception
        """
        conn = self.get_connection()

        try:
            yield conn
            conn.commit()
            logger.debug("transaction_committed")

        except Exception as e:
            conn.rollback()
            logger.error("transaction_rolled_back", error=str(e))
            raise

        finally:
            self.put_connection(conn)

    def close_pool(self):
        """Ferme toutes les connexions du pool."""
        if self._pool:
            self._pool.closeall()
            self._pool = None
            logger.info("database_pool_closed")

    def close(self):
        """Alias pour close_pool() - ferme toutes les connexions."""
        self.close_pool()

    def __del__(self):
        """Destructeur - ferme le pool si nécessaire."""
        self.close_pool()
