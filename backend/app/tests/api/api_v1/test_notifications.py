import pytest
from unittest.mock import MagicMock, patch, Mock
from fastapi import HTTPException

from app.api.api_v1.endpoints.notifications import (
    format_diff_as_html,
    parse_git_show_details,
    get_change_detail,
    mark_notification_as_done,
    get_unread_git_updates,
    commit_id_exists_in_db
)
from app.services.notifications.models import GitCommitInfoOut


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
