from app.api.api_v1.endpoints import auth
from fastapi import APIRouter

api_router = APIRouter()

api_router.include_router(auth.router, tags=["auth"])
