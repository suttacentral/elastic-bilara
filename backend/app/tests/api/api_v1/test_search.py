from unittest.mock import patch

import pytest


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_unauthenticated(self, async_client) -> None:
        response = await async_client.get("/search/")
        assert response.status_code == 401
        assert "detail" in response.json()
        assert response.json() == {"detail": "Not authenticated"}

    @pytest.mark.asyncio
    async def test_search_no_query_parameters(self, async_client, mock_get_current_user) -> None:
        response = await async_client.get(
            "/search/",
        )
        assert response.status_code == 400
        assert "detail" in response.json()
        assert response.json() == {"detail": "No query parameters provided"}

    @pytest.mark.asyncio
    async def test_search_only_uid_provided(self, async_client, mock_get_current_user) -> None:
        response = await async_client.get("/search/?uid=test56.1:0.1")
        assert response.status_code == 400
        assert "detail" in response.json()
        assert response.json() == {"detail": "Please provide at least one muid"}

    @pytest.mark.parametrize(
        "params, results",
        [
            (
                "?uid=test56.1:0.1&translation-en-test=test",
                {
                    "test56.1:0.1": {
                        "translation-en-test": "This value should contain test",
                    }
                },
            ),
            (
                "?uid=test56.1:0.1&translation-en-test=test&translation-en-test2=",
                {
                    "test56.1:0.1": {
                        "translation-en-test": "This value should contain test",
                    },
                    "test56.1:0.2": {
                        "translation-en-test": "This value should contain test",
                        "translation-en-test2": "This value contains what's under that uid",
                    },
                },
            ),
            (
                "?uid=test56.1:0.1&translation-en-test=test&translation-en-test2=test2",
                {
                    "test56.1:0.1": {
                        "translation-en-test": "This value should contain test",
                        "translation-en-test2": "This value should contain test2",
                    },
                    "test56.1:0.2": {
                        "translation-en-test": "This value should contain test",
                        "translation-en-test2": "This value should contain test2",
                    },
                },
            ),
            (
                "?uid=test56.1:0.1&translation-en-test=",
                {
                    "test56.1:0.1": {
                        "translation-en-test": "Some value",
                    },
                    "test56.1:0.5": {
                        "translation-en-test": "Some value",
                    },
                },
            ),
            (
                "?uid=test56.1:0.1&translation-en-test=&translation-en-test2=",
                {
                    "test56.1:0.1": {
                        "translation-en-test": "Some value",
                        "translation-en-test2": "Some other value",
                    },
                    "test56.1:0.3": {
                        "translation-en-test": "Some value",
                        "translation-en-test2": "Some other value",
                    },
                },
            ),
            (
                "?translation-en-test=test",
                {
                    "test1.1:1.1": {
                        "translation-en-test": "This value should contain test",
                    }
                },
            ),
            (
                "?translation-en-test=test&translation-en-test2=",
                {
                    "test1.1:1.1": {
                        "translation-en-test": "This value should contain test",
                        "translation-en-test2": "This value contains what's under that uid",
                    },
                    "test1.1:1.2": {
                        "translation-en-test": "This value should contain test",
                        "translation-en-test2": "This value contains what's under that uid",
                    },
                    "test3.2:2.8": {
                        "translation-en-test": "This value should contain test",
                        "translation-en-test2": "This value contains what's under that uid",
                    },
                },
            ),
            (
                "?translation-en-test=test&translation-en-test2=test2&translation-en-test3=",
                {
                    "test1.1:1.1": {
                        "translation-en-test": "This value should contain test",
                        "translation-en-test2": "This value should contain test2",
                        "translation-en-test3": "This value contains what's under test1.1:1.1 uid",
                    }
                },
            ),
            ("?translation-en-test=", {}),
            ("?translation-en-test=&translation-en-test2=", {}),
        ],
    )
    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.search.es.get_segments")
    async def test_search(self, mock_get_segments, async_client, mock_get_current_user, params, results) -> None:
        mock_get_segments.return_value = results
        response = await async_client.get(f"/search/{params}")
        assert response.status_code == 200
        assert "results" in response.json()
        assert response.json() == {"results": results}
