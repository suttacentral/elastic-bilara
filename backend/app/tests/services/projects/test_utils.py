import json
from unittest.mock import mock_open, patch

import pytest
from app.services.projects.utils import sort_paths, update_file


class TestProjectsUtils:
    def test_sort_paths(self):
        paths = {"path/2b", "path/10a", "path/1c"}
        assert sort_paths(paths) == ["path/1c", "path/2b", "path/10a"]

        paths = {"path/2", "path/10", "path/1"}
        assert sort_paths(paths) == ["path/1", "path/2", "path/10"]

        paths = {"path/a", "path/c", "path/b"}
        assert sort_paths(paths) == ["path/a", "path/b", "path/c"]

        paths = {"path/a2", "path/a10", "path/a1"}
        assert sort_paths(paths) == ["path/a1", "path/a2", "path/a10"]

        paths = set()
        assert sort_paths(paths) == []

    @pytest.mark.parametrize(
        "update_segments_return, data, expected_result, expected_error_type, open_error, commit",
        [
            ((True, None), {"key1": "value1"}, True, None, None, True),
            ((True, None), {"key3": "value3"}, True, None, None, True),
            ((True, None), {"key4": "value4"}, False, KeyError, None, False),
            ((False, Exception("Search service error")), {"key1": "value1"}, False, Exception, None, False),
            ((True, None), {"key1": "value1"}, False, OSError, OSError("File error"), False),
            ((True, None), {"key1": "value1"}, False, TypeError, TypeError("Type error"), False),
        ],
    )
    def test_update_file(
        self,
        update_segments_return,
        data,
        expected_result,
        expected_error_type,
        open_error,
        commit,
        tmp_path,
        user,
    ):
        path = tmp_path / "file.json"
        root_path = tmp_path / "root.json"

        with open(path, "w") as f:
            json.dump({"key1": "old_value1", "key2": "old_value2"}, f)
        with open(root_path, "w") as f:
            json.dump({"key1": "root_value1", "key2": "root_value2"}, f)

        def open_side_effect(*args, **kwargs):
            if "w" in args[1]:
                if open_error:
                    raise open_error
            if str(args[0]) == str(root_path):
                return mock_open(
                    read_data=json.dumps(
                        {
                            "key1": "root_value1",
                            "key2": "root_value2",
                            "key3": "root_value3",
                        }
                    )
                )(*args, **kwargs)
            else:
                return mock_open(read_data=json.dumps({"key1": "old_value1", "key2": "old_value2"}))(*args, **kwargs)

        with patch("app.services.projects.utils.search") as mock_search, patch(
            "builtins.open", side_effect=open_side_effect
        ), patch("app.tasks.commit.delay") as mock_commit, patch(
            "app.services.projects.utils.get_user"
        ) as mock_get_user:
            mock_get_user.return_value = user
            mock_search.update_segments.return_value = update_segments_return
            result, error, task_id = update_file(path, data, root_path, user)

            assert mock_commit.called == commit

        assert result == expected_result
        if expected_error_type is None:
            assert error is None
        else:
            assert isinstance(error, expected_error_type)
