#!/bin/bash
# scripts/release.sh -- Commands to run on every Heroku release

set -euo pipefail

python manage.py migrate --noinput
python manage.py createcachetable && python manage.py clear_cache

# Optional: Check if initial data exists, and if not, run initial imports.
if [ `psql ${DATABASE_URL} -tAX -c "SELECT COUNT(*) FROM la_metro_translations_document"` -eq "0" ]; then
   # Define an initial data loading command here, if one exists.
   python manage.py create_initial_docs
fi
