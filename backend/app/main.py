from app.api.api_v1.api import api_router
from app.core.config import settings
from app.db.database import Base, engine
from app.db.models.remark import Remark
from app.db.models.user import User
from app.db.models.notification import Notification
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

Base.metadata.create_all(bind=engine, checkfirst=True)

app = FastAPI(
    title=settings.PROJECT_NAME, docs_url="/api/v1/docs", redoc_url="/api/v1/redoc", openapi_url="/api/v1/openapi.json"
)


# Set all CORS enabled origins
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_V1_STR)
