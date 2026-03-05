# GraysonsDrawOdds — Multi-State App

## Prerequisites

- Python 3.10+
- Docker (for PostgreSQL)
- pip packages: `flask`, `psycopg2-binary`, `gunicorn`

## Setup

### 1. Start the database

From the repo root (parent of this `app/` directory):

```bash
docker compose up -d
```

This starts PostgreSQL on `localhost:5432` with:
- Database: `draws`
- User: `draws`
- Password: `drawspass`

### 2. Run the NM data migration

```bash
python scripts/migrate_nm.py
```

This reads `nm_hunts.db` from the repo root and loads all NM data into PostgreSQL.

### 3. Start the app

```bash
bash run.sh
```

Or manually:

```bash
export DRAWS_DB_HOST=localhost DRAWS_DB_PORT=5432 DRAWS_DB_NAME=draws DRAWS_DB_USER=draws DRAWS_DB_PASS=drawspass
python server.py
```

The app runs on `http://127.0.0.1:5000`.

### Production

```bash
gunicorn wsgi:app -b 0.0.0.0:8000
```

## Database connection

| Variable | Default |
|----------|---------|
| `DRAWS_DB_HOST` | `localhost` |
| `DRAWS_DB_PORT` | `5432` |
| `DRAWS_DB_NAME` | `draws` |
| `DRAWS_DB_USER` | `draws` |
| `DRAWS_DB_PASS` | `drawspass` |
