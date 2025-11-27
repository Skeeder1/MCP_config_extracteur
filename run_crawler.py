#!/usr/bin/env python3
"""
Main entry point for GitHub crawler.
Fetches files and metadata from MCP server repositories.
"""

import json
import sys
from datetime import datetime

import structlog
from src.config import CrawlerConfig
from src.github_crawler import GitHubCrawler

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer()
    ]
)

logger = structlog.get_logger()


def main():
    """Main execution function."""
    try:
        # 1. Load configuration
        logger.info("loading_configuration")
        config = CrawlerConfig()

        logger.info(
            "config_loaded",
            test_mode=config.test_mode,
            test_limit=config.test_limit if config.test_mode else "all",
            input_file=config.input_file,
            output_file=config.output_file
        )

        # 2. Initialize crawler
        logger.info("initializing_crawler")
        crawler = GitHubCrawler(config.github_token)

        # 3. Load server list
        logger.info("loading_server_list", file=config.input_file)
        with open(config.input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            servers = data["servers"]

        logger.info("servers_loaded", total=len(servers))

        # 4. Apply test mode if enabled
        if config.test_mode:
            servers = servers[:config.test_limit]
            print(f"\n🔬 Mode test activé: traitement de {len(servers)} serveurs\n")
        else:
            print(f"\n🚀 Mode production: traitement de {len(servers)} serveurs\n")

        # 5. Check rate limit before starting
        crawler.check_rate_limit()

        # 6. Crawl each repository
        results = []
        total = len(servers)

        for i, server in enumerate(servers, 1):
            github_url = server["github_url"]
            print(f"[{i}/{total}] Crawling: {github_url}")

            # Fetch repo data with retry
            repo_data = crawler.fetch_repo_data_with_retry(github_url)
            results.append(repo_data)

            # Display result
            if "error" in repo_data:
                print(f"  ❌ Erreur: {repo_data['error']}")
            else:
                files_count = repo_data['files_count']
                language = repo_data['metadata'].get('language', 'Unknown')
                print(f"  ✓ {files_count} fichiers récupérés ({language})")

            # Check rate limit periodically
            if i % 10 == 0:
                crawler.check_rate_limit()

        # 7. Calculate statistics
        stats = {
            "total_repos": total,
            "success": len([r for r in results if "error" not in r]),
            "failed": len([r for r in results if "error" in r]),
            "total_files_fetched": sum(r.get("files_count", 0) for r in results)
        }

        # Calculate average files per successful repo
        if stats["success"] > 0:
            stats["avg_files_per_repo"] = round(
                stats["total_files_fetched"] / stats["success"], 2
            )
        else:
            stats["avg_files_per_repo"] = 0

        # 8. Build final output
        output = {
            "metadata": {
                "crawled_at": datetime.utcnow().isoformat() + "Z",
                "source_file": config.input_file,
                "test_mode": config.test_mode,
                "stats": stats
            },
            "repos": results
        }

        # 9. Save to file
        logger.info("saving_results", file=config.output_file)
        with open(config.output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        # 10. Display summary
        print("\n" + "="*60)
        print("✓ Crawling terminé!")
        print("="*60)
        print(f"  Succès:           {stats['success']}/{stats['total_repos']} repos")
        print(f"  Échecs:           {stats['failed']}/{stats['total_repos']} repos")
        print(f"  Fichiers récupérés: {stats['total_files_fetched']} total")
        print(f"  Moyenne:          {stats['avg_files_per_repo']} fichiers/repo")
        print(f"  Output:           {config.output_file}")
        print("="*60)

        # Final rate limit check
        crawler.check_rate_limit()

        logger.info("crawling_completed", stats=stats)

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


if __name__ == "__main__":
    sys.exit(main())
