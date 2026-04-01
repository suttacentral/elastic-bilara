from pathlib import Path
from typing import Any

from app.core.config import settings
from app.db.database import get_sess
from app.db.models.remark import Remark as mRemark
from app.db.schemas.remark import Remark, RemarkBase
from fastapi import HTTPException, status
from sqlalchemy import distinct
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


def get_remarks_by_source_file_path_and_github_id(source_file_path: Path, github_id: int) -> list[Remark]:
    with get_sess() as sess:
        return [
            Remark.model_validate(remark)
            for remark in sess.query(mRemark)
            .filter(mRemark.source_file_path == str(settings.WORK_DIR.joinpath(source_file_path)))
            .filter(mRemark.github_id == github_id)
            .all()
            if remark
        ]


def get_remark_users_by_source_file_path(source_file_path: Path) -> list[int]:
    with get_sess() as sess:
        rows = (
            sess.query(distinct(mRemark.github_id))
            .filter(mRemark.source_file_path == str(settings.WORK_DIR.joinpath(source_file_path)))
            .all()
        )
        return [row[0] for row in rows]


def get_remark_by_source_file_path_and_segment_id(
    source_file_path: Path, segment_id: str, github_id: int | None = None
) -> Remark:
    try:
        with get_sess() as sess:
            query = (
                sess.query(mRemark)
                .filter(mRemark.source_file_path == str(settings.WORK_DIR.joinpath(source_file_path)))
                .filter(mRemark.segment_id == segment_id)
            )
            if github_id is not None:
                query = query.filter(mRemark.github_id == github_id)
            return Remark.model_validate(query.one())
    except NoResultFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Remark not found for given source file path and segment id."
            f" 'source_file_path': {source_file_path}, 'segment_id': {segment_id}",
        )


def get_remark_or_none(source_file_path: Path, segment_id: str, github_id: int | None = None) -> Remark | None:
    with get_sess() as sess:
        query = (
            sess.query(mRemark)
            .filter(mRemark.source_file_path == str(source_file_path))
            .filter(mRemark.segment_id == segment_id)
        )
        if github_id is not None:
            query = query.filter(mRemark.github_id == github_id)
        remark = query.first()
        return Remark.model_validate(remark) if remark else None


def update_or_create_remark(remark_data: RemarkBase | dict[str, Any], github_id: int) -> Remark:
    remark_data: RemarkBase = RemarkBase.model_validate(remark_data)
    try:
        with get_sess() as sess:
            remark = (
                sess.query(mRemark)
                .filter(mRemark.source_file_path == str(remark_data.source_file_path))
                .filter(mRemark.segment_id == str(remark_data.segment_id))
                .filter(mRemark.github_id == github_id)
                .one()
            )
            for key, value in remark_data.model_dump(exclude={"muid", "prefix"}).items():
                setattr(remark, key, value)
            sess.commit()
            return Remark.model_validate(remark)
    except NoResultFound:
        with get_sess() as sess:
            dump = remark_data.model_dump(exclude={"muid", "prefix"})
            dump["github_id"] = github_id
            sess.add(mRemark(**dump))
            sess.commit()
            return Remark.model_validate(
                sess.query(mRemark)
                .filter(mRemark.source_file_path == str(remark_data.source_file_path))
                .filter(mRemark.segment_id == str(remark_data.segment_id))
                .filter(mRemark.github_id == github_id)
                .first()
            )
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Unique data conflict")


def delete_remark_by_source_file_path_and_segment_it(
    source_file_path: Path, segment_id: str, github_id: int
) -> None:
    try:
        with get_sess() as sess:
            remark = (
                sess.query(mRemark)
                .filter(mRemark.source_file_path == str(settings.WORK_DIR.joinpath(source_file_path)))
                .filter(mRemark.segment_id == segment_id)
                .filter(mRemark.github_id == github_id)
                .one()
            )
            sess.delete(remark)
            sess.commit()
    except NoResultFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Remark not found")
