from pathlib import Path
from threading import Lock
from time import monotonic

from app.core.config import settings
from app.db.database import get_sess
from app.db.models.notification import RemarkNotification
from app.db.models.user import User
from search.utils import find_root_path, get_prefix
from sqlalchemy import func


REMARK_PARTICIPANTS_CACHE_TTL_SECONDS = 300
_participant_cache: dict[str, tuple[float, set[str]]] = {}
_participant_cache_lock = Lock()


def _extract_author_and_type(file_name: str) -> tuple[str | None, str | None]:
    # e.g. 'mn1_translation-en-sujato.json' -> ('sujato', 'translation')）。
    stem = Path(file_name).stem
    if "_" not in stem:
        return None, None

    payload = stem.split("_", 1)[1]
    parts = payload.split("-")
    if len(parts) < 3:
        return None, None

    file_type = parts[0]
    author = parts[-1]
    return author, file_type


def _collect_participant_usernames(prefix: str) -> set[str]:
    now = monotonic()
    with _participant_cache_lock:
        cached = _participant_cache.get(prefix)
        if cached and cached[0] > now:
            return set(cached[1])

    usernames: set[str] = set()
    for file_path in settings.WORK_DIR.rglob(f"{prefix}_*.json"):
        author, file_type = _extract_author_and_type(file_path.name)
        if not author or not file_type or file_type == "root":
            continue
        usernames.add(author.lower())

    expires_at = now + REMARK_PARTICIPANTS_CACHE_TTL_SECONDS
    with _participant_cache_lock:
        _participant_cache[prefix] = (expires_at, set(usernames))

    return usernames


def create_remark_notifications(
    *,
    source_file_path: str | Path,
    segment_id: str,
    remark_value: str | None,
    action: str,
    actor_username: str,
    actor_github_id: int,
) -> int:
    source_path = Path(source_file_path)
    root_path = find_root_path(source_path)
    if root_path is None:
        return 0

    uid = get_prefix(root_path)
    participant_usernames = _collect_participant_usernames(uid)
    actor_username_normalized = actor_username.lower()
    participant_usernames.discard(actor_username_normalized)

    if not participant_usernames:
        return 0

    with get_sess() as sess:
        recipients = (
            sess.query(User)
            .filter(func.lower(User.username).in_(participant_usernames))
            .filter(User.github_id != actor_github_id)
            .all()
        )

        notifications = [
            RemarkNotification(
                recipient_github_id=user.github_id,
                actor_username=actor_username,
                action=action,
                uid=uid,
                segment_id=segment_id,
                source_file_path=str(source_path),
                remark_value=remark_value,
            )
            for user in recipients
        ]

        if not notifications:
            return 0

        sess.add_all(notifications)
        sess.commit()
        return len(notifications)
