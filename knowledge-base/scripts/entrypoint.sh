#!/bin/bash
set -e

/usr/local/bin/docker-entrypoint.sh eswrapper &

until curl -s http://localhost:9200 >/dev/null; do
  echo "Waiting for Elasticsearch..."
  sleep 5
done

if [ "$SEARCH_BACKUP" = "on" ]; then
  echo "Triggering Elasticsearch S3 backup..."
  curl -X PUT "http://localhost:9200/_snapshot/s3_backup/snapshot_$(date +%Y%m%d%H%M)" \
    -H 'Content-Type: application/json' \
    -d '{"indices": "_all"}'
else
  echo "Backup skipped (SEARCH_BACKUP is not 'on')"
fi

wait

