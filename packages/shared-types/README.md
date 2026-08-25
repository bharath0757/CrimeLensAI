# CrimeLensAI — Shared Types
# ============================
# Cross-module type definitions shared between frontend (TypeScript)
# and backend (Python/Pydantic) services.
#
# This package is the API contract. Changes here affect all modules.
# Any modification requires team-wide review (see CODEOWNERS).

## Structure
# /packages/shared-types/
# ├── python/          # Pydantic models for Python services
# │   └── schemas.py
# ├── typescript/      # TypeScript interfaces for frontend
# │   └── types.ts
# └── openapi/         # OpenAPI specs per service (contract-first)
#     ├── extraction.yaml
#     ├── graph.yaml
#     ├── ledger.yaml
#     └── api.yaml
