from pathlib import Path
from typing import Any

from app.core.config import settings
from app.db.database import get_sess
from app.db.models.remark import Remark as mRemark
from app.db.schemas.remark import Remark, RemarkBase
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, NoResultFound


def get_remarks_by_source_file_path(source_file_path: Path) -> list[Remark]:
    with get_sess() as sess:
        return [
            Remark.model_validate(remark)
            for remark in sess.query(mRemark)
            .filter(mRemark.source_file_path == str(settings.WORK_DIR.joinpath(source_file_path)))
            .all()
            if remark
        ]


def get_remark_by_source_file_path_and_segment_id(source_file_path: Path, segment_id: str) -> Remark:
    try:
        with get_sess() as sess:
            return Remark.model_validate(
                sess.query(mRemark)
                .filter(mRemark.source_file_path == str(settings.WORK_DIR.joinpath(source_file_path)))
                .filter(mRemark.segment_id == segment_id)
                .one()
            )
    except NoResultFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Remark not found for given source file path and segment id."
            f" 'source_file_path': {source_file_path}, 'segment_id': {segment_id}",
        )


def update_or_create_remark(remark_data: RemarkBase | dict[str, Any]) -> Remark:
    remark_data: RemarkBase = RemarkBase.model_validate(remark_data)
    try:
        with get_sess() as sess:
            remark = (
                sess.query(mRemark)
                .filter(mRemark.source_file_path == str(remark_data.source_file_path))
                .filter(mRemark.segment_id == str(remark_data.segment_id))
                .one()
            )
            for key, value in remark_data.model_dump().items():
                setattr(remark, key, value)
            sess.commit()
            return Remark.model_validate(remark)
    except NoResultFound:
        with get_sess() as sess:
            sess.add(mRemark(**remark_data.model_dump()))
            sess.commit()
            return Remark.model_validate(
                sess.query(mRemark)
                .filter(mRemark.source_file_path == str(remark_data.source_file_path))
                .filter(mRemark.segment_id == str(remark_data.segment_id))
                .first()
            )
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Unique data conflict")


def delete_remark_by_source_file_path_and_segment_it(source_file_path: Path, segment_id: str) -> None:
    try:
        with get_sess() as sess:
            remark = (
                sess.query(mRemark)
                .filter(mRemark.source_file_path == str(settings.WORK_DIR.joinpath(source_file_path)))
                .filter(mRemark.segment_id == segment_id)
                .one()
            )
            sess.delete(remark)
            sess.commit()
    except NoResultFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Remark not found")
