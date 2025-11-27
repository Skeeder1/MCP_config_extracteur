"""Validates extracted MCP configurations."""

from typing import Dict

import structlog

from .config import ExtractorConfig

logger = structlog.get_logger()


class ConfigValidator:
    """Validates extracted MCP configurations."""

    # Confidence penalties (clear, named constants instead of magic numbers)
    PENALTY_UNUSUAL_COMMAND = 0.15      # 85% confidence (1.0 - 0.15)
    PENALTY_NPX_MISSING_Y_FLAG = 0.05   # 95% confidence
    PENALTY_NPX_MISSING_PACKAGE = 0.10  # 90% confidence
    PENALTY_DOCKER_MISSING_RUN = 0.10   # 90% confidence
    PENALTY_DOCKER_MISSING_I_FLAG = 0.08  # 92% confidence
    PENALTY_DOCKER_MISSING_RM = 0.05    # 95% confidence
    PENALTY_PYTHON_MISSING_M_FLAG = 0.08  # 92% confidence
    PENALTY_ENV_VAR_MISSING_FIELD = 0.03  # 97% confidence

    def __init__(self, config: ExtractorConfig):
        """
        Initialize validator.

        Args:
            config: Extractor configuration
        """
        self.config = config
        self.valid_commands = [
            "npx", "npm", "python", "python3", "uvx", "uv",
            "docker", "node", "deno", "bun", "cargo", "go"
        ]

        logger.info("validator_initialized")

    def validate(self, config: Dict) -> Dict:
        """
        Validate config and return validation result.

        Args:
            config: Extracted configuration dict

        Returns:
            Validation result with validity, errors, warnings, and confidence
        """
        validation = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "confidence": 1.0
        }

        # Handle error configs
        if "error" in config:
            validation["valid"] = False
            validation["errors"].append(f"Extraction failed: {config['error']}")
            validation["confidence"] = 0.0
            return validation

        # Validate required fields
        required = ["name", "command", "args", "env"]
        for field in required:
            if field not in config:
                validation["valid"] = False
                validation["errors"].append(f"Missing required field: {field}")

        if not validation["valid"]:
            validation["confidence"] = 0.0
            return validation

        # Validate command
        if config["command"] not in self.valid_commands:
            if not config["command"].startswith("./"):
                validation["warnings"].append(f"Unusual command: {config['command']}")
                validation["confidence"] *= (1.0 - self.PENALTY_UNUSUAL_COMMAND)

        # Validate args type
        if not isinstance(config["args"], list):
            validation["valid"] = False
            validation["errors"].append("args must be an array")
            validation["confidence"] = 0.0
            return validation

        # Validate env type
        if not isinstance(config["env"], dict):
            validation["valid"] = False
            validation["errors"].append("env must be an object")
            validation["confidence"] = 0.0
            return validation

        # Command-specific validations
        validation = self._validate_command_specifics(config, validation)

        # Validate env vars
        validation = self._validate_env_vars(config, validation)

        # Incorporate LLM's own confidence
        if "confidence" in config:
            validation["confidence"] *= config["confidence"]

        # Incorporate LLM's warnings
        if "warnings" in config:
            validation["warnings"].extend(config["warnings"])

        logger.info(
            "validation_complete",
            valid=validation["valid"],
            confidence=validation["confidence"],
            warnings_count=len(validation["warnings"])
        )

        return validation

    def _validate_command_specifics(self, config: Dict, validation: Dict) -> Dict:
        """
        Apply command-specific validation rules.

        Args:
            config: Configuration dict
            validation: Current validation state

        Returns:
            Updated validation state
        """
        command = config["command"]
        args = config["args"]

        # NPX validations
        if command == "npx":
            if len(args) < 2 or args[0] != "-y":
                validation["warnings"].append("NPX should use -y flag")
                validation["confidence"] *= (1.0 - self.PENALTY_NPX_MISSING_Y_FLAG)

            if len(args) < 2:
                validation["warnings"].append("NPX missing package name")
                validation["confidence"] *= (1.0 - self.PENALTY_NPX_MISSING_PACKAGE)

        # Docker validations
        elif command == "docker":
            if len(args) < 1 or args[0] != "run":
                validation["warnings"].append("Docker command should start with 'run'")
                validation["confidence"] *= (1.0 - self.PENALTY_DOCKER_MISSING_RUN)

            if "-i" not in args and "--interactive" not in args:
                validation["warnings"].append("Docker missing -i flag for stdio")
                validation["confidence"] *= (1.0 - self.PENALTY_DOCKER_MISSING_I_FLAG)

            if "--rm" not in args:
                validation["warnings"].append("Docker should use --rm flag")
                validation["confidence"] *= (1.0 - self.PENALTY_DOCKER_MISSING_RM)

        # Python validations
        elif command in ["python", "python3"]:
            if len(args) < 2 or args[0] != "-m":
                validation["warnings"].append("Python should use -m flag")
                validation["confidence"] *= (1.0 - self.PENALTY_PYTHON_MISSING_M_FLAG)

        return validation

    def _validate_env_vars(self, config: Dict, validation: Dict) -> Dict:
        """
        Validate environment variables structure.

        Args:
            config: Configuration dict
            validation: Current validation state

        Returns:
            Updated validation state
        """
        for var_name, var_config in config.get("env", {}).items():
            if not isinstance(var_config, dict):
                validation["valid"] = False
                validation["errors"].append(f"Env var {var_name} must be an object")
                continue

            required_fields = ["required", "description", "example"]
            for field in required_fields:
                if field not in var_config:
                    validation["warnings"].append(
                        f"Env var {var_name} missing field: {field}"
                    )
                    validation["confidence"] *= (1.0 - self.PENALTY_ENV_VAR_MISSING_FIELD)

        return validation

    def categorize(self, validation: Dict) -> str:
        """
        Categorize extraction based on confidence.

        Args:
            validation: Validation result

        Returns:
            Category: "approved", "needs_review", or "rejected"
        """
        if not validation["valid"]:
            return "rejected"

        confidence = validation["confidence"]

        if confidence >= self.config.auto_approve_threshold:
            return "approved"
        elif confidence >= self.config.needs_review_threshold:
            return "needs_review"
        else:
            return "rejected"
