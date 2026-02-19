FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gdal-bin \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

COPY apps/api/requirements.txt /workspace/apps/api/requirements.txt
RUN pip install --no-cache-dir -r /workspace/apps/api/requirements.txt

COPY apps/api /workspace/apps/api
COPY apps/worker /workspace/apps/worker

WORKDIR /workspace/apps/api
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
