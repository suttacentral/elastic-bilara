from pathlib import Path

import pytest
from fastapi import HTTPException

from app.services.directories.utils import is_prefix_in_uid, validate_root_data


class TestUtils:
    def test_is_prefix_in_uid_positive(self):
        assert is_prefix_in_uid("an1.1-10", "an1.1:0.1")
        assert is_prefix_in_uid("an1.1-10", "an1.2:0.8")
        assert is_prefix_in_uid("an1.1-10", "an1.10:5.2")
        assert is_prefix_in_uid("an1.1-10abc", "an1.7abc:5.2")
        assert is_prefix_in_uid("test1", "test1:1.5")
        assert is_prefix_in_uid("test1a", "test1a:1.5")

    def test_is_prefix_in_uid_negative(self):
        assert not is_prefix_in_uid("an1.1-10", "an1.11:0.1")
        assert not is_prefix_in_uid("an1.1-10", "bn1.1:0.1")
        assert not is_prefix_in_uid("an1.1-10", "an.2:0.8")
        assert not is_prefix_in_uid("an1.1-10", "")
        assert not is_prefix_in_uid("test1", "test2:1.5")
        assert not is_prefix_in_uid("test1", "ttest1:1.5")
        assert not is_prefix_in_uid("test1a", "test1:1.5")

    def test_validate_root_data_positive(self):
        path = Path("root/pli/ms/sutta/test/test1_root-pli-ms.json")
        assert validate_root_data(path, {"test1:0.1": "test", "test1:1.4": "test2"})

        assert validate_root_data(path, {"test1:0.5": "test", "test1:2.3": "test3"})

    def test_validate_root_data_no_data(self):
        path = Path("root/pli/ms/sutta/test/test1_root-pli-ms.json")
        with pytest.raises(HTTPException):
            validate_root_data(path, {})

    def test_validate_root_data_invalid_uid(self):
        path = Path("root/pli/ms/sutta/test/test1_root-pli-ms.json")
        with pytest.raises(HTTPException):
            validate_root_data(path, {"test1:0.1": "test", "test2:1.4": "test2"})

        with pytest.raises(HTTPException):
            validate_root_data(path, {"test2:0.5": "test", "test1:2.3": "test3"})
