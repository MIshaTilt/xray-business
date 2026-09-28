FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install PostgreSQL client libraries, compilation tools, and netcat
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY xray-be/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

# Copy specifications and backend code
COPY openapi.yaml DATA-API.yaml /app/
COPY xray-be /app/xray-be

WORKDIR /app/xray-be/xray_be

# Copy entrypoint script
COPY xray-be/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "xray_be.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]
