import asyncio
from unittest.mock import MagicMock, patch, Mock

from app.api.api_v1.endpoints.notifications import (
    format_diff_as_html,
    get_notifications_feed,
    parse_git_show_details,
    get_change_detail,
    get_notification_authors_or_default,
    get_unread_git_updates,
    get_user_preferences,
    mark_notification_as_done_by_type,
)
from app.services.notifications.models import (
    GitCommitInfoOut,
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

    mock_process = MagicMock()
    mock_process.communicate.return_value = (b"", b"")
    mock_process.returncode = 0

    with patch(
        "app.api.api_v1.endpoints.notifications.get_sess",
        mock_get_sess,
    ), patch(
        "app.api.api_v1.endpoints.notifications.subprocess.Popen",
        return_value=mock_process,
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
        "app.api.api_v1.endpoints.notifications.get_unread_git_update_items",
        return_value=commit_notifications,
    ), patch(
        "app.api.api_v1.endpoints.notifications._build_remark_notification_items",
        return_value=remark_notifications,
    ):
        result = get_notifications_feed(user=user)

    assert len(result.notifications) == 2
    assert result.notifications[0]["notification_type"] == "remark"
    assert result.notifications[1]["notification_type"] == "commit"


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
