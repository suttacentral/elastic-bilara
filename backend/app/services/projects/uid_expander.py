from pathlib import Path

from app.core.config import settings
from app.db.schemas.user import UserBase
from app.services.directories.utils import get_matches
from app.services.projects.utils import write_json_data, write_json_data_for_split_or_merge
from app.services.users.utils import get_user
from search.search import Search
from search.utils import get_json_data
from app.tasks import commit


class UIDExpander:
    def __init__(self, user: UserBase, path: Path, uid: str):
        self.user = user
        self.path = path
        self.uid = uid
        self.has_digits_around_dot_pattern = r"(\d+(\.\d+)+)$"
        self.related_paths = get_matches(self.path, True)

    def expand(self):
        data = self.expand_dry()
        for path in data:
            data_after = data[path]["data_after"]
            write_json_data_for_split_or_merge(Path(path), data_after)
        self.related_paths.remove(settings.WORK_DIR / self.path)
        main_task_id = self._expand_commit(
            [str(settings.WORK_DIR / self.path)],
            f"{self.user.username} changed {str(self.path).replace(str(settings.WORK_DIR), '')}",
        )
        related_task_id = self._expand_commit(
            [str(path) for path in self.related_paths],
            f"{self.user.username} changed files related to {str(self.path).replace(str(settings.WORK_DIR), '')}",
        )
        es = Search()
        for path in data:
            es.add_to_index(path)
        return data, main_task_id, related_task_id

    def expand_dry(self):
        results = {}
        failed_paths = []
        for path in self.related_paths:
            results[path] = {"data_before": get_json_data(path), "data_after": {}}
            data = results[path]["data_before"]
            start_index, end_index = self._get_pattern_boundaries(self.uid, data)
            if not start_index or not end_index:
                failed_paths.append(path)
                continue
            uids = list(data.keys())
            new_uid = self._increment_uid(uids[end_index])
            uids.insert(end_index + 1, new_uid)

            expanded_data = {}
            for uid in uids:
                if uid == new_uid:
                    expanded_data[new_uid] = ""
                else:
                    expanded_data[uid] = data[uid]

            split_separator_config = {
                "root": "",
                "translation": "",
                "comment": "",
                "variant": "",
                "html": "{}",
                "reference": ""
            }
            split_separator = split_separator_config.get(
                next((key for key in split_separator_config if key in path.stem), None), ""
            )

            for i in range(start_index, end_index + 2):
                if i == start_index:
                    expanded_data[uids[i]] = split_separator
                elif i == end_index + 1:
                    expanded_data[new_uid] = data[uids[end_index]]
                else:
                    expanded_data[uids[i]] = data[uids[i - 1]]

            results[path]["data_after"] = expanded_data

        for path in failed_paths:
            results.pop(path, None)
            self.related_paths.discard(path)
        return results

    def _increment_uid(self, uid: str) -> str:
        return uid[:-1] + str(int(uid[-1]) + 1)

    def _expand_commit(self, changed_paths: list[str], message: str) -> str:
        result = commit.delay(get_user(int(self.user.github_id)).model_dump(), changed_paths, message)
        return result.id

    def _get_pattern_boundaries(self, segment_id: str, data: dict[str, str]) -> tuple[int | None, int | None]:
        uids = list(key.split(":")[-1] for key in data.keys())
        try:
            start_index = list(data.keys()).index(segment_id)
        except ValueError:
            return None, None
        end_index = start_index

        whole_uids = list(data.keys())
        main_part = segment_id.split(":")[0]
        prefix = segment_id.split(":")[-1].rpartition(".")[0]
        for idx, uid in enumerate(uids[start_index:], start=start_index):
            if not whole_uids[idx].startswith(main_part):
                break
            if not uid.startswith(prefix):
                break
            end_index = idx
        return start_index, end_index
