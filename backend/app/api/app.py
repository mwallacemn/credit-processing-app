from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.infrastructure.db import lifespan


def create_app() -> FastAPI:
    app = FastAPI(
        title="Async Credit Processing Service",
        description="Tech Lead Take-Home Exercise: Async Credit Processing Service with FastAPI, Celery, Redis, and MongoDB",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Enable CORS for front-end access
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register API routes
    app.include_router(api_router)
    return app


app = create_app()
