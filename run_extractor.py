#!/usr/bin/env python3
"""
Main entry point for LLM extraction (Phase 2).
Extracts MCP configurations from crawled GitHub data.
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional

import structlog
from src.config import ExtractorConfig
from src.database.db_manager import DatabaseManager
from src.services.extractor_service import ExtractorService
from src.llm_extractor import LLMExtractor
from src.prompt_builder import PromptBuilder
from src.llm_validator import LLMValidator

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer()
    ]
)

logger = structlog.get_logger()


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments for extraction control."""
    parser = argparse.ArgumentParser(
        description="Extract MCP server configurations from GitHub repos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_extractor.py                    # Mode par défaut (test_mode from .env)
  python run_extractor.py --limit 10        # Extraire 10 nouveaux serveurs
  python run_extractor.py --limit 50        # Extraire 50 serveurs
        """
    )

    parser.add_argument(
        "--limit",
        type=int,
        metavar="N",
        help="Nombre de nouveaux serveurs à extraire (ignore test_mode)"
    )

    return parser.parse_args()


def get_servers_to_process(extractor_service: ExtractorService, limit: Optional[int] = None) -> List[dict]:
    """
    Récupère les serveurs à traiter depuis PostgreSQL.

    Args:
        extractor_service: Instance du ExtractorService
        limit: Nombre maximum de serveurs

    Returns:
        Liste de serveurs sans config
    """
    return extractor_service.get_servers_to_process(limit)


async def process_repo_legacy(
    repo_data: Dict,
    prompt_builder: PromptBuilder,
    extractor: LLMExtractor,
    index: int,
    total: int
) -> Dict:
    """Process a single repository (extraction only, validation done in batch)."""

    github_url = repo_data["github_url"]

    logger.info(
        "processing_repo",
        index=index,
        total=total,
        url=github_url
    )

    try:
        # Build prompt
        prompt = prompt_builder.build_prompt(
            files=repo_data["files"],
            metadata=repo_data["metadata"]
        )

        # Extract config via LLM
        config = await extractor.extract_config(prompt)

        # Build result (validation will be done later in batch)
        result = {
            "github_url": github_url,
            "github_metadata": repo_data["metadata"],
            "config": config,
            "extraction": {
                "extracted_at": datetime.utcnow().isoformat() + "Z",
                "files_analyzed": list(repo_data["files"].keys())
            }
        }

        if "error" in config:
            result["error"] = config["error"]

        print(f"  [{index}/{total}] ⏳ {repo_data['metadata']['name']} - extracted")

        logger.info(
            "repo_extracted",
            url=github_url
        )

        return result

    except Exception as e:
        logger.error(
            "repo_processing_failed",
            url=github_url,
            error=str(e),
            exc_info=True
        )

        return {
            "github_url": github_url,
            "github_metadata": repo_data.get("metadata", {}),
            "error": f"Processing failed: {str(e)}",
            "extraction": {
                "status": "rejected",
                "confidence": 0.0,
                "warnings": [],
                "errors": [str(e)],
                "extracted_at": datetime.utcnow().isoformat() + "Z"
            }
        }


async def process_batch(
    repos: List[Dict],
    prompt_builder: PromptBuilder,
    extractor: LLMExtractor,
    validator: LLMValidator,
    start_index: int,
    total: int
) -> List[Dict]:
    """Process a batch of repos: extract configs then validate in batch."""

    # Step 1: Extract all configs in parallel
    tasks = [
        process_repo(
            repo,
            prompt_builder,
            extractor,
            start_index + i + 1,
            total
        )
        for i, repo in enumerate(repos)
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Filter exceptions
    valid_results = []
    for result in results:
        if isinstance(result, Exception):
            logger.error("batch_task_failed", error=str(result))
        else:
            valid_results.append(result)

    if not valid_results:
        return []

    # Step 2: Validate all configs in one LLM call (max 10)
    configs_to_validate = [r["config"] for r in valid_results if r.get("config")]
    
    if configs_to_validate:
        try:
            validations = await validator.validate_batch(configs_to_validate)
            
            # Merge validation results back
            validation_idx = 0
            for result in valid_results:
                if result.get("config"):
                    validation = validations[validation_idx]
                    
                    # Add validation data to extraction
                    result["extraction"]["status"] = validation["status"]
                    result["extraction"]["score"] = validation["score"]
                    result["extraction"]["confidence"] = validation["confidence"]
                    result["extraction"]["issues"] = validation["issues"]
                    result["extraction"]["warnings"] = validation["warnings"]
                    
                    # Nullify config if rejected
                    if validation["status"] == "rejected":
                        result["config"] = None
                    
                    validation_idx += 1
                    
                    # Display validated result
                    status_emoji = {
                        "approved": "✅",
                        "needs_review": "⚠️",
                        "rejected": "❌"
                    }
                    print(
                        f"  [{start_index + valid_results.index(result) + 1}/{total}] "
                        f"{status_emoji.get(validation['status'], '?')} "
                        f"{result['github_metadata']['name']} "
                        f"(score: {validation['score']:.1f}/10)"
                    )
                else:
                    # No config extracted (error case)
                    result["extraction"]["status"] = "rejected"
                    result["extraction"]["score"] = 0.0
                    result["extraction"]["confidence"] = 0.0
                    result["extraction"]["issues"] = ["Extraction failed"]
                    result["extraction"]["warnings"] = []
                    
        except Exception as e:
            logger.error("batch_validation_failed", error=str(e))
            # Fallback: mark all as needs_review with score -1 (validation failed)
            for result in valid_results:
                if result.get("config"):
                    result["extraction"]["status"] = "needs_review"
                    result["extraction"]["score"] = -1.0
                    result["extraction"]["confidence"] = 0.5
                    result["extraction"]["issues"] = [f"Validation failed: {str(e)}"]
                    result["extraction"]["warnings"] = ["Needs manual review"]

    return valid_results


async def main_async():
    """Main async execution function."""

    try:
        # 0. Parse command-line arguments
        args = parse_arguments()

        # 1. Load configuration
        logger.info("loading_configuration")
        config = ExtractorConfig()

        logger.info(
            "config_loaded",
            test_mode=config.test_mode,
            batch_size=config.batch_size,
            model=config.model
        )

        # 2. Initialize database and components
        logger.info("initializing_database")
        db_manager = DatabaseManager()

        logger.info("initializing_components")
        prompt_builder = PromptBuilder(config.prompt_template_file, config.prompts_dir)
        extractor = LLMExtractor(config)
        validator = LLMValidator(config, config.validation_prompt_file)

        # Create extractor service
        extractor_service = ExtractorService(
            db_manager,
            extractor,
            validator,
            prompt_builder
        )

        # 3. Get servers to process from PostgreSQL
        logger.info("loading_servers_to_process")

        # Determine limit
        limit = None
        if args.limit is not None:
            limit = args.limit
        elif config.test_mode:
            limit = config.test_limit

        servers = get_servers_to_process(extractor_service, limit)

        logger.info("servers_to_process_loaded", count=len(servers))

        print(f"🔍 {len(servers)} serveurs sans config disponibles\n")

        # Early exit if no servers to process
        if not servers:
            print("✓ Tous les serveurs ont déjà une config!")
            return 0

        # 4. Display processing info
        if args.limit is not None:
            print(f"🎯 Limite CLI: traitement de {len(servers)} serveurs (--limit {args.limit})\n")
        elif config.test_mode:
            print(f"🔬 Mode test: traitement de {len(servers)} serveurs\n")
        else:
            print(f"🚀 Mode production: traitement de {len(servers)} serveurs\n")

        # 5. Process servers in batches (async parallel)
        all_results = []
        total = len(servers)
        batch_size = config.batch_size

        for i in range(0, total, batch_size):
            batch = servers[i:i+batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total + batch_size - 1) // batch_size

            print(f"\n📦 Batch {batch_num}/{total_batches} ({len(batch)} serveurs)")

            # Process batch via ExtractorService (extraction + validation + storage)
            results = await extractor_service.process_batch(batch, i, total)

            all_results.extend(results)

            # Display validated results
            for result in results:
                extraction = result.get('extraction', {})
                status = extraction.get('status', 'unknown')
                score = extraction.get('score', 0.0)
                name = result.get('github_metadata', {}).get('name', 'Unknown')

                status_emoji = {
                    "approved": "✅",
                    "needs_review": "⚠️",
                    "rejected": "❌"
                }

                print(
                    f"  [{i + results.index(result) + 1}/{total}] "
                    f"{status_emoji.get(status, '?')} "
                    f"{name} "
                    f"(score: {score:.1f}/10)"
                )

            logger.info(
                "batch_completed",
                batch=batch_num,
                processed=len(all_results),
                total=total
            )

        # 6. Calculate statistics from current batch
        batch_stats = {
            "processed": len(all_results),
            "approved": len([r for r in all_results if r.get("extraction", {}).get("status") == "approved"]),
            "needs_review": len([r for r in all_results if r.get("extraction", {}).get("status") == "needs_review"]),
            "rejected": len([r for r in all_results if r.get("extraction", {}).get("status") == "rejected"])
        }

        # 7. Get global statistics from PostgreSQL
        db_stats = extractor_service.get_extraction_statistics()

        # 8. Display summary
        print("\n" + "="*70)
        print("✓ Extraction terminée!")
        print("="*70)
        print(f"  Traités:          {batch_stats['processed']} serveurs")
        print(f"  Approuvés:        {batch_stats['approved']}")
        print(f"  À réviser:        {batch_stats['needs_review']}")
        print(f"  Rejetés:          {batch_stats['rejected']}")
        print()
        print(f"  Total en base:    {db_stats['total_servers']} serveurs")
        print(f"  Avec config:      {db_stats['with_config']}")
        print(f"  Sans config:      {db_stats['without_config']}")
        print()
        print(f"  Par status:")
        for status, count in db_stats['by_status'].items():
            print(f"    - {status}: {count}")
        print("="*70)

        # 9. Cleanup
        db_manager.close()

        logger.info("extraction_completed", batch_stats=batch_stats, db_stats=db_stats)

        return 0

    except FileNotFoundError as e:
        logger.error("file_not_found", error=str(e))
        print(f"\n❌ Fichier introuvable: {e}")
        return 1

    except json.JSONDecodeError as e:
        logger.error("json_decode_error", error=str(e))
        print(f"\n❌ Erreur de parsing JSON: {e}")
        return 1

    except Exception as e:
        logger.error("unexpected_error", error=str(e), exc_info=True)
        print(f"\n❌ Erreur inattendue: {e}")
        return 1


def main():
    """Entry point."""
    return asyncio.run(main_async())


if __name__ == "__main__":
    sys.exit(main())
