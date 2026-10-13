from uuid import uuid4

import pytest
from app.core.config import settings
from search.search import Search


@pytest.fixture
def uid_search(monkeypatch):
    search = Search()
    index = f"test-uid-search-{uuid4().hex}"
    monkeypatch.setattr(settings, "ES_SEGMENTS_INDEX", index)
    try:
        search._search.indices.create(
            index=index,
            settings={**search._get_es_settings(), "number_of_replicas": 0},
            mappings=search._get_es_mappings("segments"),
        )
        for uid in ("sn1.1:1.1", "sn2.1:1.1", "mn1:1.1", "an1:1.1", "dn1:1.1", "sn3.1:1.1"):
            for muid in ("translation-en-test", "root-pli-test"):
                search._search.index(
                    index=index,
                    document={"uid": uid, "muid": muid, "segment": "unrelated" if uid == "sn3.1:1.1" else "needle"},
                )
        search._search.indices.refresh(index=index)
        yield search
    finally:
        search._search.options(ignore_status=404).indices.delete(index=index)


@pytest.mark.parametrize("text", ["", "needle"])
@pytest.mark.parametrize(
    "uid, clause",
    [
        ("sn", {"prefix": {"uid": {"value": "sn"}}}),
        (" SN% ", {"wildcard": {"uid": {"value": "sn*"}}}),
        ("sn%:1.1", {"wildcard": {"uid": {"value": "sn*:1.1"}}}),
        ("sn?%", {"wildcard": {"uid": {"value": "sn\\?*"}}}),
    ],
)
def test_query_applies_uid_globally(text, uid, clause):
    search = object.__new__(Search)
    query = search._build_search_body({"translation-en-test": "", "root-pli-test": text}, uid)["query"]["bool"]
    assert query["filter"] == [clause]
    if text:
        assert query["minimum_should_match"] == 1
        assert len(query["should"]) == 1


@pytest.mark.parametrize("uid", [None, "", "   "])
def test_query_blank_uid_has_no_filter(uid):
    search = object.__new__(Search)
    query = search._build_search_body({"root-pli-test": "needle"}, uid)["query"]["bool"]
    assert "filter" not in query


@pytest.mark.parametrize("uid", ["sn", "sn%", "SN%", "  SN%  "])
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("text", ["", "needle"])
def test_uid_limits_all_projects_and_pages(uid_search, uid, reverse, text):
    fields = {"translation-en-test": "", "root-pli-test": text}
    if reverse:
        fields = dict(reversed(list(fields.items())))
    expected = {"sn1.1:1.1", "sn2.1:1.1"}
    if not text:
        expected.add("sn3.1:1.1")
    results = uid_search.get_segments(100, 0, {**fields, "uid": uid})
    assert set(results) == expected
    assert all(set(segments) == set(fields) for segments in results.values())
    pages = [uid_search.get_segments(1, page, {**fields, "uid": uid}) for page in range(len(expected) + 1)]
    assert all(len(page) == 1 for page in pages[:-1])
    assert pages[-1] == {}
    assert {key for page in pages for key in page} == expected


@pytest.mark.parametrize("uid", [None, "", "   "])
def test_blank_uid_preserves_text_search(uid_search, uid):
    results = uid_search.get_segments(100, 0, {"uid": uid, "root-pli-test": "needle"})
    assert set(results) == {"sn1.1:1.1", "sn2.1:1.1", "mn1:1.1", "an1:1.1", "dn1:1.1"}


def test_uid_pattern_supports_internal_percent(uid_search):
    results = uid_search.get_segments(100, 0, {"uid": "SN%:1.1", "root-pli-test": ""})
    assert set(results) == {"sn1.1:1.1", "sn2.1:1.1", "sn3.1:1.1"}


def test_uid_and_text_are_both_required(uid_search):
    results = uid_search.get_segments(100, 0, {"uid": "sn", "root-pli-test": "absent"})
    assert results == {}


@pytest.fixture
def partial_projects(uid_search, monkeypatch):
    # Force transport boundaries, including a batch with no eligible UID.
    monkeypatch.setattr(uid_search, "_search_uid_batch_size", 2)
    root, target, extra = "root-pli-partial", "translation-en-partial", "translation-de-partial"
    rows = {
        "sn10:1": {root: "needle"},
        "sn10:2": {target: "translation"},
        "sn10:3": {root: "needle", target: ""},
        "sn10:4": {root: "needle", target: "translation", extra: "extra"},
        "sn10:5": {root: "needle", target: "translation"},
        "mn10:1": {root: "needle", target: "translation", extra: "extra"},
    }
    for uid, segments in rows.items():
        for muid, segment in segments.items():
            uid_search._search.index(index=settings.ES_SEGMENTS_INDEX, document={
                "uid": uid, "muid": muid, "segment": segment,
            })
    # Duplicate source documents must never substitute for a missing target.
    uid_search._search.index(index=settings.ES_SEGMENTS_INDEX, document={
        "uid": "sn10:1", "muid": root, "segment": "needle",
    })
    uid_search._search.indices.refresh(index=settings.ES_SEGMENTS_INDEX)
    return uid_search, root, target, extra


@pytest.mark.parametrize("text", ["", "needle"])
@pytest.mark.parametrize("uid", ["sn10:", "SN10:%", "sn%:3"])
def test_required_projects_and_optional_display_are_consistent(partial_projects, text, uid):
    search, root, target, extra = partial_projects
    fields = {"uid": uid, root: text, target: "", extra: ""}
    roles = {"source_muid": root, "target_muid": target}
    expected = {"sn10:3", "sn10:4", "sn10:5"} if uid != "sn%:3" else {"sn10:3"}
    results = search.get_segments(100, 0, fields, **roles)
    assert set(results) == expected
    assert results["sn10:3"] == {root: "needle", target: ""}
    if "sn10:4" in results:
        assert results["sn10:4"][extra] == "extra"
        assert extra not in results["sn10:5"]
    # Missing optional records must not consume pages or cause early termination.
    pages = [search.get_segments(1, page, fields, **roles) for page in range(len(expected) + 1)]
    assert all(len(page) == 1 for page in pages[:-1])
    assert pages[-1] == {}
    assert {key for page in pages for key in page} == expected
    assert fields["uid"] == uid


def test_extra_keyword_is_required_and_all_keywords_must_match(partial_projects):
    search, root, target, extra = partial_projects
    fields = {"uid": "sn10:", root: "needle", target: "translation", extra: "extra"}
    roles = {"source_muid": root, "target_muid": target}
    assert set(search.get_segments(100, 0, fields, **roles)) == {"sn10:4"}
    assert search.get_segments(100, 0, {**fields, extra: "absent"}, **roles) == {}


def test_text_search_without_uid_still_requires_current_translation(partial_projects):
    search, root, target, extra = partial_projects
    results = search.get_segments(100, 0, {root: "needle", target: "", extra: ""},
                                  source_muid=root, target_muid=target)
    assert set(results) == {"sn10:3", "sn10:4", "sn10:5", "mn10:1"}


def test_absent_keyword_does_not_scan_required_projects(partial_projects, mocker):
    search, root, target, _ = partial_projects
    requests = mocker.patch.object(search._search, "search", wraps=search._search.search)
    results = search.get_segments(100, 0, {root: "absent", target: ""},
                                  source_muid=root, target_muid=target)
    assert results == {}
    assert requests.call_count == 1


@pytest.mark.parametrize("keyword_project", ["root", "target", "extra"])
def test_sparse_keyword_only_checks_matching_uids(partial_projects, mocker, keyword_project):
    search, root, target, extra = partial_projects
    keyword_muid = {"root": root, "target": target, "extra": extra}[keyword_project]
    # Many unrelated records in the required projects must not add search pages.
    for number in range(20):
        for muid in (root, target):
            search._search.index(index=settings.ES_SEGMENTS_INDEX, document={
                "uid": f"sn20:{number}", "muid": muid, "segment": "unrelated",
            })
    for uid, segments in {
        "sn20:90": {keyword_muid: "rareword"},
        "sn20:91": {root: "", target: "", extra: ""},
    }.items():
        segments[keyword_muid] = "rareword"
        for muid, segment in segments.items():
            search._search.index(index=settings.ES_SEGMENTS_INDEX, document={
                "uid": uid, "muid": muid, "segment": segment,
            })
    if keyword_project == "extra":
        # Multiple source records cannot substitute for the missing target.
        for _ in range(2):
            search._search.index(index=settings.ES_SEGMENTS_INDEX, document={
                "uid": "sn20:90", "muid": root, "segment": "",
            })
    search._search.indices.refresh(index=settings.ES_SEGMENTS_INDEX)
    fields = {root: "", target: "", extra: "", keyword_muid: "rareword"}
    requests = mocker.patch.object(search._search, "search", wraps=search._search.search)
    results = search.get_segments(1, 0, fields, source_muid=root, target_muid=target)
    assert set(results) == {"sn20:91"}
    assert results["sn20:91"][keyword_muid] == "rareword"
    # One candidate query, one bounded presence check, and one content fetch.
    assert requests.call_count == 3
    requests.reset_mock()
    assert search.get_segments(1, 1, fields, source_muid=root, target_muid=target) == {}
    # The terminal page has no content fetch; a final candidate query detects EOF.
    assert requests.call_count == 3


def test_presence_join_skips_rejected_batches_and_preserves_uid_order(partial_projects):
    search, root, target, _ = partial_projects
    for number in range(1, 5):
        search._search.index(index=settings.ES_SEGMENTS_INDEX, document={
            "uid": f"sn30:{number}", "muid": root, "segment": "batchword",
        })
        # The first candidate batch has no target. Duplicate target records make
        # presence aggregation order differ from the candidate UID order.
        for _ in range(number if number >= 3 else 0):
            search._search.index(index=settings.ES_SEGMENTS_INDEX, document={
                "uid": f"sn30:{number}", "muid": target, "segment": "",
            })
    search._search.indices.refresh(index=settings.ES_SEGMENTS_INDEX)
    fields = {root: "batchword", target: ""}
    roles = {"source_muid": root, "target_muid": target}
    assert list(search.get_segments(1, 0, fields, **roles)) == ["sn30:3"]
    assert list(search.get_segments(1, 1, fields, **roles)) == ["sn30:4"]
    assert search.get_segments(1, 2, fields, **roles) == {}


def test_source_only_page_does_not_require_a_target(partial_projects):
    search, root, _, extra = partial_projects
    results = search.get_segments(100, 0, {"uid": "sn10:", root: "", extra: ""}, source_muid=root)
    assert set(results) == {"sn10:1", "sn10:3", "sn10:4", "sn10:5"}


def test_range_file_prefixes_from_real_indexes(uid_search, monkeypatch):
    main_index = f"test-search-prefixes-{uuid4().hex}"
    monkeypatch.setattr(settings, "ES_INDEX", main_index)
    muid = "translation-en-test"
    try:
        uid_search._search.indices.create(index=main_index)
        for doc_id, uid, prefix in [
            ("range-file", "dhp148:4", "dhp146-156"),
            ("single-file", "dhp200:4", "dhp200"),
        ]:
            uid_search._search.index(index=main_index, id=doc_id, document={"prefix": prefix})
            uid_search._search.index(index=settings.ES_SEGMENTS_INDEX, document={
                "uid": uid, "muid": muid, "segment": "for life ends in death. ", "main_doc_id": doc_id,
            })
        uid_search._search.indices.refresh(index=settings.ES_SEGMENTS_INDEX)
        results = uid_search.get_segments(100, 0, {muid: "for life ends in death. "})
        assert set(results) == {"dhp148:4", "dhp200:4"}
        assert uid_search.get_segment_prefixes(results) == {
            "dhp148:4": {muid: "dhp146-156"}, "dhp200:4": {muid: "dhp200"},
        }
    finally:
        uid_search._search.options(ignore_status=404).indices.delete(index=main_index)
