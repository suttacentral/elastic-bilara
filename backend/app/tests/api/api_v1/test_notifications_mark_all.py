from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.api_v1.endpoints import notifications
from app.db.models.notification import Notification, RemarkNotification
from app.services.auth.schema import TokenData


def test_mark_all_persists_beyond_feed_limit_and_only_for_current_user():
    engine = create_engine('sqlite://')
    Notification.__table__.create(engine)
    RemarkNotification.__table__.create(engine)

    @contextmanager
    def session():
        with Session(engine) as sess:
            yield sess

    def remark(recipient):
        return RemarkNotification(
            recipient_github_id=recipient, actor_username='author', action='updated',
            uid='mn1', segment_id='mn1:1', source_file_path='remark.json',
        )

    with session() as sess:
        sess.add_all([remark(123), remark(456), Notification(github_id=123, commit_id='old')])
        sess.commit()

    log_output = '\n'.join(
        [f'commit{i}|Selected <selected@example.com>' for i in range(105)]
        + ['old|Selected <selected@example.com>', 'other|Other <other@example.com>']
    )
    with patch.object(notifications, 'get_sess', session), patch.object(
        notifications, '_get_selected_authors_and_days', return_value=(['Selected'], 30)
    ), patch.object(
        notifications.subprocess, 'run',
        return_value=SimpleNamespace(returncode=0, stdout=log_output),
    ) as git_run, patch.object(
        notifications.subprocess, 'Popen', side_effect=AssertionError('Must not generate diffs')
    ):
        user = TokenData(github_id="123", username="test")
        assert notifications.get_unread_notification_count(user) == 106
        git_run.reset_mock()
        assert notifications.mark_all_notifications_as_done(user=user).success
        git_run.assert_called_once()
        command = git_run.call_args.args[0]
        assert 'log' in command
        assert '--since=30 days ago' in command
        assert '--no-merges' in command
        assert notifications.get_unread_notification_count(user) == 0
        assert notifications.mark_all_notifications_as_done(user=user).success

    with session() as sess:
        assert sess.query(Notification).filter_by(github_id=123).count() == 106
        assert sess.query(Notification).filter_by(github_id=456).count() == 0
        assert sess.query(RemarkNotification).filter_by(recipient_github_id=123).one().is_done
        assert not sess.query(RemarkNotification).filter_by(recipient_github_id=456).one().is_done
    engine.dispose()


@pytest.mark.parametrize('operation', [
    notifications.mark_all_notifications_as_done,
    notifications.get_notification_count,
])
@pytest.mark.parametrize('launch_error', [False, True])
def test_git_failure_is_reported_without_writing_read_state(operation, launch_error):
    with patch.object(
        notifications, '_get_selected_authors_and_days', return_value=(['Selected'], 30)
    ), patch.object(
        notifications, 'get_all_commit_ids_in_db', return_value=[]
    ), patch.object(
        notifications.subprocess, 'run',
        return_value=SimpleNamespace(returncode=128, stdout=''),
        side_effect=OSError('Git unavailable') if launch_error else None,
    ), patch.object(
        notifications.subprocess, 'Popen', side_effect=AssertionError('Must not generate diffs')
    ), patch.object(notifications, 'get_sess') as session:
        with pytest.raises(HTTPException) as error:
            operation(user=TokenData(github_id="123", username="test"))
        assert error.value.status_code == 502
        session.assert_not_called()


def test_mark_all_rejects_missing_github_id_before_reading_or_writing():
    with patch.object(notifications, '_get_unread_git_commit_ids') as get_ids, patch.object(
        notifications, 'get_sess'
    ) as session:
        with pytest.raises(HTTPException) as error:
            notifications.mark_all_notifications_as_done(user=TokenData(username='test'))
        assert error.value.status_code == 401
        get_ids.assert_not_called()
        session.assert_not_called()
