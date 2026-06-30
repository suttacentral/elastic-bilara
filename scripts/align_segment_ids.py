import json
from pathlib import Path
from typing import Any, Generator
import pandas as pd
from tqdm import tqdm

TEXT_TYPES = ("root", "html", "translation", "variant", "reference", "comment")
WORK_DIR: Path = Path(__file__).parent / "unpublished"


def get_prefix(path: Path):
    return path.stem.split("_")[0]


def get_muid(path: Path):
    after_unpublished: tuple[str] = path.parts[path.parts.index("unpublished") + 1 :]
    return "-".join(after_unpublished[:3])


def get_muid_from_name(path: Path) -> str:
    return path.stem.split("_")[1]


def yield_file_data(path: Path) -> Generator[tuple[Any, Any], Any, None]:
    with open(path, "r") as file:
        for key, value in json.load(file).items():
            yield key, value


def generate_data_dict():
    data_dict: dict[str, list[dict[str, str]]] = {text_type: [] for text_type in TEXT_TYPES}
    for text_type in TEXT_TYPES:
        files = [p for p in WORK_DIR.rglob(f"{text_type}/**/*") if p.is_file()]
        for path in tqdm(files, desc=f"扫描 {text_type}", unit="file"):
            muid = get_muid(path)
            for key, value in yield_file_data(path):
                data_dict[text_type].append(
                    {
                        "MUID": muid,
                        "Segment_ID": key,
                        "Segment_Value": value,
                        "Path": str(path),
                        "Prefix": get_prefix(path),
                    }
                )
    return data_dict


def check_missing_segments():
    data_dict = generate_data_dict()

    root_data = {item["Segment_ID"]: {"Path": item["Path"], "Prefix": item["Prefix"]} for item in data_dict["root"]}
    translation_ids = {item["Segment_ID"]: item["Path"] for item in data_dict["translation"]}
    html_data = {item["Segment_ID"]: {"Path": item["Path"], "Prefix": item["Prefix"]} for item in data_dict["html"]}

    missing_both = list(set(html_data.keys()) - (set(root_data.keys()).union(set(translation_ids.keys()))))
    missing_root_segments = list(
        set(html_data.keys()).intersection(set(translation_ids.keys())) - set(root_data.keys())
    )

    issues = []

    for segment_id in missing_both:
        html_prefix = html_data[segment_id]["Prefix"]
        corresponding_root = [data["Path"] for id, data in root_data.items() if data["Prefix"] == html_prefix]
        issues.append(
            {
                "issue_type": "missing_both",
                "segment_id": segment_id,
                "html_path": html_data[segment_id]["Path"],
                "root_path": corresponding_root[0] if corresponding_root else None,
            }
        )

    for segment_id in missing_root_segments:
        html_prefix = html_data[segment_id]["Prefix"]
        corresponding_root = [data["Path"] for id, data in root_data.items() if data["Prefix"] == html_prefix]
        issues.append(
            {
                "issue_type": "missing_root",
                "segment_id": segment_id,
                "html_path": html_data[segment_id]["Path"],
                "root_path": corresponding_root[0] if corresponding_root else None,
            }
        )

    df = pd.DataFrame(issues)
    df.to_csv("missing_segments.csv", index=False)
    return "missing_segments.csv"


def fix_roots(csv_name):
    try:
        df = pd.read_csv(csv_name)
    except pd.errors.EmptyDataError:
        print("未检测到缺失的母版段号，跳过修复母版。")
        return
    df.drop_duplicates(subset=["html_path", "root_path"], inplace=True)
    for _, row in tqdm(df.iterrows(), total=len(df), desc="修复母版", unit="file"):
        with open(row["html_path"], "r") as sf:
            html_data = json.load(sf)
        with open(row["root_path"], "r") as tf:
            try:
                root_data = json.load(tf)
            except json.JSONDecodeError:
                root_data = {}
        with open(row["root_path"], "w") as tf:
            merged_data = {key: root_data.get(key, "") for key in html_data.keys()}
            merged_data.update(root_data)
            json.dump(merged_data, tf, indent=2, ensure_ascii=False)


def generate_path_dict():
    path_dict: dict[str, list[dict[str, str]]] = {text_type: [] for text_type in TEXT_TYPES}
    for text_type in TEXT_TYPES:
        for path in WORK_DIR.rglob(f"{text_type}/**/*"):
            if path.is_file():
                muid = get_muid(path)
                path_dict[text_type].append(
                    {
                        "MUID": muid,
                        "Path": str(path),
                        "Prefix": get_prefix(path),
                    }
                )
    return path_dict


def prefix_to_paths_mapping():
    path_dict = generate_path_dict()
    prefix_to_paths_mapping = {}
    for _, data in path_dict.items():
        for item in data:
            prefix = item["Prefix"]
            if prefix not in prefix_to_paths_mapping:
                prefix_to_paths_mapping[prefix] = []
            prefix_to_paths_mapping[prefix].append(item["Path"])
    return prefix_to_paths_mapping


def update_data():
    prefix_to_paths = prefix_to_paths_mapping()
    items = [(prefix, paths) for prefix, paths in prefix_to_paths.items()
             if any("unpublished/root" in path for path in paths)]
    for prefix, paths in tqdm(items, desc="补全段号", unit="prefix"):
        root_index = paths.index(next(path for path in paths if "unpublished/root" in path))
        root_path = paths.pop(root_index)
        with open(root_path, "r") as file:
            root_data = json.load(file)
        for path in paths:
            with open(path, "r") as file:
                data = json.load(file)
            merged_data = {key: data.get(key, "") for key in root_data.keys()}
            with open(path, "w") as file:
                json.dump(merged_data, file, indent=2, ensure_ascii=False)


def main():
    data_csv = check_missing_segments()
    fix_roots(data_csv)
    update_data()


if __name__ == "__main__":
    main()
