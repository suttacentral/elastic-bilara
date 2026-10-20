from pathlib import Path
from typing import Annotated

from app.core.config import settings
from app.db.schemas.user import UserBase
from app.services.auth import utils
from app.services.directories.index import create_indexed_directory
from app.services.storage import StorageError, storage_errors, write_json
from app.services.tags import sync
from app.services.tags.service import TagService
from app.services.tags.store import TagError, TagStore
from app.services.users.permissions import is_admin_or_superuser, is_user_active
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from search.search import Search
from search.utils import get_json_data, get_prefix, yield_file_path

router = APIRouter(prefix="/tags")
search = Search()


def tag_service():
    try:
        yield TagService(settings.WORK_DIR)
    except TagError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail) from exc
    except StorageError as exc:
        raise HTTPException(
            status_code=503,
            detail="Tag storage is unavailable. A saved operation may be awaiting recovery; reload before retrying.",
        ) from exc


@router.get("/")
def get_tags(user=Depends(utils.get_current_user), service=Depends(tag_service)):
    return service.list()


@router.get("/sync/", dependencies=[Depends(is_admin_or_superuser), Depends(is_user_active)])
def sync_status(service=Depends(tag_service)):
    return sync.status(service.store.work)


@router.post("/sync/retry/", status_code=status.HTTP_202_ACCEPTED,
             dependencies=[Depends(is_admin_or_superuser), Depends(is_user_active)])
def retry_sync(background_tasks: BackgroundTasks, service=Depends(tag_service)):
    result = sync.retry(service.store.work)
    background_tasks.add_task(sync.dispatch_safely, service.store.work)
    return result


@router.post("/", status_code=status.HTTP_201_CREATED, dependencies=[Depends(is_user_active)])
def create_tag(data: dict, background_tasks: BackgroundTasks,
               user=Depends(is_admin_or_superuser), service=Depends(tag_service)):
    result = service.mutate("create", user, data=data)
    background_tasks.add_task(sync.dispatch_safely, service.store.work)
    return result


@router.patch("/{tag_name}/", dependencies=[Depends(is_user_active)])
def update_tag(tag_name: str, data: dict, background_tasks: BackgroundTasks,
               user=Depends(is_admin_or_superuser), service=Depends(tag_service)):
    result = service.mutate("update", user, tag_name, data)
    background_tasks.add_task(sync.dispatch_safely, service.store.work)
    return result


@router.delete("/{tag_name}/", dependencies=[Depends(is_user_active)])
def delete_tag(tag_name: str, background_tasks: BackgroundTasks,
               user=Depends(is_admin_or_superuser), service=Depends(tag_service)):
    result = service.mutate("delete", user, tag_name)
    background_tasks.add_task(sync.dispatch_safely, service.store.work)
    return result


@router.post(
    "/data/{prefix}/",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(is_admin_or_superuser), Depends(is_user_active)],
)
def create_tag_data_file(
    user: Annotated[UserBase, Depends(utils.get_current_user)],
    prefix: str,
) -> dict:
    """Create a new tag data file for a given prefix, mirroring the root file structure."""
    try:
        return _ensure_tag_data_file(prefix)
    except TagError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail) from exc
    except StorageError as exc:
        raise HTTPException(
            status_code=503,
            detail="Tag storage is unavailable. Reload before retrying.",
        ) from exc


def _ensure_tag_data_file(prefix):
    with TagStore(settings.WORK_DIR).locked():
        tag_path = _find_tag_data_file(prefix)
        root_path = None
        if tag_path is None:
            root_files = search.get_file_paths(muid="root-pli-ms", prefix=prefix, exact=True, _type="file_path")
            roots = [Path(path) for path in root_files if Path(path).is_file()]
            if not roots:
                raise HTTPException(status_code=404, detail=f"Root file for prefix '{prefix}' not found")
            root_path = roots[0]
            relative = root_path.relative_to(settings.WORK_DIR / "root")
            tag_path = settings.WORK_DIR / "tag" / relative.parent / f"{prefix}_tag.json"
        result = _create_tag_data_file(prefix, tag_path, root_path)
        with storage_errors():
            indexed, error = search.add_to_index(tag_path)
        if not indexed:
            raise HTTPException(status_code=503, detail="Tag file exists, but indexing failed. Retry this operation.") from error
        return result


def _find_tag_data_file(prefix):
    # Check if tag file already exists on disk
    tag_dir = settings.WORK_DIR / "tag"
    if tag_dir.exists():
        for f in yield_file_path(tag_dir, level=1):
            if get_prefix(f) == prefix:
                return f
    return None


def _create_tag_data_file(prefix, tag_file_path, root_path):
    if root_path is None:
        data = TagStore(settings.WORK_DIR).read_json(tag_file_path)
        if not isinstance(data, dict) or any(not isinstance(value, str) for value in data.values()):
            raise TagError(409, f"Invalid tag data in {tag_file_path.name}. Repair the file before retrying.")
        return {"detail": f"Tag data file for '{prefix}' already exists", "path": str(tag_file_path)}
    with storage_errors():
        root_data = get_json_data(root_path)
        create_indexed_directory(tag_file_path.parent)
    tag_data = {key: "" for key in root_data.keys()}
    write_json(tag_file_path, tag_data)

    return {"detail": f"Tag data file created for '{prefix}'", "path": str(tag_file_path)}


@router.post(
    "/reindex/",
    dependencies=[Depends(is_admin_or_superuser), Depends(is_user_active)],
)
async def reindex_tag_files(
    user: Annotated[UserBase, Depends(utils.get_current_user)],
) -> dict:
    """Scan all tag files on disk and index any that are not yet in ES."""
    tag_dir = settings.WORK_DIR / "tag"
    if not tag_dir.exists():
        return {"detail": "No tag directory found", "indexed": 0}

    indexed_count = 0
    for f in yield_file_path(tag_dir, level=1):
        success, error = search.add_to_index(f)
        if success:
            indexed_count += 1

    return {"detail": f"Reindexed {indexed_count} tag file(s)", "indexed": indexed_count}
