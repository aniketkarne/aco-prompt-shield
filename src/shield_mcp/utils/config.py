import os
import json
from pathlib import Path
from typing import Any, Dict

# Standard HuggingFace cache location
_HF_CACHE_DIR = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface"))


def _get_version() -> str:
    """Read version from pyproject.toml via importlib.metadata (single source of truth)."""
    try:
        from importlib.metadata import version
        return version("aco-prompt-shield")
    except Exception:
        return "unknown"


class Config:
    def __init__(self):
        # Env vars first (lowest priority), then JSON file overrides
        self.risk_threshold = float(os.environ.get("SHIELD_RISK_THRESHOLD", "0.7"))
        self.log_dir = Path(os.environ.get("SHIELD_LOG_DIR", Path.home() / ".shield-mcp" / "logs"))
        self.log_file = self.log_dir / "shield.log"
        self.model_name = os.environ.get("SHIELD_MODEL_NAME", "protectai/deberta-v3-base-prompt-injection-v2")
        # Default to ~/.cache/huggingface/ — HF_HOME controls where models are cached
        self.model_cache_dir = Path(os.environ.get("HF_HOME", str(_HF_CACHE_DIR)))
        self.offline_mode = os.environ.get("SHIELD_OFFLINE_MODE", "false").lower() in ("true", "1", "yes")

        self._load_local_config()
        self._ensure_dirs()

    def _load_local_config(self):
        """JSON file config overrides env vars."""
        config_path = Path("shield_config.json")
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    data = json.load(f)
                    self.risk_threshold = float(data.get("risk_threshold", self.risk_threshold))
                    if "log_dir" in data:
                        self.log_dir = Path(data["log_dir"])
                        self.log_file = self.log_dir / "shield.log"
                    if "model_name" in data:
                        self.model_name = data["model_name"]
                    if "model_cache_dir" in data:
                        self.model_cache_dir = Path(data["model_cache_dir"])
                    if "offline_mode" in data:
                        self.offline_mode = bool(data["offline_mode"])
            except Exception as e:
                print(f"Error loading config: {e}")

    def _ensure_dirs(self):
        self.log_dir.mkdir(parents=True, exist_ok=True)


# Global instance
config = Config()
