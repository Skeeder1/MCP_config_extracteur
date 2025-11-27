"""GitHub crawler for fetching MCP server files and metadata."""

import base64
from datetime import datetime
from typing import Dict, List, Optional

import structlog
from github import Github, GithubException

from .retry_utils import standard_retry
from .utils import parse_github_url

logger = structlog.get_logger()


class GitHubCrawler:
    """Crawls GitHub repositories to fetch MCP server configurations."""

    def __init__(self, github_token: str):
        """
        Initialize the GitHub crawler.

        Args:
            github_token: GitHub personal access token
        """
        self.github = Github(github_token)
        logger.info("github_crawler_initialized")

    def get_files_to_fetch(self, repo_language: Optional[str]) -> List[str]:
        """
        Get list of files to fetch based on repository language.

        Strategy: 3-6 files maximum
        - Always try: README, build file (language-specific), .env.example
        - Optional: Dockerfile, docker-compose.yml, Makefile

        Args:
            repo_language: Primary programming language of the repository

        Returns:
            List of file paths to attempt fetching
        """
        files = []

        # 1. README (try in order, take first found)
        readme_files = ["README.md", "README.rst", "README.txt"]
        files.extend(readme_files)

        # 2. Build file (language-specific, only one)
        build_mapping = {
            "JavaScript": "package.json",
            "TypeScript": "package.json",
            "Python": "pyproject.toml",
            "Rust": "Cargo.toml",
            "Go": "go.mod",
        }
        if repo_language and repo_language in build_mapping:
            files.append(build_mapping[repo_language])

        # 3. Environment variables (try in order)
        env_files = [".env.example", ".env.template", ".env.sample"]
        files.extend(env_files)

        # 4-6. Optional files
        files.extend(["Dockerfile", "docker-compose.yml", "Makefile"])

        return files

    def fetch_file_content(self, repo, file_path: str) -> Optional[str]:
        """
        Fetch content of a single file from repository.

        Args:
            repo: PyGithub repository object
            file_path: Path to file in repository

        Returns:
            File content as string, or None if file doesn't exist
        """
        try:
            content_file = repo.get_contents(file_path)

            # Decode content (GitHub API returns base64)
            if content_file.encoding == "base64":
                return base64.b64decode(content_file.content).decode("utf-8")
            else:
                return content_file.decoded_content.decode("utf-8")

        except GithubException as e:
            if e.status == 404:
                # File not found - this is expected, not an error
                return None
            else:
                logger.warning(
                    "file_fetch_error",
                    file=file_path,
                    status=e.status,
                    message=str(e)
                )
                return None
        except Exception as e:
            logger.warning("file_fetch_exception", file=file_path, error=str(e))
            return None

    def fetch_repo_data(self, github_url: str) -> Dict:
        """
        Fetch metadata and files for a single repository.

        Args:
            github_url: Full GitHub repository URL

        Returns:
            Dictionary containing metadata, files, and file count
        """
        # 1. Parse GitHub URL
        owner, repo_name = parse_github_url(github_url)

        # 2. Get repository object
        repo = self.github.get_repo(f"{owner}/{repo_name}")

        # 3. Fetch metadata
        metadata = {
            "name": repo.name,
            "full_name": repo.full_name,
            "description": repo.description,
            "language": repo.language,
            "topics": repo.get_topics(),
            "stars": repo.stargazers_count,
            "forks": repo.forks_count,
            "homepage": repo.homepage,
            "default_branch": repo.default_branch,
            "created_at": repo.created_at.isoformat() if repo.created_at else None,
            "updated_at": repo.updated_at.isoformat() if repo.updated_at else None,
        }

        # 4. Fetch files (3-6 maximum)
        files_to_fetch = self.get_files_to_fetch(repo.language)
        files = {}
        readme_found = False

        for file_path in files_to_fetch:
            # Skip other README variants if one already found
            if "README" in file_path and readme_found:
                continue

            content = self.fetch_file_content(repo, file_path)

            if content:
                files[file_path] = content

                # Mark README as found
                if "README" in file_path:
                    readme_found = True

        # 5. Return structured data
        return {
            "github_url": github_url,
            "metadata": metadata,
            "files": files,
            "files_count": len(files),
        }

    @standard_retry()
    def fetch_repo_data_with_retry(self, github_url: str) -> Dict:
        """
        Fetch repository data with automatic retry on failure.

        Args:
            github_url: Full GitHub repository URL

        Returns:
            Repository data dict, or error dict if all retries failed
        """
        try:
            return self.fetch_repo_data(github_url)

        except GithubException as e:
            logger.error(
                "github_api_error",
                url=github_url,
                status=e.status,
                message=str(e)
            )

            # Return error structure
            return {
                "github_url": github_url,
                "error": f"GitHub API error {e.status}: {e.data.get('message', str(e))}",
                "metadata": None,
                "files": {},
                "files_count": 0,
            }

        except Exception as e:
            logger.error("fetch_exception", url=github_url, error=str(e))

            return {
                "github_url": github_url,
                "error": f"Fetch failed: {str(e)}",
                "metadata": None,
                "files": {},
                "files_count": 0,
            }

    def check_rate_limit(self):
        """Check GitHub API rate limit and log if low."""
        try:
            rate_limit = self.github.get_rate_limit()
            remaining = rate_limit.core.remaining
            reset_time = rate_limit.core.reset

            logger.info(
                "rate_limit_check",
                remaining=remaining,
                limit=rate_limit.core.limit,
                reset_at=reset_time.isoformat()
            )

            if remaining < 100:
                logger.warning(
                    "rate_limit_low",
                    remaining=remaining,
                    reset_at=reset_time.isoformat()
                )

        except Exception as e:
            logger.warning("rate_limit_check_failed", error=str(e))
