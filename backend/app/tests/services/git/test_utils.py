from pathlib import Path
from unittest.mock import patch

import pytest
from app.services.git import utils


class TestUtils:
    @pytest.mark.parametrize(
        "branch, expected_output",
        [
            ("part1_part2", "part1/part2"),
            ("part1_part2_part3", "part1/part2/part3"),
            ("part1_part2_part3_part4_part5", "part1/part2/part3/part4/part5"),
            ("part1_part2_part3_part4_part5_extra", "part1/part2/part3/part4/part5_extra"),
            ("part1_part2_part3_part4_part5_extra1_extra2", "part1/part2/part3/part4/part5/extra1_extra2"),
        ],
    )
    def test_get_project_title(self, branch, expected_output):
        assert utils.get_project_title(branch) == expected_output

    @pytest.mark.parametrize(
        "paths, expected_output",
        [
            (
                [Path("directory1/directory2/file1.json"), Path("directory3/file2.json")],
                {
                    Path("directory1/directory2/file1.json"): "directory1_directory2_file1",
                    Path("directory3/file2.json"): "directory3_file2",
                },
            ),
            ([], {}),
            (None, {}),
        ],
    )
    def test_get_file_heads(self, paths, expected_output):
        assert utils.get_file_heads(paths) == expected_output

    @pytest.mark.parametrize(
        "path, expected_output",
        [
            (
                Path(
                    "directory1/directory2/directory3/directory4/directory5/directory6/directory7/directory8/file.json"
                ),
                "directory1_directory2_directory3_directory4_directory5_directory6_directory7_directory8",
            ),
            (
                Path(
                    "directory1/directory2/directory3/directory4/directory5/directory5a/directory6/directory7/file.json"
                ),
                "directory1_directory2_directory3_directory4_directory5_directory5a_directory6_directory7",
            ),
            (
                Path("directory1/directory2/directory3/directory4/directory5/directory5a/directory6/file.json"),
                "directory1_directory2_directory3_directory4_directory5",
            ),
            (
                Path("directory1/directory2/directory3/directory4/directory5/directory5a/file.json"),
                "directory1_directory2_directory3_directory4_directory5",
            ),
            (
                Path("directory1/directory2/directory3/directory4/directory5/file.json"),
                "directory1_directory2_directory3_directory4_directory5",
            ),
            (
                Path("directory1/directory2/directory3/directory4/file.json"),
                "directory1_directory2_directory3_directory4",
            ),
            (Path("directory1/directory2/directory3/file.json"), "directory1_directory2_directory3"),
            (Path("directory1/directory2/file.json"), "directory1_directory2"),
            (Path("directory1/file.json"), "directory1"),
            (Path("file.json"), "."),
            (Path(""), "."),
        ],
    )
    def test_get_project_head(self, path, expected_output):
        assert utils.get_project_head(path) == expected_output

    @pytest.mark.parametrize(
        "paths, expected_output",
        [
            (
                [
                    "directory1/directory2/directory3/directory4/directory5/directory5a/file1.json",
                    "directory1/directory2/directory3/directory4/directory5/directory5a/file2.json",
                ],
                (True, []),
            ),
            (
                [
                    "directory1/directory2/directory3/directory4/directory5/file1.json",
                    "directory1/directory2/directory3/directory4/directory5/file2.json",
                ],
                (True, []),
            ),
            (
                [
                    "directory1/directory2/directory3/directory4/directory5/file1.json",
                    "directoryA/directoryB/directoryC/directoryD/directoryE/file2.json",
                ],
                (False, ["/directoryA/directoryB/directoryC/directoryD/directoryE/file2.json"]),
            ),
            (["directory1/directory2/directory3/directory4/directory5/file1.json"], (True, [])),
            ([], (True, [])),
            (None, (True, [])),
        ],
    )
    def test_find_mismatched_paths(self, paths, expected_output):
        assert utils.find_mismatched_paths(paths) == expected_output

    @pytest.mark.parametrize(
        "paths, expected_output",
        [
            (
                [
                    Path("directory1/directory2/directory3/directory4/directory5/directory5a/file1.json"),
                    Path("directory1/directory2/directory3/directory4/directory5/directory5a/file2.json"),
                ],
                "directory1_directory2_directory3_directory4_directory5",
            ),
            (
                [Path("directory1/directory2/directory3/directory4/directory5/file1.json")],
                "directory1_directory2_directory3_directory4_directory5_file1",
            ),
            (
                [],
                None,
            ),
        ],
    )
    def test_get_branch_name(self, paths, expected_output, git_manager):
        if not paths:
            with pytest.raises(ValueError, match="No file paths provided."):
                utils.get_branch_name(git_manager, paths)
        else:
            assert utils.get_branch_name(git_manager, paths) == expected_output
