# Entity Extraction API

The internal extraction service combines deterministic Indian-identifier regexes,
spaCy NER, normalization, and fuzzy person-name resolution. Production requests
must include `X-Service-Token`.

- `POST /api/v1/extract` accepts FIR text and returns PERSON, PHONE, AADHAAR, PAN,
  VEHICLE, PASSPORT, UPI_ID, BANK_ACCOUNT, EMAIL, LOCATION, ORGANIZATION, DATE,
  and IPC_SECTION mentions.
- `POST /api/v1/extract/batch` processes multiple FIRs for graph analysis.
- `POST /api/v1/resolve` compares entity spellings without silently merging them.

Every mention includes a normalized value, confidence, source field, and exact
start/end offsets. The Case API validates those offsets against the original
uploaded evidence before persistence.
