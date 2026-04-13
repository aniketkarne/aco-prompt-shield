# Contributing to aco-shield-mcp

Welcome! Thanks for considering contributing.

## Development Setup

```bash
# Clone the repo
git clone https://github.com/aniketkarne/PromptInjectionShield
cd PromptInjectionShield

# Install in dev mode
pip install -e ".[dev]"

# Run tests
pytest
```

## Adding Detection Patterns

### Heuristic Rules (`src/shield_mcp/detectors/heuristics.py`)
Add regex patterns with a descriptive category name. Be specific — avoid patterns that could produce false positives on normal user input.

### Structural Checks (`src/shield_mcp/detectors/structural.py`)
For encoding/obfuscation detection. Add checks for new encoding schemes if needed.

### ML Model (`src/shield_mcp/detectors/ml_models.py`)
Uses `protectai/deberta-v3-base-prompt-injection-v2`. Only change the model if the current one shows consistent false negatives on real attack patterns.

## Pull Request Guidelines

1. **Test your changes** — add tests in `tests/` for new patterns/features
2. **Keep it focused** — one feature or fix per PR
3. **Update docs** — if you add a config option or change behavior, update README.md
4. **Run the full suite** — `pytest` should pass before submitting

## Reporting Issues

Please include:
- The prompt that triggered a false positive/negative
- Your `shield_config.json` (if custom)
- Expected vs actual behavior

## Code Style

- Standard Python formatting (Black-compatible)
- Type hints appreciated but not required
- Docstrings on public methods
