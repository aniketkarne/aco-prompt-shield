# Changelog

All notable changes will be documented in this file.

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
