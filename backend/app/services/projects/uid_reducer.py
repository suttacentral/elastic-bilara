import re
from pathlib import Path

from app.core.config import settings
from app.db.schemas.user import UserBase
from app.services.directories.utils import get_matches
from app.services.projects.utils import write_json_data
from app.services.users.utils import get_user
from search.search import Search
from search.utils import get_json_data
from app.tasks import commit


class UIDReducer:
    def __init__(self, user: UserBase, path: Path, uids: list[str], exact: bool = False):
        self.user = user
        self.path = path
        self.uids = uids
        self.exact = exact
        self.character_pattern = r"[a-zA-Z]+"
        self.starts_with_digit_pattern = r"^\d+"
        self.has_digits_around_dot_pattern = r"(\d+(\.\d+)+)$"
        self.related_paths: set[Path] = get_matches(self.path, True)

    def decrement(self) -> tuple[str, str]:
        data = self.decrement_dry()
        for path in data:
            write_json_data(Path(path), data[path])
        self.related_paths.remove(settings.WORK_DIR / self.path)
        main_task_id = self._reduce_commit(
            [str(settings.WORK_DIR / self.path)], f"{self.user.username} changed {str(self.path).replace(str(settings.WORK_DIR), '')}"
        )
        related_task_id = self._reduce_commit(
            [str(path) for path in self.related_paths], f"{self.user.username} changed files related to {str(self.path).replace(str(settings.WORK_DIR), '')}"
        )
        es = Search()
        for path in self.related_paths:
            es.remove_segments(path)
        return main_task_id, related_task_id

    def decrement_dry(self) -> dict[Path, dict[str, str]]:
        data = {match: get_json_data(match) for match in self.related_paths}
        reduced_data = {match: None for match in self.related_paths}
        for uid in self.uids:
            for path in data:
                reduced_data[path] = self._reduce(uid, data[path])
                data[path] = reduced_data[path]
        return reduced_data

    def _reduce_commit(self, changed_paths: list[str], message: str) -> str:
        result = commit.delay(get_user(int(self.user.github_id)).model_dump(), changed_paths, message)
        return result.id

    def _reduce(self, segment_id: str, data: dict[str, str]) -> dict[str, str]:
        data_copy = data.copy()
        if self.exact:
            data_copy.pop(segment_id, None)
            return data_copy
        start_index, end_index, matched_pattern = self._get_pattern_boundaries(segment_id, data_copy)

        if not matched_pattern:
            data_copy.pop(segment_id, None)
            return data_copy

        uids = list(data_copy.keys())

        if matched_pattern == self.starts_with_digit_pattern and re.search(
            self.character_pattern, segment_id.split(":")[-1]
        ):
            if not self._is_digit_pattern_consistent(uids, start_index, end_index):
                del data_copy[segment_id]
                return data_copy

            for i in range(start_index, end_index):
                current_uid_part = uids[i].split(":")[-1]
                next_uid_part = uids[i + 1].split(":")[-1]
                uid = uids[i + 1]
                new_uid = uid.replace(
                    re.match(matched_pattern, next_uid_part).group(),
                    re.match(matched_pattern, current_uid_part).group(),
                )
                data_copy[new_uid] = data_copy.pop(uid)
            del data_copy[segment_id]
            return data_copy

        if matched_pattern == self.starts_with_digit_pattern:
            if not self._is_digit_pattern_consistent(uids, start_index, end_index):
                data_copy.pop(segment_id, None)
                return data_copy

        for i in range(start_index, end_index):
            data_copy[uids[i]] = data_copy[uids[i + 1]]
        del data_copy[uids[end_index]]

        return data_copy

    def _get_pattern_boundaries(
        self, segment_id: str, data: dict[str, str]
    ) -> tuple[int | None, int | None, str | None]:
        if all(not part.isdigit() for part in segment_id.split(":")[1]):
            return None, None, None

        uids = list(key.split(":")[-1] for key in data.keys())
        try:
            start_index = list(data.keys()).index(segment_id)
        except ValueError:
            return None, None, None
        end_index = start_index
        matched_pattern = None

        uid = uids[start_index]

        if re.search(self.character_pattern, uid) and re.search(self.starts_with_digit_pattern, uid):
            matched_pattern = self.starts_with_digit_pattern
        if not matched_pattern and re.search(self.has_digits_around_dot_pattern, uid):
            matched_pattern = self.has_digits_around_dot_pattern
        if not matched_pattern and re.search(self.starts_with_digit_pattern, uid):
            matched_pattern = self.starts_with_digit_pattern
        if matched_pattern:
            if matched_pattern == self.starts_with_digit_pattern:
                for idx, uid in enumerate(uids[start_index:], start=start_index):
                    if not re.search(matched_pattern, uid):
                        break
                    end_index = idx
            else:
                whole_uids = list(data.keys())
                main_part = segment_id.split(":")[0]
                prefix = segment_id.split(":")[-1].rpartition(".")[0]
                for idx, uid in enumerate(uids[start_index:], start=start_index):
                    if not whole_uids[idx].startswith(main_part):
                        break
                    if not uid.startswith(prefix):
                        break
                    end_index = idx
            return start_index, end_index, matched_pattern
        return start_index, end_index, matched_pattern

    def _is_digit_pattern_consistent(self, uids: list[str], start_index: int, end_index: int) -> bool:
        for i in range(start_index, end_index):
            current_uid_part: str = uids[i].split(":")[-1]
            next_uid_part: str = uids[i + 1].split(":")[-1]
            if (
                int(re.match(self.starts_with_digit_pattern, next_uid_part).group())
                - int(re.match(self.starts_with_digit_pattern, current_uid_part).group())
                != 1
            ):
                return False
        return True
