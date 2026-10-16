"""
ONNX Runtime backend for prompt-injection ML detection.

Default model: Horizon-Labs/prompt-injection-guard-small (141M params,
Apache-2.0). Ships quantized ONNX (int8 embeddings, ~256 MB on disk) so
inference is CPU-only and ~5 ms on warm cache.

Model is auto-downloaded on first use from
https://huggingface.co/Horizon-Labs/prompt-injection-guard-small and cached
under $HF_HOME (defaults to ~/.cache/huggingface/).

Labels are SAFE (0) and INJECTION (1), the same convention as
protectai/deberta-v3-base-prompt-injection-v2, so this is a drop-in
replacement in score semantics.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger("shield-mcp")

# The model we ship with. Override with $SHIELD_MODEL_NAME if you want to
# point at a different local model — must have the same label layout.
DEFAULT_MODEL_ID = "Horizon-Labs/prompt-injection-guard-small"

# Files we fetch from the HF repo. Quantized ONNX keeps the same decisions
# as the fp32 model on the upstream checks (per model card).
_MODEL_FILES = [
    "onnx/model_quantized.onnx",
    "tokenizer.json",
    "config.json",
]


class ONNXDetector:
    """
    ONNX Runtime prompt-injection classifier.

    Lazy-loads the model on first call to .check() so server startup stays
    fast. After the first call the model is held in memory for the process
    lifetime — release explicitly with .close() if you need it gone.
    """

    def __init__(
        self,
        model_id: Optional[str] = None,
        cache_dir: Optional[Path] = None,
        max_length: int = 512,
        risk_threshold: float = 0.5,
    ):
        self.model_id = model_id or os.environ.get(
            "SHIELD_MODEL_NAME", DEFAULT_MODEL_ID
        )
        self.cache_dir = Path(
            cache_dir
            or os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")
        )
        self.max_length = max_length
        self.risk_threshold = risk_threshold

        self._session = None  # ort.InferenceSession (loaded lazily)
        self._tokenizer = None  # tokenizers.Tokenizer
        self._injection_label_id: Optional[int] = None
        self._loaded = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Download (if needed) and load the model. Idempotent."""
        if self._loaded:
            return

        # Import here so a base install (no [ml]) still imports the module.
        try:
            import onnxruntime as ort  # noqa: F401
            from huggingface_hub import hf_hub_download
            from tokenizers import Tokenizer
        except ImportError as e:
            raise RuntimeError(
                "ONNX backend requires the [ml] extra: "
                "pip install aco-prompt-shield[ml]"
            ) from e

        logger.info("Loading ONNX model: %s", self.model_id)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # 1. Download model artifacts. hf_hub_download caches by ETag so
        #    subsequent runs are free.
        try:
            onnx_path = hf_hub_download(
                repo_id=self.model_id,
                filename="onnx/model_quantized.onnx",
                cache_dir=str(self.cache_dir),
            )
            tokenizer_path = hf_hub_download(
                repo_id=self.model_id,
                filename="tokenizer.json",
                cache_dir=str(self.cache_dir),
            )
            config_path = hf_hub_download(
                repo_id=self.model_id,
                filename="config.json",
                cache_dir=str(self.cache_dir),
            )
        except Exception as e:
            logger.error("Failed to download model artifacts: %s", e)
            raise

        # 2. Read config to figure out which label is INJECTION. ONNX
        #    models output logits over the model's label order, not the
        #    text label — so we need id2label.
        import json
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        id2label = {int(k): v for k, v in cfg["id2label"].items()}
        # Convention: INJECTION label id is 1 in protectai/horizon models.
        self._injection_label_id = next(
            (lid for lid, name in id2label.items()
             if name.upper() == "INJECTION"),
            None,
        )
        if self._injection_label_id is None:
            raise RuntimeError(
                f"Model {self.model_id} has no INJECTION label in id2label: {id2label}"
            )

        # 3. Build the tokenizer + ONNX session.
        self._tokenizer = Tokenizer.from_file(tokenizer_path)
        # Cap to model's max length. We deliberately do NOT pad-to-max —
        # that wastes a 4x cost on every short prompt and most prompts
        # fit in 512 tokens. Sliding-window document analysis (v0.3.0)
        # will use a longer window explicitly.
        self._tokenizer.enable_truncation(max_length=self.max_length)
        self._tokenizer.enable_padding(pad_id=0, pad_token="<pad>")

        sess_opts = ort.SessionOptions()
        sess_opts.graph_optimization_level = (
            ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        )
        # Quiet the "unauthenticated requests" warning when no HF_TOKEN is
        # set. The model is public, so the rate-limit hit is irrelevant.
        import logging as _logging
        _logging.getLogger("huggingface_hub").setLevel(_logging.ERROR)
        # CPU only — we promised "100% local" and ONNX CPU is fast enough
        # at this size.
        new_session = ort.InferenceSession(
            onnx_path, sess_opts=sess_opts, providers=["CPUExecutionProvider"]
        )

        # Only flip the loaded flag after every dependency succeeded, so a
        # partial load doesn't leave us in a half-initialised state where
        # _loaded=True but _session is None.
        self._session = new_session
        self._loaded = True
        logger.info("ONNX model loaded: %s", self.model_id)

    def close(self) -> None:
        """Release the loaded model. Safe to call multiple times."""
        self._session = None
        self._tokenizer = None
        self._loaded = False

    def check(self, prompt: str) -> tuple[bool, float, Optional[str]]:
        """
        Returns: (is_injection, risk_score, category)

        is_injection: True if the INJECTION-class probability exceeds
            self.risk_threshold.
        risk_score: the INJECTION probability (0.0–1.0).
        category: "Semantic Injection" if flagged, else None.
        """
        if not self._loaded:
            try:
                self.load()
            except Exception as e:
                logger.error("ONNX model load failed, skipping: %s", e)
                return False, 0.0, None

        # After a successful load(), these are guaranteed non-None. Pyright
        # can't follow the invariant through self.* reads, so we assert and
        # re-bind with the correct type.
        assert self._session is not None
        assert self._tokenizer is not None
        assert self._injection_label_id is not None
        session = self._session
        tokenizer = self._tokenizer
        injection_label_id: int = self._injection_label_id

        try:
            import numpy as np

            enc = tokenizer.encode(prompt)
            input_ids = np.array([enc.ids], dtype=np.int64)
            attention_mask = np.array([enc.attention_mask], dtype=np.int64)

            feeds = {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
            }
            session_inputs = {i.name for i in session.get_inputs()}
            if "token_type_ids" in session_inputs:
                feeds["token_type_ids"] = np.zeros_like(input_ids)

            logits = session.run(None, feeds)[0]
            probs = _softmax(logits[0])
            injection_prob = float(probs[injection_label_id])

            if injection_prob > self.risk_threshold:
                return True, injection_prob, "Semantic Injection"
            return False, injection_prob, None

        except Exception as e:
            logger.error("ONNX inference error: %s", e)
            return False, 0.0, None

    @property
    def loaded(self) -> bool:
        return self._loaded


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _softmax(x) -> "list[float]":
    """Numerically stable softmax over a 1-D numpy array."""
    import numpy as np
    x = np.asarray(x, dtype=np.float64)
    x = x - x.max()
    e = np.exp(x)
    return (e / e.sum()).tolist()