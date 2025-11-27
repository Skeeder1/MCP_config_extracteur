"""Utility functions for GitHub crawler."""

import json
from typing import Tuple
from urllib.parse import urlparse


def parse_github_url(github_url: str) -> Tuple[str, str]:
    """
    Parse a GitHub URL to extract owner and repository name.

    Args:
        github_url: Full GitHub URL (e.g., https://github.com/owner/repo)

    Returns:
        Tuple of (owner, repo_name)

    Examples:
        >>> parse_github_url("https://github.com/modelcontextprotocol/servers")
        ('modelcontextprotocol', 'servers')
    """
    # Parse URL
    parsed = urlparse(github_url)
    path_parts = parsed.path.strip('/').split('/')

    if len(path_parts) < 2:
        raise ValueError(f"Invalid GitHub URL: {github_url}")

    owner = path_parts[0]
    repo_name = path_parts[1]

    return owner, repo_name


def extract_json_from_text(text: str) -> str:
    """
    Extract JSON from LLM response that may contain explanatory text.
    
    Handles cases where LLM adds text before/after the JSON like:
    "Voici la configuration: { ... }"
    
    Args:
        text: Raw text that may contain JSON with surrounding text
        
    Returns:
        Cleaned JSON string ready to parse
        
    Raises:
        ValueError: If no JSON object found in text
    """
    text = text.strip()
    
    # Remove markdown code fences if present
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    
    text = text.strip()
    
    # Extract JSON by finding first { and last }
    first_brace = text.find('{')
    last_brace = text.rfind('}')
    
    if first_brace == -1 or last_brace == -1:
        raise ValueError("No JSON object found in text")
    
    # Extract the JSON portion
    json_text = text[first_brace:last_brace + 1]
    
    return json_text.strip()


def parse_llm_json(text: str) -> dict:
    """
    Parse JSON from LLM response, handling common formatting issues.
    
    Args:
        text: Raw LLM response text
        
    Returns:
        Parsed JSON as dictionary
        
    Raises:
        json.JSONDecodeError: If JSON is invalid after cleaning
        ValueError: If no JSON found in text
    """
    json_text = extract_json_from_text(text)
    return json.loads(json_text)
