from app.api.api_v1.endpoints import auth, projects, pull_request, search, tasks,directories, users
from app.services.users import permissions
from fastapi import APIRouter, Depends


api_router = APIRouter()

api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(projects.router, tags=["projects"])
api_router.include_router(search.router, tags=["search"])
api_router.include_router(pull_request.router, tags=["pull_request"])
api_router.include_router(tasks.router, tags=["tasks"])
api_router.include_router(directories.router, tags=["directories"])
api_router.include_router(
    users.router,
    tags=["users"],
    dependencies=[Depends(permissions.is_admin_or_superuser), Depends(permissions.is_user_active)],
)
api_router.include_router(users.router_exposed, tags=["users"])
