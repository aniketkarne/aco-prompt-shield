from mcp.server.fastmcp import FastMCP
from shield_mcp.detectors.heuristics import HeuristicDetector
from shield_mcp.detectors.ml_models import MLDetector
from shield_mcp.detectors.structural import StructuralDetector
from shield_mcp.utils.config import config
import logging
import sys

# Configure logging
# We want to log to file as well
file_handler = logging.FileHandler(config.log_file)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# Stderr handler for MCP stdio transport
stream_handler = logging.StreamHandler(sys.stderr)
stream_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))

logger = logging.getLogger("shield-mcp")
logger.setLevel(logging.INFO)
# Clear existing handlers to avoid duplication if reloaded or basicConfig interference
if logger.hasHandlers():
    logger.handlers.clear()
logger.addHandler(file_handler)
logger.addHandler(stream_handler)

mcp = FastMCP("PromptInjectionShield")

# Initialize detectors
heuristic_detector = HeuristicDetector()
ml_detector = MLDetector()
structural_detector = StructuralDetector()

@mcp.tool()
def analyze_prompt(prompt: str) -> dict:
    """
    Analyzes a prompt for potential injection attacks.

    Args:
        prompt: The input prompt to analyze.

    Returns:
        A dictionary containing:
        - is_injection: boolean
        - risk_score: float (0.0 to 1.0)
        - category: string (optional)
    """
    logger.info(f"Analyzing prompt: {prompt[:50]}...")

    # Level 1: Heuristics
    is_inj, score, cat = heuristic_detector.check(prompt)
    if is_inj:
        logger.warning(f"Heuristic detection: {cat}")
        return {
            "is_injection": True,
            "risk_score": score,
            "category": cat
        }

    # Level 2: Semantic Analysis (ML Model)
    is_inj_ml, score_ml, cat_ml = ml_detector.check(prompt)
    if is_inj_ml:
        logger.warning(f"ML detection: {cat_ml} (score: {score_ml:.2f})")
        return {
            "is_injection": True,
            "risk_score": score_ml,
            "category": cat_ml
        }

    # Level 3: Structural Check
    is_inj_struct, score_struct, cat_struct = structural_detector.check(prompt)
    if is_inj_struct:
        logger.warning(f"Structural detection: {cat_struct}")
        return {
            "is_injection": True,
            "risk_score": score_struct,
            "category": cat_struct
        }

    return {
        "is_injection": False,
        "risk_score": score_ml,
        "category": None
    }

if __name__ == "__main__":
    mcp.run()
