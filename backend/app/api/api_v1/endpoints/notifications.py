import asyncio
import json
import subprocess
import re
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic_core import ValidationError

from app.db.database import get_sess
from app.core.config import settings
from app.services.auth import utils as auth_utils
from app.services.notifications.models import (
    GitCommitInfoOut,
    NotificationDonePayload,
    NotificationDoneOut,
    NotificationFeedOut,
)
from app.db.models.notification import Notification, RemarkNotification
from app.db.models.user_preference import UserPreference as UserPreferenceModel
from app.db.schemas.user_preference import UserPreference, UserPreferenceUpdate


router = APIRouter(prefix="/notifications")

# '30 seconds balances server load with real-time updates and prevents Nginx 60s timeout'
NOTIFICATION_STREAM_POLL_SECONDS = 30
NOTIFICATION_STREAM_MAX_RUNTIME_SECONDS = 3600


def get_notification_authors_or_default(notification_authors):
    return notification_authors or ["sujato"]


def _get_selected_authors_and_days(user: str) -> tuple[list[str], int]:
    with get_sess() as sess:
        preference = (
            sess.query(UserPreferenceModel)
            .filter(UserPreferenceModel.github_id == user.github_id)
            .first()
        )

        if preference:
            selected_authors = get_notification_authors_or_default(
                preference.notification_authors
            )
            selected_days = preference.notification_days or 360
        else:
            selected_authors = ["sujato"]
            selected_days = 360

    return selected_authors, selected_days


def _count_unread_git_updates(user: str) -> int:
    selected_authors, selected_days = _get_selected_authors_and_days(user)
    done_commit_ids = set(get_all_commit_ids_in_db(user.github_id))

    working_directory = settings.WORK_DIR
    git_base_cmd = ["git", "-c", f"safe.directory={working_directory}"]
    git_log_cmd = git_base_cmd + [
        "log",
        "--pretty=format:%h|%an <%ae>",
        f"--since={selected_days} days ago",
        "--no-merges",
    ]

    result = subprocess.run(
        git_log_cmd,
        cwd=working_directory,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if result.returncode != 0:
        return 0

    unread_count = 0
    for raw_line in result.stdout.split("\n"):
        if not raw_line.strip() or "|" not in raw_line:
            continue

        commit_id, author = raw_line.split("|", 1)
        if commit_id in done_commit_ids:
            continue

        if any(selected_author in author for selected_author in selected_authors):
            unread_count += 1

    return unread_count


def _count_unread_remark_notifications(github_id: int) -> int:
    with get_sess() as sess:
        return (
            sess.query(RemarkNotification)
            .filter(RemarkNotification.recipient_github_id == github_id)
            .filter(RemarkNotification.is_done.is_(False))
            .count()
        )


def get_unread_notification_count(user: str) -> int:
    return _count_unread_git_updates(user) + _count_unread_remark_notifications(
        int(user.github_id)
    )


@router.get("/stream")
async def stream_notification_count(
    request: Request,
    user: str = Depends(auth_utils.get_current_user),
):
    async def event_generator():
        previous_count = None
        loop = asyncio.get_running_loop()
        stream_deadline = (
            loop.time() + NOTIFICATION_STREAM_MAX_RUNTIME_SECONDS
        )

        while loop.time() < stream_deadline:
            if await request.is_disconnected():
                break

            try:
                current_count = get_unread_notification_count(user)
                if previous_count is None or current_count != previous_count:
                    payload = json.dumps({"unread_count": current_count})
                    yield f"event: unread_count\ndata: {payload}\n\n"
                    previous_count = current_count
                else:
                    yield ": keepalive\n\n"
            except Exception as error:
                payload = json.dumps({"error": str(error)})
                yield f"event: stream_error\ndata: {payload}\n\n"

            await asyncio.sleep(NOTIFICATION_STREAM_POLL_SECONDS)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/git", response_model=GitCommitInfoOut)
def get_unread_git_updates(
    user: str = Depends(auth_utils.get_current_user),
):
    return GitCommitInfoOut(
        git_recent_commits=get_unread_git_update_items(user)
    )


def get_unread_git_update_items(user: str):
    return get_git_update_items(user, include_done=False)


def get_git_update_items(user: str, include_done: bool = False):
    recent_commits = []
    working_directory = settings.WORK_DIR

    # Get user preferences from database
    with get_sess() as sess:
        preference = (
            sess.query(UserPreferenceModel)
            .filter(UserPreferenceModel.github_id == user.github_id)
            .first()
        )

        if preference:
            selected_authors = get_notification_authors_or_default(
                preference.notification_authors
            )
            selected_days = preference.notification_days or 360
        else:
            # Use default values
            selected_authors = ["sujato"]
            selected_days = 360

    git_base_cmd = ["git", "-c", f"safe.directory={working_directory}"]
    git_log_cmd = git_base_cmd + [
        "log",
        "--oneline",
        "--abbrev-commit",
        "--pretty=format:%h %s (%cr)",
        f"--since={selected_days} days ago",
        "--no-merges"
    ]

    try:
        git_log_cmd_process = subprocess.Popen(
            git_log_cmd,
            cwd=working_directory,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        git_log_output, error = git_log_cmd_process.communicate()
    except subprocess.CalledProcessError as e:
        print(f"Git error: {e.stderr}")
        return []

    if git_log_cmd_process.returncode == 0:
        all_done_commit_ids = set(get_all_commit_ids_in_db(user.github_id))
        git_commits = git_log_output.decode('utf-8').split("\n")
        for git_commit in git_commits:
            if not git_commit.strip():
                continue

            commit_hash = git_commit.split(" ")[0]
            git_show_name_only_cmd = git_base_cmd + [
                "show", "--name-only", commit_hash
            ]
            git_show_cmd_process = subprocess.Popen(
                git_show_name_only_cmd,
                cwd=working_directory,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            git_show_output, error = git_show_cmd_process.communicate()

            git_show_stdout = git_show_output.decode('utf-8')

            if git_show_stdout.strip() == "":
                continue

            commit_match = re.search(r'commit (\w+)', git_show_stdout)
            author_match = re.search(r'Author: (.+)', git_show_stdout)
            date_match = re.search(r'Date:\s+(.+)', git_show_stdout)

            commit = commit_match[1] if commit_match else None
            author = author_match[1] if author_match else None
            date = date_match[1] if date_match else None

            # Skip if this line was a file path (not a real commit) — author will be None
            if not author or not commit:
                continue

            # Check if author is in selected authors list
            author_match_found = any(
                selected_author in author
                for selected_author in selected_authors
            )
            if not author_match_found:
                continue

            git_show_diff_cmd = git_base_cmd + ["show", commit_hash]
            git_show_cmd_process = subprocess.Popen(
                git_show_diff_cmd,
                cwd=working_directory,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            git_show_diff_output, error = git_show_cmd_process.communicate()
            git_show_details = git_show_diff_output.decode("utf-8")
            parsed_git_show_details = parse_git_show_details(git_show_details)

            json_files = re.findall(r'[\w/.-]+\.json', git_show_stdout)

            formatted_json_files = []
            for json_file in json_files:
                file_name = json_file.split("/")[-1]
                file_type = ''
                uid = file_name.split("_")[0]
                muids = file_name.split("_")[1].split(".")[0].split('-')
                author_id = ''
                lang = ''
                if len(muids) == 3:
                    author_id = muids[2]
                    lang = muids[1]
                    file_type = muids[0]

                if not file_type:
                    file_type = file_name.split('_')[1].split('.')[0]

                change_detail = get_change_detail(
                    file_name, parsed_git_show_details
                )

                formatted_json_files.append(
                    {
                        'file_name': file_name,
                        'file_type': file_type,
                        'uid': uid,
                        'author': author_id,
                        'lang': lang,
                        'sc_url': build_suttacentral_url(
                            uid,
                            lang,
                            author_id
                        ),
                        'change_detail': format_diff_as_html(
                            change_detail,
                            file_name,
                        ),
                    }
                )

            parts = git_commit.split(" ", 3)
            commit = parts[0] if parts else ""

            if len(parts) >= 3:
                message = " ".join(parts[1:3])
            elif len(parts) == 2:
                message = parts[1]
            else:
                message = ""

            git_detail = {
                'info': git_commit,
                'commit': commit,
                'message': message,
                'author': author,
                'date': date,
                'effected_files': formatted_json_files,
                'is_done': commit in all_done_commit_ids,
            }
            if include_done or commit not in all_done_commit_ids:
                recent_commits.append(git_detail)
    else:
        print(f"Error: {error.decode('utf-8')}")
    return recent_commits


def _build_remark_notification_items(
    github_id: int,
    include_done: bool = False,
) -> list[dict]:
    with get_sess() as sess:
        query = (
            sess.query(RemarkNotification)
            .filter(RemarkNotification.recipient_github_id == github_id)
            .order_by(RemarkNotification.created_at.desc())
        )

        if not include_done:
            query = query.filter(RemarkNotification.is_done.is_(False))

        notifications = query.all()

        return [
            {
                "notification_type": "remark",
                "notification_ref": str(item.id),
                "author": item.actor_username,
                "date": item.created_at.isoformat(),
                "uid": item.uid,
                "segment_id": item.segment_id,
                "action": item.action,
                "source_file_path": item.source_file_path,
                "remark_value": item.remark_value,
                "effected_files": [],
                "is_done": item.is_done,
            }
            for item in notifications
        ]


def _commit_date_sort_key(item: dict) -> datetime:
    raw_date = item.get("date")
    if not raw_date:
        return datetime.min

    parsers = [
        "%a %b %d %H:%M:%S %Y %z",
        "%a %b %d %H:%M:%S %Y",
    ]
    for parser in parsers:
        try:
            parsed = datetime.strptime(raw_date, parser)
            if parsed.tzinfo is not None:
                return parsed.astimezone().replace(tzinfo=None)
            return parsed
        except ValueError:
            continue
    return datetime.min


def _feed_sort_key(item: dict) -> datetime:
    notification_type = item.get("notification_type")
    if notification_type == "remark":
        created_at = item.get("date")
        if created_at:
            try:
                parsed = datetime.fromisoformat(created_at)
                if parsed.tzinfo is not None:
                    return parsed.astimezone().replace(tzinfo=None)
                return parsed
            except ValueError:
                return datetime.min
        return datetime.min

    return _commit_date_sort_key(item)


@router.get("/feed", response_model=NotificationFeedOut)
def get_notifications_feed(
    include_read: bool = False,
    user: str = Depends(auth_utils.get_current_user),
):
    commit_items = []

    if include_read:
        commit_source = get_git_update_items(user, include_done=True)
    else:
        commit_source = get_unread_git_update_items(user)

    for item in commit_source:
        commit_items.append(
            {
                **item,
                "notification_type": "commit",
                "notification_ref": item.get("commit", ""),
            }
        )

    remark_items = _build_remark_notification_items(
        int(user.github_id),
        include_done=include_read,
    )
    notifications = sorted(commit_items + remark_items, key=_feed_sort_key, reverse=True)
    return NotificationFeedOut(notifications=notifications)


def get_all_commit_ids_in_db(github_id):
    with get_sess() as sess:
        commit_ids = (
            sess.query(Notification.commit_id)
            .filter(Notification.github_id == github_id)
            .all()
        )
        return [commit_id[0] for commit_id in commit_ids]


def build_suttacentral_url(uid: str, lang: str, author_id: str) -> str:
    return f'https://suttacentral.net/{uid}/{lang}/{author_id}'


def parse_git_show_details(git_show_details_text):
    file_change_detail = []
    diff_git_pattern = re.compile(r"diff --git a/([^\s]+)")
    diff_content_pattern = re.compile(r'@@.*?@@(.*?)diff --git', re.DOTALL)
    diff_git_matches = diff_git_pattern.findall(git_show_details_text)
    change_blocks = diff_content_pattern.findall(
        f'{git_show_details_text}diff --git'
    )

    file_change_detail.extend(
        {
            "file_name": match.split("/")[-1],
            "change_detail": change_blocks[i].strip(),
        }
        for i, match in enumerate(diff_git_matches)
    )
    return file_change_detail


def get_change_detail(file_name, parsed_git_show_details):
    return next(
        (
            detail["change_detail"]
            for detail in parsed_git_show_details
            if detail["file_name"] == file_name
        ),
        None,
    )


def format_diff_as_html(change_detail, file_name):
    if not change_detail:
        return None

    lines = change_detail.strip().split('\n')
    processed_lines = []

    for line in lines:
        if "_html" not in file_name and line.startswith("-"):
            processed_lines.append(f'<p class="delete">{line}</p>')
        elif "_html" not in file_name and line.startswith("+"):
            processed_lines.append(f'<p class="add">{line}</p>')
        elif "_html" in file_name:
            processed_lines.append(f'{line}\n\r')
        else:
            processed_lines.append(f'<p>{line}</p>')

    return ''.join(processed_lines)


@router.get("/done/{commit_id}", response_model=NotificationDoneOut)
async def mark_notification_as_done(
    commit_id: str,
    user: str = Depends(auth_utils.get_current_user),
):
    with get_sess() as sess:
        if (
            sess.query(Notification)
            .filter(
                Notification.commit_id == commit_id,
                Notification.github_id == user.github_id
            )
            .first()
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Notification {commit_id} already marked as done",
            )

        notification = Notification(
            github_id=user.github_id,
            commit_id=commit_id,
        )
        print(notification)
        try:
            sess.add(notification)
            sess.commit()
        except ValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Error occurred while Notification {commit_id} "
                    "adding to the database"
                ),
            ) from e

    return NotificationDoneOut(success=True)


@router.post("/done", response_model=NotificationDoneOut)
async def mark_notification_as_done_by_type(
    payload: NotificationDonePayload,
    user: str = Depends(auth_utils.get_current_user),
):
    if payload.notification_type == "commit":
        return await mark_notification_as_done(payload.notification_ref, user)

    if payload.notification_type == "remark":
        try:
            notification_id = int(payload.notification_ref)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid remark notification id",
            ) from e

        with get_sess() as sess:
            notification = (
                sess.query(RemarkNotification)
                .filter(RemarkNotification.id == notification_id)
                .filter(RemarkNotification.recipient_github_id == user.github_id)
                .first()
            )
            if not notification:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Remark notification {notification_id} not found",
                )
            notification.is_done = True
            sess.commit()

        return NotificationDoneOut(success=True)

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unsupported notification type: {payload.notification_type}",
    )


@router.get("/authors")
def get_all_authors(
    user: str = Depends(auth_utils.get_current_user)
):
    """Get all unique authors from git log."""
    working_directory = settings.WORK_DIR
    git_base_cmd = ["git", "-c", f"safe.directory={working_directory}"]
    git_authors_cmd = git_base_cmd + [
        "log",
        "--all",
        "--format=%an"
    ]

    try:
        result = subprocess.run(
            git_authors_cmd,
            cwd=working_directory,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if result.returncode == 0:
            authors = result.stdout.strip().split("\n")
            # Remove duplicates and sort
            unique_authors = sorted(
                set(author.strip() for author in authors if author.strip())
            )
            return {"authors": unique_authors}
        else:
            print(f"Git error: {result.stderr}")
            return {"authors": []}
    except Exception as e:
        print(f"Error getting authors: {e}")
        return {"authors": []}


@router.get("/preferences", response_model=UserPreference)
def get_user_preferences(
    user: str = Depends(auth_utils.get_current_user)
):
    """Get user notification preferences. Returns default if not set."""
    with get_sess() as sess:
        preference = (
            sess.query(UserPreferenceModel)
            .filter(UserPreferenceModel.github_id == user.github_id)
            .first()
        )

        if preference:
            return UserPreference(
                id=preference.id,
                github_id=preference.github_id,
                notification_authors=get_notification_authors_or_default(
                    preference.notification_authors
                ),
                notification_days=preference.notification_days or 360
            )
        else:
            # Return default values without creating DB record
            return UserPreference(
                id=0,  # Dummy id for response
                github_id=user.github_id,
                notification_authors=["sujato"],
                notification_days=360
            )


@router.put("/preferences", response_model=UserPreference)
def update_user_preferences(
    preferences: UserPreferenceUpdate,
    user: str = Depends(auth_utils.get_current_user)
):
    """Create or update user notification preferences."""
    with get_sess() as sess:
        existing = (
            sess.query(UserPreferenceModel)
            .filter(UserPreferenceModel.github_id == user.github_id)
            .first()
        )

        if existing:
            # Update existing preference
            existing.notification_authors = preferences.notification_authors
            existing.notification_days = preferences.notification_days
            sess.commit()
            sess.refresh(existing)

            return UserPreference(
                id=existing.id,
                github_id=existing.github_id,
                notification_authors=existing.notification_authors,
                notification_days=existing.notification_days
            )
        else:
            # Create new preference
            new_preference = UserPreferenceModel(
                github_id=user.github_id,
                notification_authors=preferences.notification_authors,
                notification_days=preferences.notification_days
            )
            sess.add(new_preference)
            sess.commit()
            sess.refresh(new_preference)

            return UserPreference(
                id=new_preference.id,
                github_id=new_preference.github_id,
                notification_authors=new_preference.notification_authors,
                notification_days=new_preference.notification_days
            )
