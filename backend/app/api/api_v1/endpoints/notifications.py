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


@router.get("/git", response_model=GitCommitInfoOut)
def get_recently_git_updated_files(user: str = Depends(auth_utils.get_current_user)):
    recent_commits = []
    working_directory = settings.WORK_DIR

    git_log_command = [
        "git",
        "log",
        "--oneline",
        "--abbrev-commit",
        "--pretty=format:%h %s (%cr)",
        "--since=90 days ago",
        "--no-merges",
    ]

    subprocess.run([
        "git", "config", "--global", "--add", "safe.directory",
        working_directory
    ])
    git_log_command_process = subprocess.Popen(
        git_log_command,
        cwd=working_directory,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    git_log_output, error = git_log_command_process.communicate()


    if git_log_command_process.returncode == 0:
        git_commits = git_log_output.decode('utf-8').split("\n")
        for git_commit in git_commits:
            git_show_name_only_command = 'git show --name-only '
            git_show_name_only_command_process = subprocess.Popen(git_show_name_only_command + ' ' + git_commit.split(" ")[0], cwd=working_directory, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            git_show_name_only_output, error = git_show_name_only_command_process.communicate()

            git_show_name_only_details = git_show_name_only_output.decode('utf-8')
            commit_match = re.search(r'commit (\w+)', git_show_name_only_details)
            author_match = re.search(r'Author: (.+)', git_show_name_only_details)
            date_match = re.search(r'Date:\s+(.+)', git_show_name_only_details)

            commit = commit_match[1] if commit_match else None
            author = author_match[1] if author_match else None
            date = date_match[1] if date_match else None

            if 'sujato' not in author:
                continue

            git_show_command = "git show "
            git_show_command_process = subprocess.Popen(
                git_show_command + " " + git_commit.split(" ")[0],
                cwd=working_directory,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            git_show_details_output, error = git_show_command_process.communicate()
            git_show_details = git_show_details_output.decode("utf-8")
            parsed_git_show_details = parse_git_show_details(git_show_details)

            json_files = re.findall(r'[\w/.-]+\.json', git_show_name_only_details)

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

                formatted_json_files.append({
                    'file_name': file_name,
                    'file_type': file_type,
                    'uid': uid,
                    'author': author_id or 'sujato',
                    'lang': lang or 'en',
                    'sc_url': 'https://suttacentral.net/' + uid + '/' + (lang or 'en') + '/' + (author_id or 'sujato'),
                    'change_detail': format_change_detail(get_change_detail(file_name, parsed_git_show_details), file_name)
                })

            commit = git_commit.split(" ")[0]
            message = git_commit.split(" ")[1] + ' ' + git_commit.split(" ")[2]
            git_detail = {
                'info': git_commit,
                'commit': commit,
                'message': message,
                'author': author,
                'date': date,
                'effected_files': formatted_json_files
            }
            if not commit_id_exists_in_db(commit, user.github_id):
                recent_commits.append(git_detail)
    else:
        print(f"Error: {error.decode('utf-8')}")
    return GitCommitInfoOut(git_recent_commits=recent_commits)


def parse_git_show_details(git_show_details_text):
    file_change_detail = []
    diff_git_pattern = re.compile(r"diff --git a/([^\s]+)")
    change_block_pattern = re.compile(r'@@.*?@@(.*?)diff --git', re.DOTALL)
    diff_git_matches = diff_git_pattern.findall(git_show_details_text)
    change_blocks = change_block_pattern.findall(git_show_details_text + 'diff --git')

    for i, match in enumerate(diff_git_matches):
        file_change_detail.append(
            {
                "file_name": match.split("/")[-1],
                "change_detail": change_blocks[i].strip(),
            }
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


def format_change_detail(change_detail, file_name):
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
    print(user)
    print(commit_id)
    with get_sess() as sess:
        if (
            sess.query(Notification)
            .filter(Notification.commit_id == commit_id and Notification.github_id == user.github_id)
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
        try:
            sess.add(notification)
            sess.commit()
        except ValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error occurred while Notification {commit_id} adding to the database",
            ) from e

    return NotificationDoneOut(success=True)

def commit_id_exists_in_db(commit_id, github_id):
    with get_sess() as sess:
        return bool(
            (
                sess.query(Notification)
                .filter(
                    Notification.commit_id == commit_id
                    and Notification.github_id == github_id
                )
                .first()
            )
        )
