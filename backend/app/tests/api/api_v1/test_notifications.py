import asyncio
import json

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, Mock

from app.api.api_v1.endpoints.notifications import (
    format_diff_as_html,
    get_notifications_feed,
    parse_git_show_details,
    get_change_detail,
    get_notification_authors_or_default,
    get_notification_count,
    get_unread_git_updates,
    get_user_preferences,
    mark_notification_as_done_by_type,
    stream_notification_count,
)
from app.services.notifications.models import (
    GitCommitInfoOut,
    NotificationCountOut,
    NotificationDonePayload,
)


def test_format_diff_as_html_normal_file():
    """测试普通文件的变更格式化"""
    change_detail = "-old line\n+new line\nunchanged line"
    file_name = "test_translation.json"

    expected = (
        '<p class="delete">-old line</p>'
        '<p class="add">+new line</p>'
        '<p>unchanged line</p>'
    )

    result = format_diff_as_html(change_detail, file_name)
    assert result == expected


def test_format_diff_as_html_html_file():
    """测试 HTML 文件的变更格式化（特殊处理）"""
    change_detail = "<div>content</div>"
    file_name = "test_html.json"

    expected = "<div>content</div>\n\r"

    result = format_diff_as_html(change_detail, file_name)
    assert result == expected


def test_format_diff_as_html_none():
    assert format_diff_as_html(None, "file.json") is None


def test_parse_git_show_details():
    git_output = """
diff --git a/mn1_translation-en-sujato.json b/mn1_translation-en-sujato.json
index abc..def 100644
--- a/mn1_translation-en-sujato.json
+++ b/mn1_translation-en-sujato.json
@@ -1,5 +1,5 @@
 {
-  "mn1:1.1": "Old text",
+  "mn1:1.1": "New text",
 }
diff --git a/mn2_translation-en-sujato.json b/mn2_translation-en-sujato.json
index 123..456 100644
--- a/mn2_translation-en-sujato.json
+++ b/mn2_translation-en-sujato.json
@@ -1 +1 @@
-foo
+bar
"""
    result = parse_git_show_details(git_output)
    assert len(result) == 2
    assert result[0]['file_name'] == 'mn1_translation-en-sujato.json'
    assert '-  "mn1:1.1": "Old text",' in result[0]['change_detail']
    assert result[1]['file_name'] == 'mn2_translation-en-sujato.json'


def test_parse_git_show_details_handles_diff_without_hunks():
    git_output = """
diff --git a/mn1_translation-en-sujato.json b/mn1_translation-en-sujato.json
old mode 100644
new mode 100755
diff --git a/mn2_translation-en-sujato.json b/mn2_translation-en-sujato.json
index 123..456 100644
--- a/mn2_translation-en-sujato.json
+++ b/mn2_translation-en-sujato.json
@@ -1 +1 @@
-foo
+bar
"""
    result = parse_git_show_details(git_output)

    assert len(result) == 2
    assert result[0] == {
        "file_name": "mn1_translation-en-sujato.json",
        "change_detail": "",
    }
    assert result[1]["file_name"] == "mn2_translation-en-sujato.json"
    assert "-foo" in result[1]["change_detail"]
    assert "+bar" in result[1]["change_detail"]


def test_get_change_detail():
    parsed_details = [
        {'file_name': 'file1.json', 'change_detail': 'detail1'},
        {'file_name': 'file2.json', 'change_detail': 'detail2'}
    ]
    assert get_change_detail('file1.json', parsed_details) == 'detail1'
    assert get_change_detail('file3.json', parsed_details) is None


def test_get_notification_authors_or_default_returns_default_for_none():
    assert get_notification_authors_or_default(None) == ["sujato"]


def test_get_notification_authors_or_default_returns_default_for_empty_list():
    assert get_notification_authors_or_default([]) == ["sujato"]


def test_get_notification_count_returns_only_unread_count():
    user = Mock(github_id=123)

    with patch(
        "app.api.api_v1.endpoints.notifications.get_unread_notification_count",
        return_value=7,
    ) as get_unread_count:
        result = asyncio.run(get_notification_count(user=user))

    assert result == NotificationCountOut(unread_count=7)
    get_unread_count.assert_called_once_with(user)


def test_notification_stream_awaits_cancellable_count():
    user = Mock(github_id=123)
    request = Mock()
    request.is_disconnected = AsyncMock(return_value=False)

    async def get_first_event():
        with patch(
            "app.api.api_v1.endpoints.notifications.get_unread_notification_count",
            new=AsyncMock(return_value=4),
        ) as count:
            response = await stream_notification_count(request=request, user=user)
            event = await anext(response.body_iterator)
            await response.body_iterator.aclose()
            count.assert_awaited_once_with(user)
            return event

    assert asyncio.run(get_first_event()) == 'event: unread_count\ndata: {"unread_count": 4}\n\n'


def test_get_user_preferences_returns_default_authors_when_missing():
    user = Mock(github_id=123)
    preference = Mock(
        id=1,
        github_id=123,
        notification_authors=None,
        notification_days=None,
    )
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.first.return_value = (
        preference
    )
    mock_get_sess = MagicMock()
    mock_get_sess.return_value.__enter__.return_value = mock_session
    mock_get_sess.return_value.__exit__.return_value = None

    with patch(
        "app.api.api_v1.endpoints.notifications.get_sess",
        mock_get_sess,
    ):
        result = get_user_preferences(user=user)

    assert result.notification_authors == ["sujato"]
    assert result.notification_days == 360


def test_get_unread_git_updates_handles_missing_authors_preference():
    user = Mock(github_id=123)
    preference = Mock(
        notification_authors=None,
        notification_days=30,
    )
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.first.return_value = (
        preference
    )
    mock_get_sess = MagicMock()
    mock_get_sess.return_value.__enter__.return_value = mock_session
    mock_get_sess.return_value.__exit__.return_value = None

    with patch(
        "app.api.api_v1.endpoints.notifications.get_sess",
        mock_get_sess,
    ), patch(
        "app.api.api_v1.endpoints.notifications.feed_service.metadata",
        return_value=[],
    ), patch(
        "app.api.api_v1.endpoints.notifications.get_all_commit_ids_in_db",
        return_value=[],
    ):
        result = get_unread_git_updates(user=user)

    assert isinstance(result, GitCommitInfoOut)
    assert result.git_recent_commits == []


def test_get_notifications_feed_merges_and_sorts():
    user = Mock(github_id=123)
    commit_notifications = [
        {
            "author": "commit-author",
            "commit": "abc123",
            "date": "Mon Mar 10 10:00:00 2025 +0000",
            "effected_files": [],
        }
    ]
    remark_notifications = [
        {
            "notification_type": "remark",
            "notification_ref": "7",
            "author": "remark-author",
            "date": "2026-03-13T12:00:00",
            "uid": "mn1",
            "segment_id": "mn1:1.1",
            "action": "updated",
            "source_file_path": "/tmp/mn1_translation-en-a.json",
            "remark_value": "new remark",
            "effected_files": [],
        }
    ]

    with patch(
        "app.api.api_v1.endpoints.notifications._get_git_candidates",
        return_value=commit_notifications,
    ), patch(
        "app.api.api_v1.endpoints.notifications._render_git_items",
        side_effect=lambda items: items,
    ), patch(
        "app.api.api_v1.endpoints.notifications._build_remark_notification_items",
        return_value=remark_notifications,
    ):
        result = get_notifications_feed(user=user)

    assert len(result.notifications) == 2
    assert result.notifications[0]["notification_type"] == "remark"
    assert result.notifications[1]["notification_type"] == "commit"


def test_get_notifications_feed_selects_metadata_before_rendering():
    user = Mock(github_id=123)

    with patch(
        "app.api.api_v1.endpoints.notifications._get_git_candidates",
        return_value=[],
    ) as git_update_items, patch(
        "app.api.api_v1.endpoints.notifications._build_remark_notification_items",
        return_value=[],
    ):
        result = get_notifications_feed(include_read=True, limit=50, user=user)

    git_update_items.assert_called_once_with(user, include_done=True)
    assert result.notifications == []


def test_mark_notification_as_done_by_type_commit_uses_legacy_endpoint():
    user = Mock(github_id=123)
    payload = NotificationDonePayload(
        notification_type="commit",
        notification_ref="abc123",
    )

    async def fake_done(*args, **kwargs):
        return {"success": True}

    with patch(
        "app.api.api_v1.endpoints.notifications.mark_notification_as_done",
        side_effect=fake_done,
    ) as mocked:
        result = asyncio.run(
            mark_notification_as_done_by_type(payload=payload, user=user)
        )

    assert mocked.called
    assert result["success"] is True


def test_http_disconnect_cancels_query():
    from app.api.api_v1.endpoints import notifications
    from fastapi import HTTPException

    async def scenario():
        started = asyncio.Event()
        cancelled = asyncio.Event()
        async def count(user):
            started.set()
            try:
                await asyncio.Future()
            finally:
                cancelled.set()
        async def disconnected():
            return started.is_set()
        request = Mock(is_disconnected=disconnected)
        with patch.object(notifications, 'get_unread_notification_count', side_effect=count):
            try:
                await notifications.get_notification_count(user=Mock(), request=request)
            except HTTPException as error:
                assert error.status_code == 499
            else:
                raise AssertionError('disconnect must stop the query')
        assert cancelled.is_set()
    asyncio.run(scenario())


def test_sse_cancellation_propagates_into_pending_query():
    from app.api.api_v1.endpoints import notifications

    async def scenario():
        started = asyncio.Event()
        cancelled = asyncio.Event()
        async def count(user):
            started.set()
            try:
                await asyncio.Future()
            finally:
                cancelled.set()
        request = Mock(is_disconnected=AsyncMock(return_value=False))
        with patch.object(notifications, 'get_unread_notification_count', side_effect=count):
            response = await notifications.stream_notification_count(request, Mock())
            read = asyncio.create_task(anext(response.body_iterator))
            await started.wait()
            read.cancel()
            await asyncio.gather(read, return_exceptions=True)
            await response.body_iterator.aclose()
        assert cancelled.is_set()
    asyncio.run(scenario())


def test_sse_deadline_ends_without_error_event_or_poll_sleep():
    from app.api.api_v1.endpoints import notifications

    async def scenario():
        cancelled = asyncio.Event()
        async def slow_count(user):
            try:
                await asyncio.Future()
            finally:
                cancelled.set()
        request = Mock(is_disconnected=AsyncMock(return_value=False))
        with patch.object(notifications, 'NOTIFICATION_STREAM_MAX_RUNTIME_SECONDS', 0.02), patch.object(
            notifications, 'get_unread_notification_count', side_effect=slow_count
        ), patch.object(notifications.asyncio, 'sleep', new=AsyncMock()) as sleep:
            response = await notifications.stream_notification_count(request, Mock())
            try:
                with pytest.raises(StopAsyncIteration):
                    await asyncio.wait_for(anext(response.body_iterator), 0.5)
                assert cancelled.is_set()
                sleep.assert_not_awaited()
            finally:
                await response.body_iterator.aclose()
    asyncio.run(scenario())


@pytest.mark.parametrize('status', [502, 503, 504, None])
def test_sse_query_failures_keep_meaningful_error_messages(status):
    from app.api.api_v1.endpoints import notifications
    from fastapi import HTTPException

    message = f'Git query failure {status}' if status else 'Notification query timed out'
    error = HTTPException(status_code=status, detail=message) if status else asyncio.TimeoutError()
    async def scenario():
        request = Mock(is_disconnected=AsyncMock(return_value=False))
        with patch.object(notifications, 'get_unread_notification_count', side_effect=error):
            response = await notifications.stream_notification_count(request, Mock())
            try:
                event = await anext(response.body_iterator)
                assert event.startswith('event: stream_error\n')
                assert json.loads(event.split('data: ', 1)[1]) == {'error': message}
            finally:
                await response.body_iterator.aclose()
    asyncio.run(scenario())


def test_sse_last_poll_sleep_is_limited_to_remaining_lifetime():
    from app.api.api_v1.endpoints import notifications

    async def scenario():
        request = Mock(is_disconnected=AsyncMock(return_value=False))
        real_sleep = asyncio.sleep
        with patch.object(notifications, 'NOTIFICATION_STREAM_MAX_RUNTIME_SECONDS', 0.05), patch.object(
            notifications, 'get_unread_notification_count', new=AsyncMock(return_value=4)
        ) as count, patch.object(notifications.asyncio, 'sleep', new=AsyncMock(wraps=real_sleep)) as sleep:
            response = await notifications.stream_notification_count(request, Mock())
            try:
                assert 'event: unread_count' in await anext(response.body_iterator)
                with pytest.raises(StopAsyncIteration):
                    await asyncio.wait_for(anext(response.body_iterator), 0.5)
                sleep.assert_awaited_once()
                assert 0 < sleep.await_args.args[0] <= 0.05
                count.assert_awaited_once()
            finally:
                await response.body_iterator.aclose()
    asyncio.run(scenario())


def test_sse_does_not_sleep_if_deadline_passed_while_event_was_consumed():
    from app.api.api_v1.endpoints import notifications

    async def scenario():
        request = Mock(is_disconnected=AsyncMock(return_value=False))
        with patch.object(notifications, 'NOTIFICATION_STREAM_MAX_RUNTIME_SECONDS', 0.05), patch.object(
            notifications, 'get_unread_notification_count', new=AsyncMock(return_value=4)
        ):
            response = await notifications.stream_notification_count(request, Mock())
            try:
                assert 'event: unread_count' in await anext(response.body_iterator)
                await asyncio.sleep(0.06)
                with patch.object(notifications.asyncio, 'sleep', new=AsyncMock()) as sleep:
                    with pytest.raises(StopAsyncIteration):
                        await anext(response.body_iterator)
                    sleep.assert_not_awaited()
            finally:
                await response.body_iterator.aclose()
    asyncio.run(scenario())
