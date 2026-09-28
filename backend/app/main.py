from asyncio import to_thread
from contextlib import asynccontextmanager

from app.api.api_v1.api import api_router
from app.core.config import settings
from app.db.database import Base, engine
from app.db.models.notification import Notification, RemarkNotification
from app.db.models.remark import Remark
from app.db.models.user import User
from app.db.models.user_preference import UserPreference
from app.db.models.dictionary_note import DictionaryNote
from app.db.models.dictionary_hidden_word import DictionaryHiddenWord
from app.db.models.directory_index import DirectoryIndexEntry, DirectoryIndexState
from app.services.directories.index import DirectoryIndex
from fastapi import FastAPI
from sqlalchemy import text
from starlette.middleware.cors import CORSMiddleware


with engine.begin() as connection:
    # Both Web workers can start with the new index tables absent. Serialize
    # schema creation so their checkfirst/create operations cannot race.
    connection.execute(text("SELECT pg_advisory_xact_lock(hashtext('bilara-schema-initialization'))"))
    Base.metadata.create_all(bind=connection, checkfirst=True)

# Safe column migrations for existing tables
with engine.connect() as conn:
    conn.execute(text(
        "ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS hint_style VARCHAR"
    ))
    conn.execute(text(
        "ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS dblclick_search_collapse_inputs BOOLEAN"
    ))
    conn.execute(text(
        "ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS hint_count INTEGER"
    ))
    conn.commit()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # The entrypoint may have pulled the checkout before starting the workers.
    await to_thread(DirectoryIndex().rebuild)
    yield


app = FastAPI(
    title=settings.PROJECT_NAME, docs_url="/api/v1/docs", redoc_url="/api/v1/redoc", openapi_url="/api/v1/openapi.json",
    lifespan=lifespan,
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
