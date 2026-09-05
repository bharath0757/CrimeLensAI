"""Bounded, retry-safe graph writes from the authenticated case API outbox."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.routes import graph_service
from app.models.schemas import EntityUpsertRequest, RelationshipCreateRequest
from app.security import require_service_token


class EntityOperation(BaseModel):
    kind: Literal["entity"]
    payload: EntityUpsertRequest


class RelationshipOperation(BaseModel):
    kind: Literal["relationship"]
    payload: RelationshipCreateRequest


class BatchRequest(BaseModel):
    operations: list[Annotated[EntityOperation | RelationshipOperation, Field(discriminator="kind")]] = Field(min_length=1, max_length=100)


class BatchReceipt(BaseModel):
    processed: int


router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_service_token)])


@router.post("/batches", response_model=BatchReceipt)
def write_batch(request: BatchRequest):
    try:
        for operation in request.operations:
            if operation.kind == "entity":
                graph_service.upsert_entity(operation.payload)
            else:
                graph_service.create_relationship(operation.payload)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(409, "Both graph relationship endpoints must exist") from exc
    return BatchReceipt(processed=len(request.operations))
