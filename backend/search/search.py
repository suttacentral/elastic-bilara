from collections import Counter
from collections.abc import KeysView
from pathlib import Path
from typing import Any, Generator, List

from app.core.config import settings
from elasticsearch import Elasticsearch, RequestError, helpers

from . import utils


class Search:
    _instance = None

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
            self._populate_index(settings.ES_INDEX)

    def _create_index(self, index: str) -> None:
        if not self._index_exists(index):
            self._search.indices.create(
                index=index,
                settings=self._get_es_settings(),
                mappings=self._get_es_mappings(),
            )

    def _populate_index(self, index: str) -> None:
        if self._is_index_empty(index):
            self._search.indices.put_settings(
                index=index,
                body={"index": {"refresh_interval": "180s", "number_of_replicas": 0}},
            )
            for data in self._yield_data():
                actions: list[dict[str, Any]] = [
                    {
                        "_index": index,
                        "_id": document["_id"],
                        "_source": document["_source"],
                    }
                    for document in data
                ]
                helpers.bulk(
                    self._search,
                    actions,
                    chunk_size=self._batch_size,
                    raise_on_error=True,
                )
            self._search.indices.put_settings(
                index=index,
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

    def _get_es_mappings(self) -> dict:
        return {
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
                    },
                },
                "muid": {"type": "keyword"},
                "is_root": {"type": "boolean"},
                "root_path": {"type": "keyword"},
            }
        }

    def _yield_data(
        self,
    ) -> Generator[list, None, None]:
        buffer: list = []
        for file_path in utils.yield_file_path(settings.WORK_DIR):
            buffer.append(self._process_file(file_path))
            if len(buffer) >= self._batch_size:
                yield buffer
                buffer = []
        if buffer:
            yield buffer

    def _process_file(self, file_path: Path) -> dict[str, str | bool | None | list[dict[str, str]]]:
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

    def _build_unique_query(self, field: str = None, prefix: str = None) -> dict[str, Any]:
        query = {
            "size": 0,
            "aggs": {
                "unique_data": {
                    "terms": {
                        "field": field,
                        "size": self._search.count(index=settings.ES_INDEX)["count"],
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

    def _scroll_search(self, query) -> Generator:
        scroll = "1m"
        size = 1000
        response = self._search.search(index=settings.ES_INDEX, body=query, scroll=scroll, size=size)
        old_scroll_id = response["_scroll_id"]
        yield from response["hits"]["hits"]
        while len(response["hits"]["hits"]):
            response = self._search.scroll(scroll_id=old_scroll_id, scroll=scroll)
            old_scroll_id = response["_scroll_id"]
            yield from response["hits"]["hits"]

    def find_unique_data(self, field: str = None, prefix: str = None) -> list[str]:
        results = self._search.search(index=settings.ES_INDEX, body=self._build_unique_query(field, prefix))[
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

    def get_file_paths(self, muid: str, prefix: str = None, _type: str = "root_path") -> set[str]:
        query = {
            "query": {"bool": {"must": [{"term": {"muid": muid}}]}},
            "_source": [_type],
        }

        if prefix is not None:
            query["query"]["bool"]["must"].append({"match": {"prefix": prefix}})

        paths: set[str] = set()

        for hit in self._scroll_search(query):
            path = hit["_source"][_type]
            if path is not None:
                paths.add(path)

        return paths

    def update_segments(self, file_path: Path, data: dict[str, str]) -> tuple[bool, Exception | None]:
        doc_id: str = utils.create_doc_id(file_path)
        doc: dict[str, str | bool | None | list[dict[str, str]]] = self._search.get(index=settings.ES_INDEX, id=doc_id)[
            "_source"
        ]

        segments_dict: dict[str, dict[str, str]] = {segment["uid"]: segment for segment in doc["segments"]}

        for uid, new_segment in data.items():
            if uid in segments_dict:
                segments_dict[uid]["segment"] = new_segment
            else:
                segments_dict[uid] = {"uid": uid, "segment": new_segment}

        doc["segments"] = list(segments_dict.values())

        try:
            self._search.index(index=settings.ES_INDEX, id=doc_id, body=doc)
        except RequestError as e:
            return False, e
        return True, None

    def get_segments(self, **kwargs) -> dict[str, dict[str, str] | dict]:
        uid: str | None = kwargs.pop("uid", None)
        if uid:
            if any(kwargs.values()):
                return self._get_segments_by_uid_and_muids(uid, kwargs)
            else:
                return self._get_segments_by_uid(uid, kwargs.keys())
        if any(kwargs.values()):
            return self._get_segments_by_muids(kwargs)
        return {}

    def _build_get_segments_query(self, muid: str, uid: str = None, segment: str = None) -> dict[str, Any]:
        query: dict[str, Any] = {
            "bool": {
                "must": [
                    {"term": {"muid": muid}},
                ]
            }
        }
        if uid:
            query["bool"]["must"].append(
                {
                    "nested": {
                        "path": "segments",
                        "query": {"prefix": {"segments.uid": uid}},
                        "inner_hits": {"size": 100},
                    }
                }
            )
        if segment:
            query["bool"]["must"].append(
                {
                    "nested": {
                        "path": "segments",
                        "query": {"match_phrase": {"segments.segment": segment}},
                        "inner_hits": {"size": 100},
                    }
                }
            )
        return query

    def _get_segments_by_uid_and_muids(self, uid: str, muids: dict[str, str | None]) -> dict[str, dict[str, str]]:
        muid_data: dict[str, dict[str, str]] = self._get_segments_by_muids(muids)
        uid_data: dict[str, dict[str, str]] = self._get_segments_by_uid(uid, muids.keys())
        common_uids: set[str] = set.intersection(set(muid_data.keys()), set(uid_data.keys()))
        return {uid: uid_data[uid] for uid in common_uids if uid in uid_data}

    def _get_segments_by_muids(self, muids: dict[str, str | None]) -> dict[str, dict[str, str]]:
        result: dict[str, dict[str, str]] = {}
        for muid, segment in muids.items():
            es_result = self._search.search(
                index=settings.ES_INDEX,
                query=self._build_get_segments_query(muid=muid, segment=segment),
                size=1000,
            )
            result[muid] = self._get_inner_hits(es_result)
        common_uids: list[str] = self._get_common_uids(result)
        data: dict[str, dict[str, str]] = {}
        for common_uid in common_uids:
            if item := self._get_segments_by_uid(common_uid, result.keys()):
                data.update(item)
        return data

    def _get_segments_by_uid(self, uid: str, muids: KeysView[str]) -> dict[str, dict[str, str]]:
        result: dict[str, dict[str, str]] = {}
        for muid in muids:
            result[muid] = {}
            es_result = self._search.search(
                index=settings.ES_INDEX,
                query=self._build_get_segments_query(muid=muid, uid=uid),
                size=1000,
            )
            result[muid] = self._get_inner_hits(es_result)
        common_uids: list[str] = self._get_common_uids(result)
        return {
            common_uid: {muid: data.get(common_uid, "") for muid, data in result.items()} for common_uid in common_uids
        }

    def _get_inner_hits(self, es_result: dict[str, Any]) -> dict[str, str]:
        result: dict[str, str] = {}
        for hit in es_result["hits"]["hits"]:
            if inner_hits := hit.get("inner_hits"):
                data = inner_hits["segments"]["hits"]["hits"]
                for item in data:
                    result[item["_source"]["uid"]] = item["_source"]["segment"]
        return result

    def _get_common_uids(self, data: dict[str, dict[str, str]]) -> list[str]:
        uids: Counter[str] = Counter([uid for d in data.values() for uid in d.keys()])
        common_uids: list[str] = [uid for uid, count in uids.items() if count > 1]
        if not common_uids:
            common_uids = [uid for uid, count in uids.items() if count == 1]
        return common_uids
