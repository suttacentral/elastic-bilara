import json
from pathlib import Path


def create_repo_structure_with_content(repo_dir):
    repo_dir = Path(repo_dir)
    file_path = repo_dir / "translations" / "en" / "test" / "sutta" / "an" / "an1"
    file_path.mkdir(parents=True, exist_ok=True)

    if "unpublished" in str(repo_dir):
        content = {
            "an1.1:0.1": "Numbered Discourses 1.1–10 ",
            "an1.1:0.2": "The Chapter on What Occupies the Mind ",
            "an1.1:1.0": "1 ",
            "an1.1:1.1": "So I have heard. ",
            "an1.1:1.2": "At one time the Buddha was staying near Sāvatthī in Jeta’s Grove, Anāthapiṇḍika’s monastery. ",
        }

    else:
        content = {
            "an1.1:0.1": "Numbered Discourses 1.1–10 ",
            "an1.1:0.2": "This is a test",
            "an1.1:1.0": "1 ",
            "an1.1:1.1": "Some test data. ",
            "an1.1:1.2": "Test data",
        }

    with open(file_path / "an1.1-10_translation-en-test.json", "w") as f:
        json.dump(content, f, indent=2, ensure_ascii=False)
