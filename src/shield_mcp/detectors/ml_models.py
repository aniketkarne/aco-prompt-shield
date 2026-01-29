import torch
from transformers import pipeline
from shield_mcp.utils.config import config
import logging

logger = logging.getLogger("shield-mcp")

class MLDetector:
    def __init__(self):
        self.model_name = config.model_name
        self.cache_dir = config.model_cache_dir
        self.pipeline = None
        self.loaded = False

        self.load_model()

    def load_model(self):
        try:
            logger.info(f"Loading ML model: {self.model_name}...")
            # Check if model exists locally or download it
            # We use the pipeline API for simplicity, specifying cache_dir
            # device=-1 ensures CPU usage
            self.pipeline = pipeline(
                "text-classification",
                model=self.model_name,
                tokenizer=self.model_name,
                device=-1,
                model_kwargs={"cache_dir": str(self.cache_dir)}
            )
            self.loaded = True
            logger.info("ML model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load ML model: {e}")
            self.loaded = False

    def check(self, prompt: str):
        """
        Returns: (is_injection, risk_score, category)
        """
        if not self.loaded:
            logger.warning("ML model not loaded, skipping semantic analysis.")
            return False, 0.0, None

        try:
            # Result is a list of dicts: [{'label': 'INJECTION', 'score': 0.99}]
            result = self.pipeline(prompt, truncation=True, max_length=512)

            label = result[0]['label']
            score = result[0]['score']

            risk_score = score
            if label.upper() == 'SAFE':
                risk_score = 1.0 - score

            if label.upper() == 'INJECTION' and score > config.risk_threshold:
                return True, risk_score, "Semantic Injection"

            return False, risk_score, None

        except Exception as e:
            logger.error(f"Inference error: {e}")
            return False, 0.0, None
