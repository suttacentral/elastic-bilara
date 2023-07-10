from app.api.api_v1.endpoints import auth, projects
from fastapi import APIRouter

api_router = APIRouter()

api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(projects.router, tags=["projects"])
