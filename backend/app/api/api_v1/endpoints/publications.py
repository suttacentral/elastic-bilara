from fastapi import APIRouter, Depends, Header, HTTPException, status
from kombu.exceptions import OperationalError

from app.core.config import settings
from app.services.auth import utils as auth_utils
from app.services.publications.errors import PublicationError, PublicationStorageError
from app.services.publications.schema import PublicationMetadata, PublicationUpdate
from app.services.publications.service import PublicationService
from app.services.publications.store import PUBLICATION_FILES
from app.services.users.utils import get_user
from app.tasks import commit as commit_task

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


@router.post("/publish/", status_code=status.HTTP_202_ACCEPTED)
def publish_to_github(service=Depends(publication_service)):
    service.check_publish()
    user = service.user.model_dump()
    try:
        result = commit_task.delay(user, list(PUBLICATION_FILES), "Update publication metadata", add=True)
    except (OSError, OperationalError) as exc:
        raise HTTPException(status_code=503, detail="Publication task submission failed. Please retry publishing later.") from exc
    return {"task_id": result.id, "detail": "GitHub submission queued"}


@router.get("/")
def list_publications(service=Depends(publication_service)):
    return service.list()


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_publication(body: PublicationMetadata, service=Depends(publication_service)):
    return service.create(body)


@router.get("/{publication_number}")
def get_publication(publication_number: str, service=Depends(publication_service)):
    return service.get(publication_number)


@router.patch("/{publication_number}")
def update_publication(publication_number: str, body: PublicationUpdate, service=Depends(publication_service)):
    return service.update(publication_number, body)


@router.delete("/{publication_number}")
def delete_publication(publication_number: str, if_match: str = Header(), service=Depends(publication_service)):
    service.delete(publication_number, if_match)
    return {"detail": f"{publication_number} deleted"}
