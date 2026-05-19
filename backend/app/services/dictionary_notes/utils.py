from app.db.database import get_sess
from app.db.models.dictionary_note import DictionaryNote as mNote
from app.db.schemas.dictionary_note import DictionaryNoteResponse
from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert


def get_note(word: str, github_id: int) -> DictionaryNoteResponse | None:
    with get_sess() as sess:
        note = sess.query(mNote).filter(
            mNote.word == word, mNote.github_id == github_id
        ).first()
        return DictionaryNoteResponse.model_validate(note) if note else None


def upsert_note(word: str, note_value: str, github_id: int) -> DictionaryNoteResponse:
    with get_sess() as sess:
        stmt = (
            insert(mNote)
            .values(word=word, note_value=note_value, github_id=github_id)
            .on_conflict_do_update(
                index_elements=[mNote.word, mNote.github_id],
                set_={"note_value": note_value, "updated_at": func.now()},
            )
            .returning(mNote)
        )
        note = sess.execute(stmt).scalar_one()
        sess.commit()
        return DictionaryNoteResponse.model_validate(note)


def delete_note(word: str, github_id: int) -> None:
    with get_sess() as sess:
        note = sess.query(mNote).filter(
            mNote.word == word, mNote.github_id == github_id
        ).first()
        if not note:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
        sess.delete(note)
        sess.commit()
