import shutil
from pathlib import Path

from app.core.config import settings
from app.core.text_types import TextType
from app.db.schemas.user import UserBase
from app.services.directories.utils import get_matches
from app.services.users.utils import get_user
from search.search import Search
from search.utils import is_root
from app.tasks import commit


class Remover:
    def __init__(self, user: UserBase, path: Path):
        self.user = user
        self.path = path
        self.is_dir = path.is_dir()
        self.is_root = (
            any(part == TextType.ROOT.value for part in self.path.parts) if self.is_dir else is_root(self.path)
        )

    def delete(self) -> tuple[str, str]:
        return self._delete()

    def delete_dry(self) -> list[str]:
        return [str(match).replace(str(settings.WORK_DIR), "") for match in self._get_matches()]

    def _delete(self) -> tuple[str, str | None]:
        to_be_removed: set[Path] = self._get_matches()
        related_to_main_path = {str(path) for path in self._get_paths({self.path})}
        matches = to_be_removed.copy()
        matches.remove(self.path)
        related_matches = {str(match) for match in self._get_paths(matches)}
        self._delete_elements(to_be_removed)
        main_task_id = self._remove_commit(
            list(related_to_main_path), self._create_message("deleted")
        )
        related_task_id = None
        if related_matches:
            related_task_id = self._remove_commit(
                list(related_matches), self._create_message("deleted files related to")
            )

        to_be_removed_from_elastic = {Path(path) for path in related_to_main_path.union(related_matches)}
        self._remove_from_elastic(to_be_removed_from_elastic)
        return main_task_id, related_task_id

    def _delete_elements(self, matches):
        for match in matches:
            shutil.rmtree(match) if self.is_dir else match.unlink()

    def _get_matches(self) -> set[Path]:
        matches = get_matches(self.path, True)
        path_str = str(self.path)

        if TextType.TRANSLATION.value in path_str or TextType.COMMENT.value in path_str:
            text_values = set()

            if TextType.TRANSLATION.value in path_str:
                text_values.add(TextType.TRANSLATION.value)
                text_values.add(TextType.COMMENT.value)
                path_str = path_str.replace("translation", "comment")

            if TextType.COMMENT.value in path_str:
                text_values.add(TextType.COMMENT.value)

            matches = {
                match
                for match in matches
                if any(part in str(match) for part in text_values)
                and (str(match).startswith(str(self.path)) or str(match).startswith(path_str))
            }

        return matches

    def _create_message(self, action):
        file_or_directory = "directory" if self.is_dir else "file"
        return f"{self.user.username} {action} {file_or_directory} {str(self.path).replace(str(settings.WORK_DIR), '')}"

    def _remove_commit(self, removed_paths: list[str], message: str) -> str:
        result = commit.delay(
            get_user(int(self.user.github_id)).model_dump(),
            removed_paths,
            message,
            False,
        )
        return result.id

    def _get_paths(self, matches: set[Path]) -> set[Path]:
        if self.is_dir:
            paths = set()
            for match in matches:
                paths.update(path for path in match.rglob("*") if path.is_file())
            return paths
        return matches

    def _remove_from_elastic(self, removed_paths: set[Path]) -> None:
        es = Search()
        for path in removed_paths:
            es.remove_segments(path)
