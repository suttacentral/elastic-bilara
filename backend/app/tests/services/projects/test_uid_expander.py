from pathlib import Path
from unittest.mock import patch

from app.core.config import settings
from app.services.projects.uid_expander import UIDExpander


class TestUIDExpander:
    @patch("app.services.projects.uid_expander.Search")
    @patch("app.services.projects.uid_expander.write_json_data_for_split_or_merge")
    @patch("app.services.projects.uid_expander.get_json_data")
    @patch("app.services.projects.uid_expander.get_matches")
    def test_expand_does_not_auto_commit(
        self,
        mock_get_matches,
        mock_get_json_data,
        mock_write_json_data_for_split_or_merge,
        mock_search,
        user,
    ):
        path = settings.WORK_DIR / "root/pli/ms/sutta/test/test1/test1.1_root-pli-ms.json"
        related_path = (
            settings.WORK_DIR
            / "translation/en/test_user/sutta/test/test1/test1.1_translation-en-test_user.json"
        )
        existing_json_data = {
            path: {"test:1.1": "one", "test:1.2": "two"},
            related_path: {"test:1.1": "one", "test:1.2": "two"},
        }
        mock_get_matches.return_value = set(existing_json_data.keys())
        mock_get_json_data.side_effect = lambda arg: existing_json_data[arg]
        expander = UIDExpander(user, path, "test:1.1")

        data, main_task_id, related_task_id = expander.expand()

        assert main_task_id is None
        assert related_task_id is None
        assert set(data.keys()) == set(existing_json_data.keys())
        assert mock_write_json_data_for_split_or_merge.call_count == 2
        assert not hasattr(expander, "_expand_commit")
        assert mock_search.return_value.add_to_index.call_count == 2
