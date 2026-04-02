import sys
from sqlalchemy import select, desc
from app.db.database import get_sess
from app.db.models.notification import RemarkNotification

with get_sess() as sess:
    notifs = sess.execute(select(RemarkNotification).order_by(desc(RemarkNotification.created_at)).limit(5)).scalars().all()
    print(f"Top 5 Recent notifications:")
    for n in notifs:
        print(f"[{n.id}] {n.action} by {n.actor_username} to {n.recipient_github_id} at {n.created_at} for {n.uid}:{n.segment_id}")
