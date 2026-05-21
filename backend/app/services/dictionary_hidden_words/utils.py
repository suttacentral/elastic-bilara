from app.db.database import get_sess
from app.db.models.dictionary_hidden_word import DictionaryHiddenWord
from sqlalchemy.dialects.postgresql import insert


def hide_word(word: str, github_id: int) -> None:
    """Hide a word for a specific user. Idempotent — no-op if already hidden."""
    with get_sess() as sess:
        stmt = (
            insert(DictionaryHiddenWord)
            .values(word=word, github_id=github_id)
            .on_conflict_do_nothing(
                index_elements=[DictionaryHiddenWord.word, DictionaryHiddenWord.github_id],
            )
        )
        sess.execute(stmt)
        sess.commit()
