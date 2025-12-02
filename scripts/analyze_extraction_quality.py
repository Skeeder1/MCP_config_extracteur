#!/usr/bin/env python3
"""Analyze extraction quality from PostgreSQL database."""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.db_manager import DatabaseManager
from src.database.repositories.servers_repository import ServersRepository
from src.database.repositories.configs_repository import ConfigsRepository


def analyze_extraction_quality(db_manager: DatabaseManager = None):
    """Analyze extraction quality, cost, and performance metrics from PostgreSQL."""

    print("\n📈 Analyse de Qualité depuis PostgreSQL\n")
    print("=" * 70)

    # Initialize database
    if db_manager is None:
        db_manager = DatabaseManager()

    servers_repo = ServersRepository(db_manager)
    configs_repo = ConfigsRepository(db_manager)

    # Get all servers
    all_servers = servers_repo.get_all_servers()
    all_configs = configs_repo.get_all_configs()

    if not all_servers:
        print("❌ Aucun serveur trouvé dans la base de données")
        return

    # Provider info (from configs)
    providers = set()
    models = set()

    for config_data in all_configs:
        config = config_data.get('config_json', {})
        if '_llm_metadata' in config:
            meta = config['_llm_metadata']
            if 'provider' in meta:
                providers.add(meta['provider'])
            if 'model' in meta:
                models.add(meta['model'])

    print(f"🤖 Providers: {', '.join(providers) if providers else 'N/A'}")
    print(f"🧠 Models: {', '.join(models) if models else 'N/A'}")
    print()

    # Token usage
    total_input_tokens = 0
    total_output_tokens = 0

    for config_data in all_configs:
        config = config_data.get('config_json', {})
        if '_llm_metadata' in config:
            meta = config['_llm_metadata']
            total_input_tokens += meta.get("input_tokens", 0)
            total_output_tokens += meta.get("output_tokens", 0)

    print(f"📊 Utilisation de tokens:")
    print(f"  Input:  {total_input_tokens:,} tokens")
    print(f"  Output: {total_output_tokens:,} tokens")
    print(f"  Total:  {total_input_tokens + total_output_tokens:,} tokens")

    # Cost estimation (Claude Haiku pricing)
    input_cost = (total_input_tokens / 1_000_000) * 0.25  # $0.25 per 1M tokens
    output_cost = (total_output_tokens / 1_000_000) * 1.25  # $1.25 per 1M tokens
    total_cost = input_cost + output_cost

    print(f"\n💰 Coût estimé (Claude Haiku):")
    print(f"  Input:  ${input_cost:.4f}")
    print(f"  Output: ${output_cost:.4f}")
    print(f"  Total:  ${total_cost:.4f}")

    # Comparison with Claude Sonnet
    sonnet_input_cost = (total_input_tokens / 1_000_000) * 3.00
    sonnet_output_cost = (total_output_tokens / 1_000_000) * 15.00
    sonnet_total_cost = sonnet_input_cost + sonnet_output_cost

    savings = sonnet_total_cost - total_cost
    savings_pct = (savings / sonnet_total_cost * 100) if sonnet_total_cost > 0 else 0

    print(f"\n💸 Économies vs Claude Sonnet:")
    print(f"  Sonnet coût:    ${sonnet_total_cost:.4f}")
    print(f"  Haiku coût:     ${total_cost:.4f}")
    print(f"  Économies:      ${savings:.4f} ({savings_pct:.1f}%)")

    # Quality metrics (from server status)
    status_counts = {}
    for server in all_servers:
        status = server.get('status', 'unknown')
        status_counts[status] = status_counts.get(status, 0) + 1

    print(f"\n🎯 Métriques de qualité:")

    # Get servers by status
    approved = [s for s in all_servers if s.get('status') == 'approved']
    pending = [s for s in all_servers if s.get('status') == 'pending']
    rejected = [s for s in all_servers if s.get('status') == 'rejected']

    if approved:
        avg_stars_approved = sum(s.get('github_stars', 0) for s in approved) / len(approved)
        print(f"  Approuvés ({len(approved)}) - Moyenne étoiles: {avg_stars_approved:.0f} ⭐")

    if pending:
        avg_stars_pending = sum(s.get('github_stars', 0) for s in pending) / len(pending)
        print(f"  Pending ({len(pending)}) - Moyenne étoiles: {avg_stars_pending:.0f} ⭐")

    if rejected:
        avg_stars_rejected = sum(s.get('github_stars', 0) for s in rejected) / len(rejected)
        print(f"  Rejetés ({len(rejected)}) - Moyenne étoiles: {avg_stars_rejected:.0f} ⭐")

    # Command type distribution
    command_types = {}
    for config_data in all_configs:
        config = config_data.get('config_json', {})
        if "command" in config:
            cmd = config["command"]
            command_types[cmd] = command_types.get(cmd, 0) + 1

    if command_types:
        print(f"\n🔧 Types de commandes détectées:")
        for cmd, count in sorted(command_types.items(), key=lambda x: x[1], reverse=True):
            print(f"  {cmd}: {count}")

    # Config type distribution
    config_type_counts = {}
    for config_data in all_configs:
        config_type = config_data.get('config_type', 'unknown')
        config_type_counts[config_type] = config_type_counts.get(config_type, 0) + 1

    if config_type_counts:
        print(f"\n📦 Distribution des types de config:")
        for config_type, count in sorted(config_type_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {config_type}: {count}")

    # Environment variables analysis
    total_env_vars = 0
    env_vars_by_requirement = {"required": 0, "optional": 0}

    for config_data in all_configs:
        config = config_data.get('config_json', {})
        if "env" in config:
            env = config["env"]
            total_env_vars += len(env)
            for var_name, var_config in env.items():
                if var_config.get("required"):
                    env_vars_by_requirement["required"] += 1
                else:
                    env_vars_by_requirement["optional"] += 1

    if total_env_vars > 0:
        print(f"\n🔑 Variables d'environnement:")
        print(f"  Total: {total_env_vars}")
        print(f"  Requises: {env_vars_by_requirement['required']}")
        print(f"  Optionnelles: {env_vars_by_requirement['optional']}")

    # Installation commands
    with_install = sum(1 for config_data in all_configs
                      if config_data.get('config_json', {}).get("install") is not None)
    print(f"\n📦 Commandes d'installation:")
    print(f"  Avec install: {with_install}/{len(all_configs)}")

    # Language distribution
    language_counts = {}
    for server in all_servers:
        lang = server.get('primary_language', 'Unknown')
        language_counts[lang] = language_counts.get(lang, 0) + 1

    if language_counts:
        print(f"\n🌐 Distribution des langages:")
        for lang, count in sorted(language_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"  {lang}: {count}")

    # Top servers by stars
    top_servers = sorted(all_servers, key=lambda s: s.get('github_stars', 0), reverse=True)[:5]

    if top_servers:
        print(f"\n⭐ Top 5 serveurs par étoiles:")
        for i, server in enumerate(top_servers, 1):
            name = server.get('name', 'Unknown')
            stars = server.get('github_stars', 0)
            status = server.get('status', 'unknown')
            print(f"  {i}. {name}: {stars:,} ⭐ (status: {status})")

    print("=" * 70)

    # Detailed server analysis
    print(f"\n📋 Analyse détaillée par serveur:\n")

    # Create a map of server_id to config
    config_map = {}
    for config_data in all_configs:
        server_id = config_data.get('server_id')
        if server_id:
            config_map[server_id] = config_data.get('config_json', {})

    for i, server in enumerate(all_servers, 1):
        server_id = server['id']
        server_name = server.get('name', f"Server {i}")
        status = server.get('status', 'unknown')

        if status == "rejected":
            print(f"[{i}] ❌ {server_name}: {status.upper()}")
            continue

        config = config_map.get(server_id)

        if config is None:
            print(f"[{i}] ⚠️ {server_name}: Pas de config")
            continue

        status_emoji = "✅" if status == "approved" else "⚠️"
        print(f"[{i}] {status_emoji} {server_name}: {status.upper()}")

        if "_llm_metadata" in config:
            meta = config["_llm_metadata"]
            print(f"     Provider: {meta.get('provider', 'N/A')}")
            print(f"     Model: {meta.get('model', 'N/A')}")
            print(f"     Tokens: {meta.get('input_tokens', 0)} → {meta.get('output_tokens', 0)}")

        if "install" in config:
            install = config.get("install") or "null"
            print(f"     Install: {install[:60]}...")

        if "command" in config:
            cmd = config.get("command", "N/A")
            args = config.get("args", [])
            print(f"     Command: {cmd} {' '.join(args[:3])}")

        if "env" in config:
            env_count = len(config.get("env", {}))
            print(f"     Env vars: {env_count}")

        # GitHub stats
        stars = server.get('github_stars', 0)
        lang = server.get('primary_language', 'Unknown')
        print(f"     GitHub: {stars:,} ⭐ | {lang}")

        print()

    print("=" * 70)


if __name__ == "__main__":
    analyze_extraction_quality()
