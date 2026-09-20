# Changelog

All notable changes will be documented in this file.

## [Unreleased]

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
