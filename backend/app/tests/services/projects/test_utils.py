import builtins
import json
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest
from app.services.projects.utils import (
    OverrideException,
    create_new_project_file_names,
    create_new_project_paths,
    create_project_file,
    generate_file_name_prefixes,
    get_json_data,
    sort_paths,
    update_file,
)


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
        path = tmp_path / "test1_file.json"
        root_path = tmp_path / "test1_root.json"

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


@pytest.mark.parametrize(
    ("root_path", "expected_result", "user", "language"),
    [
        (
            Path("checkouts/published/root/pli/ms/abhidhamma/ds/ds1/ds1.1_root-pli-ms.json"),
            Path("/app/checkouts/unpublished/translation/en/user_1/abhidhamma/ds/ds1/"),
            "user_1",
            "en",
        ),
        (
            Path("checkouts/published/root/lzh/sct/sutta/ea/ea19/ea19.1_root-lzh-sct.json"),
            Path("/app/checkouts/unpublished/translation/de/user_2/sutta/ea/ea19/"),
            "user_2",
            "de",
        ),
        (
            Path("checkouts/published/root/pli/ms/sutta/an/an1/an1.1-10_root-pli-ms.json"),
            Path("/app/checkouts/unpublished/translation/en/user_3/sutta/an/an1/"),
            "user_3",
            "en",
        ),
        (
            Path("checkouts/published/root/lzh/sct/sutta/ma/ma1_root-lzh-sct.json"),
            Path("/app/checkouts/unpublished/translation/pl/user_4/sutta/ma/"),
            "user_4",
            "pl",
        ),
    ],
)
def test_create_new_project_paths(root_path, expected_result, user, language):
    assert create_new_project_paths(user, language, root_path, ["translation"]) == [expected_result]


@pytest.mark.parametrize(
    ("root_path", "expected_result", "user", "language", "directories"),
    [
        (
            Path("checkouts/published/root/pli/ms/abhidhamma/ds/ds1/ds1.1_root-pli-ms.json"),
            [
                Path("/app/checkouts/unpublished/translation/en/user_1/abhidhamma/ds/ds1/"),
                Path(f"/app/checkouts/unpublished/comment/en/user_1/abhidhamma/ds/ds1/"),
            ],
            "user_1",
            "en",
            ["translation", "comment"],
        ),
        (
            Path("checkouts/published/root/lzh/sct/sutta/ea/ea19/ea19.1_root-lzh-sct.json"),
            [
                Path("/app/checkouts/unpublished/translation/de/user_2/sutta/ea/ea19/"),
                Path("/app/checkouts/unpublished/new_dir/de/user_2/sutta/ea/ea19/"),
            ],
            "user_2",
            "de",
            ["translation", "new_dir"],
        ),
        (
            Path("checkouts/published/root/pli/ms/sutta/an/an1/an1.1-10_root-pli-ms.json"),
            [
                Path("/app/checkouts/unpublished/translation/en/user_3/sutta/an/an1/"),
                Path("/app/checkouts/unpublished/new_dir/en/user_3/sutta/an/an1/"),
            ],
            "user_3",
            "en",
            ["translation", "new_dir"],
        ),
        (
            Path("checkouts/published/root/lzh/sct/sutta/ma/ma1_root-lzh-sct.json"),
            [
                Path("/app/checkouts/unpublished/translation/pl/user_4/sutta/ma/"),
                Path("/app/checkouts/unpublished/comment/pl/user_4/sutta/ma/"),
                Path("/app/checkouts/unpublished/new_dir/pl/user_4/sutta/ma/"),
            ],
            "user_4",
            "pl",
            ["translation", "comment", "new_dir"],
        ),
    ],
)
def test_create_new_project_paths_multiple_dirs(root_path, expected_result, user, language, directories):
    assert all([elem in expected_result for elem in create_new_project_paths(user, language, root_path, directories)])


def test_create_new_project_paths_invalid_root_path():
    with pytest.raises(ValueError):
        create_new_project_paths("user_1", "en", Path("/checkouts/no_exact_root_directory/bla/test"), ["translation"])


def test_generate_file_name_prefixes_file_as_source(mock_path_iterdir):
    root_path = Path("checkouts/published/root/pli/ms/abhidhamma/ds/ds1/ds1_root-pli-ms.json")
    assert generate_file_name_prefixes(root_path) == ["ds1.1", "ds1.2", "ds1.3", "ds1.4", "ds1.5"]


def test_generate_file_name_prefixes_dir_as_source(mock_path_iterdir):
    root_path = Path("checkouts/published/root/pli/ms/abhidhamma/ds/ds1/")
    assert generate_file_name_prefixes(root_path) == ["ds1.1", "ds1.2", "ds1.3", "ds1.4", "ds1.5"]


@pytest.mark.parametrize(
    ("root_path", "translation_path", "comment_path", "user", "language", "file_name_prefixes"),
    [
        (
            Path("checkouts/published/root/pli/ms/abhidhamma/ds/ds1/ds1.1_root-pli-ms.json"),
            Path("/app/checkouts/unpublished/translation/en/user_1/abhidhamma/ds/ds1/"),
            Path("/app/checkouts/unpublished/comment/en/user_1/abhidhamma/ds/ds1/"),
            "user_1",
            "en",
            ["ds1.1", "ds1.2", "ds1.3", "ds1.4", "ds1.5"],
        ),
        (
            Path("checkouts/published/root/lzh/sct/sutta/ea/ea19/ea19.1_root-lzh-sct.json"),
            Path("/app/checkouts/unpublished/translation/de/user_2/sutta/ea/ea19/"),
            Path("/app/checkouts/unpublished/comment/de/user_2/sutta/ea/ea19/"),
            "user_2",
            "de",
            ["ea19.1", "ea19.2", "ea19.3", "ea19.4", "ea19.5"],
        ),
        (
            Path("checkouts/published/root/pli/ms/sutta/an/an1/an1.1-10_root-pli-ms.json"),
            Path("/app/checkouts/unpublished/translation/en/user_3/sutta/an/an1/"),
            Path("/app/checkouts/unpublished/comment/en/user_3/sutta/an/an1/"),
            "user_3",
            "en",
            ["an1.1-10", "an1.11-20", "an1.21-30", "an1.31-40", "an1.41-50"],
        ),
        (
            Path("checkouts/published/root/lzh/sct/sutta/ma/ma1_root-lzh-sct.json"),
            Path("/app/checkouts/unpublished/translation/pl/user_4/sutta/ma/"),
            Path("/app/checkouts/unpublished/comment/pl/user_4/sutta/ma/"),
            "user_4",
            "pl",
            ["ma1", "ma2", "ma3", "ma4", "ma5"],
        ),
    ],
)
def test_create_new_project_file_names(
    mocker, root_path, translation_path, comment_path, user, language, file_name_prefixes
):
    directory_list = ["translation", "comment"]

    expected_file_names = [
        (
            translation_path / f"{prefix}_translation-{language}-{user}.json",
            comment_path / f"{prefix}_comment-{language}-{user}.json",
        )
        for prefix in file_name_prefixes
    ]

    mocker.patch("app.services.projects.utils.create_new_project_paths", return_value=[translation_path, comment_path])
    mocker.patch("app.services.projects.utils.generate_file_name_prefixes", return_value=file_name_prefixes)

    actual = create_new_project_file_names(user, language, root_path, directory_list)

    assert actual == expected_file_names


def test_create_project_file_success(mocker):
    def mock_get_json_data():
        return {
            "segment1": "some existing translation data",
            "segment2": "some other translation data",
        }

    class MockOpen:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def write(self, _):
            pass

    segments_root_path = Path("/path/to/segments/root.json")
    new_file_path = Path("/path/to/new/file.json")

    mocker.patch.object(Path, "exists", return_value=False)
    mocker.patch.object(Path, "mkdir", return_value=None)

    mocker.patch("search.utils.get_json_data", return_value=mock_get_json_data())
    mocker.patch("json.dump", autospec=True, return_value=new_file_path.parent)
    mocker.patch("json.load", return_value=mock_get_json_data())

    mock_open_instance = MockOpen()
    mocker.patch("builtins.open", return_value=mock_open_instance)

    create_project_file(segments_root_path, new_file_path)

    assert json.dump.call_args[0][0] == {"segment1": "", "segment2": ""}
    Path.mkdir.assert_called_once()
    json.dump.assert_called_once_with(
        {"segment1": "", "segment2": ""}, mock_open_instance, indent=2, ensure_ascii=False
    )
    builtins.open.assert_called_with(new_file_path, "w+")


def test_create_project_file_exists_exception(mocker):
    # Mocked input paths
    segments_root_path = Path("/path/to/segments/root.json")
    existing_file_path = Path("/path/to/existing/file.json")

    mocker.patch.object(Path, "exists", return_value=True)

    with pytest.raises(OverrideException) as e:
        create_project_file(segments_root_path, existing_file_path)

    assert str(existing_file_path) in str(e.value)
