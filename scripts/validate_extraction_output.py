#!/usr/bin/env python3
"""Validate extraction output from PostgreSQL database."""

import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.db_manager import DatabaseManager
from src.database.repositories.servers_repository import ServersRepository
from src.database.repositories.configs_repository import ConfigsRepository


def validate_config_schema(config: Dict, server_name: str) -> Tuple[bool, List[str]]:
    """
    Validate a single config against the expected schema.

    Returns: (is_valid, errors)
    """
    errors = []

    # Handle error case
    if "error" in config:
        if "requires_manual_review" not in config:
            errors.append(f"{server_name}: Missing 'requires_manual_review' field in error response")
        return len(errors) == 0, errors

    # Required fields
    required_fields = ["name", "command", "args", "env"]
    for field in required_fields:
        if field not in config:
            errors.append(f"{server_name}: Missing required field '{field}'")

    # Type validation
    if "name" in config and not isinstance(config["name"], str):
        errors.append(f"{server_name}: 'name' must be a string")

    if "command" in config and not isinstance(config["command"], str):
        errors.append(f"{server_name}: 'command' must be a string")

    if "args" in config:
        if not isinstance(config["args"], list):
            errors.append(f"{server_name}: 'args' must be an array")
        elif not all(isinstance(arg, str) for arg in config["args"]):
            errors.append(f"{server_name}: All items in 'args' must be strings")

    if "env" in config:
        if not isinstance(config["env"], dict):
            errors.append(f"{server_name}: 'env' must be an object")
        else:
            # Validate each env var
            for var_name, var_config in config["env"].items():
                if not isinstance(var_config, dict):
                    errors.append(f"{server_name}: env.{var_name} must be an object")
                    continue

                # Required env var fields
                required_env_fields = ["required", "description", "example"]
                for env_field in required_env_fields:
                    if env_field not in var_config:
                        errors.append(f"{server_name}: env.{var_name} missing '{env_field}'")

                # Type validation for env vars
                if "required" in var_config and not isinstance(var_config["required"], bool):
                    errors.append(f"{server_name}: env.{var_name}.required must be boolean")

                if "description" in var_config and not isinstance(var_config["description"], str):
                    errors.append(f"{server_name}: env.{var_name}.description must be string")

    # Optional fields validation
    if "install" in config and config["install"] is not None and not isinstance(config["install"], str):
        errors.append(f"{server_name}: 'install' must be string or null")

    if "confidence" in config:
        if not isinstance(config["confidence"], (int, float)):
            errors.append(f"{server_name}: 'confidence' must be number")
        elif not (0 <= config["confidence"] <= 1):
            errors.append(f"{server_name}: 'confidence' must be between 0 and 1")

    if "warnings" in config and not isinstance(config["warnings"], list):
        errors.append(f"{server_name}: 'warnings' must be an array")

    return len(errors) == 0, errors


def validate_database_integrity(db_manager: DatabaseManager) -> Tuple[bool, List[str]]:
    """
    Validate database integrity constraints.

    Returns: (is_valid, errors)
    """
    errors = []

    # Check for NULL values in NOT NULL columns
    null_checks = [
        ("mcp_servers", "slug", "SELECT COUNT(*) FROM mcp_servers WHERE slug IS NULL"),
        ("mcp_servers", "name", "SELECT COUNT(*) FROM mcp_servers WHERE name IS NULL"),
        ("mcp_servers", "github_url", "SELECT COUNT(*) FROM mcp_servers WHERE github_url IS NULL"),
        ("mcp_configs", "server_id", "SELECT COUNT(*) FROM mcp_configs WHERE server_id IS NULL"),
        ("mcp_configs", "config_json", "SELECT COUNT(*) FROM mcp_configs WHERE config_json IS NULL"),
    ]

    for table, column, query in null_checks:
        count = db_manager.fetch_value(query)
        if count and count > 0:
            errors.append(f"{table}.{column}: Found {count} NULL values in NOT NULL column")

    # Check foreign key integrity
    orphaned_configs = db_manager.fetch_value("""
        SELECT COUNT(*)
        FROM mcp_configs c
        LEFT JOIN mcp_servers s ON s.id = c.server_id
        WHERE s.id IS NULL
    """)
    if orphaned_configs and orphaned_configs > 0:
        errors.append(f"Found {orphaned_configs} orphaned configs (server_id doesn't exist)")

    # Check UNIQUE constraints
    duplicate_slugs = db_manager.fetch_value("""
        SELECT COUNT(*)
        FROM (
            SELECT slug, COUNT(*) as cnt
            FROM mcp_servers
            GROUP BY slug
            HAVING COUNT(*) > 1
        ) t
    """)
    if duplicate_slugs and duplicate_slugs > 0:
        errors.append(f"Found {duplicate_slugs} duplicate slugs in mcp_servers")

    duplicate_github_urls = db_manager.fetch_value("""
        SELECT COUNT(*)
        FROM (
            SELECT github_url, COUNT(*) as cnt
            FROM mcp_servers
            GROUP BY github_url
            HAVING COUNT(*) > 1
        ) t
    """)
    if duplicate_github_urls and duplicate_github_urls > 0:
        errors.append(f"Found {duplicate_github_urls} duplicate github_urls in mcp_servers")

    # Check status constraint
    invalid_status = db_manager.fetch_value("""
        SELECT COUNT(*)
        FROM mcp_servers
        WHERE status NOT IN ('approved', 'pending', 'rejected')
    """)
    if invalid_status and invalid_status > 0:
        errors.append(f"Found {invalid_status} servers with invalid status")

    # Check config_type constraint
    invalid_config_type = db_manager.fetch_value("""
        SELECT COUNT(*)
        FROM mcp_configs
        WHERE config_type NOT IN ('npm', 'docker', 'python', 'binary', 'inferred', 'other')
    """)
    if invalid_config_type and invalid_config_type > 0:
        errors.append(f"Found {invalid_config_type} configs with invalid config_type")

    return len(errors) == 0, errors


def validate_extraction_output(db_manager: DatabaseManager = None):
    """Validate the extraction output from PostgreSQL database."""

    print(f"📋 Validation de la base de données PostgreSQL\n")
    print("=" * 70)

    # Initialize database
    if db_manager is None:
        db_manager = DatabaseManager()

    servers_repo = ServersRepository(db_manager)
    configs_repo = ConfigsRepository(db_manager)

    # Get all servers
    all_servers = servers_repo.get_all_servers()

    if not all_servers:
        print("❌ Aucun serveur trouvé dans la base de données")
        return False

    # Get statistics
    total_servers = len(all_servers)
    with_config = db_manager.fetch_value("SELECT COUNT(DISTINCT server_id) FROM mcp_configs") or 0
    without_config = total_servers - with_config

    status_counts = {}
    for server in all_servers:
        status = server.get('status', 'unknown')
        status_counts[status] = status_counts.get(status, 0) + 1

    print(f"\n📊 Statistiques globales:")
    print(f"  Total: {total_servers} serveurs")
    print(f"  Avec config: {with_config}")
    print(f"  Sans config: {without_config}")
    print(f"  Par status:")
    for status, count in sorted(status_counts.items()):
        print(f"    - {status}: {count}")
    print()

    # Validate database integrity
    print("🔒 Validation de l'intégrité de la base de données:\n")
    integrity_valid, integrity_errors = validate_database_integrity(db_manager)

    if integrity_valid:
        print("  ✅ Intégrité de la base de données: OK")
    else:
        print(f"  ❌ Intégrité de la base de données: {len(integrity_errors)} erreurs")
        for error in integrity_errors:
            print(f"     - {error}")
    print()

    # Validate each config
    all_valid = True
    total_errors = []

    print("🔍 Validation de chaque configuration:\n")

    for i, server in enumerate(all_servers, 1):
        server_id = server['id']
        server_name = server.get('name', f"Server {i}")
        status = server.get('status', 'unknown')

        # Get config for this server
        config_data = configs_repo.get_config_by_server_id(server_id)

        # Skip servers without config
        if config_data is None:
            print(f"  [{i}] ⚠️  {server_name}: Pas de config (status: {status})")
            continue

        # Get the JSONB config
        config = config_data.get('config_json', {})

        # Validate config schema
        is_valid, errors = validate_config_schema(config, server_name)

        if is_valid:
            # Check completeness
            has_install = config.get("install") is not None
            has_env_vars = len(config.get("env", {})) > 0
            completeness = "complet" if has_install and has_env_vars else "partiel"

            print(f"  [{i}] ✅ {server_name}: {status.upper()} ({completeness})")

            # Show command summary
            command = config.get("command", "N/A")
            args_count = len(config.get("args", []))
            env_count = len(config.get("env", {}))
            print(f"       {command} [{args_count} args, {env_count} env vars]")
        else:
            all_valid = False
            total_errors.extend(errors)
            print(f"  [{i}] ❌ {server_name}: ERREURS DE VALIDATION")
            for error in errors:
                print(f"       - {error}")

        print()

    # Summary
    print("=" * 70)
    if all_valid and integrity_valid:
        print("✅ VALIDATION RÉUSSIE: Toutes les configurations sont conformes")
        return True
    else:
        total_error_count = len(total_errors) + len(integrity_errors)
        print(f"❌ VALIDATION ÉCHOUÉE: {total_error_count} erreurs détectées")
        return False


if __name__ == "__main__":
    success = validate_extraction_output()
    sys.exit(0 if success else 1)
