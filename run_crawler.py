#!/usr/bin/env python3
"""
Main entry point for GitHub crawler.
Fetches files and metadata from MCP server repositories.
"""

import argparse
import json
import os
import sys
from datetime import datetime

import structlog
from src.config import CrawlerConfig
from src.database.db_manager import DatabaseManager
from src.services.crawler_service import CrawlerService

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
    """Parse command-line arguments for crawling control."""
    parser = argparse.ArgumentParser(
        description="Crawl GitHub repositories for MCP server files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_crawler.py                      # Mode par défaut (test_mode from .env)
  python run_crawler.py --limit 10          # Crawler 10 nouveaux serveurs
  python run_crawler.py --limit 50          # Crawler 50 serveurs
        """
    )

    parser.add_argument(
        "--limit",
        type=int,
        metavar="N",
        help="Nombre de nouveaux serveurs à crawler (ignore test_mode)"
    )

    return parser.parse_args()


def get_processed_repos(crawler_service: CrawlerService) -> set[str]:
    """
    Récupère les URLs déjà crawlées depuis PostgreSQL.

    Args:
        crawler_service: Instance du CrawlerService

    Returns:
        Set des github_url déjà présentes dans la base de données
    """
    return crawler_service.get_processed_urls()


def main():
    """Main execution function."""
    try:
        # 0. Parse command-line arguments
        args = parse_arguments()

        # 1. Load configuration
        logger.info("loading_configuration")
        config = CrawlerConfig()

        logger.info(
            "config_loaded",
            test_mode=config.test_mode,
            test_limit=config.test_limit if config.test_mode else "all",
            input_file=config.input_file
        )

        # 2. Initialize database and crawler service
        logger.info("initializing_database")
        db_manager = DatabaseManager()
        crawler_service = CrawlerService(db_manager, config.github_token)

        # 2b. Load existing crawled repos from PostgreSQL
        crawled_urls = get_processed_repos(crawler_service)

        if crawled_urls:
            logger.info("existing_repos_loaded", count=len(crawled_urls))
            print(f"📂 {len(crawled_urls)} serveurs déjà crawlés chargés depuis PostgreSQL\n")
        else:
            logger.info("no_existing_repos")
            print(f"📂 Aucun repo existant (base de données vide)\n")

        # 3. Load server list
        logger.info("loading_server_list", file=config.input_file)
        with open(config.input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            servers = data["servers"]

        logger.info("servers_loaded", total=len(servers))

        # 3b. Filter out already-crawled servers
        original_count = len(servers)
        servers = [s for s in servers if s["github_url"] not in crawled_urls]
        filtered_count = original_count - len(servers)

        logger.info(
            "servers_filtered",
            original=original_count,
            filtered=filtered_count,
            remaining=len(servers)
        )

        print(f"🔍 {original_count} serveurs dans l'input")
        print(f"⏭️  {filtered_count} serveurs déjà crawlés (skippés)")
        print(f"✨ {len(servers)} nouveaux serveurs disponibles\n")

        # Early exit if no new servers
        if not servers:
            print("✓ Tous les serveurs ont déjà été crawlés!")
            return 0

        # 4. Apply limit from --limit or test_mode
        if args.limit is not None:
            # CLI argument takes precedence
            limit = min(args.limit, len(servers))
            servers = servers[:limit]
            print(f"🎯 Limite CLI: crawling de {len(servers)} nouveaux serveurs (--limit {args.limit})\n")
        elif config.test_mode:
            # Fallback to test mode
            servers = servers[:config.test_limit]
            print(f"🔬 Mode test: crawling de {len(servers)} nouveaux serveurs\n")
        else:
            print(f"🚀 Mode production: crawling de {len(servers)} nouveaux serveurs\n")

        # 5. Check rate limit before starting
        crawler_service.crawler.check_rate_limit()

        # 6. Crawl each repository and store in PostgreSQL
        results = []
        total = len(servers)
        success_count = 0
        skipped_count = 0
        error_count = 0

        for i, server in enumerate(servers, 1):
            github_url = server["github_url"]
            print(f"[{i}/{total}] Crawling: {github_url}")

            # Process server (crawl + store in DB)
            result = crawler_service.process_server(server)
            results.append(result)

            # Display result
            status = result.get('status')
            if status == 'success':
                success_count += 1
                files_count = result.get('files_count', 0)
                readme = "✓" if result.get('readme_stored') else "✗"
                print(f"  ✓ {files_count} fichiers récupérés | README: {readme}")
            elif status == 'skipped':
                skipped_count += 1
                print(f"  ⏭️  {result.get('message', 'Skipped')}")
            else:  # error
                error_count += 1
                print(f"  ❌ Erreur: {result.get('error', 'Unknown error')}")

            # Check rate limit periodically
            if i % 10 == 0:
                crawler_service.crawler.check_rate_limit()

        # 7. Get statistics from PostgreSQL
        db_stats = crawler_service.get_crawl_statistics()

        # 8. Display summary
        print("\n" + "="*60)
        print("✓ Crawling terminé!")
        print("="*60)
        print(f"  Traités:            {len(results)} serveurs")
        print(f"  Succès:             {success_count}/{len(results)} serveurs")
        print(f"  Skippés:            {skipped_count}/{len(results)} serveurs")
        print(f"  Échecs:             {error_count}/{len(results)} serveurs")
        print()
        print(f"  Total en base:      {db_stats['total_servers']} serveurs")
        print(f"  Avec README:        {db_stats['with_readme']} serveurs")
        print(f"  Moyenne étoiles:    {db_stats['avg_stars']} ⭐")
        print()
        print(f"  Par status:")
        for status, count in db_stats['by_status'].items():
            print(f"    - {status}: {count}")
        print("="*60)

        # 9. Final rate limit check
        crawler_service.crawler.check_rate_limit()

        # 10. Cleanup
        db_manager.close()

        logger.info("crawling_completed", processed=len(results), db_stats=db_stats)

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
