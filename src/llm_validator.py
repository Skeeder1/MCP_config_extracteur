"""LLM-based validator for MCP configurations."""

import json
from pathlib import Path
from typing import Dict, List

import structlog

from .config import ExtractorConfig
from .llm_provider import create_provider
from .utils import extract_json_from_text

logger = structlog.get_logger()


class LLMValidator:
    """Validates MCP configurations using an LLM evaluator."""

    # Score thresholds for categorization
    THRESHOLD_APPROVED = 7.0      # 7.0-10.0 → approved
    THRESHOLD_NEEDS_REVIEW = 5.0  # 5.0-6.9 → needs_review
    # < 5.0 → rejected

    def __init__(self, config: ExtractorConfig, prompt_template_path: str = "config/validation_prompt.txt"):
        """
        Initialize LLM validator.

        Args:
            config: Extractor configuration
            prompt_template_path: Path to validation prompt template
        """
        self.config = config
        self.llm_provider = create_provider(config)
        
        # Counter for batch numbering
        self.batch_counter = 0
        
        # Prompts directory
        self.prompts_dir = Path(config.prompts_dir)
        self.prompts_dir.mkdir(parents=True, exist_ok=True)

        # Load validation prompt template
        with open(prompt_template_path, 'r', encoding='utf-8') as f:
            self.prompt_template = f.read()

        logger.info("llm_validator_initialized", prompt_path=prompt_template_path, prompts_dir=str(self.prompts_dir))

    async def validate_batch(self, configs: List[Dict]) -> List[Dict]:
        """
        Validate a batch of configs (max 10) using LLM.

        Args:
            configs: List of config dictionaries (max 10)

        Returns:
            List of validation results with score and status
        """
        if len(configs) > 10:
            raise ValueError(f"Batch size must be <= 10, got {len(configs)}")

        logger.info("validating_batch", batch_size=len(configs))

        # Build configs batch text
        configs_text = ""
        for i, config in enumerate(configs):
            configs_text += f"\n## Configuration {i}\n```json\n{json.dumps(config, indent=2)}\n```\n"

        # Build prompt
        prompt = self.prompt_template.format(configs_batch=configs_text)
        
        # Save prompt to file with incremental numbering
        self.batch_counter += 1
        prompt_file = self.prompts_dir / f"validation_{self.batch_counter}.txt"
        with open(prompt_file, 'w', encoding='utf-8') as f:
            f.write(prompt)
        
        logger.info(
            "validation_prompt_saved",
            batch=self.batch_counter,
            configs_count=len(configs),
            saved_to=str(prompt_file)
        )

        try:
            # Call LLM
            response = await self.llm_provider.create_completion(
                prompt=prompt,
                max_tokens=2000,
                temperature=0.0,
                model=self.config.active_model
            )

            # Parse JSON response
            response_text = response.content.strip()

            # Save raw response for debugging
            response_file = self.prompts_dir / f"validation_{self.batch_counter}_response.txt"
            with open(response_file, 'w', encoding='utf-8') as f:
                f.write(response_text)

            logger.info(
                "llm_response_received",
                batch=self.batch_counter,
                response_length=len(response_text),
                response_preview=response_text[:200]
            )

            # Extract JSON from response (handles text before/after JSON)
            try:
                response_text = extract_json_from_text(response_text)
                evaluations_data = json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.error(
                    "json_parse_error",
                    error=str(e),
                    response_length=len(response_text),
                    response_preview=response_text[:500]
                )
                raise
            evaluations = evaluations_data.get("evaluations", [])

            # Build validation results
            results = []
            for i, config in enumerate(configs):
                # Find corresponding evaluation
                eval_data = next((e for e in evaluations if e["index"] == i), None)

                if eval_data:
                    score = eval_data.get("score", 0.0)
                    issues = eval_data.get("issues", [])
                else:
                    # Fallback if LLM didn't return evaluation for this index
                    score = 0.0
                    issues = ["LLM evaluation missing"]

                # Categorize based on score
                status = self._categorize_by_score(score)

                # Normalize score to 0-1 confidence
                confidence = score / 10.0

                result = {
                    "valid": status != "rejected",
                    "score": score,
                    "confidence": confidence,
                    "status": status,
                    "issues": issues,
                    "warnings": issues if issues else []
                }

                results.append(result)

            logger.info(
                "batch_validated",
                batch_size=len(configs),
                avg_score=sum(r["score"] for r in results) / len(results) if results else 0
            )

            return results

        except json.JSONDecodeError as e:
            logger.error("llm_validation_json_error", error=str(e), response=response_text[:200])

            # Fallback: mark all as needs_review with score -1 to indicate failure
            return [
                {
                    "valid": True,
                    "score": -1.0,
                    "confidence": 0.5,
                    "status": "needs_review",
                    "issues": [f"LLM returned invalid JSON: {str(e)}"],
                    "warnings": ["Validation failed, needs manual review"]
                }
                for _ in configs
            ]

        except Exception as e:
            logger.error("llm_validation_error", error=str(e))

            # Fallback: mark all as needs_review with score -1 to indicate failure
            return [
                {
                    "valid": True,
                    "score": -1.0,
                    "confidence": 0.5,
                    "status": "needs_review",
                    "issues": [f"Validation error: {str(e)}"],
                    "warnings": ["Validation failed, needs manual review"]
                }
                for _ in configs
            ]

    def _categorize_by_score(self, score: float) -> str:
        """
        Categorize config based on LLM score.

        Args:
            score: Score from 0-10

        Returns:
            Status: approved, needs_review, or rejected
        """
        if score >= self.THRESHOLD_APPROVED:
            return "approved"
        elif score >= self.THRESHOLD_NEEDS_REVIEW:
            return "needs_review"
        else:
            return "rejected"
