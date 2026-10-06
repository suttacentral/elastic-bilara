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
    query = search._build_search_body(10, 0, {"translation-en-test": "", "root-pli-test": text}, uid)["query"]["bool"]
    assert query["filter"] == [clause]
    if text:
        assert query["minimum_should_match"] == 1
        assert len(query["should"]) == 2


@pytest.mark.parametrize("uid", [None, "", "   "])
def test_query_blank_uid_has_no_filter(uid):
    search = object.__new__(Search)
    query = search._build_search_body(10, 0, {"root-pli-test": "needle"}, uid)["query"]["bool"]
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
