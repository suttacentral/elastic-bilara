from pathlib import Path
from typing import Any, Generator, List

from app.core.config import settings
from elasticsearch import Elasticsearch, helpers

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
            for data in self._yield_data():
                actions: list[dict[str, Any]] = [{"_index": index, "_source": document} for document in data]
                helpers.bulk(
                    self._search,
                    actions,
                    chunk_size=self._batch_size,
                    raise_on_error=True,
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
        prefix: str = utils.get_prefix(file_path)
        filename: str = utils.get_filename(file_path)
        segments: list[dict[str, str]] = self._prepare_json_data(utils.get_json_data(file_path))
        muid: str = utils.get_muid(file_path)
        is_root: bool = utils.is_root(file_path)
        root_path: Path | None = utils.find_root_path(file_path)
        return {
            "file_path": str(file_path),
            "prefix": prefix,
            "filename": filename,
            "segments": segments,
            "muid": muid,
            "is_root": is_root,
            "root_path": str(root_path) if root_path else None,
        }

    def _prepare_json_data(self, data: dict[str, str]) -> List[dict[str, str]]:
        return [{"uid": item, "segment": data[item]} for item in data]

    def _index_exists(self, index: str) -> bool:
        return self._search.indices.exists(index=index)

    def _is_index_empty(self, index: str) -> bool:
        return self._search.count(index=index)["count"] == 0
