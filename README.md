```
▀█▓▒░██▀█▓▒░▄▄  ▀█▓▒░██▀█▓▒░▄▄   ▀█▓▒░██▀ ██▓▒░    ▓▒░██ ▀█▓▒░██▀▀▀▀▓▒░█ ▀█▓▒░██▀ ▀█▓▒░██▀       
 ▓▒░███  ▀▓▒░██  ▓▒░███  ▀▓▒░██   ▓▒░███  █▓▒░█    ▓▒░██  ▓▒░███    ▒░░█  ▓▒░███   ▓▒░███        
 ▒░████   ▒░███  ▒░████   ▒░███   ▒░████  ▓▒░██    ▒░███  ▒░████     ▀▀▀  ▒░████   ▒░████        
 ░█████▄▄░███▀   ░█████▄▄░███▀    ░█████  ▒░███    ░████  ░█████▄▄▄█▄     ░█████   ░█████        
 ░█████          ░█████   ░███▄   ░█████  ███░█    ░████  ░█████   ▀      ░█████   ░█████        
 ░█████          ░█████   ░████   ░█████  ▐█░▒█    ▒░██▌  ░█████    ▓▒░█  ░█████   ░█████    ▓▒░█
 ░█████          ░█████   ░████   ░█████   ▀███▄ ▄░███▀   ░█████    ▒░██  ░█████   ░█████    ▒░██
▀▀▀▀▀▀▀▀        ▀▀▀▀▀▀▀▀ ▀▀▀▀▀▀▀ ▀▀▀▀▀▀▀▀    ▀▀▀▀▀▀▀▀    ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀ ▀▀▀▀▀▀▀▀ ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀
```

A pseudonymisation service for reducing obvious PII exposure in text workflows, with strong support for Australian financial identifiers — **not a substitute for true anonymisation**.

> [!IMPORTANT]
> **Read this before integrating:** Priveil replaces known PII patterns with consistent placeholders. It cannot enumerate all possible identifying information, does not account for auxiliary data an attacker might possess, and makes no mathematical guarantee about re-identification risk. See [**On anonymisation and its limits**](#on-anonymisation-and-its-limits) below.

> [!CAUTION]
> **Service hardening is your responsibility:** this API ships with **no built-in authentication, no rate limiting, and no TLS termination**. Deploy it only behind your own trusted gateway/load balancer (authn/authz, traffic limits, TLS, and network controls).

---

> [!WARNING]  
> ## On anonymisation and its limits
>
> The word "anonymise" appears throughout this codebase and documentation because it is the term practitioners use. It is not accurate, and that matters.
> 
> What Priveil produces is **pseudonymisation**: detected entity spans are replaced with labelled placeholders (`<PERSON>`, `***-***-***`). The `entity_map` returned by `/anonymise` records the original PII spans as keys — it is sensitive data that must be protected with the same controls as the original text. (It is not a complete  reconstruction of the original: placeholders are not positionally indexed and multiple spans may collapse to the same label, so the map is useful for audit but not sufficient to reverse the full document on its own.)
> 
> Beyond that, no tool that works by finding and replacing known patterns can produce truly anonymous data, for three reasons that the privacy research literature has established clearly:
> 
> 1. **Data is more identifying than it appears.** A name, a postcode, and a date of birth together uniquely identify most people. A sequence of transactions, a writing style, or a combination of fields that each look innocuous can be just as identifying. There is no way to enumerate what an attacker might use.
> 
> 2. **Auxiliary data is an unknown variable.** Information that looks private may be public for specific individuals — politicians, athletes, executives. Data that is safe today may become identifying after an unrelated breach. A pseudonymisation scheme that does not account for what an attacker might already know provides no robust guarantee.
> 
> 3. **Attacks improve over time.** AI-assisted reconstruction attacks, linkage attacks, and re-identification techniques continue to improve. Mitigating only known attacks is not enough.

> [!TIP]
> The only approach with a mathematical guarantee that holds regardless of auxiliary data and future attacks is differential privacy — applied to aggregations, not to text. If you need data that is safe to publish or share without downstream privacy controls, you need differential privacy, not this service.
> 
> **What Priveil is useful for:** keeping PII out of logs and analytics pipelines, reducing accidental exposure when data crosses trust boundaries, improving compliance posture, and making data *less obviously identifying* for operational purposes. These are real and valuable things. They are not anonymisation.
> 
> For further reading: Damien Desfontaines' [*What anonymization techniques can you trust?*](https://desfontain.es/blog/trustworthy-anonymization.html) is the clearest account of why pattern-based techniques fail. Katharine Jarmul's [*Probably Private*](https://probablyprivate.com/) covers probabilistic privacy and the practical gap between claimed and actual privacy guarantees.


## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness check |
| `POST` | `/detect` | Detect PII entities in text |
| `POST` | `/anonymise` | Anonymise PII in text |
| `POST` | `/assess` | Assess content risk and sensitivity |

### `POST /detect`

Returns detected entities with type, character offsets, confidence score, PII classification, and sensitivity tier. Every response includes an HMAC-SHA-256 audit hash of the input.

```bash
curl -X POST http://localhost:8000/detect \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Jane Smith TFN 123 456 782, BSB 062-000, jane@westpac.com.au",
    "mode": "judge"
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
  "input_hash": "hmac-sha256:...",
  "mode_requested": "judge",
  "mode_used": "judge"
}
```

**`mode` field** (default `"judge"`):

| Value | Behaviour |
|-------|-----------|
| `"judge"` | Runs an LLM pass to remove false positives before returning. Requires `PRIVEIL_JUDGE_MODEL`. When unconfigured, the response surfaces fallback with `mode_used: "fast"` and the service logs a warning. |
| `"fast"` | Returns raw detector output immediately. No LLM involvement. |

### `POST /anonymise`

Replaces detected entities with configurable operator strategies. Detections can be passed from a prior `/detect` call to avoid running the detector twice.

```bash
curl -X POST http://localhost:8000/anonymise \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Jane Smith TFN 123 456 782",
    "mode": "judge"
  }'
```

```json
{
  "anonymised_text": "<PERSON> TFN ***-***-***",
  "entity_map": {
    "Jane Smith":  "<PERSON>",
    "123 456 782": "***-***-***"
  },
  "mode_requested": "judge",
  "mode_used": "judge"
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

Produces a risk profile of a piece of text — overall sensitivity tier, applicable Australian regulatory frameworks, and handling guidance. Requires `PRIVEIL_JUDGE_MODEL`.

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
  "advisory_disclaimer": "Regulatory flags and recommendations are LLM-generated advisory hints only, not legal determinations.",
  "entity_breakdown": [
    { "entity_type": "AU_TFN", "sensitivity": "critical", "count": 1 },
    { "entity_type": "AU_BSB", "sensitivity": "high",     "count": 1 }
  ],
  "reasoning": "..."
}
```

---

## Australian Entity Types

Priveil ships purpose-built recognisers for Australian financial identifiers, each with checksum validation where the issuing authority publishes an algorithm.

| Entity type | Description | PII | Sensitivity | Validation |
|-------------|-------------|-----|-------------|-----------|
| `AU_TFN` | Tax File Number | ✅ | critical | ATO checksum (mod 11) |
| `AU_MEDICARE` | Medicare card number | ✅ | critical | Services Australia issuing checksum (first 8 digits) |
| `AU_ABN` | Australian Business Number | ❌ | low | ATO mod-89 checksum |
| `AU_ACN` | Australian Company Number | ❌ | low | ASIC complement-of-10 checksum |
| `AU_BSB` | Bank State Branch code | ✅ | high | Format: `XXX-XXX` (classified high in this domain because it commonly appears with account/customer data) |
| `AU_ACCOUNT_NUMBER` | Bank account number | ✅ | high | Requires BSB context |
| `AU_PHONE` | Australian mobile/landline | ✅ | medium | 04XX, +61 4XX, (0X) XXXX XXXX |

Standard presidio types (`PERSON`, `EMAIL_ADDRESS`, `CREDIT_CARD`, `LOCATION`, `PHONE_NUMBER`, `DATE_TIME`) are also detected.

---

## Configuration

Copy `.env.example` to `.env` and set values.

| Variable | Default | Description |
|----------|---------|-------------|
| `PRIVEIL_JUDGE_MODEL` | _(unset)_ | LLM for `mode='judge'` and `/assess`. Format: `provider:model`, e.g. `anthropic:claude-sonnet-4-6` |
| `PRIVEIL_JUDGE_TEMPERATURE` | `0.0` | Sampling temperature for the LLM judge |
| `PRIVEIL_AUDIT_HASH_KEY` | _(unset)_ | Secret key for `input_hash` HMAC generation. Set this for stable audit hashes across restarts. |
| `PRIVEIL_SPACY_MODEL` | `en_core_web_sm` | spaCy model. Use `en_core_web_lg` for higher recall in production |
| `PRIVEIL_EXECUTOR_MAX_WORKERS` | `4` | Thread-pool size for presidio (CPU-bound) |
| `PRIVEIL_DEBUG` | `false` | Enable FastAPI debug mode |
| `ANTHROPIC_API_KEY` | _(unset)_ | Required when using the `anthropic` provider |
| `OPENAI_API_KEY` | _(unset)_ | Required when using the `openai` provider |

> [!CAUTION]
> **LLM egress and regulated data:** `mode="judge"` and `/assess` send raw, un-redacted text to your configured LLM provider. For regulated data, only use approved providers/configurations (private tenancy, data-retention disabled where available, regional controls, contractual safeguards) or run a self-hosted/local OpenAI-compatible endpoint via `PRIVEIL_JUDGE_BASE_URL`.

### TFN scope note

Priveil currently validates and detects modern 9-digit TFNs only. Legacy 8-digit TFNs are deliberately excluded.

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

## MCP Server

Priveil exposes its tools over the [Model Context Protocol](https://modelcontextprotocol.io), so LLM clients (Claude Desktop, Cursor, etc.) can call `detect`, `anonymise`, and `assess` directly.

### Install

```bash
pip install "priveil[mcp]"

# Pre-download the spaCy model — required before first use.
# Without this the server downloads it on first start (~4s), which causes
# MCP clients to time out before the server becomes ready.
python -m spacy download en_core_web_sm
```

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "priveil": {
      "command": "priveil-mcp",
      "env": {
        "PRIVEIL_JUDGE_MODEL": "anthropic:claude-sonnet-4-6",
        "ANTHROPIC_API_KEY": "<your-key>"
      }
    }
  }
}
```

**Tools available:**

| Tool | Description |
|------|-------------|
| `detect` | Detect PII entities — returns types, offsets, sensitivity, audit hash |
| `anonymise` | Replace PII with placeholders — returns anonymised text and entity map |
| `assess` | Risk profile a document — requires `PRIVEIL_JUDGE_MODEL` |


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
src/priveil/
├── api/
│   ├── deps.py          # FastAPI dependency injection
│   └── routes/          # detect, anonymise, assess, health
├── domain/              # Pydantic models — DetectionResult, AnonymisationResult, AssessmentResult
├── engine/              # Async wrappers over presidio analyser and anonymiser
├── judge/
│   ├── prompts/         # System prompts as markdown files (refiner.md, assessor.md)
│   ├── refiner.py       # Internal LLM refiner for mode='judge'
│   └── assessor.py      # LLM assessor for POST /assess
├── mcp/                 # Optional MCP server (pip install "priveil[mcp]")
│   ├── server.py        # _State, lifespan, FastMCP instance
│   └── tools.py         # detect/anonymise/assess tools
├── recognisers/         # AU-specific PatternRecognisers with checksum validation
├── settings.py          # Pydantic-settings, all vars prefixed PRIVEIL_
└── app.py               # FastAPI app factory + lifespan

tests/
├── unit/                # Pure function tests — no engine, no network
├── integration/         # Full request→response via httpx AsyncClient
└── mcp/                 # MCP tool tests
```
