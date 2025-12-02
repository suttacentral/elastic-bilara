import subprocess
import re
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic_core import ValidationError

from app.db.database import get_sess
from app.core.config import settings
from app.api.api_v1.endpoints.projects import get_paths_for_project
from app.services.users import permissions
from app.services.auth import utils as auth_utils
from app.services.notifications.models import GitCommitInfoOut, NotificationDoneOut
from app.db.models.notification import Notification


router = APIRouter(prefix="/notifications")

FILTER_AUTHOR = 'sujato'
DEFAULT_AUTHOR = 'sujato'
DEFAULT_LANG = 'en'
GIT_LOG_DAYS = 360


@router.get("/git", response_model=GitCommitInfoOut)
def get_unread_git_updates(
  user: str = Depends(auth_utils.get_current_user)):
    recent_commits = []
    working_directory = settings.WORK_DIR

    git_base_cmd = ["git", "-c", f"safe.directory={working_directory}"]
    git_log_cmd = git_base_cmd + [
        "log",
        "--oneline",
        "--abbrev-commit",
        "--pretty=format:%h %s (%cr)",
        f"--since={GIT_LOG_DAYS} days ago",
        "--no-merges",
        "--name-only"
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
        return GitCommitInfoOut(git_recent_commits=[])

    if git_log_cmd_process.returncode == 0:
        all_done_commit_ids = get_all_commit_ids_in_db(user.github_id)
        git_commits = git_log_output.decode('utf-8').split("\n")
        for git_commit in git_commits:
            if not git_commit.strip():
                continue

            commit_hash = git_commit.split(" ")[0]
            git_show_name_only_cmd = git_base_cmd + ["show", "--name-only", commit_hash]
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

            if FILTER_AUTHOR not in author:
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

            if json_files:
                json_files.pop(0)

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

                change_detail = get_change_detail(file_name, parsed_git_show_details)

                formatted_json_files.append(
                    {
                        'file_name': file_name,
                        'file_type': file_type,
                        'uid': uid,
                        'author': author_id or DEFAULT_AUTHOR,
                        'lang': lang or DEFAULT_LANG,
                        'sc_url': build_suttacentral_url(
                            uid,
                            lang or DEFAULT_LANG,
                            author_id or DEFAULT_AUTHOR
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
                'effected_files': formatted_json_files
            }
            if commit not in all_done_commit_ids:
                recent_commits.append(git_detail)
    else:
        print(f"Error: {error.decode('utf-8')}")
    return GitCommitInfoOut(git_recent_commits=recent_commits)


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
            .filter(Notification.commit_id == commit_id, Notification.github_id == user.github_id)
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
                detail=f"Error occurred while Notification {commit_id} adding to the database",
            ) from e

    return NotificationDoneOut(success=True)