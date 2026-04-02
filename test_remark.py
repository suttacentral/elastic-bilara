import asyncio
from pathlib import Path
from app.services.notifications.remark_notifications import _extract_author_and_type, _collect_participant_usernames, create_remark_notifications
from app.core.config import settings

print("WORK_DIR is:", settings.WORK_DIR)
prefix = "an2.1-10"
print(f"Collecting participants for prefix {prefix}:")
print(_collect_participant_usernames(prefix))

