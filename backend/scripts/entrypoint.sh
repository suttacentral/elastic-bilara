#!/bin/bash

for branch in published unpublished
do
  dir="/app/checkouts/$branch"

  if [ -d "$dir/.git" ]; then
    echo "Repository exists in $dir, pulling latest changes..."
    git -C "$dir" pull

  else
    echo "No repository in $dir, cloning..."
    git clone -b "$branch" "$BILARA_DATA_REPO" "$dir"
  fi
done

exec poetry run uvicorn app.main:app --host 0.0.0.0 --port $DOCKER_BACKEND_PORT --reload