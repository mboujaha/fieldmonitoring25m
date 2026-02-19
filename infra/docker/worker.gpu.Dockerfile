FROM mdl4eo/otbtf:3.4.0-gpu

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    python3-dev \
    build-essential \
    gdal-bin \
    libgdal-dev \
    git \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

COPY apps/api/requirements.txt /workspace/apps/api/requirements.txt
RUN pip3 install --no-cache-dir -r /workspace/apps/api/requirements.txt

RUN git clone --depth 1 https://github.com/remicres/sr4rs.git /opt/sr4rs

COPY apps/api /workspace/apps/api
COPY apps/worker /workspace/apps/worker

WORKDIR /workspace
CMD ["celery", "-A", "worker.celery_app.celery_app", "worker", "-Q", "sr_gpu", "-l", "info"]
