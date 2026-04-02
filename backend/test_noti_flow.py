import sys
import logging
from pathlib import Path

from app.services.notifications.remark_notifications import create_remark_notifications

logging.basicConfig(level=logging.DEBUG)

source_file_path = "/app/checkouts/unpublished/translation/en/ihongda/sutta/an/an2/an2.1-10_translation-en-ihongda.json"

try:
    res = create_remark_notifications(
        source_file_path=source_file_path,
        segment_id="an2.1-10:1.1",
        remark_value="test",
        action="updated",
        actor_username="ihongda",
        actor_github_id=4037966
    )
    print(f"Created {res} notifications")
except Exception as e:
    import traceback
    traceback.print_exc()

