from pathlib import Path
from unittest.mock import patch

import pytest

from app.core.config import settings
from app.core.text_types import TextType
from app.services.directories.finder import Finder


class TestFinder:
    @pytest.mark.parametrize(
        "path_mapping, iterdir_values, target_path, expected_len, path_contains",
        [
            (
                {
                    TextType.TRANSLATION: [
                        "translation/en/user/sutta/an/an1/an1.1-10_translation-en-user.json",
                    ],
                },
                ["pli"],
                Path("root/pli/ms/sutta/an/an2/"),
                5,
                ["root/pli/ms", "translation/en/user", "html/pli/ms", "reference/pli/ms", "variant/pli/ms"],
            ),
            (
                {
                    TextType.TRANSLATION: [
                        "translation/en/user/sutta/an/an1/an1.1-10_translation-en-user.json",
                    ],
                },
                ["pli"],
                Path("root/pli/ms/sutta/an/an2/an2.1-10_root-pli-ms.json"),
                5,
                ["root/pli/ms", "translation/en/user", "html/pli/ms", "reference/pli/ms", "variant/pli/ms"],
            ),
            (
                {
                    TextType.TRANSLATION: [
                        "translation/en/user/sutta/an/an1/an1.1-10_translation-en-user.json",
                    ],
                    TextType.COMMENT: [
                        "comment/en/user/sutta/an/an1/an1.1-10_comment-en-user.json",
                    ],
                },
                ["pli"],
                Path("root/pli/ms/sutta/an/an2/"),
                6,
                [
                    "root/pli/ms",
                    "translation/en/user",
                    "comment/en/user",
                    "html/pli/ms",
                    "reference/pli/ms",
                    "variant/pli/ms",
                ],
            ),
            (
                {
                    TextType.TRANSLATION: [
                        "translation/en/user/sutta/an/an1/an1.1-10_translation-en-user.json",
                    ],
                    TextType.COMMENT: [
                        "comment/en/user/sutta/an/an1/an1.1-10_comment-en-user.json",
                    ],
                },
                ["pli"],
                Path("root/pli/ms/sutta/an/an2/an2.1-10_root-pli-ms.json"),
                6,
                [
                    "root/pli/ms",
                    "translation/en/user",
                    "comment/en/user",
                    "html/pli/ms",
                    "reference/pli/ms",
                    "variant/pli/ms",
                ],
            ),
            (
                {
                    TextType.TRANSLATION: [
                        "translation/en/user/sutta/an/an1/an1.1-10_translation-en-user.json",
                        "translation/en/user/sutta/an/an2/an2.1-10_translation-en-user.json",
                        "translation/en/user2/sutta/an/an1/an1.11-20_translation-en-user.json",
                        "translation/en/user2/sutta/mn/mn2/mn2.1_translation-en-user2.json",
                    ],
                    TextType.COMMENT: [
                        "comment/en/user/sutta/an/an1/an1.1-10_comment-en-user.json",
                        "comment/en/user/sutta/an/an2/an2.1-10_comment-en-user.json",
                        "comment/en/user2/sutta/mn/mn2/mn2.1_translation-en-user2.json",
                    ],
                },
                ["pli"],
                Path("root/pli/ms/sutta/an/an2/"),
                8,
                [
                    "root/pli/ms",
                    "translation/en/user",
                    "translation/en/user2",
                    "comment/en/user",
                    "comment/en/user2",
                    "html/pli/ms",
                    "reference/pli/ms",
                    "variant/pli/ms",
                ],
            ),
            (
                {
                    TextType.TRANSLATION: [
                        "translation/en/user/sutta/an/an1/an1.1-10_translation-en-user.json",
                        "translation/en/user/sutta/an/an2/an2.1-10_translation-en-user.json",
                        "translation/en/user2/sutta/an/an1/an1.11-20_translation-en-user.json",
                        "translation/en/user2/sutta/mn/mn2/mn2.1_translation-en-user2.json",
                    ],
                    TextType.COMMENT: [
                        "comment/en/user/sutta/an/an1/an1.1-10_comment-en-user.json",
                        "comment/en/user/sutta/an/an2/an2.1-10_comment-en-user.json",
                        "comment/en/user2/sutta/mn/mn2/mn2.1_translation-en-user2.json",
                    ],
                },
                ["pli"],
                Path("root/pli/ms/sutta/an/an2/an2.1-10_root-pli-ms.json"),
                8,
                [
                    "root/pli/ms",
                    "translation/en/user",
                    "translation/en/user2",
                    "comment/en/user",
                    "comment/en/user2",
                    "html/pli/ms",
                    "reference/pli/ms",
                    "variant/pli/ms",
                ],
            ),
            (
                {},
                ["pli"],
                Path("root/pli/ms/sutta/an/an1/"),
                4,
                ["root/pli/ms", "html/pli/ms", "reference/pli/ms", "variant/pli/ms"],
            ),
            (
                {},
                ["pli"],
                Path("root/pli/ms/sutta/an/an1/an1.1.10_root-pli-ms.json"),
                4,
                ["root/pli/ms", "html/pli/ms", "reference/pli/ms", "variant/pli/ms"],
            ),
            (
                {TextType.REFERENCE: ["reference/pli/ms/sutta/an/an1/an1.1-10_reference-pli-ms.json"]},
                ["pli"],
                Path("root/pli/ms/sutta/an/an1/"),
                4,
                ["root/pli/ms", "html/pli/ms", "variant/pli/ms", "reference/pli/ms"],
            ),
            (
                {TextType.REFERENCE: ["reference/pli/ms/sutta/an/an1/an1.1-10_reference-pli-ms.json"]},
                ["pli"],
                Path("root/pli/ms/sutta/an/an1/an1.1-10_root-pli-ms.json"),
                4,
                ["root/pli/ms", "html/pli/ms", "variant/pli/ms", "reference/pli/ms"],
            ),
            (
                {TextType.REFERENCE: ["reference/pli/ms/sutta/an/an1/"]},
                ["pli"],
                Path("root/pli/ms/sutta/an/an1/"),
                4,
                ["root/pli/ms", "html/pli/ms", "variant/pli/ms", "reference/pli/ms"],
            ),
            (
                {TextType.REFERENCE: ["reference/pli/ms/sutta/an/an1/"]},
                ["pli"],
                Path("root/pli/ms/sutta/an/an1/an1.1-10_root-pli-ms.json"),
                4,
                ["root/pli/ms", "html/pli/ms", "variant/pli/ms", "reference/pli/ms"],
            ),
            (
                {TextType.ROOT: ["root/pra/pts/sutta/test/test1-10_root-pli-pts.json", "root/pli/ms/sutta/an/an2/"]},
                ["pli"],
                Path("root/pli/ms/sutta/an/an1/"),
                4,
                ["root/pli/ms", "html/pli/ms", "variant/pli/ms", "reference/pli/ms"],
            ),
            (
                {TextType.ROOT: ["root/pra/pts/sutta/test/test1-10_root-pli-pts.json", "root/pli/ms/sutta/an/an2/"]},
                ["pli"],
                Path("root/pli/ms/sutta/an/an1/an1.1-10_root-pli-ms.json"),
                4,
                ["root/pli/ms", "html/pli/ms", "variant/pli/ms", "reference/pli/ms"],
            ),
            (
                {
                    TextType.ROOT: [
                        "root/pli/ms/sutta/an/an1/an1.1-10_root-pli-ms.json",
                        "root/en/blurb/an-blurbs_root-en.json",
                        "root/misc/site/name/super-name_root-misc-site.json",
                        "root/misc/site/name/sutta/an-name_root-misc-site.json",
                    ],
                    TextType.HTML: ["html/pli/ms/sutta/an/an1/an1.1-10_html-pli-ms.json"],
                    TextType.TRANSLATION: [
                        "translation/en/user/sutta/an/an1/an1.1-10_translation-en-user.json",
                        "translation/en/user/sutta/mn/mn1/mn1.1-10_translation-en-user.json",
                        "translation/en/user/name/sutta/an-name_translation-en-user.json",
                        "translation/de/site/name/sutta/an-name_translation-de-site.json",
                        "translation/de/user2/sutta/an/an1/an1.1-10_translation-de-user2.json",
                    ],
                    TextType.COMMENT: [
                        "comment/en/user/sutta/an/an1/an1.1-10_comment-en-user.json",
                        "comment/en/user/sutta/mn/mn1/mn1.1-10_comment-en-user.json",
                        "comment/de/user2/sutta/an/an1/an1.1-10_comment-de-user2.json",
                    ],
                },
                ["pli", "misc", "en"],
                Path("root/misc/site/name/sutta/test/"),
                6,
                [
                    "root/misc/site",
                    "html/misc/site",
                    "variant/misc/site",
                    "reference/misc/site",
                    "translation/de/site/name",
                    "translation/en/user/name",
                ],
            ),
            (
                {
                    TextType.ROOT: [
                        "root/pli/ms/sutta/an/an1/an1.1-10_root-pli-ms.json",
                        "root/en/blurb/an-blurbs_root-en.json",
                        "root/misc/site/name/super-name_root-misc-site.json",
                        "root/misc/site/name/sutta/an-name_root-misc-site.json",
                    ],
                    TextType.HTML: ["html/pli/ms/sutta/an/an1/an1.1-10_html-pli-ms.json"],
                    TextType.TRANSLATION: [
                        "translation/en/user/sutta/an/an1/an1.1-10_translation-en-user.json",
                        "translation/en/user/sutta/mn/mn1/mn1.1-10_translation-en-user.json",
                        "translation/en/user/name/sutta/an-name_translation-en-user.json",
                        "translation/de/site/name/sutta/an-name_translation-de-site.json",
                        "translation/de/user2/sutta/an/an1/an1.1-10_translation-de-user2.json",
                    ],
                    TextType.COMMENT: [
                        "comment/en/user/sutta/an/an1/an1.1-10_comment-en-user.json",
                        "comment/en/user/sutta/mn/mn1/mn1.1-10_comment-en-user.json",
                        "comment/de/user2/sutta/an/an1/an1.1-10_comment-de-user2.json",
                    ],
                },
                ["pli", "misc", "en"],
                Path("root/misc/site/name/sutta/arv-name_root-misc-site.json/"),
                6,
                [
                    "root/misc/site",
                    "html/misc/site",
                    "variant/misc/site",
                    "reference/misc/site",
                    "translation/de/site/name",
                    "translation/en/user/name",
                ],
            ),
            (
                {
                    TextType.ROOT: [
                        "root/pli/ms/sutta/an/an1/an1.1-10_root-pli-ms.json",
                        "root/en/blurb/an-blurbs_root-en.json",
                        "root/en/site/abbreviations_root-en-site.json",
                        "root/misc/site/name/super-name_root-misc-site.json",
                        "root/misc/site/name/sutta/an-name_root-misc-site.json",
                    ],
                    TextType.HTML: ["html/pli/ms/sutta/an/an1/an1.1-10_html-pli-ms.json"],
                    TextType.TRANSLATION: [
                        "translation/en/user/sutta/an/an1/an1.1-10_translation-en-user.json",
                        "translation/en/user/sutta/mn/mn1/mn1.1-10_translation-en-user.json",
                        "translation/en/user/name/sutta/an-name_translation-en-user.json",
                        "translation/en/user/name/abbreviations_translation-en-user.json",
                        "translation/de/site/name/sutta/an-name_translation-de-site.json",
                        "translation/de/site/abbreviations_translation-de-site.json",
                        "translation/de/user2/sutta/an/an1/an1.1-10_translation-de-user2.json",
                    ],
                    TextType.COMMENT: [
                        "comment/de/site/discourses_comment-de-site.json",
                    ],
                },
                ["pli", "misc", "en"],
                Path("root/en/site/test_root-en-site.json"),
                6,
                [
                    "root/en/site",
                    "html/en/site",
                    "variant/en/site",
                    "reference/en/site",
                    "translation/de/site",
                    "comment/de/site",
                ],
            ),
            (
                {
                    TextType.ROOT: [
                        "root/pli/ms/sutta/an/an1/an1.1-10_root-pli-ms.json",
                        "root/en/blurb/an-blurbs_root-en.json",
                        "root/en/site/abbreviations_root-en-site.json",
                        "root/misc/site/name/super-name_root-misc-site.json",
                        "root/misc/site/name/sutta/an-name_root-misc-site.json",
                    ],
                    TextType.HTML: ["html/pli/ms/sutta/an/an1/an1.1-10_html-pli-ms.json"],
                    TextType.TRANSLATION: [
                        "translation/en/user/sutta/an/an1/an1.1-10_translation-en-user.json",
                        "translation/en/user/sutta/mn/mn1/mn1.1-10_translation-en-user.json",
                        "translation/en/user/name/sutta/an-name_translation-en-user.json",
                        "translation/en/user/name/abbreviations_translation-en-user.json",
                        "translation/de/site/name/sutta/an-name_translation-de-site.json",
                        "translation/de/site/abbreviations_translation-de-site.json",
                        "translation/de/user2/sutta/an/an1/an1.1-10_translation-de-user2.json",
                    ],
                    TextType.COMMENT: [
                        "comment/de/site/discourses_comment-de-site.json",
                    ],
                },
                ["pli", "misc", "en"],
                Path("root/en/site/test/"),
                6,
                [
                    "root/en/site",
                    "html/en/site",
                    "variant/en/site",
                    "reference/en/site",
                    "translation/de/site",
                    "comment/de/site",
                ],
            ),
            (
                {
                    TextType.ROOT: [
                        "root/pli/ms/sutta/an/an1/an1.1-10_root-pli-ms.json",
                        "root/en/blurb/an-blurbs_root-en.json" "root/misc/site/name/super-name_root-misc-site.json",
                        "root/misc/site/name/sutta/an-name_root-misc-site.json",
                    ],
                    TextType.HTML: ["html/pli/ms/sutta/an/an1/an1.1-10_html-pli-ms.json"],
                    TextType.TRANSLATION: [
                        "translation/en/user/sutta/an/an1/an1.1-10_translation-en-user.json",
                        "translation/en/user/sutta/mn/mn1/mn1.1-10_translation-en-user.json",
                        "translation/en/user/name/sutta/an-name_translation-en-user.json",
                        "translation/de/site/name/sutta/an-name_translation-de-site.json",
                        "translation/de/user2/sutta/an/an1/an1.1-10_translation-de-user2.json",
                    ],
                    TextType.COMMENT: [
                        "comment/en/user/sutta/an/an1/an1.1-10_comment-en-user.json",
                        "comment/en/user/sutta/mn/mn1/mn1.1-10_comment-en-user.json",
                        "comment/de/user2/sutta/an/an1/an1.1-10_comment-de-user2.json",
                    ],
                },
                ["pli", "misc", "en"],
                Path("root/pli/ms/sutta/test"),
                8,
                [
                    "root/pli/ms",
                    "html/pli/ms",
                    "variant/pli/ms",
                    "reference/pli/ms",
                    "translation/en/user",
                    "comment/en/user",
                    "translation/de/user2",
                    "comment/de/user2",
                ],
            ),
            (
                {
                    TextType.ROOT: [
                        "root/pli/ms/sutta/an/an1/an1.1-10_root-pli-ms.json",
                        "root/en/blurb/an-blurbs_root-en.json" "root/misc/site/name/super-name_root-misc-site.json",
                        "root/misc/site/name/sutta/an-name_root-misc-site.json",
                    ],
                    TextType.HTML: ["html/pli/ms/sutta/an/an1/an1.1-10_html-pli-ms.json"],
                    TextType.TRANSLATION: [
                        "translation/en/user/sutta/an/an1/an1.1-10_translation-en-user.json",
                        "translation/en/user/sutta/mn/mn1/mn1.1-10_translation-en-user.json",
                        "translation/en/user/name/sutta/an-name_translation-en-user.json",
                        "translation/de/site/name/sutta/an-name_translation-de-site.json",
                        "translation/de/user2/sutta/an/an1/an1.1-10_translation-de-user2.json",
                    ],
                    TextType.COMMENT: [
                        "comment/en/user/sutta/an/an1/an1.1-10_comment-en-user.json",
                        "comment/en/user/sutta/mn/mn1/mn1.1-10_comment-en-user.json",
                        "comment/de/user2/sutta/an/an1/an1.1-10_comment-de-user2.json",
                    ],
                },
                ["pli", "misc", "en"],
                Path("root/pli/ms/sutta/an/an1/an1.11-20_root-pli-ms.json"),
                8,
                [
                    "root/pli/ms",
                    "html/pli/ms",
                    "variant/pli/ms",
                    "reference/pli/ms",
                    "translation/en/user",
                    "comment/en/user",
                    "translation/de/user2",
                    "comment/de/user2",
                ],
            ),
        ],
    )
    @patch("pathlib.Path.iterdir")
    def test_find(
        self,
        mock_iterdir,
        mock_paths,
        mock_path_obj,
        mock_path_exists,
        path_mapping,
        iterdir_values,
        target_path,
        expected_len,
        path_contains,
    ):
        mock_path_exists([settings.WORK_DIR / x for sublist in path_mapping.values() for x in sublist])
        paths = {text_type.value: [settings.WORK_DIR / x for x in paths] for text_type, paths in path_mapping.items()}
        mock_paths(paths)
        mock_iterdir.return_value = [mock_path_obj(True, value) for value in iterdir_values]

        finder = Finder()
        result = finder.find(target_path)

        assert len(result) == expected_len
        for item in path_contains:
            assert any(item in str(match) for match in result)
