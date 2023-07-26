from app.api.api_v1.endpoints import auth, projects, search
from fastapi import APIRouter

api_router = APIRouter()

api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(projects.router, tags=["projects"])
api_router.include_router(search.router, tags=["search"])
