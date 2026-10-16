# Changelog

All notable changes will be documented in this file.

## [0.2.0] - 2026-10-16

### Changed (BREAKING for users with custom ML configs)

- **Tiered install — `pip install aco-prompt-shield` is now ~3 MB.**
  The default install includes only the MCP server + regex + structural
  detectors. No ML inference is performed and no model is downloaded.
- **`pip install aco-prompt-shield[ml]` adds ONNX Runtime + Horizon-Labs
  prompt-injection-guard-small (Apache-2.0).** Replaces the previous
  torch+transformers + ProtectAI DeBERTa stack. The new model is
  multilingual (30 languages), trained on direct AND indirect injection,
  and has a 2048-token context window (vs 512). First-run downloads
  ~280 MB of quantized ONNX to `$HF_HOME`.
- **`pip install aco-prompt-shield[full]` keeps the original
  torch+transformers path for users with DeBERTa cached.** Opt-in only.
- **`scipy` removed as a hard dependency.** Shannon entropy in
  StructuralDetector is now pure-stdlib. Saves ~99 MB on every tier.
- **ML detector is lazy-loaded on first `analyze_prompt` call.**
  Server startup drops from ~6 s to <1 s. Model loads once, cached for
  the process lifetime.
- **New env var `SHIELD_ML_BACKEND` (default `auto`)** — selects
  `onnx | full | off | auto`. `auto` picks the best backend available.
  `off` disables ML entirely.

### Improved

- **Heuristic FP reduction on real-world benign text** — tightened 4
  patterns that were triggering on legitimate phrases:
  - `cooking instructions` no longer matches Prompt Exfiltration (was
    matching "show me the cooking instructions")
  - `how do I enable developer mode` no longer matches Jailbreak
    (Android UI mode is a legitimate phrase)
  - `required by law` alone no longer matches Fake Authority (the
    imperative follow-on is now required)
  - `<user>` / `<div>` style XML/HTML no longer matches Delimiter
    Hijacking (only injection-target tags do)
  - See `tests/fp_corpus.yaml` for the 35-prompt corpus and
    `tests/test_fp_corpus.py` for the regression test.
- **Default model horizon** — README updated with new benchmarks
  against the 19-attack + 5-indirect-injection + 20-benign corpus.
  Detection rate: 19/19 on direct attacks + 5/5 on indirect attacks
  (previously DeBERTa-v2 missed 1/23). FP rate: 2/20 on benign text
  (both at ~0.71 confidence — borderline calls).

### Added

- `tests/fp_corpus.yaml` and `tests/test_fp_corpus.py` — regression
  suite of 35 real-world benign prompts that should NOT flag. Covers
  12+ trigger-word categories.
- `tests/test_onnx_backend.py` — unit tests for the new ONNX backend
  with mocked dependencies.
- `demo/bench.py` — runnable benchmark script, writes
  `demo/bench-results.json`.

## [0.1.5] - 2026-10-16

### Fixed
- **StructuralDetector false positives on benign long tokens.** The previous
  regex flagged any long word of hex or base64 characters, which meant a
  routine MD5 / SHA hash, UUID, JWT header, or base64-encoded attachment in
  a prompt was blocked at `risk_score=1.0`. Detection of *encoded* injection
  prompts (base64 / hex of "ignore all previous instructions", etc.) is
  preserved — only the decoded payload is now scanned for natural-language
  injection indicators, so opaque data no longer trips the layer.
- **Server logged analyzed prompts to disk.** `analyze_prompt` previously did
  `logger.info(f"Analyzing prompt: {prompt[:50]}...")`, which contradicts
  the README's "100% local, all private" promise. Logs now contain only a
  16-char sha256 fingerprint and the prompt length — no substring of the
  analyzed content is ever written to disk.
- **`mcp` dependency pinned to `>=1.10,<2`.** mcp 2.x renamed
  `FastMCP` → `MCPServer` and made other breaking API changes; without the
  pin, a fresh `pip install aco-prompt-shield` could install mcp 2.x and
  crash the server on import with `ModuleNotFoundError: mcp.server.fastmcp`.

### Tests
- Added `tests/test_structural.py` regression cases for MD5 / SHA / UUID /
  JWT / base64 attachment false positives (10 parametrized cases).
- Added `tests/test_structural.py` regression cases proving encoded injection
  phrases (base64 / hex of canonical attack text) still flag.
- Added `tests/test_server_logging.py` covering the privacy invariant
  (prompt text never appears in any log record) and the fingerprint format.

## [0.1.0] - 2026-04-13

### Added
- Initial release
- Tiered detection pipeline:
  - Level 1: Heuristic (regex) detection
  - Level 2: Semantic analysis via DeBERTa ML model
  - Level 3: Structural encoding/obfuscation checks
- MCP server integration (`analyze_prompt` tool)
- Configurable risk threshold via `shield_config.json`
- Docker support
- Test suite covering all detectors
