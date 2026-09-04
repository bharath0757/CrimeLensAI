# Entity Extraction Service

NLP microservice for extracting and resolving entities from Indian FIR text, call records, and financial transaction logs.

**Owner:** Member 3 (AI / NLP Lead)

## Supported Entity Types

| Type | Method | Confidence | Example |
|------|--------|------------|---------|
| `PERSON` | spaCy NER | 0.70 | Rajesh Kumar |
| `ORG` | spaCy NER | 0.70 | Tata Consultancy Services |
| `LOCATION` | spaCy NER (GPE/LOC) | 0.70 | Hyderabad |
| `DATE` | spaCy NER | 0.70 | 15th January 2024 |
| `PHONE` | Regex | 0.95 | +91 98765 43210 |
| `VEHICLE` | Regex | 0.95 | AP 39 AB 1234 |
| `UPI_ID` | Regex | 0.95 | rajesh@oksbi |

## Endpoints

### `POST /api/v1/extract`

Extract entities from raw text.

**Request:**
```json
{
  "text": "Rajesh Kumar (phone: +91 98765 43210) was seen driving AP 39 AB 1234 near Hyderabad.",
  "source_type": "fir_text",
  "case_id": "CASE-001"
}
```

**Response:**
```json
{
  "status": "ok",
  "entities": [
    {
      "entity_id": "uuid",
      "entity_type": "PHONE",
      "value": "+91 98765 43210",
      "normalized_value": "+919876543210",
      "confidence": 0.95,
      "start_offset": 21,
      "end_offset": 36,
      "source_field": "fir_text",
      "case_id": "CASE-001",
      "confirmed": null
    }
  ]
}
```

### `POST /api/v1/resolve`

Group extracted entities that refer to the same real-world identity.

**Request:**
```json
{
  "entities": [
    {"entity_id": "a", "entity_type": "PERSON", "value": "Rajesh Kumar", "normalized_value": "rajesh kumar", "confidence": 0.7, "start_offset": 0, "end_offset": 12, "source_field": "fir_text"},
    {"entity_id": "b", "entity_type": "PERSON", "value": "RAJESH KUMAR", "normalized_value": "rajesh kumar", "confidence": 0.7, "start_offset": 50, "end_offset": 62, "source_field": "fir_text"}
  ]
}
```

**Response:**
```json
{
  "status": "ok",
  "resolved_groups": [
    {
      "canonical_entity_id": "uuid",
      "canonical_value": "RAJESH KUMAR",
      "entity_type": "PERSON",
      "variants": ["..."],
      "merge_confidence": 1.0,
      "resolution_method": "fuzzy_match"
    }
  ]
}
```

### `GET /health`

Health check. Returns `{"status": "healthy", "spacy_model_loaded": true}`.

## Local Development

### Prerequisites

- Python 3.11+
- spaCy model: `en_core_web_sm`

### Setup & Run

```bash
cd services/entity-extraction-service
pip install -r requirements.txt
python -m spacy download en_core_web_sm
uvicorn app.main:app --port 8001 --reload
```

### Run Tests

```bash
pytest tests/ -v
```

### Docker

```bash
docker compose up extraction
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SPACY_MODEL` | `en_core_web_sm` | spaCy model to load |
| `CONFIDENCE_REGEX` | `0.95` | Confidence score for regex matches |
| `CONFIDENCE_SPACY_FLOOR` | `0.70` | Floor confidence for spaCy NER |
| `RESOLUTION_FUZZY_THRESHOLD` | `80` | RapidFuzz threshold (0–100) for fuzzy resolution |
