#!/usr/bin/env python3
"""Validate extraction output against expected schema."""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple


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


def validate_extraction_output(file_path: str):
    """Validate the entire extraction output file."""

    print(f"📋 Validation de {file_path}\n")
    print("=" * 70)

    # Load JSON
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"❌ Fichier introuvable: {file_path}")
        return False
    except json.JSONDecodeError as e:
        print(f"❌ JSON invalide: {e}")
        return False

    # Validate top-level structure
    if "metadata" not in data:
        print("❌ Champ 'metadata' manquant")
        return False

    if "extractions" not in data:
        print("❌ Champ 'extractions' manquant")
        return False

    if not isinstance(data["extractions"], list):
        print("❌ 'extractions' doit être un array")
        return False

    # Validate metadata
    metadata = data["metadata"]
    required_metadata_fields = ["extracted_at", "source_file", "model", "test_mode", "stats"]
    for field in required_metadata_fields:
        if field not in metadata:
            print(f"❌ metadata.{field} manquant")
            return False

    # Stats
    stats = metadata["stats"]
    print(f"\n📊 Statistiques globales:")
    print(f"  Model: {metadata['model']}")
    print(f"  Total: {stats['total_repos']} serveurs")
    print(f"  Approuvés: {stats['approved']}")
    print(f"  À réviser: {stats['needs_review']}")
    print(f"  Rejetés: {stats['rejected']}")
    print(f"  Taux de succès: {stats['success_rate']}%")
    print()

    # Validate each extraction
    all_valid = True
    total_errors = []

    print("🔍 Validation de chaque extraction:\n")

    for i, extraction in enumerate(data["extractions"], 1):
        server_name = extraction.get("github_metadata", {}).get("name", f"Server {i}")
        status = extraction.get("extraction", {}).get("status", "unknown")
        confidence = extraction.get("extraction", {}).get("confidence", 0.0)

        # Skip rejected without config
        if status == "rejected" and extraction.get("config") is None:
            print(f"  [{i}] ⚠️  {server_name}: Rejeté (confidence: {confidence:.2f})")
            if "error" in extraction:
                print(f"       Erreur: {extraction['error'][:100]}")
            continue

        # Validate config
        config = extraction.get("config", {})
        is_valid, errors = validate_config_schema(config, server_name)

        if is_valid:
            # Check completeness
            has_install = config.get("install") is not None
            has_env_vars = len(config.get("env", {})) > 0
            completeness = "complet" if has_install and has_env_vars else "partiel"

            print(f"  [{i}] ✅ {server_name}: {status.upper()} (confidence: {confidence:.2f}, {completeness})")

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
    if all_valid:
        print("✅ VALIDATION RÉUSSIE: Toutes les extractions sont conformes au schéma")
        return True
    else:
        print(f"❌ VALIDATION ÉCHOUÉE: {len(total_errors)} erreurs détectées")
        return False


if __name__ == "__main__":
    file_path = sys.argv[1] if len(sys.argv) > 1 else "data/output/extracted_configs.json"
    success = validate_extraction_output(file_path)
    sys.exit(0 if success else 1)
