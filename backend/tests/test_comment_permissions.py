import pytest

from app.services.projects.segment_permissions import is_comment_read_only, validate_comment_edits, ReadOnlyCommentError
from app.services.projects.structure_engine import build_preview, apply_edits, load_rules


@pytest.mark.parametrize("uid", ["an1.1:0.1", "an1.1:0.2", "an1.1:0.3", "an1.1:1.0", "an1.1:2.0", "an1.1:1.0.2", "an1.1:0", "an1.1:00.1"])
def test_zero_components_reject_comment(uid):
    assert is_comment_read_only("comment-en-u", uid)
    with pytest.raises(ReadOnlyCommentError, match=uid):
        validate_comment_edits("comment-en-u", ["an1.1:1.1", uid])


@pytest.mark.parametrize("uid", ["an1.1:10.1", "an1.1:1.20", "an10.0:1.1", "an1.1:1.2", "an1.1:10"])
def test_nonzero_components_allow_comment(uid):
    assert not is_comment_read_only("comment-en-u", uid)
    validate_comment_edits("comment-en-u", [uid])


@pytest.mark.parametrize("muid", ["translation-en-u", "root-pli-ms", "html-pli-ms", "tag-en-u", "remarks:1"])
def test_other_types_are_unaffected(muid):
    validate_comment_edits(muid, ["an1.1:0.1", "an1.1:1.0"])


@pytest.mark.parametrize("operation", ["split", "merge"])
def test_structure_automatic_results_allowed_but_manual_zero_comment_edits_rejected(operation):
    root = "root/pli/ms/an1.1_root-pli-ms.json"
    files = {
        root: {"an1.1:0.1": "A", "an1.1:0.2": "B", "an1.1:1.1": "C"},
        "comment/en/u/an1.1_comment-en-u.json": {"an1.1:0.1": "a", "an1.1:0.2": "b", "an1.1:1.1": "c"},
    }
    preview = build_preview(files, root, operation, "an1.1:0.1", load_rules(operation))
    result = apply_edits(preview, {}, [])
    assert result["comment-en-u"] == preview["projects"][1]["data"]
    with pytest.raises(ReadOnlyCommentError):
        apply_edits(preview, {"comment-en-u": {"an1.1:0.1": "manual"}}, [])
    assert apply_edits(preview, {"comment-en-u": {"an1.1:1.1": "allowed"}}, [])["comment-en-u"]["an1.1:1.1"] == "allowed"
