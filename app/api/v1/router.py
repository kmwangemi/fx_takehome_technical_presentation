from fastapi import APIRouter

from app.api.v1.routers import customer_router, executions_router, quotes_router

api_router = APIRouter(prefix="/api/v1")


api_router.include_router(customer_router.router)
api_router.include_router(executions_router.router)
api_router.include_router(quotes_router.router)
