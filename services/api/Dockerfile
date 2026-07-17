FROM python:3.12.13-slim-bookworm AS runtime

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN pip install --no-cache-dir uv==0.10.8

COPY pyproject.toml uv.lock ./
COPY services/api/src ./services/api/src

RUN uv sync --frozen --no-dev --no-editable \
    && chmod -R a-w /app

USER 65532

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('PORT', '8080') + '/api/v1/health', timeout=3)"

ENTRYPOINT ["/bin/sh", "-c", "case \"$1\" in api) exec uvicorn creditops.main:app --host 0.0.0.0 --port \"${PORT:-8080}\" ;; worker) exec python -m creditops.worker.main ;; *) echo 'usage: creditops-container api|worker' >&2; exit 64 ;; esac", "creditops-container"]
CMD ["api"]
