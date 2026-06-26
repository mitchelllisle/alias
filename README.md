```
 ▄▄▄▄▄▄▄▄▄   ▄▄▄▄       ▄▄▄▄▄  ▄▄▄▄▄▄▄▄▄   ▄▄▄▄▄▄▄▄▄ 
█▄███████▄█ █████       █████ █▄███████▄█ █▄███████▄█
█▓▓▓▓▓▓▓▓▓█ █▓▓▓█       █▓▓▓█ █▓▓▓▓▓▓▓▓▓█ █▓▓▓▓▓▓▓▓▓█
█▒▒▒█▀█▒▒▒█ █▒▒▒█       █▒▒▒█ █▒▒▒█▀█▒▒▒█ █▒▒▒█▀█▒▒▒█
█░░░█▄█░░░█ █░░░█       █░░░█ █░░░█▄█░░░█ █░░░█▄█▀▀▀█
█░░░░░░░░░█ █░░░█ ▄▄▄▄▄ █░░░█ █░░░░░░░░░█ ██▀▀▀▀▀░░▄█
█▒▒▒▒▒▒▒▒▒█ █▒▒▒█▄█▒▒▒█ █▒▒▒█ █▒▒▒▒▒▒▒▒▒█ █▒▒▒█▄█▒▒▒█
█▓▓▓█▀█▓▓▓█ █▓▓▓▓▓▓▓▓▓█ █▓▓▓█ █▓▓▓█▀█▓▓▓█ █▓▓▓▓▓▓▓▓▓█
█████ █████ ███████████ █████ █████ █████ ███████████
▀▀▀▀▀ ▀▀▀▀▀ ▀▀▀▀▀▀▀▀▀▀▀ ▀▀▀▀▀ ▀▀▀▀▀ ▀▀▀▀▀ ▀▀▀▀▀▀▀▀▀▀▀
```

Pseudonymisation service for Australian financial services. Detects PII in text, anonymises it with configurable operators, and optionally assesses content risk using an LLM — all over a FastAPI HTTP interface.

---

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness check |
| `POST` | `/detect` | Detect PII entities in text |
| `POST` | `/anonymise` | Anonymise PII in text |
| `POST` | `/assess` | Assess content risk and sensitivity |

### `POST /detect`

Returns detected entities with type, character offsets, confidence score, PII classification, and sensitivity tier. Every response includes a SHA-256 audit hash of the input.

```bash
curl -X POST http://localhost:8000/detect \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Jane Smith TFN 123 456 782, BSB 062-000, jane@westpac.com.au",
    "mode": "accurate"
  }'
```

```json
{
  "entities": [
    { "text": "Jane Smith", "entity_type": "PERSON",        "is_pii": true, "sensitivity": "high",     "score": 0.85 },
    { "text": "123 456 782", "entity_type": "AU_TFN",       "is_pii": true, "sensitivity": "critical", "score": 1.0  },
    { "text": "062-000",     "entity_type": "AU_BSB",        "is_pii": true, "sensitivity": "high",     "score": 0.85 },
    { "text": "jane@westpac.com.au", "entity_type": "EMAIL_ADDRESS", "is_pii": true, "sensitivity": "medium", "score": 1.0 }
  ],
  "input_hash": "sha256:..."
}
```

**`mode` field** (default `"accurate"`):

| Value | Behaviour |
|-------|-----------|
| `"accurate"` | Runs an LLM pass to remove false positives before returning. Requires `ALIAS_JUDGE_MODEL`. Degrades silently to `"fast"` when unconfigured. |
| `"fast"` | Returns raw detector output immediately. No LLM involvement. |

### `POST /anonymise`

Replaces detected entities with configurable operator strategies. Detections can be passed from a prior `/detect` call to avoid running the detector twice.

```bash
curl -X POST http://localhost:8000/anonymise \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Jane Smith TFN 123 456 782",
    "mode": "accurate"
  }'
```

```json
{
  "anonymised_text": "<PERSON> TFN ***-***-***",
  "entity_map": {
    "Jane Smith":  "<PERSON>",
    "123 456 782": "***-***-***"
  }
}
```

**Default operators by entity type:**

| Entity type | Default operator | Output example |
|-------------|-----------------|----------------|
| `PERSON` | replace | `<PERSON>` |
| `EMAIL_ADDRESS` | replace | `<EMAIL>` |
| `PHONE_NUMBER` / `AU_PHONE` | replace | `<PHONE>` |
| `AU_TFN` | replace | `***-***-***` |
| `AU_BSB` | replace | `XXX-XXX` |
| `AU_ABN` | replace | `*** *** ***` |
| `CREDIT_CARD` | mask (last 4 digits) | `**** **** **** 1234` |
| `LOCATION` | replace | `<LOCATION>` |
| `DATE_TIME` | replace | `<DATE>` |

Override per request with `operator_overrides`:

```json
{
  "text": "Contact Jane Smith on 0412 345 678",
  "operator_overrides": { "PERSON": "redact", "AU_PHONE": "mask" }
}
```

Available operators: `replace`, `mask`, `redact`, `hash`.

### `POST /assess`

Produces a risk profile of a piece of text — overall sensitivity tier, applicable Australian regulatory frameworks, and handling guidance. Requires `ALIAS_JUDGE_MODEL`.

Pass pre-computed detections to avoid running the detector again.

```bash
curl -X POST http://localhost:8000/assess \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Applicant Jane Smith TFN 123 456 782. BSB 062-000.",
    "context": "Australian home loan application"
  }'
```

```json
{
  "overall_sensitivity": "critical",
  "risk_summary": "Contains TFN and BSB — highest regulatory exposure",
  "categories": ["identity", "financial"],
  "regulatory_flags": ["Privacy Act s16B", "ATO data standards"],
  "recommended_handling": "Encrypt at rest, restrict to need-to-know, purge after 90 days",
  "entity_breakdown": [
    { "entity_type": "AU_TFN", "sensitivity": "critical", "count": 1 },
    { "entity_type": "AU_BSB", "sensitivity": "high",     "count": 1 }
  ],
  "reasoning": "..."
}
```

---

## Australian Entity Types

Alias ships purpose-built recognisers for Australian financial identifiers, each with checksum validation where the issuing authority publishes an algorithm.

| Entity type | Description | PII | Sensitivity | Validation |
|-------------|-------------|-----|-------------|-----------|
| `AU_TFN` | Tax File Number | ✅ | critical | ATO checksum (mod 11) |
| `AU_MEDICARE` | Medicare card number | ✅ | critical | DVA checksum |
| `AU_ABN` | Australian Business Number | ❌ | low | ATO mod-89 checksum |
| `AU_ACN` | Australian Company Number | ❌ | low | ASIC complement-of-10 checksum |
| `AU_BSB` | Bank State Branch code | ✅ | high | Format: `XXX-XXX` |
| `AU_ACCOUNT_NUMBER` | Bank account number | ✅ | high | Requires BSB context |
| `AU_PHONE` | Australian mobile/landline | ✅ | medium | 04XX, +61 4XX, (0X) XXXX XXXX |

Standard presidio types (`PERSON`, `EMAIL_ADDRESS`, `CREDIT_CARD`, `LOCATION`, `PHONE_NUMBER`, `DATE_TIME`) are also detected.

---

## Configuration

Copy `.env.example` to `.env` and set values.

| Variable | Default | Description |
|----------|---------|-------------|
| `ALIAS_JUDGE_MODEL` | _(unset)_ | LLM for `mode='accurate'` and `/assess`. Format: `provider:model`, e.g. `anthropic:claude-sonnet-4-6` |
| `ALIAS_JUDGE_TEMPERATURE` | `0.0` | Sampling temperature for the LLM judge |
| `ALIAS_SPACY_MODEL` | `en_core_web_sm` | spaCy model. Use `en_core_web_lg` for higher recall in production |
| `ALIAS_EXECUTOR_MAX_WORKERS` | `4` | Thread-pool size for presidio (CPU-bound) |
| `ALIAS_DEBUG` | `false` | Enable FastAPI debug mode |
| `ANTHROPIC_API_KEY` | _(unset)_ | Required when using the `anthropic` provider |
| `OPENAI_API_KEY` | _(unset)_ | Required when using the `openai` provider |

---

## Quickstart

```bash
# Install dependencies (includes spaCy model)
make install

# Start the server (hot-reload)
make serve
```

The API is at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

---

## Development

```bash
make test      # run tests (pytest)
make lint      # ruff + mypy
make format    # auto-fix lint issues
```

**Docker:**

```bash
make docker-build   # build images
make docker-serve   # run the service
make docker-test    # run the test suite in Docker
```

CI runs the full test matrix across Python 3.11, 3.12, and 3.13.

---

## Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Docker (for `make docker-*` targets and CI matrix runs)

---

## Project structure

```
src/alias/
├── api/
│   ├── deps.py          # FastAPI dependency injection
│   └── routes/          # detect, anonymise, assess, health
├── domain/              # Pydantic models — DetectionResult, AnonymisationResult, AssessmentResult
├── engine/              # Async wrappers over presidio analyser and anonymiser
├── judge/
│   ├── prompts/         # System prompts as markdown files (refiner.md, assessor.md)
│   ├── refiner.py       # Internal LLM refiner for mode='accurate'
│   └── assessor.py      # LLM assessor for POST /assess
├── recognisers/         # AU-specific PatternRecognisers with checksum validation
├── settings.py          # Pydantic-settings, all vars prefixed ALIAS_
└── app.py               # FastAPI app factory + lifespan

tests/
├── unit/                # Pure function tests — no engine, no network
└── integration/         # Full request→response via httpx AsyncClient
```
