import sys
import os

sys.path.append("/home/hongda/eb/elastic-bilara/backend")

from search.search import Search
from app.core.config import settings
import json

s = Search()

query = {
    "size": 0,
    "query": {
        "wildcard": {
            "prefix": {
                "value": "*-*"
            }
        }
    },
    "aggs": {
        "prefixes_with_hyphen": {
            "terms": {
                "field": "prefix",
                "size": 10000
            }
        }
    }
}

res = s._search.search(index=settings.ES_INDEX, body=query)
buckets = res.get("aggregations", {}).get("prefixes_with_hyphen", {}).get("buckets", [])

prefixes = [b["key"] for b in buckets]
print(json.dumps(prefixes))
