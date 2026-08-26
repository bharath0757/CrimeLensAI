# CrimeLensAI - AI-Powered Criminal Network Analysis System

> **Smart India Hackathon 2026** · PS SIH26189 · Ministry of Home Affairs / NCRB Women Safety Division
> Theme: Blockchain & Cybersecurity · Category: Software

## Why This Exists
Every day, FIRs are filed across thousands of police stations in India - each recorded in isolation. CrimeLensAI breaks this fragmentation by ingesting case data, extracting entities (people, phone numbers, vehicles, UPI IDs, locations) using NLP, linking them across cases in a graph database, and surfacing hidden connections. Every relationship is backed by a tamper-evident, hash-chained audit record traceable to its exact source.

## Architecture

\\\mermaid
flowchart TD
    UI[Frontend / Web UI] --> API[Case API Gateway]
    
    API --> INGEST[Ingestion Service]
    API --> EXTRACT[Entity Extraction Service]
    API --> GRAPH[Graph Service]
    API --> LEDGER[Audit Ledger Service]
    
    INGEST -.->|Validates| EXTRACT
    EXTRACT --> GRAPH
    EXTRACT -.-> LEDGER
    GRAPH -.-> LEDGER
    
    API --> PG[(PostgreSQL)]
    LEDGER --> PG
    GRAPH --> N4J[(Neo4j)]
\\\

## Module Ownership

| Folder | Owner | Responsibility |
|---|---|---|
| /services/audit-ledger-service/ | **Member 1 (@reshmasri009)** | Hash-chain ledger, JWT auth, RBAC, privacy masking |
| /services/case-api/, /services/ingestion-service/ | **Member 2 (@reshmasri009)** | Orchestration API, ingestion validation, PostgreSQL |
| /services/entity-extraction-service/ | **Member 3 (@bharath0757)** | NLP entity extraction, fuzzy matching & resolution |
| /services/graph-service/, /data/ | **Member 4 (@jithendar-guttula)** | Neo4j graph operations, cross-case linkage, analytics |
| /frontend/ | **Member 5 (@avskrishna2-coder)** | React frontend - Case Intake, Dashboard, Audit Trail |

*Note: See \docs/team-ownership/OWNERSHIP.md\ for complete details.*

## Local Setup

### One-Command Start

\\\ash
# Clone the repository
git clone https://github.com/<your-org>/CrimeLensAI.git
cd CrimeLensAI

# Copy example environment files
cp .env.example .env

# Start all services + databases
docker compose up --build
\\\

| Service | URL |
|---|---|
| Web Frontend | http://localhost:5173 |
| Case API | http://localhost:8000/docs |
| Extraction Service | http://localhost:8001/docs |
| Graph Service | http://localhost:8002/docs |
| Ledger Service | http://localhost:8003/docs |
| Ingestion Service| http://localhost:8004/docs |
| Neo4j Browser | http://localhost:7474 |
| PostgreSQL | localhost:5432 |

## Git Workflow
See \CONTRIBUTING.md\ for branching and review processes.
