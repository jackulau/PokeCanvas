# Canvas LMS MCP server — runs on any container host (Fly, Railway, Render,
# Cloud Run, a plain VPS, ...). Reads PORT from the environment (defaults 8000).
FROM python:3.12-slim

WORKDIR /app

# Install dependencies first so this layer caches across code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Only the runtime code is needed in the image (tests/scripts stay out).
COPY src ./src

ENV PORT=8000
EXPOSE 8000

CMD ["python", "src/server.py"]
