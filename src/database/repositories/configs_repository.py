"""
ConfigsRepository - Gestion des configurations MCP (table mcp_configs).

Repository pour les opérations CRUD sur les configurations d'installation.
"""

from typing import Optional, Dict
import json
import structlog

logger = structlog.get_logger(__name__)


class ConfigsRepository:
    """
    Repository pour la table mcp_configs.

    Gère les configurations d'installation (npm, docker, python, binary)
    stockées en JSONB.
    """

    def __init__(self, db_manager):
        """
        Initialise le repository.

        Args:
            db_manager: Instance de DatabaseManager
        """
        self.db = db_manager

    def insert_config(self, server_id: str, config_data: dict) -> str:
        """
        Insère une nouvelle configuration pour un serveur.

        Args:
            server_id: UUID du serveur (foreign key vers mcp_servers)
            config_data: Dict contenant la configuration complète
                Doit contenir: config_type, config_json

        Returns:
            UUID de la config créée

        Example:
            config_id = repo.insert_config(server_id, {
                'config_type': 'npm',
                'config_json': {
                    'command': 'npx',
                    'args': ['-y', '@modelcontextprotocol/server-brave-search'],
                    'env': {...}
                }
            })
        """
        query = """
            INSERT INTO mcp_configs (
                server_id, config_type, config_json
            ) VALUES (
                %(server_id)s, %(config_type)s, %(config_json)s
            )
            RETURNING id
        """

        # Si config_json n'est pas fourni dans config_data, utiliser config_data lui-même comme config_json
        if 'config_json' in config_data:
            config_json = config_data['config_json']
        else:
            # Utiliser tout config_data comme config_json (sauf config_type)
            config_json = {k: v for k, v in config_data.items() if k != 'config_type'}

        params = {
            'server_id': server_id,
            'config_type': config_data.get('config_type', 'inferred'),  # Default to 'inferred'
            'config_json': json.dumps(config_json)
        }

        with self.db.get_cursor(dict_cursor=False) as cursor:
            cursor.execute(query, params)
            config_id = cursor.fetchone()[0]

        logger.info("config_inserted", config_id=str(config_id), server_id=server_id)
        return str(config_id)

    def get_config_by_id(self, config_id: str) -> Optional[Dict]:
        """
        Récupère une configuration par son ID.

        Args:
            config_id: UUID de la configuration

        Returns:
            Dict contenant la configuration ou None
        """
        query = "SELECT * FROM mcp_configs WHERE id = %s"
        return self.db.fetch_one(query, (config_id,))

    def get_config_by_server_id(self, server_id: str) -> Optional[Dict]:
        """
        Récupère la configuration d'un serveur.

        Args:
            server_id: UUID du serveur

        Returns:
            Dict contenant la configuration ou None

        Note:
            Relation 1:1, donc une seule config par serveur
        """
        query = "SELECT * FROM mcp_configs WHERE server_id = %s"
        return self.db.fetch_one(query, (server_id,))

    def update_config(self, server_id: str, config_json: dict) -> bool:
        """
        Met à jour la configuration d'un serveur.

        Args:
            server_id: UUID du serveur
            config_json: Nouvelle configuration complète (JSONB)

        Returns:
            True si mis à jour

        Example:
            repo.update_config(server_id, {
                'command': 'npx',
                'args': ['-y', '@package/name'],
                'env': {...}
            })
        """
        query = """
            UPDATE mcp_configs
            SET config_json = %s
            WHERE server_id = %s
        """

        self.db.execute_query(query, (json.dumps(config_json), server_id))
        logger.info("config_updated", server_id=server_id)
        return True

    def config_exists(self, server_id: str) -> bool:
        """
        Vérifie si un serveur a déjà une configuration.

        Args:
            server_id: UUID du serveur

        Returns:
            True si une config existe
        """
        query = "SELECT EXISTS(SELECT 1 FROM mcp_configs WHERE server_id = %s)"
        return self.db.fetch_value(query, (server_id,))

    def delete_config(self, config_id: str) -> bool:
        """
        Supprime une configuration.

        Args:
            config_id: UUID de la configuration

        Returns:
            True si supprimé
        """
        query = "DELETE FROM mcp_configs WHERE id = %s"
        self.db.execute_query(query, (config_id,))
        logger.info("config_deleted", config_id=config_id)
        return True

    def get_configs_by_type(self, config_type: str) -> list:
        """
        Récupère toutes les configurations d'un type donné.

        Args:
            config_type: Type de config (npm/docker/python/binary)

        Returns:
            Liste de configurations
        """
        query = "SELECT * FROM mcp_configs WHERE config_type = %s"
        return self.db.fetch_all(query, (config_type,))

    def search_in_config(self, search_key: str, search_value: str) -> list:
        """
        Recherche dans les configs JSONB.

        Args:
            search_key: Clé dans le JSON (ex: 'command')
            search_value: Valeur à rechercher

        Returns:
            Liste de configs correspondantes

        Example:
            # Trouver toutes les configs avec command='npx'
            configs = repo.search_in_config('command', 'npx')
        """
        query = f"""
            SELECT * FROM mcp_configs
            WHERE config_json->>'{search_key}' = %s
        """
        return self.db.fetch_all(query, (search_value,))

    def get_all_configs(self) -> list:
        """
        Récupère toutes les configurations.

        Returns:
            Liste de toutes les configurations
        """
        query = "SELECT * FROM mcp_configs"
        return self.db.fetch_all(query)
