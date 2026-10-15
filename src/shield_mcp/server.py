from mcp.server.fastmcp import FastMCP
from shield_mcp.detectors.heuristics import HeuristicDetector
from shield_mcp.detectors.ml_models import MLDetector
from shield_mcp.detectors.structural import StructuralDetector
from shield_mcp.utils.config import config
import hashlib
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
# Only configure if not already configured (avoid duplicate handlers on reload)
if not logger.handlers:
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

mcp = FastMCP("aco-prompt-shield")

# Initialize detectors
heuristic_detector = HeuristicDetector()
ml_detector = MLDetector()
structural_detector = StructuralDetector()


def _fingerprint(prompt: str) -> str:
    """
    Stable, non-reversible identifier for an analyzed prompt.

    Used in logs instead of the prompt text so we keep an audit trail
    without ever writing user input to disk. The README claims
    "100% local, all private" — logging even truncated prompt text
    would contradict that promise.
    """
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]


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
    # Log metadata only — never the prompt itself. Length + a sha256
    # fingerprint lets operators correlate / debug without storing
    # any user content on disk.
    logger.info(
        "analyze_prompt: fp=%s len=%d", _fingerprint(prompt), len(prompt)
    )

    # Level 1: Heuristics
    is_inj, score, cat = heuristic_detector.check(prompt)
    if is_inj:
        logger.warning("heuristic hit: fp=%s category=%s", _fingerprint(prompt), cat)
        return {
            "is_injection": True,
            "risk_score": score,
            "category": cat
        }

    # Level 2: Semantic Analysis (ML Model)
    is_inj_ml, score_ml, cat_ml = ml_detector.check(prompt)
    if is_inj_ml:
        logger.warning(
            "ml hit: fp=%s category=%s score=%.2f",
            _fingerprint(prompt), cat_ml, score_ml,
        )
        return {
            "is_injection": True,
            "risk_score": score_ml,
            "category": cat_ml
        }

    # Level 3: Structural Check
    is_inj_struct, score_struct, cat_struct = structural_detector.check(prompt)
    if is_inj_struct:
        logger.warning(
            "structural hit: fp=%s category=%s",
            _fingerprint(prompt), cat_struct,
        )
        return {
            "is_injection": True,
            "risk_score": score_struct,
            "category": cat_struct
        }

    return {
        "is_injection": False,
        "risk_score": 0.0,
        "category": None
    }


def main():
    mcp.run()


if __name__ == "__main__":
    main()
