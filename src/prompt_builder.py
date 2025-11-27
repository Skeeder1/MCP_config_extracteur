"""Builds extraction prompts from repository data."""

import os
import re
from pathlib import Path
from typing import Dict

import structlog

logger = structlog.get_logger()


class PromptBuilder:
    """Builds extraction prompts from repository data."""

    def __init__(self, template_path: str, prompts_dir: str = "prompts"):
        """
        Load prompt template once at initialization.

        Args:
            template_path: Path to the prompt template file
            prompts_dir: Directory to save individual prompts
        """
        with open(template_path, 'r', encoding='utf-8') as f:
            self.template = f.read()

        self.prompts_dir = Path(prompts_dir)
        self.prompts_dir.mkdir(parents=True, exist_ok=True)

        logger.info("prompt_template_loaded", path=template_path, prompts_dir=prompts_dir)

    def build_prompt(self, files: Dict[str, str], metadata: Dict) -> str:
        """
        Build complete prompt for LLM extraction.

        Args:
            files: Dictionary of filename -> content
            metadata: Repository metadata from GitHub

        Returns:
            Complete formatted prompt ready for LLM
        """
        # Build files section
        files_content = ""

        for filename, content in files.items():
            if content:
                # Truncate if too long (15KB max per file to prevent token overflow)
                if len(content) > 15000:
                    content = content[:15000] + "\n\n[... truncated ...]"
                    logger.info(
                        "file_truncated",
                        filename=filename,
                        original_length=len(content),
                        truncated_to=15000
                    )

                files_content += f"\n## {filename}\n```\n{content}\n```\n"

        # Format template with metadata and files
        prompt = self.template.format(
            name=metadata.get("name", "unknown"),
            description=metadata.get("description", "No description"),
            topics=", ".join(metadata.get("topics", [])) or "None",
            language=metadata.get("language", "Unknown"),
            homepage=metadata.get("homepage", "None"),
            files_content=files_content
        )

        # Save prompt to individual file
        repo_name = metadata.get("name", "unknown")
        safe_filename = self._sanitize_filename(repo_name) + ".txt"
        prompt_file = self.prompts_dir / safe_filename

        # Overwrite if exists (no duplicates)
        with open(prompt_file, 'w', encoding='utf-8') as f:
            f.write(prompt)

        logger.info(
            "prompt_built",
            prompt_length=len(prompt),
            files_count=len(files),
            repo_name=repo_name,
            saved_to=str(prompt_file)
        )

        return prompt

    def _sanitize_filename(self, name: str) -> str:
        """
        Sanitize repo name for safe filename.

        Args:
            name: Repository name

        Returns:
            Safe filename without special characters
        """
        # Replace invalid characters with underscore
        safe = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
        # Remove consecutive underscores
        safe = re.sub(r'_+', '_', safe)
        # Limit length
        return safe[:200]
