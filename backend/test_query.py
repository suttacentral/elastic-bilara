import sys
from sqlalchemy import func
from app.db.database import get_sess
from app.db.models.user import User

actor_github_id = 4037966 # ihongda
participant_usernames = {'ihongda', 'dhammaisland', 'sujato', 'sabbamitta'}

participant_usernames.discard("ihongda")

with get_sess() as sess:
    recipients = (
        sess.query(User)
        .filter(func.lower(User.username).in_(participant_usernames))
        .filter(User.github_id != actor_github_id)
        .all()
    )
    print("Recipients found:")
    for r in recipients:
        print(f" - {r.username} ({r.github_id})")
    print(f"Total: {len(recipients)}")
