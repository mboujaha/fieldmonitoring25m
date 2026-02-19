import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from titiler.application.main import app as titiler_app

app = FastAPI(title="Field Monitoring Tiler", version="0.1.0")
app.mount("/", titiler_app)

allowed_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
