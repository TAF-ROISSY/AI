# syntax=docker/dockerfile:1
# TAF WAREHOUSE — image serveur (production AWS ou recette).
# Construire : docker build -t taf-warehouse:<version> .
FROM public.ecr.aws/docker/library/python:3.12.8-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    TAF_DATA_DIR=/var/lib/taf-warehouse
WORKDIR /app

COPY requirements.txt .
# Certificat d'autorité optionnel (proxy d'entreprise) : docker build --secret id=ca,src=ca.pem ...
# Il n'est utilisé que pendant l'installation et n'est pas conservé dans l'image.
RUN --mount=type=secret,id=ca,required=false \
    if [ -f /run/secrets/ca ]; then export PIP_CERT=/run/secrets/ca; fi; \
    pip install --no-cache-dir -r requirements.txt \
 && useradd --system --uid 10001 --home /app taf \
 && mkdir -p /var/lib/taf-warehouse && chown taf /var/lib/taf-warehouse

COPY app ./app
COPY web ./web
USER taf
EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys;sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8765/healthz',timeout=4).status==200 else 1)"

# Les en-têtes X-Forwarded-* ne sont acceptés que parce que le port 8765 n'est joignable
# que par le proxy HTTPS (réseau Docker interne). Ne jamais publier ce port directement.
CMD ["uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8765", "--proxy-headers", "--forwarded-allow-ips", "*", "--workers", "1"]
