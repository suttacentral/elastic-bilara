BILARA_DATA_REPO=https://github.com/ihongda/bilara-data.git

for branch in published unpublished
do
  dir="./backend/checkouts/$branch"

  if [ -d "$dir/.git" ]; then
    echo "Repository exists in $dir, pulling latest changes..."
    git -C "$dir" pull

  else
    echo "No repository in $dir, cloning..."
    git clone -b "$branch" "$BILARA_DATA_REPO" "$dir"
  fi
done