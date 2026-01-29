import sys
from unittest.mock import MagicMock

# Mock torch and transformers to avoid installation requirement for this test
sys.modules["torch"] = MagicMock()
sys.modules["transformers"] = MagicMock()

import pytest
from unittest.mock import patch
from shield_mcp.server import analyze_prompt

@patch("shield_mcp.server.ml_detector")
@patch("shield_mcp.server.structural_detector")
@patch("shield_mcp.server.heuristic_detector")
def test_full_flow(mock_heur, mock_struct, mock_ml):
    # Case 1: Heuristic Catch
    mock_heur.check.return_value = (True, 1.0, "Heuristic")
    result = analyze_prompt("test")
    assert result["is_injection"] is True
    assert result["category"] == "Heuristic"
    # Verify others not called
    mock_ml.check.assert_not_called()

    # Case 2: Heuristic Safe, ML Catch
    mock_heur.check.return_value = (False, 0.0, None)
    mock_ml.check.return_value = (True, 0.9, "ML")
    result = analyze_prompt("test")
    assert result["is_injection"] is True
    assert result["category"] == "ML"
    assert result["risk_score"] == 0.9

    # Case 3: Heuristic Safe, ML Safe, Structural Catch
    mock_heur.check.return_value = (False, 0.0, None)
    mock_ml.check.return_value = (False, 0.01, None)
    mock_struct.check.return_value = (True, 1.0, "Structural")
    result = analyze_prompt("test")
    assert result["is_injection"] is True
    assert result["category"] == "Structural"

    # Case 4: All Safe
    mock_heur.check.return_value = (False, 0.0, None)
    mock_ml.check.return_value = (False, 0.01, None)
    mock_struct.check.return_value = (False, 0.0, None)
    result = analyze_prompt("test")
    assert result["is_injection"] is False
    assert result["category"] is None
