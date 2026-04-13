import os
import json
from pathlib import Path
from typing import Any, Dict

class Config:
    def __init__(self):
        self.risk_threshold = 0.7
        self.log_dir = Path.home() / ".shield-mcp" / "logs"
        self.log_file = self.log_dir / "shield.log"
        self.model_name = "protectai/deberta-v3-base-prompt-injection-v2"
        self.model_cache_dir = Path("models")
        self.offline_mode = False

        self._load_local_config()
        self._ensure_dirs()

    def _load_local_config(self):
        config_path = Path("shield_config.json")
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    data = json.load(f)
                    self.risk_threshold = data.get("risk_threshold", self.risk_threshold)
                    if "log_dir" in data:
                        self.log_dir = Path(data["log_dir"])
                        self.log_file = self.log_dir / "shield.log"
            except Exception as e:
                print(f"Error loading config: {e}")

    def _ensure_dirs(self):
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.model_cache_dir.mkdir(parents=True, exist_ok=True)

__version__ = "0.1.0"

# Global instance
config = Config()
