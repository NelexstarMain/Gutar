# Serwer transkrypcji gen 6 (tools/gen6/server). Cloud Run: gcloud run deploy gutar --source . (patrz docs/SERWER.md)
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch && pip install -r /dev/stdin <<'REQ'
numpy>=1.24
fastapi>=0.110
uvicorn>=0.29
REQ
COPY tools/gen6 tools/gen6
ENV GUTAR_CKPT=/app/tools/gen6/server/model/best.pt
# GUTAR_TOKEN ustaw przy wdrożeniu (nie wpisuj go tutaj); Cloud Run podaje port w $PORT
CMD exec uvicorn tools.gen6.server.app:app --host 0.0.0.0 --port ${PORT:-8080}
