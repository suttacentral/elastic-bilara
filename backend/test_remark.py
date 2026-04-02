import sys
import os

# Ensure backend paths work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pathlib import Path
from app.services.notifications.remark_notifications import _extract_author_and_type, _collect_participant_usernames, create_remark_notifications
from app.core.config import settings

print("WORK_DIR is:", settings.WORK_DIR)
prefix = "an2.1-10"
print(f"Collecting participants for prefix {prefix}:")
try:
    print(_collect_participant_usernames(prefix))
except Exception as e:
    print("Error:", e)
