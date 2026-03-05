#!/bin/bash
cd "$(dirname "$0")"
export DRAWS_DB_HOST=localhost
export DRAWS_DB_PORT=5432
export DRAWS_DB_NAME=draws
export DRAWS_DB_USER=draws
export DRAWS_DB_PASS=drawspass
python3 server.py
