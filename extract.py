#!/usr/bin/env python3
"""
Unified CLI entry point for MCP config extraction.

Usage:
    python extract.py crawl              # Run Phase 1 (GitHub crawler)
    python extract.py extract            # Run Phase 2 (LLM extraction)
    python extract.py validate           # Validate PostgreSQL data
    python extract.py analyze            # Analyze quality from PostgreSQL
    python extract.py pipeline           # Run full pipeline (default)
"""
import sys
import argparse
import asyncio
from pathlib import Path

# Import existing entry points
from run_crawler import main as crawler_main
from run_extractor import main_async as extractor_main


def main():
    parser = argparse.ArgumentParser(
        prog='extract.py',
        description='MCP Configuration Extractor - Unified CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python extract.py                    # Run full pipeline (default)
    python extract.py pipeline           # Run full pipeline explicitly
    python extract.py crawl              # Run Phase 1 only
    python extract.py extract            # Run Phase 2 only
    python extract.py validate           # Validate PostgreSQL data
    python extract.py analyze            # Analyze extraction quality from PostgreSQL

For more help on each command, use:
    python extract.py <command> --help
"""
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Crawl command
    crawl = subparsers.add_parser('crawl', help='Run GitHub crawler (Phase 1)')

    # Extract command
    extract = subparsers.add_parser('extract', help='Run LLM extraction (Phase 2)')

    # Validate command
    validate = subparsers.add_parser('validate', help='Validate PostgreSQL data')

    # Analyze command
    analyze = subparsers.add_parser('analyze', help='Analyze extraction quality from PostgreSQL')

    # Pipeline command (default)
    pipeline = subparsers.add_parser('pipeline', help='Run full pipeline (crawl + extract + validate)')

    args = parser.parse_args()

    # Default to pipeline if no command
    if not args.command:
        args.command = 'pipeline'

    try:
        if args.command == 'crawl':
            return crawler_main()

        elif args.command == 'extract':
            return asyncio.run(extractor_main())

        elif args.command == 'validate':
            sys.path.insert(0, 'scripts')
            from validate_extraction_output import validate_extraction_output
            success = validate_extraction_output()
            return 0 if success else 1

        elif args.command == 'analyze':
            sys.path.insert(0, 'scripts')
            from analyze_extraction_quality import analyze_extraction_quality
            analyze_extraction_quality()
            return 0

        elif args.command == 'pipeline':
            print("\n" + "="*70)
            print("  MCP CONFIG EXTRACTION PIPELINE")
            print("="*70)
            print("\n📡 Phase 1: GitHub Crawling...\n")

            result = crawler_main()
            if result != 0:
                print("\n❌ Crawler failed!")
                return result

            print("\n🧠 Phase 2: LLM Extraction...\n")
            result = asyncio.run(extractor_main())
            if result != 0:
                print("\n❌ Extraction failed!")
                return result

            print("\n✅ Phase 3: Validation...\n")
            sys.path.insert(0, 'scripts')
            from validate_extraction_output import validate_extraction_output
            validate_extraction_output()

            print("\n" + "="*70)
            print("  ✅ PIPELINE COMPLETED")
            print("="*70)
            print(f"  All data stored in PostgreSQL")
            print("="*70 + "\n")

            return 0

        else:
            parser.print_help()
            return 1

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        return 130
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
