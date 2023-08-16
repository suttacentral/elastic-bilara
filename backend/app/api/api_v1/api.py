from app.api.api_v1.endpoints import auth, projects, pull_request, search, tasks
from fastapi import APIRouter

api_router = APIRouter()

api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(projects.router, tags=["projects"])
api_router.include_router(search.router, tags=["search"])
api_router.include_router(pull_request.router, tags=["pull_request"])
api_router.include_router(tasks.router, tags=["tasks"])
