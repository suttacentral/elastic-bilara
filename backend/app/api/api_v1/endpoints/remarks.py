from pathlib import Path
from typing import Optional

from app.api.api_v1.endpoints.projects import get_paths_for_project
from app.db.schemas.remark import Remark, RemarkBase
from app.services.auth import utils as auth_utils
from app.services.notifications.remark_notifications import create_remark_notifications
from app.services.remarks import utils
from app.services.users import permissions
from app.services.users import utils as user_utils
from fastapi import APIRouter, Depends, HTTPException, Query, status

router = APIRouter(prefix="/remarks", dependencies=[Depends(permissions.is_user_active)])


@router.post("/", response_model=Remark, status_code=status.HTTP_201_CREATED)
async def create_remark(
    remark: RemarkBase,
    user=Depends(auth_utils.get_current_user),
):
    if user.github_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="GitHub account required to create remarks"
        )
    github_id = int(user.github_id)
    existing_remark = utils.get_remark_or_none(
        Path(str(remark.source_file_path)), remark.segment_id, github_id
    )
    updated_remark = utils.update_or_create_remark(remark, github_id)

    action = "created" if existing_remark is None else "updated"
    if existing_remark is None or existing_remark.remark_value != updated_remark.remark_value:
        create_remark_notifications(
            source_file_path=updated_remark.source_file_path,
            segment_id=updated_remark.segment_id,
            remark_value=updated_remark.remark_value,
            action=action,
            actor_username=user.username,
            actor_github_id=github_id,
        )

    return updated_remark


@router.put("/", response_model=Remark)
async def update_remark(
    remark: RemarkBase,
    user=Depends(auth_utils.get_current_user),
):
    if user.github_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="GitHub account required to update remarks"
        )
    github_id = int(user.github_id)
    path = (
        remark.source_file_path
        if remark.source_file_path
        else await get_paths_for_project(None, remark.muid, remark.prefix, "file_path")
    )
    if not path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Path for provided data not found. {remark}")
    existing_remark = utils.get_remark_by_source_file_path_and_segment_id(path, remark.segment_id, github_id)
    if existing_remark is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Remark not found")
    updated_remark = utils.update_or_create_remark(remark, github_id)

    if existing_remark.remark_value != updated_remark.remark_value:
        create_remark_notifications(
            source_file_path=updated_remark.source_file_path,
            segment_id=updated_remark.segment_id,
            remark_value=updated_remark.remark_value,
            action="updated",
            actor_username=user.username,
            actor_github_id=github_id,
        )

    return updated_remark


@router.get("/users/{muid}/{prefix}/")
async def get_remark_users_by_muid_and_prefix(
    muid: str,
    prefix: str,
    user=Depends(auth_utils.get_current_user),
):
    # Only allow admins or the user themselves to see remark contributors
    paths = await get_paths_for_project(None, muid, prefix, "file_path")
    if not paths:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Path not found")
    github_ids = utils.get_remark_users_by_source_file_path(Path(paths.paths[0]))
    users = []
    for gid in github_ids:
        try:
            u = user_utils.get_user(gid)
            users.append({"github_id": u.github_id, "username": u.username})
        except Exception:
            users.append({"github_id": gid, "username": str(gid)})
    return users


@router.get("/{muid}/{prefix}/", response_model=list[Remark])
async def get_remarks_by_muid_and_prefix(
    muid: str,
    prefix: str,
    github_id: Optional[int] = Query(None),
):
    paths = await get_paths_for_project(None, muid, prefix, "file_path")
    if not paths:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Path not found")
    if github_id is not None:
        return utils.get_remarks_by_source_file_path_and_github_id(Path(paths.paths[0]), github_id)
    return await get_remarks(Path(paths.paths[0]))


@router.get("/{muid}/{prefix}/{segment_id}", response_model=Remark)
async def get_remark_by_muid_and_prefix(
    muid: str,
    prefix: str,
    segment_id: str,
    user=Depends(auth_utils.get_current_user),
):
    if user.github_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="GitHub account required to access remarks"
        )
    paths = await get_paths_for_project(None, muid, prefix, "file_path")
    if not paths:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Path not found")
    github_id = int(user.github_id)
    return utils.get_remark_by_source_file_path_and_segment_id(Path(paths.paths[0]), segment_id, github_id)


@router.get("/{source_file_path:path}/", response_model=list[Remark])
async def get_remarks(source_file_path: Path):
    return utils.get_remarks_by_source_file_path(source_file_path)


@router.get("/{source_file_path:path}/{segment_id}", response_model=Remark)
async def get_remark(
    source_file_path: Path,
    segment_id: str,
    user=Depends(auth_utils.get_current_user),
):
    if user.github_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="GitHub account required to access remarks"
        )
    github_id = int(user.github_id)
    return utils.get_remark_by_source_file_path_and_segment_id(source_file_path, segment_id, github_id)


@router.delete("/{source_file_path:path}/{segment_id}")
async def delete_remark(
    source_file_path: Path,
    segment_id: str,
    user=Depends(auth_utils.get_current_user),
):
    if user.github_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="GitHub account required to delete remarks"
        )
    github_id = int(user.github_id)
    existing_remark = utils.get_remark_by_source_file_path_and_segment_id(source_file_path, segment_id, github_id)
    if existing_remark is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Remark not found")
    utils.delete_remark_by_source_file_path_and_segment_it(source_file_path, segment_id, github_id)
    create_remark_notifications(
        source_file_path=existing_remark.source_file_path,
        segment_id=existing_remark.segment_id,
        remark_value=existing_remark.remark_value,
        action="deleted",
        actor_username=user.username,
        actor_github_id=github_id,
    )
    return {"detail": "Remark deleted"}


@router.delete("/{muid}/{prefix}/{segment_id}")
async def delete_remark_by_muid_and_prefix(
    muid: str,
    prefix: str,
    segment_id: str,
    user=Depends(auth_utils.get_current_user),
):
    if user.github_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="GitHub account required to delete remarks"
        )
    github_id = int(user.github_id)
    paths = await get_paths_for_project(None, muid, prefix, "file_path")
    if not paths:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Path not found")
    existing_remark = utils.get_remark_by_source_file_path_and_segment_id(Path(paths.paths[0]), segment_id, github_id)
    if existing_remark is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Remark not found")
    utils.delete_remark_by_source_file_path_and_segment_it(Path(paths.paths[0]), segment_id, github_id)
    create_remark_notifications(
        source_file_path=existing_remark.source_file_path,
        segment_id=existing_remark.segment_id,
        remark_value=existing_remark.remark_value,
        action="deleted",
        actor_username=user.username,
        actor_github_id=github_id,
    )
    return {"detail": "Remark deleted"}
