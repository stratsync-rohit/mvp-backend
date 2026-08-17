# Local development

## Docker Compose (recommended)

Prerequisites: Docker with Compose.

```bash
cd backend
cp .env.example .env
docker compose up --build
docker compose exec backend python -m scripts.seed
```

The API binds only to host loopback at `127.0.0.1:8000`; MongoDB has no host port mapping. Check `curl http://localhost:8000/health` and `http://localhost:8000/docs`. Stop with `docker compose down`; adding `-v` deletes the Mongo volume and is destructive.

## Native Python

Python 3.12 and a reachable MongoDB are required.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# For host MongoDB, set MONGODB_URL=mongodb://localhost:27017
PYTHONPATH=. uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Run tests with `PYTHONPATH=. pytest -q`. Tests replace the database with `mongomock-motor` and mock n8n; a real Mongo/n8n is not required.

At documentation time the existing `.venv` contained Python/pip but no pytest executable, and system `pytest` was unavailable, so the suite could not be executed without installing requirements. Recreate/install the environment before relying on it.

The seed command is `PYTHONPATH=. python -m scripts.seed`. Note the index inconsistency described in Database Design before using it on shared multi-tenant data.
