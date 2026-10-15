from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status

from app.core.config import settings
from app.services.auth import utils as auth_utils
from app.services.publications.errors import PublicationError, PublicationStorageError
from app.services.publications.schema import PublicationMetadata, PublicationUpdate
from app.services.publications.service import PublicationService
from app.services.publications import sync
from app.services.users.utils import get_user

router = APIRouter(prefix="/publications")


def publication_service(token=Depends(auth_utils.get_current_user)):
    # Read the current role, activity and username from the database.
    try:
        yield PublicationService(settings.WORK_DIR, get_user(int(token.github_id)))
    except PublicationError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail) from exc
    except PublicationStorageError as exc:
        raise HTTPException(status_code=503, detail="Publication storage is unavailable. Reload before retrying the save.") from exc


@router.get("/next-number/")
def get_next_publication_number(service=Depends(publication_service)):
    return {"next_number": service.next_number()}


@router.get("/sync/")
def sync_status(service=Depends(publication_service)):
    return sync.status(settings.WORK_DIR, service.user)


@router.post("/sync/retry/", status_code=status.HTTP_202_ACCEPTED)
def retry_sync(background_tasks: BackgroundTasks, service=Depends(publication_service)):
    result = sync.retry(settings.WORK_DIR, service.user)
    background_tasks.add_task(sync.dispatch_safely, settings.WORK_DIR)
    return result


@router.get("/")
def list_publications(service=Depends(publication_service)):
    return service.list()


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_publication(body: PublicationMetadata, background_tasks: BackgroundTasks, service=Depends(publication_service)):
    result = service.create(body)
    background_tasks.add_task(sync.dispatch_safely, settings.WORK_DIR)
    return result


@router.get("/{publication_number}")
def get_publication(publication_number: str, service=Depends(publication_service)):
    return service.get(publication_number)


@router.patch("/{publication_number}")
def update_publication(publication_number: str, body: PublicationUpdate, background_tasks: BackgroundTasks, service=Depends(publication_service)):
    result = service.update(publication_number, body)
    background_tasks.add_task(sync.dispatch_safely, settings.WORK_DIR)
    return result


@router.delete("/{publication_number}")
def delete_publication(publication_number: str, background_tasks: BackgroundTasks, if_match: str = Header(), service=Depends(publication_service)):
    result = service.delete(publication_number, if_match)
    background_tasks.add_task(sync.dispatch_safely, settings.WORK_DIR)
    return result
