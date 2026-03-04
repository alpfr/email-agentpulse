# ============================================================
# Email AgentPulse — Backend (FastAPI)
# ============================================================
# Multi-stage build for a slim production image.
#
#   docker build -t email-agentpulse-backend .
#   docker run -p 8000:8000 email-agentpulse-backend
# ============================================================

# --- Stage 1: Dependencies ---
FROM python:3.12-slim AS deps

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Stage 2: Production ---
FROM python:3.12-slim AS production

# Security: run as non-root
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

# Copy installed packages from deps stage
COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Copy application code
COPY server.py agent.py main.py ./
COPY tools/ ./tools/

# If .env.example exists, copy it (will be overridden by configmap/secret at runtime)
COPY .env.example .env.example

# Own files as appuser
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
