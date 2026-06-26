# Domain: Alias — Pseudonymisation Service

> **One sentence:** Alias detects, redacts, and assesses the sensitivity of personally identifiable information in text for Australian financial services consumers.

---

## Ubiquitous Language

**Entity**
Definition: A span of text with a semantic type, character offsets, a confidence score, a PII flag, and a sensitivity tier. The atomic unit of detection output.
Not to be confused with: A database entity or ORM model. An Entity here is always a detected text span, never a persisted record.

**EntityType**
Definition: The semantic class of an Entity — what kind of thing it is. Standard presidio types (`PERSON`, `EMAIL_ADDRESS`, `CREDIT_CARD`) plus Australian financial types (`AU_TFN`, `AU_ABN`, `AU_BSB`, `AU_MEDICARE`, `AU_PHONE`, `AU_ACCOUNT_NUMBER`).
Not to be confused with: Sensitivity. An `AU_ABN` is an EntityType but is **not** PII — it is a business identifier. EntityType and PII status are independent.

**PII (Personally Identifiable Information)**
Definition: A boolean classification on an Entity. True means the entity identifies or could be used to identify a natural person. False means it is a business or contextual identifier with no personal link (e.g. ABN, ACN).
Not to be confused with: Sensitivity. PII is a binary flag; sensitivity is a four-tier scale. An entity can be PII at medium sensitivity (email) or critical sensitivity (TFN).

**Sensitivity**
Definition: A four-tier classification of the harm potential if an entity were exposed: `low`, `medium`, `high`, `critical`. Assigned per EntityType from the classification map; not computed dynamically.

| Tier     | Examples                                         |
|----------|--------------------------------------------------|
| critical | TFN, Medicare, credit card                       |
| high     | Full name + BSB, passport, driver licence        |
| medium   | Email, phone, street address                     |
| low      | ABN/ACN, dates, publicly available information   |

**Detection**
Definition: The act of running recognisers over input text and returning a `DetectionResult`. Detection is always deterministic given the same text and model — no side effects.

**DetectionResult**
Definition: The output of a Detection: a sorted tuple of Entities plus a SHA-256 audit hash of the original input. Immutable (frozen Pydantic model).

**Recogniser**
Definition: A presidio `EntityRecognizer` subclass — the atomic detection unit. Each recogniser is responsible for exactly one EntityType. Australian financial recognisers include checksum validation where the issuing authority publishes an algorithm (TFN, ABN, Medicare).

**Anonymisation**
Definition: The act of applying an Operator to each detected Entity in text and returning an `AnonymisationResult`. In this codebase, "anonymisation" is technically pseudonymisation — identifiers are replaced with consistent placeholders, not destroyed. True anonymisation (irreversible) is not implemented.
Alias / external term: "Redaction" is used loosely by customers to mean any of mask, replace, or redact. In code, redact means full removal (empty string replacement).

**Operator**
Definition: A named strategy for transforming a detected Entity span: `replace` (swap with a labelled placeholder), `mask` (overwrite characters), `redact` (remove entirely), `hash` (SHA-256 of the span). Each EntityType has a default Operator; callers may override per-request.

**AnonymisationResult**
Definition: The output of Anonymisation: the anonymised text string plus an `entity_map` that records the original span → replacement for audit purposes. The entity_map is an approximation for `mask` and `hash` operators where the exact output is not knowable before the engine runs.

**Mode**
Definition: A request-level switch that controls the speed/accuracy tradeoff: `fast` returns raw detector output; `accurate` runs an LLM refinement pass to remove false positives before returning. Defaults to `accurate`; degrades silently to `fast` when no judge model is configured.
Not to be confused with: A global server setting. Mode is per-request.

**Refiner**
Definition: An internal LLM agent that receives a DetectionResult and returns a cleaned DetectionResult — removing false positives and surfacing missed entities. The Refiner is never exposed on the API surface; callers see only its output via Mode.

**Assessment**
Definition: An LLM-produced risk profile of a piece of text: overall sensitivity tier, risk categories, applicable Australian regulatory frameworks, recommended handling guidance, and a per-EntityType breakdown. Distinct from Detection (what is here?) and Anonymisation (hide it); Assessment answers "how sensitive is this content and how should we handle it?"

**AssessmentResult**
Definition: The output of an Assessment. `entity_breakdown` is computed from the DetectionResult (not from the LLM) so it is always grounded in the actual detected entities.

**Input Hash**
Definition: A SHA-256 hex digest of the original input text, included in every DetectionResult and AnonymisationResult. Used for audit — downstream systems can verify the text they processed matches what was detected without storing the text itself.

---

## Bounded Contexts

### Detection
Owns: entity recognition over text, AU financial recognisers, checksum validation, DetectionResult construction.
Depends on: presidio-analyzer (NLP engine), spaCy (NLP backend), recogniser registry.
Does not own: anonymisation logic, LLM calls, risk assessment.

### Anonymisation
Owns: operator configuration, applying operators to detected spans, AnonymisationResult construction.
Depends on: presidio-anonymizer (engine), Detection (for auto-detect when no detections are provided).
Does not own: what counts as PII, which entities to detect, risk classification.

### Judge
Owns: LLM refinement (Refiner), content risk assessment (Assessor), system prompt files.
Depends on: pydantic-ai (agent framework), Detection (for entity context), a configured LLM provider.
Does not own: detection logic, anonymisation operators, API routing.
Note: The Judge context is entirely internal for Refiner; only Assessment is exposed on the API surface.

### API
Owns: HTTP routing, request/response schema validation, dependency injection, error handling.
Depends on: all three above contexts.
Does not own: any business logic — routes are thin wrappers over domain operations.

---

## Integration Points

| Direction | System | What crosses the boundary |
|-----------|--------|--------------------------|
| Inbound | Any HTTP client | DetectionRequest, AnonymisationRequest, AssessmentRequest (JSON) |
| Outbound | presidio-analyzer | Text + language → RecognizerResult list |
| Outbound | presidio-anonymizer | RecognizerResult list + OperatorConfig map → anonymised text |
| Outbound | LLM provider (Anthropic/OpenAI) | Prompt + structured output schema → RefinerDecision / AssessmentDecision |
| Outbound | spaCy | Text → NLP pipeline (tokenisation, NER) |

---

## Domain Events

**EntityDetected**
Triggered by: a call to `/detect` or the internal detection step in `/anonymise` and `/assess`.
Downstream: DetectionResult is returned to caller; optionally passed to Refiner or Assessor.

**DetectionRefined**
Triggered by: Mode = `accurate` and a judge model is configured.
Downstream: Cleaned DetectionResult replaces the raw result before the API response is sent.

**TextAnonymised**
Triggered by: a call to `/anonymise`.
Downstream: AnonymisationResult returned; entity_map available for audit trail.

**ContentAssessed**
Triggered by: a call to `/assess`.
Downstream: AssessmentResult returned; caller uses sensitivity tier and regulatory flags to determine handling.

---

## Architecture Decisions

**Decision: Presidio as the detection core, not a fine-tuned model**
Context: Detection needs to be fast, deterministic, explainable, and auditable. LLMs add latency and non-determinism as the primary detection mechanism.
Decision: Presidio (rule-based + NER) handles all entity recognition. LLM is additive — refinement and assessment only, never on the critical detection path.
Consequences: High precision on Australian financial identifiers via checksum validation. Recall on edge cases handled by Mode = `accurate`. No LLM dependency for core functionality.

**Decision: Australian financial entity types are explicit in the enum, not inferred**
Context: Generic spaCy/presidio models do not reliably surface TFN, ABN, BSB, Medicare card numbers.
Decision: Each AU type is a dedicated `PatternRecognizer` with checksum validation where applicable. They are registered at engine startup and contribute to the same DetectionResult as standard types.
Consequences: High precision on AU financial entities. No magic fallback — if an EntityType is not in the enum, it does not exist in this domain.

**Decision: Anonymisation is pseudonymisation, not true anonymisation**
Context: Presidio's `replace` operator substitutes a labelled placeholder (`<PERSON>`, `***-***-***`). The link between original and replacement is preserved in the entity_map.
Decision: The service is documented and named as a pseudonymisation service ("Alias"). True anonymisation — where the mapping is destroyed and re-identification is mathematically infeasible — is out of scope.
Consequences: Callers must treat the entity_map as sensitive. The service reduces PII exposure in transit and at rest but does not satisfy anonymisation requirements under the Privacy Act where re-identification must be impossible.

**Decision: Mode (fast/accurate) is per-request, not a server-side global**
Context: Some callers need throughput (batch jobs); others need accuracy (interactive, compliance-sensitive).
Decision: `mode` is a field on DetectionRequest and AnonymisationRequest. `accurate` is the default. The LLM is only invoked when mode = `accurate` and a judge model is configured.
Consequences: Callers opt out explicitly by setting `mode: fast`. When ALIAS_JUDGE_MODEL is unset, accurate silently degrades to fast — no config change required on the client side.

**Decision: Refiner is internal; Assessment is the only LLM-facing endpoint**
Context: Exposing an endpoint that lets callers "judge" detector accuracy couples them to an internal implementation detail and reveals that AI is involved in routine detection.
Decision: The Refiner is invoked transparently inside `/detect` and `/anonymise`. The only public LLM endpoint is `/assess`, which answers a genuinely different question: how sensitive is this content and how should it be handled?
Consequences: The public API surface is stable regardless of whether the underlying LLM changes, is disabled, or is replaced. Assessment is explicitly an LLM feature — callers know what they are getting.

**Decision: Checksum validation on AU financial identifiers**
Context: TFN, ABN, Medicare, and ACN all have publicly published checksum algorithms from the issuing authority (ATO, ASIC, DVA). Without checksum validation, pattern-only recognisers produce unacceptably high false positive rates on nine-digit sequences.
Decision: Each recogniser implements the authority's checksum. A failed checksum returns `False` (no match); the entity is silently dropped. A passing checksum boosts the score to 1.0.
Consequences: Near-zero false positives on AU financial identifiers in structured financial text. Any TFN that passes is cryptographically consistent with the ATO's algorithm, though not guaranteed to be a real issued number.

---

## Goals and Success Criteria

**What "good" looks like:**
- A TFN, BSB, or Medicare number in any realistic Australian financial document is detected and anonymised correctly, without the caller writing any detection logic.
- Clean financial text (interest rates, loan amounts, product codes) produces zero entities — no noise that burdens downstream systems.
- Mode = `accurate` removes the false positives that pattern matching alone cannot; mode = `fast` is suitable for high-volume preprocessing where a small FP rate is acceptable.
- The service adds no friction to callers who don't want the LLM — `ALIAS_JUDGE_MODEL` unset means the service runs purely on presidio with no degraded behaviour, just no LLM features.

**How we know the domain is struggling:**
- False positive rate on clean financial text rises — rates, amounts, dates being flagged as entities.
- Checksum-valid but contextually wrong detections that the Refiner does not catch (e.g. a 9-digit product code that happens to pass TFN checksum).
- `entity_map` drift — the audit map diverges from what was actually anonymised in the text (indicates a bug in the entity map construction logic, not in presidio).
- Assessment regulatory flags that are consistently wrong for a document type — indicates the assessor system prompt needs tuning.
