from app.api.api_v1.api import api_router
from app.core.config import settings
from app.db.database import Base, engine
from app.db.models.notification import Notification, RemarkNotification
from app.db.models.remark import Remark
from app.db.models.user import User
from fastapi import FastAPI
from sqlalchemy import inspect, text
from starlette.middleware.cors import CORSMiddleware

# Migrate remarks table: drop old table if github_id column is missing
with engine.connect() as conn:
    inspector = inspect(engine)
    if inspector.has_table("remarks"):
        columns = [c["name"] for c in inspector.get_columns("remarks")]
        if "github_id" not in columns:
            conn.execute(text("DROP TABLE remarks"))
            conn.commit()

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
