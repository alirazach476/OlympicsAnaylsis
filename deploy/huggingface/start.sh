#!/bin/sh
# Download the warehouse from the Hugging Face dataset repo (first boot only), then start the API.
set -e
DB=/app/data/olympics_warehouse.db
if [ ! -s "$DB" ]; then
  echo "Downloading the Olympics warehouse from ${WAREHOUSE_REPO} ..."
  python -c "
import os, shutil
from huggingface_hub import hf_hub_download
p = hf_hub_download(repo_id=os.environ['WAREHOUSE_REPO'], repo_type='dataset', filename='olympics_warehouse.db', token=os.environ.get('HF_TOKEN'))
shutil.copy(p, '$DB') if not os.path.exists('$DB') else None
print('warehouse ready', os.path.getsize('$DB') // 2**20, 'MB')
"
fi
exec uvicorn backend.api.main:app --host 0.0.0.0 --port 7860 --workers 2
