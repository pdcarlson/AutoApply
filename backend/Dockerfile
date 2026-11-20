# The AutoApply API, agent and its Chromium in one image. Build from backend/:
#   docker build -t autoapply-api .
# One container only, always on: filled forms are open browser windows inside this process,
# and its data (every user's folder) lives on the volume mounted at /data.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app/backend

# Dependencies first, so code changes don't reinstall them (or Chromium).
COPY agent/requirements.txt agent/requirements.txt
COPY server/requirements.txt server/requirements.txt
# libatomic1: Playwright's bundled Node needs it, and the slim image doesn't have it.
RUN apt-get update && apt-get install -y --no-install-recommends libatomic1 \
    && pip install -r server/requirements.txt \
    && playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

COPY agent agent
COPY server server
COPY onboarding onboarding
COPY deploy/entrypoint.sh /entrypoint.sh

RUN useradd --create-home --uid 1000 app \
    && mkdir -p /data \
    && chmod +x /entrypoint.sh

ENV AUTOAPPLY_HOST=0.0.0.0 \
    AUTOAPPLY_PORT=8080 \
    AUTOAPPLY_DATA_DIR=/data

VOLUME /data
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,os; urllib.request.urlopen('http://127.0.0.1:%s/api/health' % os.environ.get('AUTOAPPLY_PORT','8080'), timeout=4)"

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "-m", "server"]
