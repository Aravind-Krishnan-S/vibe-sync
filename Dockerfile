FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Cloud Run expects port 8080
ENV PORT=8080

# Run the MCP server via uvicorn (FastMCP supports ASGI)
CMD ["python", "server.py"]
