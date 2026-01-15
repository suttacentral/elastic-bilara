import re
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.text_types import TextType
from app.db.schemas.user import UserBase
from app.services.directories.models import FilesAndDirsOut
from app.services.directories import utils
from app.services.auth.utils import get_current_user
from app.services.directories.remover import Remover
from app.services.directories.utils import get_muid_from_path, get_language
from app.services.projects.utils import sort_paths
from app.services.users.permissions import can_delete_projects

router = APIRouter(prefix="/directories")


@router.get("/search/{search_path:path}/", response_model=dict)
async def search_path_tree(
    search_path: str,
    user: Annotated[UserBase, Depends(get_current_user)],
    exact_match: bool = False
):
    """
    Search for directories by name and return matches with their parent directory trees.

    Given a directory name, searches the entire directory structure and returns
    all matching directories along with their complete parent directory paths.

    Args:
        search_path: Directory name or path to search for
        user: Current authenticated user (required for authentication)
        exact_match: If True, requires exact name match; if False, allows partial matching

    Returns:
        dict: Object containing matching directories with their parent trees
    """

    def search_directories(root_dir: Path, search_name: str, exact: bool = False) -> list[Path]:
        """
        Recursively search for directories matching the search criteria.

        Args:
            root_dir: Root directory to start searching from
            search_name: Directory name to search for
            exact: Whether to use exact matching or partial matching

        Returns:
            List of Path objects that match the search criteria
        """
        matching_dirs = []

        def recursive_search(current_path: Path):
            """Recursively traverse directories to find matches."""
            try:
                for item in current_path.iterdir():
                    if item.is_dir():
                        # Skip TextType directories at root level
                        if (current_path == root_dir and
                            item.name in {text_type.value for text_type in TextType}):
                            recursive_search(item)
                            continue

                        # Check if current directory matches search criteria
                        if exact:
                            if item.name == search_name:
                                matching_dirs.append(item)
                        else:
                            if search_name.lower() in item.name.lower():
                                matching_dirs.append(item)

                        # Continue searching in subdirectories
                        recursive_search(item)

            except (PermissionError, OSError) as e:
                # Skip directories that can't be accessed
                print(f"Warning: Cannot access {current_path}: {e}")

        recursive_search(root_dir)
        return matching_dirs

    def get_parent_tree(target_path: Path) -> list[str]:
        """
        Get all parent directories for a given path.

        Args:
            target_path: The target directory path

        Returns:
            List of parent directory paths from root to immediate parent
        """
        parents = []
        try:
            relative_path = target_path.relative_to(settings.WORK_DIR)

            # Get all parent directories
            current_parent = relative_path.parent
            while str(current_parent) != ".":
                parents.append(f"{current_parent}/")
                current_parent = current_parent.parent

            # Reverse to show from root to immediate parent
            parents.reverse()

        except ValueError:
            # Path is not relative to WORK_DIR
            pass

        return parents

    def get_directory_info(dir_path: Path) -> dict:
        """
        Get detailed information about a directory.

        Args:
            dir_path: Directory path to analyze

        Returns:
            Dictionary with directory information
        """
        try:
            relative_path = str(dir_path.relative_to(settings.WORK_DIR))
            parent_tree = get_parent_tree(dir_path)

            # Count immediate children
            child_dirs = 0
            child_files = 0

            try:
                for item in dir_path.iterdir():
                    if item.is_dir():
                        if item.name not in {text_type.value for text_type in TextType}:
                            child_dirs += 1
                    elif item.is_file():
                        child_files += 1
            except (PermissionError, OSError):
                pass

            return {
                "path": f"{relative_path}/",
                "name": dir_path.name,
                "parent_tree": parent_tree,
                "depth": len(relative_path.split("/")),
                "child_directories": child_dirs,
                "child_files": child_files,
                "total_children": child_dirs + child_files
            }

        except ValueError:
            return None

    # Perform the search
    all_matches = []

    # Search in the entire work directory
    matching_paths = search_directories(settings.WORK_DIR, search_path, exact_match)

    # Process each match
    for match_path in matching_paths:
        dir_info = get_directory_info(match_path)
        if dir_info:
            all_matches.append(dir_info)

    # Sort matches by depth and then by path
    all_matches.sort(key=lambda x: (x["depth"], x["path"]))

    # Prepare response
    response = {
        "search_query": search_path,
        "exact_match": exact_match,
        "total_matches": len(all_matches),
        "matches": all_matches
    }

    # Add search statistics
    if all_matches:
        depths = [match["depth"] for match in all_matches]
        response["statistics"] = {
            "min_depth": min(depths),
            "max_depth": max(depths),
            "avg_depth": sum(depths) / len(depths)
        }

    return response


@router.get("/", response_model=FilesAndDirsOut)
async def get_root_content(user: Annotated[UserBase, Depends(get_current_user)]):
    directories = []
    for p in settings.WORK_DIR.iterdir():
        if p.is_dir() and p.name in {item.value for item in TextType}:
            directories.append(str(p.relative_to(settings.WORK_DIR)) + "/")
    directories.sort()
    return FilesAndDirsOut(directories=directories)


@router.get("/{path:path}/", response_model=FilesAndDirsOut)
async def get_dir_content(
    user: Annotated[UserBase, Depends(get_current_user)], target_path: Path = Depends(utils.validate_dir_path)
):
    from app.db.database import get_sess
    from app.db.models.translation_progress import TranslationProgress

    base = str(target_path.relative_to(settings.WORK_DIR)) + "/"
    directories = []
    files = []
    files_with_progress = []

    is_translation_dir = base.startswith("translation/")

    progress_cache = {}
    if is_translation_dir:
        with get_sess() as db:
            # Query all progress records for files in this directory
            like_pattern = base + "%"
            cached_records = db.query(TranslationProgress).filter(
                TranslationProgress.file_path.like(like_pattern)
            ).all()
            for record in cached_records:
                file_name = Path(record.file_path).name
                progress_cache[file_name] = {
                    "name": file_name,
                    "progress": record.progress,
                    "total_keys": record.total_keys,
                    "translated_keys": record.translated_keys,
                }

    for p in target_path.iterdir():
        if p.is_dir() and p.name not in {item.value for item in TextType}:
            dir_path = str(p.relative_to(settings.WORK_DIR)) + "/"
            directories.append(dir_path.replace(base, "", 1))
        elif p.is_file() and str(target_path) != str(settings.WORK_DIR):
            file_name = p.name
            file_path = str(p.relative_to(settings.WORK_DIR))
            files.append(file_path.replace(base, "", 1))

            if is_translation_dir:
                if file_name in progress_cache:
                    files_with_progress.append(progress_cache[file_name])
                else:
                    progress_info = utils.calculate_file_progress(p)
                    files_with_progress.append(progress_info)

    directories.sort(key=lambda s: [int(c) if c.isdigit() else c for c in re.split('(\d+)', s)])
    files.sort(key=lambda s: [int(c) if c.isdigit() else c for c in re.split('(\d+)', s)])
    if files_with_progress:
        files_with_progress.sort(key=lambda f: [int(c) if c.isdigit() else c for c in re.split('(\d+)', f["name"])])

    return FilesAndDirsOut(base=base, directories=directories, files=files, files_with_progress=files_with_progress if is_translation_dir else None)


@router.delete("/{path:path}/")
async def delete_path(
    user: Annotated[UserBase, Depends(get_current_user)],
    target_path: Path = Depends(utils.validate_path),
    dry_run: bool = False,
):
    if not can_delete_projects(int(user.github_id)):
        raise HTTPException(status_code=403, detail="You are not allowed to delete projects")
    remover = Remover(user, target_path)
    if dry_run:
        data = remover.delete_dry()
        results = []
        for path in data:
            results.append(
                {
                    "muid": get_muid_from_path(Path(str(path).removeprefix("/"))),
                    "language": get_language(Path(path)),
                    "is_parent": Path(path).parts[-1] == target_path.parts[-1],
                    "path": path,
                }
            )
        results.sort(
            key=lambda x: (
                not x["muid"].startswith("root"),
                x["muid"],
                not x["is_parent"],
                sort_paths(set(data)).index(x["path"]),
            )
        )
        return JSONResponse(status_code=200, content={"message": "Dry run successful", "results": results})
    main_path_task_id, related_paths_task_id = remover.delete()
    return JSONResponse(
        status_code=200,
        content={
            "message": "Deletion successful",
            "main_task_id": main_path_task_id,
            "related_paths_task_id": related_paths_task_id,
        },
    )
