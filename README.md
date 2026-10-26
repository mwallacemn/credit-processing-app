# Async Credit Processing Service

An asynchronous credit processing service built with **Python 3.11+**, **FastAPI**, **Celery**, **Redis**, **MongoDB**, and a **React** frontend, fully orchestrated with **Docker Compose**.

---

## Architecture Overview

```
                      +-----------------------------+
                      |   React Web Frontend (UI)   |
                      |     (Port 3000 / Nginx)     |
                      +--------------+--------------+
                                     |
                                     | HTTP Requests
                                     v
                      +-----------------------------+
                      |    FastAPI Core Python      |
                      |         (Port 8000)         |
                      +------+---------------+------+
                             |               |
       1. Set status to      |               | 2. Publish task
          "processing"       |               |
                             v               v
                      +------------+   +------------+
                      |  MongoDB   |   |   Redis    |
                      | (Port 27017)   | (Broker &  |
                      +------------+   |  Backend)  |
                             ^         +-----+------+
                             |               |
           3. Update balance |               | 4. Consume task
              & status to    |               |
              "processed"    +-------+-------+
                                     |
                              +------+-------+
                              |    Celery    |
                              |    Worker    |
                              +--------------+
```

### Components

1. **`backend` (FastAPI)**: Validates incoming requests, marks the user's status as `processing` in MongoDB, queues a task via Celery/Redis, and returns `202 Accepted` immediately with the task ID.
2. **`celery-worker`**: Consumes credit tasks from the Redis queue, atomically increments the user balance (`$inc`) creating the field if it does not exist, and updates the status to `processed`.
3. **`redis`**: Serves as the message broker for Celery and result storage.
4. **`mongodb`**: Document store holding user accounts, balances, and processing states.
5. **`frontend` (React + Vite + Nginx)**: Provides an interactive UI to submit credit requests, view task status, and query live user balances.

---

## Getting Started

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (v20.10+)
- [Docker Compose](https://docs.docker.com/compose/) (v2.0+)

### Running the Entire Stack

Clone the repository and run:

```bash
docker compose up --build
```

Once running, the services will be accessible at:

| Service | URL | Description |
|---|---|---|
| **Frontend** | [http://localhost:3000](http://localhost:3000) | Web UI console |
| **FastAPI Swagger Docs** | [http://localhost:8000/docs](http://localhost:8000/docs) | Interactive API documentation |
| **FastAPI Healthcheck** | [http://localhost:8000/health](http://localhost:8000/health) | API & MongoDB health |
| **MongoDB** | `localhost:27017` | Database instance |
| **Redis** | `localhost:6379` | Broker instance |

To stop the containers:

```bash
docker compose down
```

To stop and remove persistent data volumes:

```bash
docker compose down -v
```

---

## API Endpoints

### 1. Submit Credit Request
- **Method**: `POST`
- **Path**: `/credits`
- **Status**: `202 Accepted`
- **Payload**:
  ```json
  {
    "user_id": "u_123",
    "amount": 150.00
  }
  ```
- **Response**:
  ```json
  {
    "task_id": "4b684cb6-5c5e-4ef2-957f-13d8faea5792",
    "message": "Credit request accepted and queued for processing",
    "status": "processing"
  }
  ```

### 2. Fetch User Account & Balance
- **Method**: `GET`
- **Path**: `/users/{user_id}`
- **Response**:
  ```json
  {
    "user_id": "u_123",
    "balance": 150.00,
    "status": "processed"
  }
  ```

### 3. Check Task Status
- **Method**: `GET`
- **Path**: `/credits/{task_id}`
- **Response**:
  ```json
  {
    "task_id": "4b684cb6-5c5e-4ef2-957f-13d8faea5792",
    "status": "SUCCESS",
    "result": {
      "user_id": "u_123",
      "balance": 150.00,
      "status": "processed"
    }
  }
  ```

---

## Running Backend Tests

You can execute the test suite inside the backend container or locally:

### Via Docker Compose:
```bash
docker compose run --rm backend pytest tests/ -v
```

---

## Directory Structure

```
├── .env.example
├── .gitignore
├── README.md
├── docker-compose.yml
├── docs/
│   └── architecture.md        # Sequence diagrams & architectural design notes
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py            # Application entrypoint & ASGI runner
│   │   ├── config.py          # Environment settings
│   │   ├── api/               # Presentation layer (FastAPI routes & DI)
│   │   │   ├── __init__.py
│   │   │   ├── app.py         # FastAPI application factory & lifecycle
│   │   │   ├── dependencies.py# FastAPI dependency injection providers
│   │   │   ├── router.py      # Master API router
│   │   │   ├── credits.py     # Credit endpoints (POST /credits, GET /credits/{id})
│   │   │   ├── users.py       # User endpoints (GET /users/{id})
│   │   │   └── health.py      # Health & monitoring endpoints
│   │   ├── use_cases/         # Application business logic & orchestration
│   │   │   ├── __init__.py
│   │   │   ├── user_credit_service.py  # API credit ingestion & user query service
│   │   │   └── credit_task_service.py  # Worker 5-min duplicate guard, revocation & balance update
│   │   ├── domain/            # Core domain models, enums & repository interfaces
│   │   │   ├── __init__.py
│   │   │   ├── user.py              # User domain entity & UserStatus enum
│   │   │   ├── credit_task_event.py # CreditTaskEvent entity & TaskStatus enum
│   │   │   └── interfaces.py        # IUserInterface repository port
│   │   └── infrastructure/    # External systems & persistence
│   │       ├── __init__.py
│   │       ├── celery_app.py  # Celery broker configuration
│   │       ├── tasks.py       # Celery background task runner
│   │       ├── db/
│   │       │   ├── __init__.py
│   │       │   └── database.py# MongoDB async & sync connections
│   │       └── repositories/
│   │           ├── __init__.py
│   │           └── user_repository.py # MongoUserRepository implementation
│   └── tests/
│       ├── __init__.py
│       ├── api/
│       │   ├── __init__.py
│       │   ├── test_credits.py      # POST /credits & GET /credits/{id} route tests
│       │   ├── test_dependencies.py # FastAPI DI provider tests
│       │   ├── test_users.py        # GET /users/{id} route tests
│       │   ├── test_health.py       # GET /health (healthy & unhealthy) route tests
│       │   └── test_schemas.py      # CreditRequest/Response & UserResponse DTO tests
│       ├── domain/
│       │   ├── __init__.py
│       │   ├── test_user.py              # User entity & UserStatus enum tests
│       │   ├── test_credit_task_event.py # CreditTaskEvent, TaskStatus & had_failed tests
│       │   └── test_interfaces.py        # IUserInterface abstract contract tests
│       ├── use_cases/
│       │   ├── __init__.py
│       │   ├── test_user_credit_service.py # UserCreditService submission & query tests
│       │   └── test_credit_task_service.py # CreditTaskService duplicate guard & worker execution tests
│       └── infrastructure/
│           ├── __init__.py
│           ├── test_tasks.py             # Celery worker task, retry & event loop tests
│           ├── db/
│           │   ├── __init__.py
│           │   └── test_database.py      # Lifespan index provisioning & client reuse tests
│           └── repositories/
│               ├── __init__.py
│               └── test_user_repository.py # MongoUserRepository & terminal-state guard tests
└── frontend/
    ├── Dockerfile             # Multi-stage build + Nginx
    ├── nginx.conf             # Proxy and static file serving
    ├── package.json
    ├── vite.config.js
    ├── index.html
    └── src/
        ├── App.jsx            # Interactive React console
        ├── main.jsx
        └── index.css
```
