"""
Unit tests for the ONNX backend. The actual model download is exercised
in test_onnx_integration.py (network-dependent); here we test the
detection logic with a mocked ONNX session + tokenizer.
"""

import sys
from unittest.mock import MagicMock

# Mock the optional [ml] deps so the test runs without them installed.
mock_ort = MagicMock()
mock_ort.GraphOptimizationLevel.ORT_ENABLE_ALL = "ORT_ENABLE_ALL"
mock_hf = MagicMock()
mock_tok = MagicMock()
sys.modules["onnxruntime"] = mock_ort
sys.modules["huggingface_hub"] = mock_hf
sys.modules["tokenizers"] = mock_tok

from shield_mcp.detectors.ml_onnx import ONNXDetector  # noqa: E402
from pathlib import Path


def _make_mock_session(logits):
    sess = MagicMock()
    sess.run.return_value = [logits]
    sess.get_inputs.return_value = [
        MagicMock(name="input_ids"),
        MagicMock(name="attention_mask"),
    ]
    return sess


def _make_mock_tokenizer(ids=None, attention_mask=None):
    tok = MagicMock()
    enc = MagicMock()
    enc.ids = ids or [101, 2023, 102]
    enc.attention_mask = attention_mask or [1, 1, 1]
    tok.encode.return_value = enc
    return tok


def _make_detector(logits):
    d = ONNXDetector.__new__(ONNXDetector)
    d.model_id = "Horizon-Labs/prompt-injection-guard-small"
    d.cache_dir = Path("/tmp/fake")
    d.max_length = 512
    d.risk_threshold = 0.5
    d._session = _make_mock_session(logits)
    d._tokenizer = _make_mock_tokenizer()
    d._injection_label_id = 1  # INJECTION
    d._loaded = True
    return d


def test_onnx_flags_injection_high_score():
    # 2-class softmax with strong INJECTION logit
    import math
    inj_logit, safe_logit = 4.0, 0.0
    e_inj, e_safe = math.exp(inj_logit), math.exp(safe_logit)
    d = _make_detector([[safe_logit, inj_logit]])
    is_inj, score, cat = d.check("attack")
    assert is_inj is True
    assert 0.9 < score < 1.0
    assert cat == "Semantic Injection"


def test_onnx_passes_benign():
    import math
    inj_logit, safe_logit = 0.0, 4.0
    d = _make_detector([[safe_logit, inj_logit]])
    is_inj, score, cat = d.check("benign")
    assert is_inj is False
    assert 0.0 < score < 0.1
    assert cat is None


def test_onnx_below_threshold_returns_false():
    """A score at the threshold is not flagged (strict >)."""
    import math
    # Build logits so softmax gives exactly threshold=0.5
    # equal logits -> p = 0.5 each
    d = _make_detector([[0.0, 0.0]])
    is_inj, score, cat = d.check("borderline")
    assert is_inj is False
    assert abs(score - 0.5) < 1e-9


def _make_mock_input(name: str):
    """A MagicMock with a fixed .name (so get_inputs() iter yields it)."""
    m = MagicMock()
    m.name = name
    return m


def test_onnx_handles_token_type_ids_when_model_expects_them():
    """Some ONNX exports need token_type_ids; we send it conditionally."""
    sess = MagicMock()
    # Run returns [[batch_of_results]] — outer list is batches, inner is
    # the logits array for that batch. So .run()[0] is the per-batch
    # logits array.
    sess.run.return_value = [[[0.0, 4.0]]]
    sess.get_inputs.return_value = [
        _make_mock_input("input_ids"),
        _make_mock_input("attention_mask"),
        _make_mock_input("token_type_ids"),
    ]
    d = ONNXDetector.__new__(ONNXDetector)
    d.model_id = "x"
    d.cache_dir = Path("/tmp")
    d.max_length = 512
    d.risk_threshold = 0.5
    d._session = sess
    d._tokenizer = _make_mock_tokenizer()
    d._injection_label_id = 1
    d._loaded = True
    is_inj, score, cat = d.check("test")
    assert is_inj is True
    # Verify token_type_ids was sent
    feeds = sess.run.call_args[0][1]
    assert "token_type_ids" in feeds


def test_onnx_runtime_error_returns_safe():
    """If inference throws, we log and return safe rather than crash."""
    sess = MagicMock()
    sess.run.side_effect = RuntimeError("simulated")
    sess.get_inputs.return_value = [MagicMock(name="input_ids"), MagicMock(name="attention_mask")]
    d = ONNXDetector.__new__(ONNXDetector)
    d.model_id = "x"
    d.cache_dir = Path("/tmp")
    d.max_length = 512
    d.risk_threshold = 0.5
    d._session = sess
    d._tokenizer = _make_mock_tokenizer()
    d._injection_label_id = 1
    d._loaded = True
    is_inj, score, cat = d.check("test")
    assert is_inj is False
    assert score == 0.0
    assert cat is None


def test_onnx_lazy_load_when_unloaded():
    """First call without _loaded should trigger load() — which is mocked to fail here."""
    d = ONNXDetector.__new__(ONNXDetector)
    d.model_id = "x"
    d.cache_dir = Path("/tmp")
    d.max_length = 512
    d.risk_threshold = 0.5
    d._session = None
    d._tokenizer = None
    d._injection_label_id = None
    d._loaded = False
    is_inj, score, cat = d.check("test")
    assert is_inj is False
    assert score == 0.0