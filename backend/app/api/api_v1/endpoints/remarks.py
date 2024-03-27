from pathlib import Path

from app.db.schemas.remark import Remark, RemarkBase
from app.services.remarks import utils
from app.services.users import permissions
from fastapi import APIRouter, Depends, HTTPException, status

router = APIRouter(prefix="/remarks", dependencies=[Depends(permissions.is_user_active)])


@router.post("/", response_model=Remark, status_code=status.HTTP_201_CREATED)
async def create_remark(remark: RemarkBase):
    return utils.update_or_create_remark(remark)


@router.get("/{source_file_path:path}/", response_model=list[Remark])
async def get_remarks(source_file_path: Path):
    return utils.get_remarks_by_source_file_path(source_file_path)


@router.get("/{source_file_path:path}/{segment_id}", response_model=Remark)
async def get_remark(source_file_path: Path, segment_id: str):
    return utils.get_remark_by_source_file_path_and_segment_id(source_file_path, segment_id)


@router.put("/{source_file_path:path}/{segment_id}", response_model=Remark)
async def update_remark(remark: RemarkBase):
    existing_remark = utils.get_remark_by_source_file_path_and_segment_id(remark.source_file_path, remark.segment_id)
    if existing_remark is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Remark not found")
    print(remark)
    return utils.update_or_create_remark(remark)


@router.delete("/{source_file_path:path}/{segment_id}")
async def delete_remark(source_file_path: Path, segment_id: str):
    existing_remark = utils.get_remark_by_source_file_path_and_segment_id(source_file_path, segment_id)
    if existing_remark is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Remark not found")
    utils.delete_remark_by_source_file_path_and_segment_it(source_file_path, segment_id)
    return {"detail": "Remark deleted"}
