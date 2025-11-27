#!/usr/bin/env python3
"""
Main entry point for LLM extraction (Phase 2).
Extracts MCP configurations from crawled GitHub data.
"""

import asyncio
import json
import sys
from datetime import datetime
from typing import Dict, List

import structlog
from src.config import ExtractorConfig
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


async def process_repo(
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
        # 1. Load configuration
        logger.info("loading_configuration")
        config = ExtractorConfig()

        logger.info(
            "config_loaded",
            test_mode=config.test_mode,
            batch_size=config.batch_size,
            model=config.model
        )

        # 2. Initialize components
        logger.info("initializing_components")
        prompt_builder = PromptBuilder(config.prompt_template_file, config.prompts_dir)
        extractor = LLMExtractor(config)
        validator = LLMValidator(config, config.validation_prompt_file)

        # 3. Load Phase 1 data
        logger.info("loading_phase1_data", file=config.input_file)
        with open(config.input_file, 'r', encoding='utf-8') as f:
            phase1_data = json.load(f)
            repos = phase1_data["repos"]

        logger.info("phase1_data_loaded", total_repos=len(repos))

        # 4. Apply test mode if enabled
        if config.test_mode:
            repos = repos[:config.test_limit]
            print(f"\n🔬 Mode test activé: traitement de {len(repos)} repos\n")
        else:
            print(f"\n🚀 Mode production: traitement de {len(repos)} repos\n")

        # 5. Process repos in batches (async parallel)
        all_results = []
        total = len(repos)
        batch_size = config.batch_size

        for i in range(0, total, batch_size):
            batch = repos[i:i+batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total + batch_size - 1) // batch_size

            print(f"\n📦 Batch {batch_num}/{total_batches} ({len(batch)} repos)")

            results = await process_batch(
                batch,
                prompt_builder,
                extractor,
                validator,
                i,
                total
            )

            all_results.extend(results)

            logger.info(
                "batch_completed",
                batch=batch_num,
                processed=len(all_results),
                total=total
            )

        # 6. Calculate statistics
        stats = {
            "total_repos": total,
            "approved": len([r for r in all_results if r["extraction"]["status"] == "approved"]),
            "needs_review": len([r for r in all_results if r["extraction"]["status"] == "needs_review"]),
            "rejected": len([r for r in all_results if r["extraction"]["status"] == "rejected"])
        }

        stats["success_rate"] = round(
            (stats["approved"] + stats["needs_review"]) / stats["total_repos"] * 100, 2
        ) if stats["total_repos"] > 0 else 0

        stats["auto_approval_rate"] = round(
            stats["approved"] / stats["total_repos"] * 100, 2
        ) if stats["total_repos"] > 0 else 0

        # Calculate average confidence by category
        for category in ["approved", "needs_review", "rejected"]:
            category_results = [
                r for r in all_results
                if r["extraction"]["status"] == category
            ]
            if category_results:
                avg_conf = sum(r["extraction"]["confidence"] for r in category_results) / len(category_results)
                stats[f"avg_confidence_{category}"] = round(avg_conf, 3)

        # 7. Build final output
        output = {
            "metadata": {
                "extracted_at": datetime.utcnow().isoformat() + "Z",
                "source_file": config.input_file,
                "model": config.model,
                "test_mode": config.test_mode,
                "batch_size": config.batch_size,
                "stats": stats
            },
            "extractions": all_results
        }

        # 8. Save to file
        logger.info("saving_results", file=config.output_file)
        with open(config.output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        # 9. Display summary
        print("\n" + "="*70)
        print("✓ Extraction terminée!")
        print("="*70)
        print(f"  Total:            {stats['total_repos']} repos")
        print(f"  Approuvés:        {stats['approved']} ({stats['auto_approval_rate']:.1f}%)")
        print(f"  À réviser:        {stats['needs_review']}")
        print(f"  Rejetés:          {stats['rejected']}")
        print(f"  Taux de succès:   {stats['success_rate']:.1f}%")
        print(f"  Output:           {config.output_file}")
        print("="*70)

        logger.info("extraction_completed", stats=stats)

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
