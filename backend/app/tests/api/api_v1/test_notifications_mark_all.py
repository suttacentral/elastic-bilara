from contextlib import contextmanager
import asyncio
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.services.notifications.history import HistoryUnavailable, HistoryTimeout, HistoryBusy

from app.api.api_v1.endpoints import notifications
from app.db.models.notification import Notification, RemarkNotification
from app.services.auth.schema import TokenData


def test_mark_all_persists_beyond_feed_limit_and_only_for_current_user():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
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

    history = [(f'commit{i}', 'Selected <selected@example.com>') for i in range(105)]
    history += [('old', 'Selected <selected@example.com>'), ('other', 'Other <other@example.com>')]
    with patch.object(notifications, 'get_sess', session), patch.object(
        notifications, '_get_selected_authors_and_days', return_value=(['Selected'], 30)
    ), patch.object(notifications.history_service, 'history', return_value=history) as query:
        user = TokenData(github_id="123", username="test")
        assert asyncio.run(notifications.get_unread_notification_count(user)) == 106
        query.reset_mock()
        assert asyncio.run(notifications.mark_all_notifications_as_done(user=user)).success
        query.assert_awaited_once_with(notifications.settings.WORK_DIR, 30)
        assert asyncio.run(notifications.get_unread_notification_count(user)) == 0
        assert asyncio.run(notifications.mark_all_notifications_as_done(user=user)).success

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
@pytest.mark.parametrize('failure, expected_status', [(HistoryUnavailable, 502), (HistoryTimeout, 504), (HistoryBusy, 503)])
def test_git_failure_is_reported_without_writing_read_state(operation, failure, expected_status):
    with patch.object(
        notifications, '_get_selected_authors_and_days', return_value=(['Selected'], 30)
    ), patch.object(
        notifications, 'get_all_commit_ids_in_db', return_value=[]
    ), patch.object(
        notifications.history_service, 'history', side_effect=failure('failed'),
    ), patch.object(notifications, 'get_sess') as session:
        with pytest.raises(HTTPException) as error:
            asyncio.run(operation(user=TokenData(github_id="123", username="test")))
        assert error.value.status_code == expected_status
        session.assert_not_called()


def test_mark_all_rejects_missing_github_id_before_reading_or_writing():
    with patch.object(notifications, '_get_unread_git_commit_ids') as get_ids, patch.object(
        notifications, 'get_sess'
    ) as session:
        with pytest.raises(HTTPException) as error:
            asyncio.run(notifications.mark_all_notifications_as_done(user=TokenData(username='test')))
        assert error.value.status_code == 401
        get_ids.assert_not_called()
        session.assert_not_called()
