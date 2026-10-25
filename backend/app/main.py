from app.api.app import app, create_app
from app.api.router import api_router

# Expose app for ASGI servers like uvicorn (uvicorn app.main:app)
__all__ = ["app", "create_app", "api_router"]

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
