#!/bin/bash

for branch in published unpublished
do
  dir="/app/checkouts/$branch"

  if [ -d "$dir/.git" ]; then
    echo "Repository exists in $dir, pulling latest changes..."
    if [ "$branch" = "unpublished" ]; then
      # Recover durable metadata/tag writes before Git can update the checkout.
      git -C "$dir" fetch
      poetry run python - "$dir" <<'PYTHON'
import subprocess
import sys
from app.services.git.checkout import checkout_lock
from app.services.publications.store import PublicationStore
from app.services.tags.store import TagStore
with checkout_lock(sys.argv[1]):
    PublicationStore(sys.argv[1]).recover()
    TagStore(sys.argv[1]).recover()
    subprocess.run(["git", "-C", sys.argv[1], "merge", "--no-edit", "@{u}"], check=True)
PYTHON
    else
      git -C "$dir" pull
    fi

  else
    echo "No repository in $dir, cloning..."
    git clone -b "$branch" "$BILARA_DATA_REPO" "$dir"
  fi
done

exec poetry run uvicorn app.main:app \
  --host 0.0.0.0 \
  --port $DOCKER_BACKEND_PORT \
  --ssl-keyfile=/app/certs/key.pem \
  --ssl-certfile=/app/certs/cert.pem \
  --workers 2 \
  --timeout-keep-alive 5
