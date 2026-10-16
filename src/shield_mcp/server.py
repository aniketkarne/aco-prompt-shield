from mcp.server.fastmcp import FastMCP
from shield_mcp.detectors.heuristics import HeuristicDetector
from shield_mcp.detectors.structural import StructuralDetector
from shield_mcp.utils.config import config, resolve_ml_backend
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

# Heuristic + Structural detectors are pure-stdlib and loaded eagerly —
# they're cheap and we always want them available as the first line of
# defence.
heuristic_detector = HeuristicDetector()
structural_detector = StructuralDetector()

# ML detector is loaded lazily on the first call to analyze_prompt. This
# keeps server startup under 1 s even with the [ml] extra installed.
_ml_detector = None
_ml_backend_resolved: str | None = None


def _get_ml_detector():
    """
    Lazily instantiate the ML detector.

    Returns None if ML is disabled (off) or unavailable (deps missing).
    """
    global _ml_detector, _ml_backend_resolved

    if _ml_detector is not None:
        return _ml_detector

    backend = resolve_ml_backend()
    _ml_backend_resolved = backend

    if backend == "off":
        logger.debug("ML backend disabled (no ML extra installed).")
        return None

    if backend == "onnx":
        try:
            from shield_mcp.detectors.ml_onnx import ONNXDetector
            _ml_detector = ONNXDetector(
                model_id=config.model_name,
                cache_dir=config.model_cache_dir,
                risk_threshold=config.risk_threshold,
            )
            logger.info("ML backend: ONNX Runtime (%s)", config.model_name)
            return _ml_detector
        except Exception as e:
            logger.error("Failed to init ONNX backend: %s", e)
            return None

    if backend == "full":
        try:
            from shield_mcp.detectors.ml_models import MLDetector
            _ml_detector = MLDetector()  # uses config internally
            logger.info("ML backend: torch+transformers (%s)", config.model_name)
            return _ml_detector
        except Exception as e:
            logger.error("Failed to init full backend: %s", e)
            return None

    return None


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
    """Analyzes a prompt for potential injection attacks.

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

    # Level 2: Semantic Analysis (ML Model) — lazy load.
    ml = _get_ml_detector()
    if ml is not None:
        is_inj_ml, score_ml, cat_ml = ml.check(prompt)
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