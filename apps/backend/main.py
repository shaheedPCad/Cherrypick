from fastapi import FastAPI
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize async database connection pool
    print("🚀 Starting Cherrypick Backend")
    yield
    # Shutdown: Close connections
    print("👋 Shutting down Cherrypick Backend")

app = FastAPI(
    title="Cherrypick API",
    description="Intelligent Resume Assembly Engine",
    version="0.1.0",
    lifespan=lifespan
)

@app.get("/")
async def root():
    return {"message": "Cherrypick API - Ready"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "backend"}
