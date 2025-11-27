#!/usr/bin/env python3
"""Analyze extraction quality and DeepSeek performance."""

import json
import sys


def analyze_extraction_quality(file_path: str):
    """Analyze extraction quality, cost, and performance metrics."""

    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print("\n📈 Analyse de Qualité DeepSeek\n")
    print("=" * 70)

    # Provider info
    metadata = data.get("metadata", {})
    print(f"🤖 Provider: openrouter")
    print(f"🧠 Model: {metadata.get('model', 'N/A')}")
    print()

    # Token usage
    total_input_tokens = 0
    total_output_tokens = 0

    for ext in data["extractions"]:
        if ext.get("config") and "_llm_metadata" in ext["config"]:
            meta = ext["config"]["_llm_metadata"]
            total_input_tokens += meta.get("input_tokens", 0)
            total_output_tokens += meta.get("output_tokens", 0)

    print(f"📊 Utilisation de tokens:")
    print(f"  Input:  {total_input_tokens:,} tokens")
    print(f"  Output: {total_output_tokens:,} tokens")
    print(f"  Total:  {total_input_tokens + total_output_tokens:,} tokens")

    # Cost estimation (DeepSeek pricing)
    input_cost = (total_input_tokens / 1_000_000) * 0.27
    output_cost = (total_output_tokens / 1_000_000) * 1.10
    total_cost = input_cost + output_cost

    print(f"\n💰 Coût estimé (DeepSeek v3.2):")
    print(f"  Input:  ${input_cost:.4f}")
    print(f"  Output: ${output_cost:.4f}")
    print(f"  Total:  ${total_cost:.4f}")

    # Comparison with Claude
    claude_input_cost = (total_input_tokens / 1_000_000) * 3.00
    claude_output_cost = (total_output_tokens / 1_000_000) * 15.00
    claude_total_cost = claude_input_cost + claude_output_cost

    savings = claude_total_cost - total_cost
    savings_pct = (savings / claude_total_cost * 100) if claude_total_cost > 0 else 0

    print(f"\n💸 Économies vs Claude Sonnet 4:")
    print(f"  Claude coût:    ${claude_total_cost:.4f}")
    print(f"  DeepSeek coût:  ${total_cost:.4f}")
    print(f"  Économies:      ${savings:.4f} ({savings_pct:.1f}%)")

    # Quality metrics
    print(f"\n🎯 Métriques de qualité:")

    approved = [e for e in data["extractions"] if e["extraction"]["status"] == "approved"]
    needs_review = [e for e in data["extractions"] if e["extraction"]["status"] == "needs_review"]
    rejected = [e for e in data["extractions"] if e["extraction"]["status"] == "rejected"]

    if approved:
        avg_score_approved = sum(e["extraction"].get("score", 0) for e in approved) / len(approved)
        print(f"  Approuvés ({len(approved)}) - Score moyen: {avg_score_approved:.1f}/10")

    if needs_review:
        avg_score_review = sum(e["extraction"].get("score", 0) for e in needs_review) / len(needs_review)
        print(f"  À réviser ({len(needs_review)}) - Score moyen: {avg_score_review:.1f}/10")

    if rejected:
        avg_score_rejected = sum(e["extraction"].get("score", 0) for e in rejected) / len(rejected)
        print(f"  Rejetés ({len(rejected)}) - Score moyen: {avg_score_rejected:.1f}/10")

    # Command type distribution
    command_types = {}
    for ext in data["extractions"]:
        if ext.get("config") and "command" in ext["config"]:
            cmd = ext["config"]["command"]
            command_types[cmd] = command_types.get(cmd, 0) + 1

    print(f"\n🔧 Types de commandes détectées:")
    for cmd, count in sorted(command_types.items(), key=lambda x: x[1], reverse=True):
        print(f"  {cmd}: {count}")

    # Environment variables analysis
    total_env_vars = 0
    env_vars_by_requirement = {"required": 0, "optional": 0}

    for ext in data["extractions"]:
        if ext.get("config") and "env" in ext["config"]:
            env = ext["config"]["env"]
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
    with_install = sum(1 for e in data["extractions"]
                      if e.get("config") and e["config"].get("install") is not None)
    print(f"\n📦 Commandes d'installation:")
    print(f"  Avec install: {with_install}/{len(data['extractions'])}")

    print("=" * 70)

    # Detailed server analysis
    print(f"\n📋 Analyse détaillée par serveur:\n")

    for i, ext in enumerate(data["extractions"], 1):
        server_name = ext.get("github_metadata", {}).get("name", f"Server {i}")
        status = ext.get("extraction", {}).get("status", "unknown")

        if status == "rejected":
            print(f"[{i}] ❌ {server_name}: {status.upper()}")
            continue

        config = ext.get("config", {})
        score = ext.get("extraction", {}).get("score", 0.0)

        print(f"[{i}] {'✅' if status == 'approved' else '⚠️'} {server_name}: {status.upper()} (score: {score:.1f}/10)")

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

        warnings = ext.get("extraction", {}).get("warnings", [])
        issues = ext.get("extraction", {}).get("issues", [])
        if warnings or issues:
            all_messages = warnings + issues
            print(f"     Issues: {len(all_messages)}")
            for msg in all_messages[:2]:
                print(f"       - {msg}")

        print()

    print("=" * 70)


if __name__ == "__main__":
    file_path = sys.argv[1] if len(sys.argv) > 1 else "data/output/extracted_configs.json"
    analyze_extraction_quality(file_path)
