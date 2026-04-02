import sys
import os

from app.db.database import get_sess
from app.db.models.user import User

with get_sess() as sess:
    users = sess.query(User).all()
    for u in users:
        print(f"User: {u.username}, github_id: {u.github_id}")

