import sys
from unittest.mock import MagicMock

# Mock torch and transformers
sys.modules["torch"] = MagicMock()
sys.modules["transformers"] = MagicMock()

import pytest
from unittest.mock import patch
from shield_mcp.detectors.ml_models import MLDetector

@patch("shield_mcp.detectors.ml_models.pipeline")
def test_ml_detector_mock(mock_pipeline):
    # Setup mock
    mock_pipe_instance = MagicMock()
    mock_pipeline.return_value = mock_pipe_instance

    # Test INJECTION
    mock_pipe_instance.return_value = [{'label': 'INJECTION', 'score': 0.95}]

    detector = MLDetector()
    assert detector.loaded is True

    is_inj, score, cat = detector.check("unsafe prompt")
    assert is_inj is True
    assert score == 0.95
    assert cat == "Semantic Injection"

    # Test SAFE
    mock_pipe_instance.return_value = [{'label': 'SAFE', 'score': 0.99}]

    is_inj, score, cat = detector.check("safe prompt")
    assert is_inj is False
    assert abs(score - 0.01) < 1e-6 # Risk should be 1 - 0.99 = 0.01
    assert cat is None
