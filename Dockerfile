FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN apt-get update && apt-get install -y --no-install-recommends iputils-ping traceroute dnsutils nmap \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --no-create-home noctv
COPY noctv/ ./noctv/
COPY web/ ./web/
COPY config/demo.json ./config/demo.json
USER 10001:10001
EXPOSE 8080
CMD ["gunicorn", "noctv.server:create_app()", "--bind", "0.0.0.0:8080", "--workers", "1", "--no-control-socket", "--threads", "8", "--worker-tmp-dir", "/tmp", "--access-logfile", "-"]
