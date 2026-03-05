import json
from pathlib import Path
from fastapi import APIRouter

router = APIRouter(prefix="/languages")


def _load_languages():
    """Load languages from the published _language.json file."""
    try:
        # Get the checkouts directory from the WORK_DIR
        work_dir = Path(__file__).parent.parent.parent.parent.parent / "checkouts" / "published" / "_language.json"
        
        if work_dir.exists():
            with open(work_dir, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            # Fallback if the file doesn't exist
            return {}
    except Exception as e:
        print(f"Error loading languages: {e}")
        return {}


@router.get("")
def get_languages():
    """Get all available languages from the _language.json configuration."""
    return _load_languages()
