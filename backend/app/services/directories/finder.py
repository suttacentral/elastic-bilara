from pathlib import Path

from app.core.config import settings
from app.core.text_types import TextType


class Finder:
    def __init__(self):
        self.root_dir = settings.WORK_DIR / TextType.ROOT.value
        self.paths = {
            text_type.value: [path for path in (settings.WORK_DIR / text_type.value).rglob("*")]
            for text_type in TextType
        }
        self.similar = (TextType.ROOT.value, TextType.HTML.value, TextType.VARIANT.value, TextType.REFERENCE.value)

    def find(self, target_path: Path, exact: bool = False) -> set[Path]:
        if exact:
            return self._find_exact(target_path)
        result = set()
        for text_type in TextType:
            matches = self._match_for_type(text_type, target_path)
            if not matches and text_type.value in self.similar:
                path = Path(*target_path.parts[:-1]) if target_path.parts[-1].endswith(".json") else target_path
                result.add(settings.WORK_DIR / str(path).replace(TextType.ROOT.value, text_type.value))
            for match in matches:
                result.add(match)
        return result

    def _find_exact(self, target_path: Path) -> set[Path]:
        result = set()
        pattern = (
            f"**/{target_path.parts[-1]}/**" if target_path.is_dir() else f"**/{target_path.stem.split('_')[0]}_*.json"
        )
        for text_type in TextType:
            matches = [path for path in (settings.WORK_DIR / text_type.value).glob(pattern)]
            for match in matches:
                result.add(match)
        return result

    def _match_for_type(self, text_type: TextType, target_path: Path) -> set[Path]:
        paths = self.paths[text_type.value]
        target_parts = [
            part for part in target_path.parts if not part.endswith(".json") and part != TextType.ROOT.value
        ]
        if target_parts[0] not in [d.name for d in self.root_dir.iterdir() if d.is_dir()]:
            if text_type.value in {TextType.TRANSLATION.value, TextType.COMMENT.value}:
                return set()
            return {settings.WORK_DIR / str(target_path).replace(TextType.ROOT.value, text_type.value)}
        matches = set()
        for path in paths:
            path_parts = [
                part for part in path.parts if not part.endswith(".json") and part not in settings.WORK_DIR.parts
            ]
            if text_type.value == TextType.ROOT.value and (
                ("misc" in target_parts and "en" in path_parts) or ("en" in target_parts and "misc" in path_parts)
            ):
                continue
            if text_type.value == TextType.TRANSLATION.value and "misc" in target_parts and "name" in target_parts:
                if "en" in path_parts and "name" in path_parts:
                    result = self._longest_match(target_parts, path_parts)
                    if result:
                        index = self._find_index(result, path_parts)
                        matches.add(Path(*path_parts[: index + len(result)]))
                        continue
            if "name" in path_parts and "name" not in target_parts:
                continue
            if "blurb" in target_parts and "blurb" not in path_parts:
                continue
            if "site" in target_parts and "site" not in path_parts:
                continue
            result = self._longest_match(target_parts, path_parts)
            if result:
                index = self._find_index(result, path_parts)
                matches.add(Path(*path_parts[: index + len(result)]))
        matches = {
            settings.WORK_DIR / result for result in self._normalize_results(self._reduce_paths(matches), target_parts)
        }
        if text_type.value in self.similar:
            tmp_matches = {match for match in matches if text_type.value in str(match)}
            if tmp_matches:
                to_remove = self._check_similarity(target_path, tmp_matches)
                for path in to_remove:
                    matches.remove(Path(path))
        return matches

    @staticmethod
    def _longest_match(target_parts: list[str], path_parts: list[str]) -> list:
        parts = []
        path_parts_indexes = {x: i for i, x in enumerate(path_parts)}
        for i in range(len(target_parts)):
            if target_parts[i] in path_parts_indexes:
                j = i + 1
                part = [target_parts[i]]
                while (
                    j < len(target_parts)
                    and target_parts[j] in path_parts_indexes
                    and path_parts_indexes[target_parts[j - 1]] + 1 == path_parts_indexes[target_parts[j]]
                ):
                    part.append(target_parts[j])
                    j += 1
                parts.append(part)
        parts = sorted(parts, key=len)
        if parts:
            return parts[-1]
        return []

    @staticmethod
    def _find_index(result: list, path_parts: list[str]) -> int:
        indexes = [i for i, x in enumerate(path_parts) if x == result[0]]
        return indexes[-1] if indexes else None

    @staticmethod
    def _reduce_paths(paths: set[Path]) -> set[Path]:
        """Removes any directory that is a parent of another directory in the set"""
        results = set(paths)
        for path in paths:
            while len(path.parts) > 2:
                path = path.parent
                if path in results:
                    results.remove(path)
        return results

    @staticmethod
    def _normalize_results(matches: set[Path], target_parts: list[str]) -> set[Path]:
        """
        Normalizes a set of path matches based on a list of target path parts.

        For each match, the function iterates over the target parts in reverse order.
        If a target part is found in the match parts, it appends the subsequent
        target parts to the match and adds the new path to the results. The iteration
        over target parts for this match is then halted.
        """
        results = set()
        for match in matches:
            for part in target_parts[::-1]:
                if part in match.parts:
                    new_parts = target_parts[target_parts.index(part) + 1 :]
                    results.add(match / Path(*new_parts))
                    break
        return results

    @staticmethod
    def _check_similarity(target_path: Path, path_set: set[Path]) -> list[str] | set[Path]:
        count_dict = {}
        while len(target_path.parts) > 0:
            for path in path_set:
                if str(target_path) in str(path):
                    if path in count_dict:
                        count_dict[path] += 1
                    else:
                        count_dict[path] = 1
            target_path = Path(*target_path.parts[1:])
        if count_dict:
            max_count = max(count_dict.values())
            filtered_paths = [str(path) for path, count in count_dict.items() if count < max_count]
            return filtered_paths
        return path_set
