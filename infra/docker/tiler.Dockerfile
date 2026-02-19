FROM ghcr.io/developmentseed/titiler:latest

WORKDIR /app
COPY apps/tiler /app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8081"]
