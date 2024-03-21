from pathlib import Path
from typing import Any, Generator, List

from app.core.config import settings
from elasticsearch import Elasticsearch, NotFoundError, RequestError, helpers

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

    def get_segments(self, size: int, page: int, muids: dict[str, str]) -> dict[str, dict[str, str]] | dict:
        from_: int = page * size
        uid: str | None = muids.pop("uid", None)
        if uid:
            if any(muids.values()):
                return self._uid_muids_lookup(size, from_, uid, muids)
            else:
                return self._uid_lookup(size, from_, uid, muids)
        if any(muids.values()):
            return self._muids_lookup(size, from_, muids)
        return {}

    def _uid_lookup(self, size: int, from_: int, uid: str | None, muids: dict[str, str]) -> dict[str, dict[str, str]]:
        body: dict[str, Any] = self._build_search_body(size, from_, muids, uid)
        es_results: dict[str, Any] = self._search.search(
            index=settings.ES_SEGMENTS_INDEX,
            body=body,
        )
        return self._get_results(es_results)

    def _muids_lookup(self, size: int, from_: int, muids: dict[str, str]) -> dict[str, dict[str, str]]:
        body: dict[str, Any] = self._build_search_body(size, from_, muids)
        es_results: dict[str, Any] = self._search.search(
            index=settings.ES_SEGMENTS_INDEX,
            body=body,
        )
        return self._sort_segments(self._get_segments_for_remaining_muids(self._get_results(es_results), muids))

    def _uid_muids_lookup(
        self, size: int, from_: int, uid: str | None, muids: dict[str, str]
    ) -> dict[str, dict[str, str]]:
        body: dict[str, Any] = self._build_search_body(size, from_, muids, uid)
        es_results: dict[str, Any] = self._search.search(
            index=settings.ES_SEGMENTS_INDEX,
            body=body,
        )
        return self._sort_segments(self._get_segments_for_remaining_muids(self._get_results(es_results), muids))

    def _build_search_body(
        self,
        size: int,
        from_: int,
        muids: dict[str, str],
        uid: str | None = None,
    ) -> dict[str, Any]:
        if uid and not any(muids.values()):
            doc_count = hits_size = len(muids)
            body: dict[str, Any] = {
                "query": {
                    "bool": {
                        "must": [
                            {"bool": {"should": [{"terms": {"muid": [*muids.keys()]}}]}},
                            {"prefix": {"uid": {"value": uid}}},
                        ]
                    }
                }
            }
        else:
            doc_count, hits_size = self._get_min_doc_count_and_hot_hits_size(muids)
            body: dict[str, Any] = {
                "query": {
                    "bool": {"should": []},
                }
            }
            for muid, lookup in muids.items():
                body["query"]["bool"]["should"].append(
                    {
                        "bool": {
                            "must": [
                                {"term": {"muid": {"value": muid}}},
                                {"match_phrase": {"segment": lookup}},
                            ]
                        }
                    }
                )
                if uid:
                    body["query"]["bool"]["should"][0]["bool"]["must"].append({"prefix": {"uid": {"value": uid}}})
        body["aggs"] = self._build_aggs(doc_count, hits_size, size, from_)
        body["size"] = 0
        return body

    def _get_min_doc_count_and_hot_hits_size(self, muids: dict[str, str]) -> tuple[int, int]:
        doc_count: int = sum(1 for v in muids.values() if v != "")
        hits_size: int = len(muids)
        return doc_count, hits_size

    def _build_aggs(self, doc_count: int, hits_size: int, size: int, from_: int) -> dict[str, Any]:
        return {
            "uids": {
                "terms": {
                    "field": "uid",
                    "min_doc_count": doc_count,
                    "size": 10000,
                },
                "aggs": {
                    "top_uid_hits": {
                        "top_hits": {
                            "_source": {"includes": ["muid", "segment"]},
                            "size": hits_size,
                        }
                    },
                    "uids_bucket_sort": {"bucket_sort": {"sort": [], "from": from_, "size": size}},
                },
            }
        }

    def _get_results(self, es_results: dict[str, Any]) -> dict[str, dict[str, str]]:
        results: dict[str, dict[str, str]] = {}
        for data in es_results["aggregations"]["uids"]["buckets"]:
            uid: str = data["key"]
            results[uid]: dict[str, str] = {}
            for hit in data["top_uid_hits"]["hits"]["hits"]:
                source: dict[str, str] = hit["_source"]
                results[uid][source["muid"]] = source["segment"]
        return results

    def _sort_segments(self, results: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
        return dict(sorted(results.items(), key=lambda item: len(item[1]), reverse=True))

    def _get_segments_for_remaining_muids(self, results, muids) -> dict[str, dict[str, str]]:
        if not results:
            return {}
        uids: list[str] = list(results.keys())
        muids_to_remove: list[str] = results[uids[0]].keys()
        for muid in muids_to_remove:
            del muids[muid]
        missing_data: dict[str, dict[str, str]] = self._get_missing_data(uids, muids.keys())
        data: dict[str, dict[str, str]] = {
            uid: {**results.get(uid, {}), **missing_data.get(uid, {})} for uid in set(results) | set(missing_data)
        }
        return data

    def _get_missing_data(self, uids, muids) -> dict[str, dict[str, str]]:
        size: int = len(uids) * len(muids)
        if size > 10000:
            return self._get_missing_data_by_chunks(uids, muids)
        body: dict[str, Any] = self._build_missing_data_body(uids, muids, size)
        es_results: dict[str, Any] = self._search.search(index=settings.ES_SEGMENTS_INDEX, body=body)
        results: dict[str, dict[str, str]] = {uid: {} for uid in uids}
        if hits := es_results.get("hits").get("hits"):
            for hit in hits:
                if source := hit.get("_source"):
                    results[source.get("uid")][source.get("muid")] = source.get("segment")
        return results

    def _get_missing_data_by_chunks(self, uids, muids) -> dict[str, dict[str, str]]:
        chunk_size: int = 10000
        results: dict[str, dict[str, str]] = {uid: {} for uid in uids}
        body: dict[str, Any] = self._build_missing_data_body(uids, muids, chunk_size)
        body["sort"] = [{"uid": "asc"}, {"muid": "asc"}]
        while True:
            es_results: dict[str, Any] = self._search.search(index=settings.ES_SEGMENTS_INDEX, body=body)

            if not es_results.get("hits").get("hits"):
                break

            for hit in es_results.get("hits").get("hits"):
                if source := hit.get("_source"):
                    results[source.get("uid")][source.get("muid")] = source.get("segment")

            last_hit: dict[str, Any] = es_results.get("hits").get("hits")[-1]
            body["search_after"] = last_hit.get("sort")
        return results

    def _build_missing_data_body(self, uids, muids, size) -> dict[str, Any]:
        return {
            "size": size,
            "query": {
                "bool": {
                    "must": [
                        {"terms": {"uid": [*uids]}},
                        {"bool": {"should": [{"terms": {"muid": [*muids]}}]}},
                    ]
                }
            },
        }

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

    def get_distinct_data(self, field: str, prefix: str = None) -> list[str]:
        query: dict[str, Any] = self._build_unique_query(field=field)
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

    def add_to_index(self, path: Path) -> tuple[bool, Exception | None]:
        data = self._process_file(path)
        source: dict[str, Any] = data["_source"]
        try:
            self._search.index(index=settings.ES_INDEX, id=data["_id"], body=data["_source"])
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
        if not paths:
            return
        self._process_data(index, segments_index, paths, delete)

    def delete_from_indexes(self, index, segments_index, paths: list[Path]):
        if not paths:
            return
        for path in paths:
            self._search.delete_by_query(index=index, body={"query": {"match": {"file_path": str(path)}}})
            self._search.delete_by_query(
                index=segments_index, body={"query": {"match": {"main_doc_id": utils.create_doc_id(path)}}}
            )

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
          