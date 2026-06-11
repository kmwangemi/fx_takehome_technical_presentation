# from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
# from app.core.scheduler import start_scheduler, stop_scheduler


# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     print(f"[STARTUP] {settings.APP_NAME} v{settings.APP_VERSION} starting...")
#     start_scheduler()
#     yield
#     stop_scheduler()
#     print(f"[SHUTDOWN] {settings.APP_NAME} shut down")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="MikroTik Hotspot ISP Management Platform API",
    # lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,  # ← use property not ALLOWED_ORIGINS
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(api_router)


@app.get("/", tags=["Health"])
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
    }


@app.get("/healthz", tags=["Health"])
async def health():
    return {"status": "ok"}
