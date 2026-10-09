from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PublicationMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    publication_number: str = ""
    root_lang_iso: str = ""
    root_lang_name: str = ""
    # Historical root-text records use false for fields that do not apply.
    translation_lang_iso: str | Literal[False] = ""
    translation_lang_name: str | Literal[False] = ""
    source_url: str = ""
    creator_uid: str | list[str] | Literal[False] = ""
    creator_name: str | list[str] = ""
    creator_github_handle: str | list[str] | Literal[False] = ""
    text_uid: str = ""
    translation_title: str = ""
    translation_subtitle: str = ""
    root_title: str = ""
    creation_process: str = ""
    text_description: str = ""
    is_published: bool = False
    publication_status: str = ""
    license_type: str = "Creative Commons Zero"
    license_abbreviation: str | Literal[False] = "CC0"
    license_url: str = "https://creativecommons.org/publicdomain/zero/1.0/"
    license_statement: str = ""
    first_published: str = ""
    editions_url: str = ""
    pitaka: str = ""
    edition_number: str = "1"
    publication_date: str = ""
    publisher: str = "SuttaCentral"
    publication_type: str = "website"


class PublicationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    revision: str = Field(min_length=1)
    changes: PublicationMetadata


WRITER_FIELDS = frozenset({
    "creator_name", "translation_title", "translation_subtitle", "root_title",
    "creation_process", "text_description", "publication_status",
    "license_type", "license_abbreviation", "license_url", "license_statement",
    "first_published", "editions_url",
})
