from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import settings
from app.services.auth import utils as auth_utils
from app.services.publication_documents import sync
from app.services.publication_documents.service import DocumentService
from app.services.publications.errors import PublicationError, PublicationStorageError
from app.services.users.utils import get_user

router = APIRouter(prefix="/publication-documents")


class Content(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    content: str = Field(max_length=2_000_000)


class Version(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    published_revision: str = Field(pattern=r"^[a-f0-9]{64}$")


class Save(Content, Version):
    pass


class Selection(Version):
    id: str = Field(pattern=r"^[a-f0-9]{64}$")


class Publish(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    documents: list[Selection] = Field(min_length=1, max_length=200)


def document_service(response: Response, token=Depends(auth_utils.get_current_user)):
    response.headers["Cache-Control"] = "no-store"
    try:
        yield DocumentService(settings.WORK_DIR, settings.PUBLISHED_DIR, get_user(int(token.github_id)))
    except PublicationError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail) from exc
    except PublicationStorageError as exc:
        raise HTTPException(status_code=503, detail="Document storage is unavailable. Reload before retrying.") from exc


@router.get("/counts/")
def document_counts(service=Depends(document_service)):
    return service.counts()


@router.get("/{number}/")
def list_documents(number: str, service=Depends(document_service)):
    return service.list(number)


@router.get("/{number}/status/")
def document_status(number: str, service=Depends(document_service)):
    return service.status(number)


@router.post("/{number}/retry/{operation}/")
def retry(number: str, operation: Literal["sync", "publish"], background_tasks: BackgroundTasks,
          service=Depends(document_service)):
    result = service.retry(number, operation)
    background_tasks.add_task(sync.dispatch_safely, settings.WORK_DIR, number)
    return result


@router.post("/{number}/publish/", status_code=202)
def publish(number: str, body: Publish, background_tasks: BackgroundTasks, service=Depends(document_service)):
    result = service.publish(number, body.documents)
    background_tasks.add_task(sync.dispatch_safely, settings.WORK_DIR, number)
    return result


@router.get("/{number}/documents/{uid}")
def get_document(number: str, uid: str, service=Depends(document_service)):
    return service.get(number, uid)


@router.put("/{number}/documents/{uid}")
def save_document(number: str, uid: str, body: Save, background_tasks: BackgroundTasks, service=Depends(document_service)):
    result = service.save(number, uid, body)
    background_tasks.add_task(sync.dispatch_safely, settings.WORK_DIR, number)
    return result


@router.post("/{number}/documents/{uid}/validate/")
def validate_document(number: str, uid: str, body: Content, service=Depends(document_service)):
    return service.check(number, uid, body.content)


@router.post("/{number}/documents/{uid}/diff/")
def diff_document(number: str, uid: str, body: Content, comparison: Literal["saved", "published"] = "published",
                  service=Depends(document_service)):
    return service.diff(number, uid, body.content, comparison)


@router.post("/{number}/documents/{uid}/baseline/")
def acknowledge_baseline(number: str, uid: str, body: Version, service=Depends(document_service)):
    return service.acknowledge_baseline(number, uid, body)
