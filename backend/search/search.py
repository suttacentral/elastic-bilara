import logging
import string
from itertools import batched
from pathlib import Path
from typing import Any, Generator, Iterable, List

from app.core.config import settings
from elasticsearch import Elasticsearch, NotFoundError, RequestError, helpers

from . import utils

logger = logging.getLogger(__name__)


class Search:
    _instance = None
    # A transport page size, not a candidate limit. All pages are consumed.
    _hints_batch_size = 10000
    _search_uid_batch_size = 1000

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Search, cls).__new__(cls)
            cls._instance._search = None
        return cls._instance

    def __init__(self):
        self._batch_size: int = 125
        if self._search is None:
            self._search = Elasticsearch(
                [
                    {
                        "host": settings.ES_HOST,
                        "port": settings.ES_REQUESTS_PORT,
                        "scheme": settings.ES_SCHEME,
                    }
                ],
                basic_auth=(settings.ELASTIC_USERNAME, settings.ELASTIC_PASSWORD),
                ca_certs=str(utils.get_ca_cert_path()),
            )
            self._search.options(ignore_status=400)
            self._create_index(settings.ES_INDEX)
            self._create_index(settings.ES_SEGMENTS_INDEX)
            self._populate_index(settings.ES_INDEX, settings.ES_SEGMENTS_INDEX)

    def _create_index(self, index: str) -> None:
        if not self._index_exists(index):
            mapping = self._get_es_mappings() if index == settings.ES_INDEX else self._get_es_mappings("segments")
            self._search.indices.create(
                index=index,
                settings=self._get_es_settings(),
                mappings=mapping,
            )

    def _populate_index(self, index: str, segments_index: str) -> None:
        if self._is_index_empty(index):
            self._search.indices.put_settings(
                index=index,
                body={"index": {"refresh_interval": "180s", "number_of_replicas": 0}},
            )
            self._search.indices.put_settings(
                index=segments_index,
                body={"index": {"refresh_interval": "180s", "number_of_replicas": 0}},
            )
            self._process_data(index, segments_index)
            self._search.indices.put_settings(
                index=index,
                body={"index": {"refresh_interval": "1s", "number_of_replicas": 1}},
            )
            self._search.indices.put_settings(
                index=segments_index,
                body={"index": {"refresh_interval": "1s", "number_of_replicas": 1}},
            )

    def _get_es_settings(self) -> dict:
        return {
            "analysis": {
                "analyzer": {
                    "lowercase_analyzer": {
                        "type": "custom",
                        "tokenizer": "standard",
                        "filter": ["lowercase"],
                    }
                }
            }
        }

    def _get_es_mappings(self, _type="main") -> dict:
        if _type == "main":
            mapping = {
                "properties": {
                    "file_path": {"type": "keyword"},
                    "prefix": {"type": "keyword"},
                    "filename": {"type": "keyword"},
                    "segments": {
                        "type": "nested",
                        "properties": {
                            "uid": {"type": "keyword"},
                            "segment": {
                                "type": "text",
                                "analyzer": "lowercase_analyzer",
                                "search_analyzer": "lowercase_analyzer",
                            },
                            "muid": {"type": "keyword"},
                        },
                    },
                    "muid": {"type": "keyword"},
                    "is_root": {"type": "boolean"},
                    "root_path": {"type": "keyword"},
                }
            }
        elif _type == "segments":
            mapping = {
                "properties": {
                    "main_doc_id": {"type": "keyword"},
                    "muid": {"type": "keyword"},
                    "uid": {"type": "keyword"},
                    "segment": {
                        "type": "text",
                        "analyzer": "lowercase_analyzer",
                        "search_analyzer": "lowercase_analyzer",
                    },
                }
            }
        return mapping

    def _yield_data(self, custom_file_paths: list[Path] = None) -> Generator[list, None, None]:
        buffer: list = []
        iterator = custom_file_paths if custom_file_paths else utils.yield_file_path(settings.WORK_DIR)
        for file_path in iterator:
            buffer.append(self._process_file(file_path))
            if len(buffer) >= self._batch_size:
                yield buffer
                buffer = []
        if buffer:
            yield buffer

    @staticmethod
    def _is_indexable_path(path: Path) -> bool:
        try:
            relative_path = path.relative_to(settings.WORK_DIR)
        except ValueError:
            return False
        return (
            len(relative_path.parts) > 1
            and path.suffix == ".json"
            and all(not part.startswith(".") for part in relative_path.parts)
        )

    def _process_file(self, file_path: Path) -> dict[str, Any]:
        doc_id: str = utils.create_doc_id(file_path)
        prefix: str = utils.get_prefix(file_path)
        filename: str = utils.get_filename(file_path)
        segments: list[dict[str, str]] = self._prepare_json_data(utils.get_json_data(file_path))
        muid: str = utils.get_muid(file_path)
        is_root: bool = utils.is_root(file_path)
        root_path: Path | None = utils.find_root_path(file_path)
        return {
            "_id": doc_id,
            "_source": {
                "file_path": str(file_path),
                "prefix": prefix,
                "filename": filename,
                "segments": segments,
                "muid": muid,
                "is_root": is_root,
                "root_path": str(root_path) if root_path else None,
            },
        }

    def _prepare_json_data(self, data: dict[str, str]) -> List[dict[str, str]]:
        return [{"uid": item, "segment": data[item]} for item in data]

    def _index_exists(self, index: str) -> bool:
        return self._search.indices.exists(index=index)

    def _is_index_empty(self, index: str) -> bool:
        return self._search.count(index=index)["count"] == 0

    def _build_unique_query(self, field: str = None, prefix: str = None, size: int = 10000) -> dict[str, Any]:
        query = {
            "size": 0,
            "aggs": {
                "unique_data": {
                    "terms": {
                        "field": field,
                        "size": size,
                        "order": {
                            "_key": "asc",
                        },
                    }
                }
            },
        }
        if prefix:
            query["query"] = {"prefix": {field: prefix}}
        return query

    def _scroll_search(self, query, index: str = settings.ES_INDEX, size: int = 1000) -> Generator:
        scroll = "1m"
        response = self._search.search(index=index, body=query, scroll=scroll, size=size)
        scroll_id = response.get("_scroll_id")
        try:
            hits = response.get("hits", {}).get("hits", [])
            while hits:
                yield from hits
                response = self._search.scroll(scroll_id=scroll_id, scroll=scroll)
                scroll_id = response.get("_scroll_id", scroll_id)
                hits = response.get("hits", {}).get("hits", [])
        finally:
            if scroll_id:
                try:
                    self._search.clear_scroll(scroll_id=scroll_id)
                except Exception:
                    logger.debug("Failed to clear scroll context", exc_info=True)

    def find_unique_data(self, field: str = None, prefix: str = None, size: int = 10000) -> list[str]:
        results = self._search.search(index=settings.ES_INDEX, body=self._build_unique_query(field, prefix, size=size))[
            "aggregations"
        ]["unique_data"]["buckets"]
        return [result["key"] for result in results]

    def get_root_paths(self, text: str, field: str = "muid") -> set[str]:
        query = {"query": {"term": {field: text}}, "_source": ["root_path"]}
        root_paths: set[str] = set()

        for hit in self._scroll_search(query):
            root_path = hit["_source"]["root_path"]
            if root_path is not None:
                root_paths.add(root_path)

        return root_paths

    def get_file_paths(self, muid: str, prefix: str = None, exact: bool = False, _type: str = "root_path") -> set[str]:
        query = {
            "query": {"bool": {"must": [{"term": {"muid": muid}}]}},
            "_source": [_type],
        }

        if prefix is not None and not exact:
            query["query"]["bool"]["must"].append({"prefix": {"prefix": prefix}})
        elif prefix is not None and exact:
            query["query"]["bool"]["must"].append({"term": {"prefix": prefix}})

        paths: set[str] = set()
        for hit in self._scroll_search(query):
            path = hit["_source"][_type]
            if path is not None:
                paths.add(path)

        return paths

    def get_file_paths_for_split_merge(self, muid: str, prefix: str = None, exact: bool = False, _type: str = "root_path") -> set[str]:
        query = {
            "query": {
                "bool": {
                    "must": [],
                    "should": [
                        {"term": {"muid": muid}}
                    ]
                }
            },
            "_source": [_type],
        }
        exact = True
        if prefix is not None and not exact:
            query["query"]["bool"]["must"].append({"prefix": {"prefix": prefix + '_'}})
        elif prefix is not None and exact:
            query["query"]["bool"]["must"].append({"term": {"prefix": prefix}})

        paths: set[str] = set()
        for hit in self._scroll_search(query):
            path = hit["_source"][_type]
            if path is not None:
                paths.add(path)

        return paths

    def update_segments(self, file_path: Path, data: dict[str, str]) -> tuple[bool, Exception | None]:
        try:
            self.update_segments_main_index(file_path, data)
            self.update_segments_segments_index(file_path, data)
        except (RequestError, NotFoundError) as e:
            return False, e
        return True, None

    def update_segments_main_index(self, file_path: Path, data: dict[str, str]) -> None:
        doc_id: str = utils.create_doc_id(file_path)
        doc: dict[str, Any] = self._search.get(index=settings.ES_INDEX, id=doc_id)["_source"]

        segments_dict: dict[str, dict[str, str]] = {segment["uid"]: segment for segment in doc["segments"]}

        for uid, new_segment in data.items():
            if uid in segments_dict:
                segments_dict[uid]["segment"] = new_segment
            else:
                segments_dict[uid] = {"uid": uid, "segment": new_segment}

        doc["segments"] = list(segments_dict.values())
        self._search.index(index=settings.ES_INDEX, id=doc_id, body=doc)

    def update_segments_segments_index(self, file_path: Path, data: dict[str, str]) -> None:
        uids: list[str] = list(data.keys())
        doc_ids: list[str] = [utils.create_doc_id(file_path, uid) for uid in uids]
        for uid, doc_id in zip(uids, doc_ids):
            try:
                doc: dict[str, Any] = self._search.get(index=settings.ES_SEGMENTS_INDEX, id=doc_id)["_source"]
            except NotFoundError:
                doc: dict[str, Any] = {
                    "main_doc_id": utils.create_doc_id(file_path),
                    "muid": utils.get_muid(file_path),
                    "uid": uid,
                }
            doc["segment"] = data[uid]
            self._search.index(index=settings.ES_SEGMENTS_INDEX, id=doc_id, body=doc)

    def get_segments(
        self, size: int, page: int, muids: dict[str, str],
        *, source_muid: str | None = None, target_muid: str | None = None,
    ) -> dict[str, dict[str, str]]:
        fields = dict(muids)
        uid = (fields.pop("uid", None) or "").strip().lower()
        if not uid and not any(fields.values()):
            return {}
        body = self._build_search_body(fields, uid, source_muid=source_muid, target_muid=target_muid)
        presence_muids = [
            muid for muid, text in fields.items()
            if muid in (source_muid, target_muid) and not text
        ] if any(fields.values()) else []
        offset = page * size
        uids = []
        # Stream the UID join in key order. Apply its predicates before counting
        # offsets so missing projects cannot produce short pages or hide matches.
        while len(uids) < size:
            response = self._search.search(index=settings.ES_SEGMENTS_INDEX, body=body)
            group = response["aggregations"]["uids"]
            candidates = [
                bucket["key"]["uid"] for bucket in group["buckets"]
                if all(bucket[name]["doc_count"] for name in body["aggs"]["uids"]["aggs"])
            ]
            for candidate in self._filter_uids_by_projects(candidates, presence_muids):
                if offset:
                    offset -= 1
                else:
                    uids.append(candidate)
                    if len(uids) == size:
                        break
            if not group["buckets"] or "after_key" not in group:
                break
            body["aggs"]["uids"]["composite"]["after"] = group["after_key"]
        if not uids:
            return {}
        # Optional projects only supply display content after qualifying UIDs
        # have been selected. Read all documents, including duplicates across files.
        results = {uid: {} for uid in uids}
        query = {"query": {"bool": {"filter": [
            {"terms": {"uid": uids}}, {"terms": {"muid": list(fields)}},
        ]}}, "_source": ["uid", "muid", "segment"]}
        for hit in self._scroll_search(query, index=settings.ES_SEGMENTS_INDEX):
            source = hit["_source"]
            results[source["uid"]][source["muid"]] = source["segment"]
        return results

    def _filter_uids_by_projects(self, uids: list[str], muids: list[str]) -> list[str]:
        """Check project presence only for this batch of keyword-matching UIDs."""
        if not uids or not muids:
            return uids
        body = {
            "size": 0,
            "query": {"bool": {"filter": [
                {"terms": {"uid": uids}}, {"terms": {"muid": muids}},
            ]}},
            "aggs": {"uids": {
                # The query bounds the distinct keys, so these terms cannot truncate.
                "terms": {"field": "uid", "size": len(uids)},
                "aggs": {"projects": {"terms": {"field": "muid", "size": len(muids)}}},
            }},
        }
        response = self._search.search(index=settings.ES_SEGMENTS_INDEX, body=body)
        required = set(muids)
        eligible = {
            bucket["key"] for bucket in response["aggregations"]["uids"]["buckets"]
            if {project["key"] for project in bucket["projects"]["buckets"]} == required
        }
        return [uid for uid in uids if uid in eligible]

    def get_segment_prefixes(self, results: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
        """Resolve result locations through indexed file IDs, never by parsing a UID."""
        if not results:
            return {}
        muids = {muid for segments in results.values() for muid in segments}
        query = {
            "query": {"bool": {"filter": [
                {"terms": {"uid": list(results)}},
                {"terms": {"muid": sorted(muids)}},
            ]}},
            "_source": ["uid", "muid", "main_doc_id"],
        }
        locations = [
            hit["_source"]
            for hit in self._scroll_search(query, index=settings.ES_SEGMENTS_INDEX)
            if hit["_source"]["muid"] in results[hit["_source"]["uid"]]
        ]
        if not locations:
            return {}
        documents = self._search.mget(
            index=settings.ES_INDEX,
            body={"ids": sorted({item["main_doc_id"] for item in locations})},
            _source_includes=["prefix"],
        )["docs"]
        file_prefixes = {doc["_id"]: doc["_source"]["prefix"] for doc in documents if doc["found"]}
        prefixes: dict[str, dict[str, str]] = {}
        for item in locations:
            if item["main_doc_id"] in file_prefixes:
                prefixes.setdefault(item["uid"], {})[item["muid"]] = file_prefixes[item["main_doc_id"]]
        return prefixes

    def _build_search_body(
        self, muids: dict[str, str], uid: str | None = None,
        *, source_muid: str | None = None, target_muid: str | None = None,
    ) -> dict[str, Any]:
        uid = (uid or "").strip().lower()
        has_keywords = any(muids.values())
        required = []
        for muid, text in muids.items():
            # Presence-only roles are joined against matching UID batches later;
            # including them here would enumerate whole projects for rare keywords.
            if text or (not has_keywords and muid in (source_muid, target_muid)):
                clauses = [{"term": {"muid": muid}}]
                if text:
                    clauses.append({"match_phrase_prefix": {"segment": text}})
                required.append({"bool": {"must": clauses}})

        query = ({"should": required, "minimum_should_match": 1} if required
                 else {"must": [{"terms": {"muid": list(muids)}}]})
        if uid:
            query["filter"] = [self._build_uid_filter(uid)]

        # Count each required project's own matching documents. A duplicate in
        # one project must not satisfy the presence or text condition of another.
        aggregations = {
            f"required_{index}": {"filter": clause}
            for index, clause in enumerate(required)
        }
        return {
            "size": 0,
            "query": {"bool": query},
            "aggs": {"uids": {
                "composite": {
                    "size": self._search_uid_batch_size,
                    "sources": [{"uid": {"terms": {"field": "uid", "order": "asc"}}}],
                },
                "aggs": aggregations,
            }},
        }

    def _build_uid_filter(self, uid: str) -> dict[str, Any]:
        if "%" not in uid:
            return {"prefix": {"uid": {"value": uid}}}
        # Only % is a user wildcard; preserve literal Elasticsearch metacharacters.
        pattern = "".join("*" if char == "%" else "\\" + char if char in "\\*?" else char for char in uid)
        return {"wildcard": {"uid": {"value": pattern}}}

    def _process_data(
        self, index: str, segments_index: str, paths: list[Path] | Generator = None, delete: bool = False
    ):
        if delete:
            self.delete_from_indexes(index, segments_index, paths)
        else:
            for data in self._yield_data(paths):
                actions_main: list[dict[str, Any]] = []
                actions_segments: list[dict[str, Any]] = []
                for document in data:
                    source: dict[str, Any] = document["_source"]
                    main_doc = {
                        "_index": index,
                        "_id": document["_id"],
                        "_source": {**source},
                    }
                    actions_main.append(main_doc)
                    file_path = Path(source["file_path"])
                    for item in source["segments"]:
                        uid = item["uid"]
                        segments_doc = {
                            "_index": segments_index,
                            "_id": utils.create_doc_id(file_path, uid),
                            "_source": {
                                "main_doc_id": document["_id"],
                                "muid": source["muid"],
                                "uid": uid,
                                "segment": item["segment"],
                            },
                        }
                        actions_segments.append(segments_doc)
                helpers.bulk(
                    self._search,
                    actions_main,
                    chunk_size=self._batch_size,
                    raise_on_error=True,
                )
                helpers.bulk(
                    self._search,
                    actions_segments,
                    chunk_size=self._batch_size,
                    raise_on_error=True,
                )

    def get_distinct_data(self, field: str, prefix: str = None, size: int = 10000) -> list[str]:
        query: dict[str, Any] = self._build_unique_query(field=field, size=size)
        query["query"] = {"term": {"prefix": {"value": prefix}}}
        result: list[dict[str, Any]] = (
            self._search.search(index=settings.ES_INDEX, body=query)
            .get("aggregations")
            .get("unique_data")
            .get("buckets")
        )
        return [item["key"] for item in result]

    def is_in_index(self, query: dict[str, Any]):
        result: list[dict[str, Any]] = self._search.search(index=settings.ES_INDEX, query=query).get("hits").get("hits")
        data = []
        if result:
            data = [item.get("_source") for item in result]
        return bool(data)

    def add_to_index(self, path: Path, refresh: bool = False) -> tuple[bool, Exception | None]:
        data = self._process_file(path)
        source: dict[str, Any] = data["_source"]
        try:
            kwargs: dict[str, Any] = {"index": settings.ES_INDEX, "id": data["_id"], "body": data["_source"]}
            if refresh:
                kwargs["refresh"] = True
            self._search.index(**kwargs)
        except RequestError as e:
            return False, e
        segment_actions: list[dict[str, Any]] = []
        for item in source["segments"]:
            segments_doc = {
                "_index": settings.ES_SEGMENTS_INDEX,
                "_id": utils.create_doc_id(path, item["uid"]),
                "_source": {
                    "main_doc_id": data["_id"],
                    "muid": source["muid"],
                    "uid": item["uid"],
                    "segment": item["segment"],
                },
            }
            segment_actions.append(segments_doc)
        try:
            helpers.bulk(
                self._search,
                segment_actions,
                chunk_size=self._batch_size,
                raise_on_error=True,
            )
        except RequestError as e:
            return False, e
        return True, None

    def get_muids_by_prefix(self, prefix: str) -> set[str]:
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"prefix": {"prefix": prefix}},
                    ]
                }
            },
            "_source": ["muid", "file_path"],
        }
        return {
            hit["_source"]["muid"]
            for hit in self._scroll_search(query)
            if any(prefix == str(parent.name) for parent in Path(hit["_source"]["file_path"]).parents)
        }

    def update_indexes(self, index, segments_index, paths: list[Path], delete: bool = False):
        indexable_paths = [path for path in paths if self._is_indexable_path(path)]
        if not indexable_paths:
            return
        self._process_data(index, segments_index, indexable_paths, delete)

    def delete_from_indexes(self, index, segments_index, paths: list[Path]):
        if not paths:
            return
        for path in paths:
            self._search.delete_by_query(index=index, body={"query": {"match": {"file_path": str(path)}}})
            self._search.delete_by_query(
                index=segments_index, body={"query": {"match": {"main_doc_id": utils.create_doc_id(path)}}}
            )

    def replace_structure_segments(self, path: Path, previous_uids: list[str]) -> tuple[bool, Exception | None]:
        """Replace a known file snapshot without a stale delete-by-query snapshot.

        The structure journal supplies the previous UIDs. Stable document IDs
        make both deletes and upserts idempotent, including interrupted retries.
        Refresh explicitly so reads after confirmation see the committed result.
        """
        data = self._process_file(path)
        source = data['_source']
        current_uids = {item['uid'] for item in source['segments']}
        actions = [
            {'_op_type': 'delete', '_index': settings.ES_SEGMENTS_INDEX,
             '_id': utils.create_doc_id(path, uid)}
            for uid in set(previous_uids) - current_uids
        ]
        actions.extend({
            '_index': settings.ES_SEGMENTS_INDEX,
            '_id': utils.create_doc_id(path, item['uid']),
            '_source': {'main_doc_id': data['_id'], 'muid': source['muid'],
                        'uid': item['uid'], 'segment': item['segment']},
        } for item in source['segments'])
        _, errors = helpers.bulk(self._search, actions, chunk_size=self._batch_size,
                                 raise_on_error=False, refresh=True)
        failures = [error for error in errors
                    if not ('delete' in error and error['delete'].get('status') == 404)]
        if failures:
            return False, RuntimeError(f'Structure indexing failed: {failures}')
        self._search.index(index=settings.ES_INDEX, id=data['_id'], body=source, refresh=True)
        return True, None

    def remove_segments(self, path: Path) -> tuple[bool, Exception | None]:
        doc_id: str = utils.create_doc_id(path)
        try:
            if not path.exists():
                try:
                    self._search.delete(index=settings.ES_INDEX, id=doc_id)
                    self._search.delete_by_query(
                        index=settings.ES_SEGMENTS_INDEX, body={"query": {"term": {"main_doc_id": doc_id}}}
                    )
                except NotFoundError:
                    pass
                return True, None
            data = self._process_file(path)
            self._search.index(index=settings.ES_INDEX, id=doc_id, body=data["_source"])
            try:
                self._search.delete_by_query(
                    index=settings.ES_SEGMENTS_INDEX, body={"query": {"term": {"main_doc_id": doc_id}}}
                )
            except NotFoundError:
                pass
            segment_actions: list[dict[str, Any]] = []
            for item in data["_source"]["segments"]:
                segments_doc = {
                    "_index": settings.ES_SEGMENTS_INDEX,
                    "_id": utils.create_doc_id(path, item["uid"]),
                    "_source": {
                        "main_doc_id": doc_id,
                        "muid": data["_source"]["muid"],
                        "uid": item["uid"],
                        "segment": item["segment"],
                    },
                }
                segment_actions.append(segments_doc)
            helpers.bulk(
                self._search,
                segment_actions,
                chunk_size=self._batch_size,
                raise_on_error=True,
            )
            return True, None
        except RequestError as e:
            return False, e

    def get_phrase_similar_segments(self, phrase_value: str, source_muid: str) -> Generator[dict, None, None]:
        if not phrase_value or not phrase_value.strip():
            return

        query = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "multi_match": {
                                "query": phrase_value,
                                "fields": ["segment"],
                                "type": "best_fields",
                                "fuzziness": "AUTO",
                                "prefix_length": 2,
                                "max_expansions": 15,
                                "operator": "or",
                            }
                        },
                        {"match": {"muid": source_muid}},
                    ]
                }
            },
            "_source": ["segment", "muid", "uid"],
        }
        for hit in self._scroll_search(query, index=settings.ES_SEGMENTS_INDEX, size=self._hints_batch_size):
            yield hit["_source"]

    def get_segment_value_for_uids_and_muid(self, uids: list[str], muid: str) -> list[dict]:
        if not uids:
            return []
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"terms": {"uid": uids}},
                        {"term": {"muid": muid}},
                    ]
                }
            },
            "_source": ["segment", "uid", "muid"],
            "track_total_hits": True,
        }
        response = self._search.search(
            index=settings.ES_SEGMENTS_INDEX, body=query, size=min(len(set(uids)), self._hints_batch_size)
        )
        hits = response["hits"]
        if hits["total"]["value"] == len(hits["hits"]):
            return [hit["_source"] for hit in hits["hits"]]

        # UID uniqueness is not enforced across files. If there are more hits
        # than fit in one response, read one complete scroll snapshot rather
        # than mixing the initial page with a later view of the index.
        return [
            hit["_source"]
            for hit in self._scroll_search(query, index=settings.ES_SEGMENTS_INDEX, size=self._hints_batch_size)
        ]

    def get_translation_hints(
        self, text_value: str, source_muid: str, target_muid: str, segment_id: str, size: int = 20
    ) -> list[dict]:
        # Page through all source matches before limiting distinct translated
        # hints: untranslated hits must not consume the result budget.
        phrases = (
            phrase
            for phrase in self.get_phrase_similar_segments(text_value, source_muid)
            if phrase["uid"] != segment_id
        )

        def translated_phrases():
            for batch in batched(phrases, self._hints_batch_size):
                translations = self.get_segment_value_for_uids_and_muid([phrase["uid"] for phrase in batch], target_muid)
                yield from self.merge_segments_with_translation_hints(
                    batch, [translation for translation in translations if (translation.get("segment") or "").strip()]
                )

        return self.aggregate_similar_segments(translated_phrases(), size=size)

    @staticmethod
    def aggregate_similar_segments(hits: Iterable[dict], size: int | None = None) -> list[dict]:
        unique_segments_dict = {}
        for hit in hits:
            segment = hit["translation_hints"].lower()
            segment = segment.translate(str.maketrans("", "", string.punctuation))
            if segment not in unique_segments_dict:
                # Keep only the returned groups, but continue counting later
                # occurrences of those groups across all remaining pages.
                if size is not None and len(unique_segments_dict) >= size:
                    continue
                unique_segments_dict[segment] = hit
                unique_segments_dict[segment]["strength"] = 1
            else:
                unique_segments_dict[segment]["strength"] += 1
        return list(unique_segments_dict.values())

    @staticmethod
    def merge_segments_with_translation_hints(similar_phrases: Iterable[dict], translation_hints: list[dict]) -> list[dict]:
        hints_by_uid: dict[str, list[dict]] = {}
        for hint in translation_hints:
            hints_by_uid.setdefault(hint["uid"], []).append(hint)
        return [
            {**phrase, "translation_hints": hint["segment"]}
            for phrase in similar_phrases
            for hint in hints_by_uid.get(phrase["uid"], [])
        ]

    def get_uids(self, muid: str, prefix: str) -> list[str]:
        query = {
            "query": {"bool": {"must": [{"match": {"muid": muid}}, {"match": {"prefix": prefix}}]}},
            "_source": ["segments.uid"],
        }
        uids = []
        for hit in self._scroll_search(query):
            for seg in hit["_source"]["segments"]:
                uids.append(seg["uid"])
        return uids
