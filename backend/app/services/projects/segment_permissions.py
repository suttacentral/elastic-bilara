"""Content restrictions for manual segment edits, independent of project ownership."""
import re
from collections.abc import Iterable


class ReadOnlyCommentError(ValueError):
    pass


def is_comment_read_only(muid: str, uid: str) -> bool:
    if not muid.startswith("comment-"):
        return False
    _, colon, suffix = uid.partition(":")
    return bool(colon) and any(re.fullmatch(r"0+", part) for part in suffix.split("."))


def validate_comment_edits(muid: str, uids: Iterable[str]) -> None:
    blocked = [uid for uid in uids if is_comment_read_only(muid, uid)]
    if blocked:
        raise ReadOnlyCommentError(
            "Comment is read-only for segments with a zero UID component: " + ", ".join(blocked)
        )
