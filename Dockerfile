FROM python:3.10-slim

LABEL org.opencontainers.image.title="aco-prompt-shield"
LABEL org.opencontainers.image.description="A Local-First, Zero-Cost Prompt Injection Detection Server for MCP"

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY src /app/src
# Create models dir if not exists (it might be empty)
RUN mkdir -p /app/models

# Install dependencies and the package
RUN pip install --no-cache-dir .

# Create log directory
RUN mkdir -p /root/.shield-mcp/logs

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the server
CMD ["python", "-m", "shield_mcp.server"]
