import json
from contextlib import suppress

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict

from app.core.config import settings
from app.services.auth import utils as auth_utils
from app.services.users.permissions import (
    is_admin_or_superuser,
    is_user_active,
)
from app.services.users.utils import get_user
from app.tasks import commit as commit_task

router = APIRouter(prefix="/publications")

V2_FILE = settings.WORK_DIR / "_publication-v2.json"


def _read_v2() -> list[dict]:
    with open(V2_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_v2(data: list[dict]):
    with open(V2_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


class PublicationMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    publication_number: str
    root_lang_iso: str = ""
    root_lang_name: str = ""
    translation_lang_iso: str = ""
    translation_lang_name: str = ""
    source_url: str = ""
    creator_uid: str | list[str] = ""
    creator_name: str | list[str] = ""
    creator_github_handle: str | list[str] = ""
    text_uid: str = ""
    translation_title: str = ""
    translation_subtitle: str = ""
    root_title: str = ""
    creation_process: str = ""
    text_description: str = ""
    is_published: bool = False
    publication_status: str = ""
    license_type: str = "Creative Commons Zero"
    license_abbreviation: str = "CC0"
    license_url: str = "https://creativecommons.org/publicdomain/zero/1.0/"
    license_statement: str = ""
    first_published: str = ""
    editions_url: str = ""


def _build_publication_entry(body: PublicationMetadata) -> dict:
    return body.model_dump()


@router.get("/next-number/")
async def get_next_publication_number(
    user=Depends(auth_utils.get_current_user),
):
    v2_data = _read_v2()
    max_num = 0
    for entry in v2_data:
        pn = entry.get("publication_number", "")
        if not pn.startswith("scpub"):
            continue

        with suppress(ValueError):
            max_num = max(max_num, int(pn[5:]))

    return {"next_number": f"scpub{max_num + 1}"}


@router.post("/publish/", status_code=status.HTTP_202_ACCEPTED)
async def publish_to_github(
    user=Depends(auth_utils.get_current_user),
    _admin=Depends(is_admin_or_superuser),
    _active=Depends(is_user_active),
):
    user_data = get_user(int(user.github_id))
    result = commit_task.delay(
        user_data.model_dump(),
        ["_publication-v2.json"],
        "Update publication metadata",
        add=True,
    )
    return {"task_id": result.id, "detail": "Publish task triggered"}


@router.get("/")
async def list_publications(
    user=Depends(auth_utils.get_current_user),
):
    return _read_v2()


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_publication(
    body: PublicationMetadata,
    user=Depends(auth_utils.get_current_user),
    _admin=Depends(is_admin_or_superuser),
    _active=Depends(is_user_active),
):
    pub_num = body.publication_number
    if not pub_num:
        raise HTTPException(
            status_code=400,
            detail="publication_number is required",
        )

    v2_data = _read_v2()

    if any(e["publication_number"] == pub_num for e in v2_data):
        raise HTTPException(
            status_code=409,
            detail=f"{pub_num} already exists in _publication-v2.json",
        )

    v2_entry = _build_publication_entry(body)

    v2_data.append(v2_entry)

    _write_v2(v2_data)

    return v2_entry


@router.get("/{publication_number}", response_model=PublicationMetadata)
async def get_publication(
    publication_number: str,
    user=Depends(auth_utils.get_current_user),
):
    v2_entry = next(
        (
            entry
            for entry in _read_v2()
            if entry["publication_number"] == publication_number
        ),
        None,
    )
    if v2_entry is None:
        raise HTTPException(status_code=404, detail="Publication not found")

    return v2_entry


@router.put("/{publication_number}")
async def update_publication(
    publication_number: str,
    body: PublicationMetadata,
    user=Depends(auth_utils.get_current_user),
    _admin=Depends(is_admin_or_superuser),
    _active=Depends(is_user_active),
):
    v2_data = _read_v2()

    v2_idx = next(
        (
            index
            for index, entry in enumerate(v2_data)
            if entry["publication_number"] == publication_number
        ),
        None,
    )
    if v2_idx is None:
        raise HTTPException(
            status_code=404,
            detail=f"{publication_number} not found in _publication-v2.json",
        )

    if body.publication_number != publication_number and any(
        entry["publication_number"] == body.publication_number
        for entry in v2_data
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                f"{body.publication_number} already exists in "
                "_publication-v2.json"
            ),
        )

    v2_data[v2_idx] = _build_publication_entry(body)

    _write_v2(v2_data)

    return v2_data[v2_idx]


@router.delete("/{publication_number}", status_code=status.HTTP_200_OK)
async def delete_publication(
    publication_number: str,
    user=Depends(auth_utils.get_current_user),
    _admin=Depends(is_admin_or_superuser),
    _active=Depends(is_user_active),
):
    v2_data = _read_v2()

    v2_len_before = len(v2_data)
    v2_data = [
        entry
        for entry in v2_data
        if entry["publication_number"] != publication_number
    ]

    if len(v2_data) == v2_len_before:
        raise HTTPException(
            status_code=404,
            detail=f"{publication_number} not found",
        )

    _write_v2(v2_data)

    return {"detail": f"{publication_number} deleted"}
