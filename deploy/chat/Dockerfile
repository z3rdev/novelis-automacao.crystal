FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv/backend
COPY deploy/chat/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && useradd --uid 10001 --create-home cargo
COPY BACKEND/app ./app
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=8s --start-period=40s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=5)"
CMD ["uvicorn", "app.chat_server.main:create_server", "--factory", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--ws-max-size", "65536", "--no-access-log"]
