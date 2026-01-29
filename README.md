# PromptInjectionShield-MCP 🛡️

A Local-First, Zero-Cost Prompt Injection Detection Server for the Model Context Protocol.

## Overview

This project provides a "Security Gateway" that identifies malicious prompt injection and jailbreak attempts locally on their machine, ensuring privacy and eliminating API costs.

## Features

- **Local Detection Engine**: No external API calls.
- **Tiered Detection**:
    - Level 1: Heuristics (Regex)
    - Level 2: Semantic Analysis (ML Model - DeBERTa)
    - Level 3: Structural Check (Entropy/Encoding)
- **MCP Specification**: Implements `analyze_prompt` tool.
- **Privacy First**: Prompt text never leaves the machine.

## Installation

1. Clone the repository.
2. Install dependencies:
   ```bash
   pip install .
   ```

## Usage

Start the MCP server:
```bash
python -m shield_mcp.server
```

## Configuration

Configuration is stored in `src/utils/config.py` (and potentially overridden by local files).
