import sys
import os
from pathlib import Path
from app.services.notifications.remark_notifications import find_root_path

path = Path("/home/hongda/eb/elastic-bilara/backend/checkouts/unpublished/translation/en/ihongda/sutta/an/an2/an2.1-10_translation-en-ihongda.json")
res = find_root_path(path)
print("Root path found:", res)
