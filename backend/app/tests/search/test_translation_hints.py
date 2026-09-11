from inspect import isawaitable
from threading import get_ident
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.api_v1.endpoints import search as endpoint
from app.services.users.permissions import is_user_active
from search.search import Search


@pytest.fixture
def hints_index(monkeypatch):
    search = object.__new__(Search)
    client = Mock()
    search._search = client
    monkeypatch.setattr(endpoint, "es", search)
    documents = []
    cursors = {}

    def response(rows, size, cursor):
        cursors[cursor] = (rows[size:], size)
        return {"_scroll_id": cursor, "hits": {"hits": [{"_source": row} for row in rows[:size]]}}

    def query(*, index, body, size, scroll=None):
        # Documents are supplied in Elasticsearch relevance order. Only the
        # transport is mocked; pagination, joining and aggregation run normally.
        rows = documents[:]
        clauses = body["query"]["bool"]
        for clause in clauses.get("must", []) + clauses.get("filter", []):
            if "terms" in clause:
                rows = [row for row in rows if row["uid"] in clause["terms"]["uid"]]
            for kind in ("term", "match"):
                if kind in clause:
                    rows = [row for row in rows if row["muid"] == clause[kind]["muid"]]
        if scroll:
            return response(rows, size, str(len(cursors)))
        return {
            "hits": {
                "total": {"value": len(rows), "relation": "eq"},
                "hits": [{"_source": row} for row in rows[:size]],
            }
        }

    def next_page(*, scroll_id, scroll):
        rows, size = cursors[scroll_id]
        return response(rows, size, scroll_id)

    client.search.side_effect = query
    client.scroll.side_effect = next_page

    def populate(rows):
        documents.extend(rows)

    populate.client = client
    populate.search = search

    yield populate
    assert {call.kwargs["scroll_id"] for call in client.clear_scroll.call_args_list} == set(cursors)


def segment(uid, text, muid="root-pli-ms"):
    return {"uid": uid, "segment": text, "muid": muid}


async def hints(uid="sn16.3:1.1", text="Sāvatthiyaṁ viharati."):
    result = endpoint.get_translation_hints("root-pli-ms", "translation-it-soma", uid, text)
    return await result if isawaitable(result) else result


@pytest.mark.parametrize("count", [0, 1, 3])
def test_translation_lookup_uses_one_request_when_results_fit(hints_index, count):
    uids = [f"sn1:{i}" for i in range(3)]
    documents = [segment(uid, "Translation", "translation-it-soma") for uid in uids[:count]]
    hints_index(documents)

    assert hints_index.search.get_segment_value_for_uids_and_muid(uids, "translation-it-soma") == documents
    client = hints_index.client
    client.search.assert_called_once()
    assert "scroll" not in client.search.call_args.kwargs
    assert client.search.call_args.kwargs["body"]["track_total_hits"] is True
    client.scroll.assert_not_called()
    client.clear_scroll.assert_not_called()


def test_translation_lookup_empty_uids_makes_no_request(hints_index):
    assert hints_index.search.get_segment_value_for_uids_and_muid([], "translation-it-soma") == []
    hints_index.client.search.assert_not_called()


@pytest.mark.parametrize("count", [2, 10001])
def test_translation_lookup_pages_duplicate_uids_without_truncation(hints_index, count):
    documents = [
        {**segment("sn1:1", "Translation", "translation-it-soma"), "main_doc_id": str(i)}
        for i in range(count)
    ]
    hints_index(documents)

    result = hints_index.search.get_segment_value_for_uids_and_muid(["sn1:1"], "translation-it-soma")

    assert result == documents
    assert len({row["main_doc_id"] for row in result}) == count
    assert "scroll" not in hints_index.client.search.call_args_list[0].kwargs
    assert hints_index.client.search.call_count == 2
    assert hints_index.client.scroll.called


async def test_hints_query_runs_outside_event_loop_thread(monkeypatch):
    app = FastAPI()
    app.include_router(endpoint.router)
    app.dependency_overrides[is_user_active] = lambda: True
    query_threads = []

    def query(*args):
        query_threads.append(get_ident())
        return []

    monkeypatch.setattr(endpoint.es, "get_translation_hints", query)
    loop_thread = get_ident()
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(
            "/search/hints/",
            params={
                "source_muid": "root-pli-ms",
                "target_muid": "translation-it-soma",
                "segment_id": "sn16.3:1.1",
                "text_value": "Sāvatthiyaṁ viharati.",
            },
        )
    assert response.status_code == 200
    assert query_threads and all(thread != loop_thread for thread in query_threads)


async def test_frequent_phrase_batches_requests_without_losing_late_counts(hints_index):
    documents = [segment(f"sn1:{i}", "evaṁ me sutaṁ") for i in range(21275)]
    for i in (0, 10001, 21274):
        documents.append(segment(f"sn1:{i}", "Così ho udito.", "translation-it-soma"))
    hints_index(documents)

    result = await hints(text="evaṁ me sutaṁ")

    assert len(result) == 1
    assert result[0].strength == 3
    client = hints_index.client
    requests = client.search.call_count + client.scroll.call_count + client.clear_scroll.call_count
    assert requests <= 20


async def test_hints_find_translations_after_untranslated_candidates_and_across_pages(hints_index):
    documents = [segment(f"sn1:{i}", "Sāvatthiyaṁ viharati.") for i in range(1100)]
    for i in range(300):
        uid = f"sn2:{i}"
        documents.extend(
            [
                segment(uid, "Sāvatthiyaṁ viharati. Longer source text."),
                segment(uid, "A Sāvatthī.", "translation-it-soma"),
            ]
        )
    hints_index(documents)

    result = await hints()

    assert len(result) == 1
    assert result[0].translation_hints == "A Sāvatthī."
    assert result[0].strength == 300


async def test_current_segment_is_excluded_before_aggregating_same_translation(hints_index):
    hints_index(
        [
            segment("sn16.3:1.1", "Sāvatthiyaṁ viharati."),
            segment("sn16.3:1.1", "A Sāvatthī.", "translation-it-soma"),
            segment("sn12.2:1.1", "Sāvatthiyaṁ viharati. Longer source text."),
            segment("sn12.2:1.1", "A Sāvatthī.", "translation-it-soma"),
        ]
    )

    result = await hints()

    assert len(result) == 1
    assert result[0].uid == "sn12.2:1.1"
    assert result[0].strength == 1


async def test_blank_and_other_project_translations_are_not_hints(hints_index):
    hints_index(
        [
            segment("sn1:1", "Sāvatthiyaṁ viharati."),
            segment("sn1:1", "  ", "translation-it-soma"),
            segment("sn1:1", "Elsewhere", "translation-en-test"),
        ]
    )
    assert await hints() == []


@pytest.mark.parametrize("translation_fields", [{"segment": None}, {}, {"segment": ""}, {"segment": " \t\n"}])
async def test_empty_translation_values_do_not_hide_valid_hints(hints_index, translation_fields):
    hints_index(
        [
            segment("sn1:1", "Sāvatthiyaṁ viharati."),
            {"uid": "sn1:1", "muid": "translation-it-soma", **translation_fields},
            segment("sn1:2", "Sāvatthiyaṁ viharati."),
            segment("sn1:2", "A Sāvatthī.", "translation-it-soma"),
        ]
    )

    result = await hints()

    assert len(result) == 1
    assert result[0].uid == "sn1:2"
    assert result[0].translation_hints == "A Sāvatthī."
    assert result[0].strength == 1


async def test_empty_source_has_no_hints(hints_index):
    assert await hints(text="  ") == []


async def test_limit_applies_after_translation_deduplication(hints_index):
    documents = []
    for i in range(30):
        documents.extend(
            [
                segment(f"sn1:{i}", "Sāvatthiyaṁ viharati."),
                segment(f"sn1:{i}", "Repeated translation", "translation-it-soma"),
            ]
        )
    for i in range(25):
        documents.extend(
            [
                segment(f"sn2:{i}", "Sāvatthiyaṁ viharati."),
                segment(f"sn2:{i}", f"Distinct translation {i}", "translation-it-soma"),
            ]
        )
    documents.extend(
        [
            segment("sn3:1", "Sāvatthiyaṁ viharati."),
            segment("sn3:1", "Repeated translation", "translation-it-soma"),
        ]
    )
    hints_index(documents)

    result = await hints()

    assert len(result) == 20
    assert result[0].strength == 31
    assert [hint.translation_hints for hint in result[1:]] == [f"Distinct translation {i}" for i in range(19)]
