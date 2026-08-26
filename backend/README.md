# CrimeLens AI — Complete Backend & API Service

FastAPI backend and REST API orchestration layer for CrimeLens AI investigator dashboard, evidence processing, and crime network analytics platform.

---

## 🏛️ Architecture Overview

The backend is built with a **modular, interface-driven architecture** that decouples API contracts from underlying storage and external ML/graph engines. This allows team members working on Frontend, Database (PostgreSQL), Graph (Neo4j), and AI/NLP to integrate their work independently without breaking backend REST APIs.

```text
CrimeLensAI / backend/
├── app/
│   ├── main.py                     # FastAPI application, CORS, exception handlers
│   ├── core/                       # App settings, security (bcrypt & JWT), exceptions
│   │   ├── config.py
│   │   ├── exceptions.py
│   │   └── security.py
│   ├── api/                        # API dependencies & version 1 router
│   │   ├── deps.py                 # OAuth2, RBAC, repository & service injection
│   │   └── v1/
│   │       ├── router.py           # V1 API Router aggregation
│   │       └── endpoints/
│   │           ├── health.py       # Mission 1: Health check
│   │           ├── auth.py         # Mission 2: User registration, login, profile
│   │           ├── cases.py        # Mission 3: Case CRUD & assignment
│   │           ├── documents.py    # Mission 4: Document upload & processing
│   │           ├── entities.py     # Mission 5: Entities & AI ingestion contract
│   │           ├── relationships.py# Mission 5: Inter-entity relationships
│   │           ├── graph.py        # Mission 6: Graph topology, shortest path & stats
│   │           ├── search.py       # Mission 7: Unified global and domain search
│   │           └── dashboard.py    # Mission 7: Dashboard summary metrics & charts
│   ├── schemas/                    # Pydantic DTOs & Validation Schemas
│   ├── repositories/               # Repository interfaces (ABC) & In-memory implementations
│   └── integrations/               # External component interfaces (AI/NLP & Graph adapters)
├── tests/                          # Complete automated test suite (19 test cases)
├── uploads/                        # Local evidence file storage directory
├── requirements.txt                # Python dependencies
├── .env.example                    # Environment variable template
├── .gitignore                      # Git ignore rules
└── README.md                       # Backend documentation
```

---

## 🚀 Quick Start & Setup

### 1. Prerequisites
- Python 3.10+ installed

### 2. Environment Setup
```powershell
cd backend
python -m venv venv

# Windows (PowerShell):
.\venv\Scripts\Activate.ps1

# Linux / macOS:
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy the example `.env.example` file:
```bash
cp .env.example .env
```

### 5. Run Development Server
```bash
uvicorn app.main:app --reload --port 8000
```
- **Interactive Swagger Documentation**: `http://127.0.0.1:8000/docs`
- **ReDoc API Documentation**: `http://127.0.0.1:8000/redoc`
- **Health Check API**: `http://127.0.0.1:8000/api/v1/health`

### 6. Run Test Suite
```bash
pytest -v
```

---

## 🔑 Default Seed Credentials (for Development & Testing)

| Role | Email | Password |
| :--- | :--- | :--- |
| **Admin** | `admin@crimelens.ai` | `AdminSecret123!` |
| **Investigator** | `investigator@crimelens.ai` | `Investigator123!` |

---

## 📡 API Reference Summary

### Mission 1 — Health
- `GET /api/v1/health` — Application health check status

### Mission 2 — Authentication (`/api/v1/auth`)
- `POST /api/v1/auth/register` — User registration
- `POST /api/v1/auth/login` — JSON Login & JWT issuance
- `POST /api/v1/auth/login/form` — OAuth2 Form Login (for Swagger UI)
- `GET /api/v1/auth/me` — Fetch current user profile

### Mission 3 — Case Management (`/api/v1/cases`)
- `POST /api/v1/cases` — Create new crime investigation case
- `GET /api/v1/cases` — List cases (with status/priority filters & search)
- `GET /api/v1/cases/{case_id}` — Get case details
- `PUT /api/v1/cases/{case_id}` — Update case info
- `PATCH /api/v1/cases/{case_id}/status` — Update status (`OPEN`, `IN_PROGRESS`, `CLOSED`, `ARCHIVED`)
- `DELETE /api/v1/cases/{case_id}` — Delete case

### Mission 4 — Document Upload & Evidence (`/api/v1`)
- `POST /api/v1/cases/{case_id}/documents` — Upload evidence document (PDF, TXT, DOCX, PNG, JPG, CSV, JSON, LOG)
- `GET /api/v1/cases/{case_id}/documents` — List documents attached to a case
- `GET /api/v1/documents/{document_id}` — Get document metadata
- `DELETE /api/v1/documents/{document_id}` — Delete document and local evidence file
- `POST /api/v1/documents/{document_id}/process` — Trigger AI/NLP document extraction
- `GET /api/v1/documents/{document_id}/processing-status` — Check AI processing status

### Mission 5 — Entities & Relationships (`/api/v1`)
- `POST /api/v1/cases/{case_id}/entities` — Create entity (`PERSON`, `ORGANIZATION`, `LOCATION`, `PHONE_NUMBER`, `BANK_ACCOUNT`, etc.)
- `GET /api/v1/cases/{case_id}/entities` — List entities for a case
- `GET /api/v1/entities/{entity_id}` — Get entity detail
- `PUT /api/v1/entities/{entity_id}` — Update entity
- `DELETE /api/v1/entities/{entity_id}` — Delete entity
- `POST /api/v1/cases/{case_id}/relationships` — Create relationship edge (`COMMUNICATED_WITH`, `TRANSFERRED_FUNDS`, `SUSPECT_IN`, etc.)
- `GET /api/v1/cases/{case_id}/relationships` — List relationships for a case
- `GET /api/v1/relationships/{relationship_id}` — Get relationship detail
- `PUT /api/v1/relationships/{relationship_id}` — Update relationship
- `DELETE /api/v1/relationships/{relationship_id}` — Delete relationship
- `POST /api/v1/integrations/ai/extraction-results` — **Contract endpoint for AI teammate** to submit batch extracted entities & relationships

### Mission 6 — Graph API Contracts (`/api/v1`)
- `GET /api/v1/cases/{case_id}/graph` — Full network graph topology (`{ nodes: [...], edges: [...] }`)
- `GET /api/v1/entities/{entity_id}/connections` — Direct connected nodes & edges
- `GET /api/v1/entities/{entity_id}/neighbors` — K-hop neighborhood graph (`?depth=1..5`)
- `GET /api/v1/cases/{case_id}/graph/stats` — Network statistics (density, degree, top connected hubs)
- `GET /api/v1/cases/{case_id}/graph/shortest-path` — Shortest path BFS between source and target entities

### Mission 7 — Search & Dashboard (`/api/v1`)
- `GET /api/v1/search/cases` — Search cases
- `GET /api/v1/search/entities` — Search entities
- `GET /api/v1/search/documents` — Search evidence documents
- `GET /api/v1/search/relationships` — Search relationship links
- `GET /api/v1/search/global` — Unified cross-domain multi-resource search
- `GET /api/v1/dashboard/summary` — Overview metrics for dashboard widgets
- `GET /api/v1/dashboard/statistics` — Categorized breakdown statistics & activity feed

---

## 🤝 Teammate Integration Guide

### 1. Database Teammate (PostgreSQL)
- Replace repository implementations in `app/repositories/` (`user_repo.py`, `case_repo.py`, `document_repo.py`, `entity_repo.py`, `relationship_repo.py`) with SQLAlchemy ORM models and sessions implementing the abstract base classes in `app/repositories/base.py`.
- No API routing or controller logic needs to change.

### 2. AI/NLP Teammate
- Connect your NLP extraction microservice to `POST /api/v1/integrations/ai/extraction-results` or implement `AIServiceInterface` in `app/integrations/ai_integration.py`.
- Set `AI_SERVICE_URL` in `.env`.

### 3. Graph Teammate (Neo4j)
- Implement `GraphServiceInterface` in `app/integrations/graph_integration.py` using official `neo4j` Python driver Cypher queries.
- Set `GRAPH_SERVICE_URL` in `.env`.

### 4. Frontend Teammate
- All REST endpoints return standardized JSON schemas validated by Pydantic.
- Interactive OpenAPI documentation available at `/docs`.
