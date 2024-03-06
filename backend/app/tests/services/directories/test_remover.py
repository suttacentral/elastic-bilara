import pytest

from app.core.config import settings


class TestRemover:
    def test_delete(self, mocker, remover, mock_path_obj):
        path = str(settings.WORK_DIR / "root/pli/ms/sutta/test/test1/test1.1_root-pli-ms.json")
        related_path = str(
            settings.WORK_DIR / "translation/en/test_user/sutta/test/test1/test1.1_translation-en-test_user.json"
        )

        path_mock = mock_path_obj(True, path)
        related_path_mock = mock_path_obj(True, related_path)

        (
            remover_instance,
            mock_remove_elastic,
            mock_remove_commit,
            mock_delete_elements,
            mock_get_paths,
            _,
            mock_get_matches_method,
        ) = remover(path_mock)

        mock_get_matches_method.return_value = {path_mock, related_path_mock}
        mock_remove_elastic.side_effect = lambda x: None
        mock_get_paths.side_effect = [{path_mock}, {related_path_mock}]

        main_task_id = "main_task_id"
        related_task_id = "related_task_id"
        mock_remove_commit.side_effect = [main_task_id, related_task_id]

        result = remover_instance.delete()

        calls = [mocker.call([path], mocker.ANY), mocker.call([related_path], mocker.ANY)]
        mock_remove_commit.assert_has_calls(calls)

        mock_delete_elements.assert_called_once_with({path_mock, related_path_mock})

        assert result == (main_task_id, related_task_id)

    @pytest.mark.parametrize(
        "path, mock_get_matches, results",
        [
            (
                "root/pli/ms/sutta/test/test1/test1.1_root-pli-ms.json",
                {
                    "/root/pli/ms/sutta/test/test1/test1.1_root-pli-ms.json",
                    "/translation/en/test_user/sutta/test/test1/test1.1_translation-en-test_user.json",
                    "/html/pli/ms/sutta/test/test1/test1.1_html-pli-ms.json",
                },
                [
                    "/root/pli/ms/sutta/test/test1/test1.1_root-pli-ms.json",
                    "/translation/en/test_user/sutta/test/test1/test1.1_translation-en-test_user.json",
                    "/html/pli/ms/sutta/test/test1/test1.1_html-pli-ms.json",
                ],
            ),
            (
                "root/pli/ms/sutta/test/test1",
                {
                    "/root/pli/ms/sutta/test/test1",
                    "/translation/en/test_user/sutta/test/test1",
                    "/html/pli/ms/sutta/test/test1",
                },
                [
                    "/root/pli/ms/sutta/test/test1",
                    "/translation/en/test_user/sutta/test/test1",
                    "/html/pli/ms/sutta/test/test1",
                ],
            ),
            (
                "translation/en/test_user/sutta/test/test1/test1.1_translation-en-test_user.json",
                {
                    "/root/pli/ms/sutta/test/test1/test1.1_root-pli-ms.json",
                    "/translation/en/test_user/sutta/test/test1/test1.1_translation-en-test_user.json",
                    "/html/pli/ms/sutta/test/test1/test1.1_html-pli-ms.json",
                    "/comment/en/test_user/sutta/test/test1/test1.1_comment-en-test_user.json",
                },
                [
                    "/root/pli/ms/sutta/test/test1/test1.1_root-pli-ms.json",
                    "/translation/en/test_user/sutta/test/test1/test1.1_translation-en-test_user.json",
                    "/html/pli/ms/sutta/test/test1/test1.1_html-pli-ms.json",
                    "/comment/en/test_user/sutta/test/test1/test1.1_comment-en-test_user.json",
                ],
            ),
        ],
    )
    def test_delete_dry(self, remover, mock_path_obj, path, mock_get_matches, results):
        remover_instance, _, _, _, _, _, mock_get_matches_method = remover(mock_path_obj(True, path))
        mock_get_matches_method.return_value = {mock_path_obj(True, p) for p in mock_get_matches}
        assert remover_instance.delete_dry().sort() == results.sort()

    @pytest.mark.parametrize(
        "path, mock_get_matches, results",
        [
            (
                "root/pli/ms/sutta/test/test1/test1.1_root-pli-ms.json",
                {
                    "/root/pli/ms/sutta/test/test1/test1.1_root-pli-ms.json",
                    "/translation/en/test_user/sutta/test/test1/test1.1_translation-en-test_user.json",
                    "/html/pli/ms/sutta/test/test1/test1.1_html-pli-ms.json",
                },
                {
                    "/root/pli/ms/sutta/test/test1/test1.1_root-pli-ms.json",
                    "/translation/en/test_user/sutta/test/test1/test1.1_translation-en-test_user.json",
                    "/html/pli/ms/sutta/test/test1/test1.1_html-pli-ms.json",
                },
            ),
            (
                "root/pli/ms/sutta/test/test1",
                {
                    "/root/pli/ms/sutta/test/test1",
                    "/translation/en/test_user/sutta/test/test1",
                    "/html/pli/ms/sutta/test/test1",
                },
                {
                    "/root/pli/ms/sutta/test/test1",
                    "/translation/en/test_user/sutta/test/test1",
                    "/html/pli/ms/sutta/test/test1",
                },
            ),
            (
                "translation/en/test_user/sutta/test/test1/test1.1_translation-en-test_user.json",
                {
                    "/root/pli/ms/sutta/test/test1/test1.1_root-pli-ms.json",
                    "/translation/en/test_user/sutta/test/test1/test1.1_translation-en-test_user.json",
                    "/html/pli/ms/sutta/test/test1/test1.1_html-pli-ms.json",
                    "/comment/en/test_user/sutta/test/test1/test1.1_comment-en-test_user.json",
                },
                {
                    "/translation/en/test_user/sutta/test/test1/test1.1_translation-en-test_user.json",
                    "/comment/en/test_user/sutta/test/test1/test1.1_comment-en-test_user.json",
                },
            ),
            (
                "translation/en/test_user/sutta/test/test1",
                {
                    "/root/pli/ms/sutta/test/test1",
                    "/translation/en/test_user/sutta/test/test1",
                    "/html/pli/ms/sutta/test/test1",
                    "/comment/en/test_user/sutta/test/test1",
                },
                {
                    "/translation/en/test_user/sutta/test/test1",
                    "/comment/en/test_user/sutta/test/test1",
                },
            ),
            (
                "comment/en/test_user/sutta/test/test1/test1.1_comment-en-test_user.json",
                {
                    "/root/pli/ms/sutta/test/test1/test1.1_root-pli-ms.json",
                    "/translation/en/test_user/sutta/test/test1/test1.1_translation-en-test_user.json",
                    "/html/pli/ms/sutta/test/test1/test1.1_html-pli-ms.json",
                    "/comment/en/test_user/sutta/test/test1/test1.1_comment-en-test_user.json",
                },
                {"/comment/en/test_user/sutta/test/test1/test1.1_comment-en-test_user.json"},
            ),
            (
                "comment/en/test_user/sutta/test/test1",
                {
                    "/root/pli/ms/sutta/test/test1",
                    "/translation/en/test_user/sutta/test/test1",
                    "/html/pli/ms/sutta/test/test1",
                    "/comment/en/test_user/sutta/test/test1",
                },
                {"/comment/en/test_user/sutta/test/test1"},
            ),
        ],
    )
    def test__get_matches(self, remover, mock_path_obj, path, mock_get_matches, results):
        remover_instance, _, _, _, _, mock_get_matches_root, _ = remover(mock_path_obj(True, path))
        mock_get_matches_root.return_value = {mock_path_obj(True, p) for p in mock_get_matches}
        for result in remover_instance._get_matches():
            assert result.name in results
