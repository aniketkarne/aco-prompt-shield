FROM python:3.10-slim

LABEL org.opencontainers.image.title="aco-prompt-shield"
LABEL org.opencontainers.image.description="A Local-First, Zero-Cost Prompt Injection Detection Server for MCP"

WORKDIR /app

COPY pyproject.toml README.md LICENSE /app/
COPY src /app/src

# Create log directory
RUN mkdir -p /root/.shield-mcp/logs

# Install dependencies and the package
RUN pip install --no-cache-dir .

# Pre-cache the DeBERTa model so first container run doesn't download ~400MB
# Uses HF_HOME so the cache lives in the standard HuggingFace location
RUN python -c "\
    import os; \
    os.environ['HF_HOME'] = '/root/.cache/huggingface'; \
    os.makedirs('/root/.cache/huggingface', exist_ok=True); \
    from shield_mcp.detectors.ml_models import MLDetector; \
    _ = MLDetector() \
    "

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV HF_HOME="/root/.cache/huggingface"

# Run the server
CMD ["python", "-m", "shield_mcp.server"]
