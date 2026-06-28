# Domain: Priveil — Pseudonymisation Service

> **One sentence:** Priveil detects known PII patterns in text and replaces them with consistent placeholders, reducing the surface area of obvious personal data exposure in Australian financial services systems — while making no claim of true anonymisation.

---

## What This System Is — and Is Not

This is the most important section of this document. Read it before building anything on top of this service.

### What Priveil does

Priveil performs **pseudonymisation**: it finds spans of text that look like personally identifiable information and replaces them with labelled placeholders (`<PERSON>`, `***-***-***`, `XXX-XXX`). It does this with reasonable precision for Australian financial identifiers. It is useful for:

- Preventing PII from appearing in application logs, analytics pipelines, and third-party integrations
- Reducing the surface area of accidental data exposure in systems that handle financial text
- Meeting process and compliance requirements around data handling
- Making data *less obviously identifying* before it crosses a trust boundary

### What Priveil does not do

Priveil **does not produce anonymised data** in any mathematically rigorous sense. Specifically:

**Detection is incomplete by design.** There is no way to enumerate all possible identifying information. A phone number formatted unusually, a name that is also a common word, a combination of innocuous-looking fields — these may identify someone. Priveil will miss them. Damien Desfontaines writes: *"Data is often more identifiable than it seems. Even a few innocuous-looking pieces of information can be enough to identify someone. And people tend to underestimate what data can be used to reidentify people in a dataset."*

**Pseudonymisation is not anonymisation.** Replacing a name with `<PERSON>` preserves the structure of the original data. The `entity_map` returned by `/anonymise` records the original PII spans as keys — it is sensitive data that must be treated with the same controls as the original text. Note that the map is not a complete reversal: placeholders are not positionally indexed, multiple spans may collapse to the same label (e.g. all names → `<PERSON>`), and the actual output for `mask`/`hash` operators is only an approximation. Even so, the map contains the real PII values and must be protected accordingly. This is explicitly the first technique Desfontaines discusses as *failing* to protect privacy: *"'No longer obvious' is very different from 'impossible to figure out'."*

**Auxiliary data breaks it.** What looks like non-identifying data combined with an auxiliary dataset can become identifying. This is not a theoretical concern. The Massachusetts medical records case, the Netflix Prize dataset, and the AOL search query release were all "de-identified" by reasonable standards at the time. Each was re-identified using public data that data owners did not know attackers would possess.

**Attacks improve over time.** Mitigating known attacks is not enough. New techniques — including AI-powered reconstruction attacks — continually lower the bar for re-identification. A dataset that is safe today may not be safe in five years.

**The LLM refiner does not change this picture.** Mode `judge` uses an LLM to remove false positives and surface missed entities. This improves operational precision but does not change the fundamental guarantee — the system still cannot enumerate all possible identifying information, and the LLM introduces its own uncertainties (hallucination, prompt sensitivity, non-determinism across versions).

### What this means for callers

If your use case requires data to be **truly anonymous** — where re-identification is mathematically infeasible regardless of what an attacker might know — this tool is not sufficient. You need differential privacy, applied to aggregations, not pseudonymisation applied to text. For an accessible introduction to why, see Desfontaines' [*What anonymization techniques can you trust?*](https://desfontain.es/blog/trustworthy-anonymization.html) and Katharine Jarmul's [*Probably Private*](https://probablyprivate.com/).

If your use case is **operational privacy** — keeping PII out of places it should not be, reducing accidental exposure, improving your compliance posture — this tool is useful. It is, as the name says, better-than-nothing. It is not a substitute for a proper data privacy programme.

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
Limitation: The PII flag is assigned from a static classification map. It does not account for context — a name is flagged as PII whether or not the person is a public figure, whether or not combining it with other fields creates a unique identifier.

**Sensitivity**
Definition: A four-tier classification of harm potential if an entity were exposed: `low`, `medium`, `high`, `critical`. Assigned per EntityType from the classification map; not computed dynamically from context.

| Tier     | Examples                                         |
|----------|--------------------------------------------------|
| critical | TFN, Medicare, credit card                       |
| high     | Full name + BSB, passport, driver licence        |
| medium   | Email, phone, street address                     |
| low      | ABN/ACN, dates, publicly available information   |

Limitation: Sensitivity is a per-type heuristic, not a property of the specific data. A person's email address is always `medium` even if that address is their legal name combined with their employer, which together are highly identifying in context.

**Detection**
Definition: The act of running recognisers over input text and returning a `DetectionResult`. Detection is deterministic given the same text and model.
Limitation: Detection finds known patterns. It does not find all possible identifying information. The set of recognisers represents known Australian financial entity types — it is not exhaustive.

**DetectionResult**
Definition: The output of a Detection: a sorted tuple of Entities plus a SHA-256 audit hash of the original input. Immutable (frozen Pydantic model).

**Recogniser**
Definition: A presidio `EntityRecognizer` subclass — the atomic detection unit. Each recogniser is responsible for exactly one EntityType. Australian financial recognisers include checksum validation where the issuing authority publishes an algorithm (TFN, ABN, Medicare).

**Pseudonymisation**
Definition: What this service actually does. Detected entity spans are replaced with consistent labelled placeholders. The `entity_map` records the original PII spans as keys — it is sensitive data that must be treated with the same controls as the original text. Note: the map is not sufficient to reconstruct the full original document — placeholders are not positionally indexed, multiple distinct spans may collapse to the same label, and the map is explicitly approximate for `mask`/`hash` operators (where the exact output is not knowable before the engine runs). Re-identification risk comes primarily from the original PII values stored as keys, not from the ability to reverse the entire document.
Priveil / external term: Callers and documentation sometimes use "anonymisation" loosely. In this codebase, "anonymise" refers to the pseudonymisation operation. True anonymisation — where re-identification is mathematically infeasible — is explicitly out of scope.
Not to be confused with: Anonymisation. The distinction matters legally (Privacy Act), technically, and ethically.

**Operator**
Definition: A named strategy for transforming a detected Entity span: `replace` (swap with a labelled placeholder), `mask` (overwrite characters), `redact` (remove entirely), `hash` (SHA-256 of the span). Each EntityType has a default Operator; callers may override per-request.
Note: Even `redact` (empty string) does not produce anonymous output — the structure of the text, the positions of other entities, and any undetected entities remain.

**AnonymisationResult**
Definition: The output of the pseudonymisation operation: the modified text string plus an `entity_map` that maps original PII spans to their replacement labels, for audit purposes. The map is an approximation for `mask` and `hash` operators — the exact transformed value is not knowable before the engine runs. The map is sensitive data (its keys are the original PII values) and must be protected with the same access controls as the original text.

**Mode**
Definition: A request-level switch controlling the speed/accuracy tradeoff: `fast` returns raw detector output; `judge` runs an LLM refinement pass to remove false positives. Defaults to `judge`; degrades silently to `fast` when no judge model is configured.
Not to be confused with: A global server setting. Mode is per-request.

**Refiner**
Definition: An internal LLM agent that receives a DetectionResult and returns a cleaned DetectionResult — removing false positives and surfacing missed entities. Never exposed on the API surface. Improves operational precision; does not provide anonymisation guarantees.

**Assessment**
Definition: An LLM-produced risk profile of a piece of text: overall sensitivity tier, risk categories, applicable Australian regulatory frameworks, recommended handling guidance, and a per-EntityType breakdown. Answers "how sensitive is this content and how should we handle it?" — not "is this content anonymous?"

**AssessmentResult**
Definition: The output of an Assessment. `entity_breakdown` is computed from the DetectionResult (not from the LLM) so it is always grounded in the actual detected entities.

**Input Hash**
Definition: A SHA-256 hex digest of the original input text, included in every DetectionResult and AnonymisationResult. Used for audit — downstream systems can verify the text they processed matches what was detected without storing the text itself.

---

## Bounded Contexts

### Detection
Owns: entity recognition over text, AU financial recognisers, checksum validation, DetectionResult construction.
Depends on: presidio-analyzer (NLP engine), spaCy (NLP backend), recogniser registry.
Does not own: pseudonymisation logic, LLM calls, risk assessment.

### Pseudonymisation
Owns: operator configuration, applying operators to detected spans, AnonymisationResult construction.
Depends on: presidio-anonymizer (engine), Detection (for auto-detect when no detections are provided).
Does not own: what counts as PII, which entities to detect, risk classification.

### Judge
Owns: LLM refinement (Refiner), content risk assessment (Assessor), system prompt files.
Depends on: pydantic-ai (agent framework), Detection (for entity context), a configured LLM provider.
Does not own: detection logic, pseudonymisation operators, API routing.
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
| Outbound | presidio-anonymizer | RecognizerResult list + OperatorConfig map → pseudonymised text |
| Outbound | LLM provider (built-in: Anthropic, OpenAI, Bedrock; custom: any OpenAI-compatible endpoint e.g. Databricks Serving Endpoints) | Prompt + structured output schema → RefinerDecision / AssessmentDecision |
| Outbound | spaCy | Text → NLP pipeline (tokenisation, NER) |

---

## Domain Events

**EntityDetected**
Triggered by: a call to `/detect` or the internal detection step in `/anonymise` and `/assess`.
Downstream: DetectionResult returned; optionally passed to Refiner or Assessor.

**DetectionRefined**
Triggered by: Mode = `judge` and a judge model is configured.
Downstream: Cleaned DetectionResult replaces the raw result before the API response is sent. Does not change the fundamental incompleteness of detection.

**TextPseudonymised**
Triggered by: a call to `/anonymise`.
Downstream: AnonymisationResult returned; entity_map available for audit trail. entity_map must be handled as sensitive.

**ContentAssessed**
Triggered by: a call to `/assess`.
Downstream: AssessmentResult returned; caller uses sensitivity tier and regulatory flags to determine handling. Assessment is a heuristic, not a legal determination.

---

## Architecture Decisions

**Decision: Presidio as the detection core, not a fine-tuned model**
Context: Detection needs to be fast, deterministic, explainable, and auditable. LLMs add latency and non-determinism as the primary detection mechanism.
Decision: Presidio (rule-based + NER) handles all entity recognition. LLM is additive — refinement and assessment only, never on the critical detection path.
Consequences: High precision on Australian financial identifiers via checksum validation. Recall on edge cases handled by Mode = `judge`. No LLM dependency for core functionality.

**Decision: Australian financial entity types are explicit in the enum, not inferred**
Context: Generic spaCy/presidio models do not reliably surface TFN, ABN, BSB, Medicare card numbers.
Decision: Each AU type is a dedicated `PatternRecognizer` with checksum validation where applicable. They are registered at engine startup and contribute to the same DetectionResult as standard types.
Consequences: High precision on AU financial entities. No magic fallback — if an EntityType is not in the enum, it does not exist in this domain. This is a deliberate limitation: unknown entity types pass through undetected.

**Decision: This service provides pseudonymisation, not anonymisation**
Context: The research literature is unambiguous that pattern-based de-identification does not produce mathematically anonymous data. Data is more identifiable than it appears; auxiliary data can break any scheme that does not have a provable guarantee; attacks improve over time. See Desfontaines, *What anonymization techniques can you trust?* (2023); Jarmul, *Probably Private* (ongoing). Only differential privacy provides guarantees that are resistant to arbitrary auxiliary data and future attacks.
Decision: This service is explicitly scoped to **operational pseudonymisation** — reducing obvious PII exposure in systems that handle financial text. It does not claim to produce anonymised data. The name "Priveil" and the term "pseudonymisation" are used throughout to signal this scope. True anonymisation is out of scope.
Consequences: Callers who need data that is safe to publish or share without privacy controls must use differential privacy, not this service. The `entity_map` must be treated as sensitive. The service is useful and valuable within its stated scope — preventing accidental PII exposure, meeting process requirements, improving compliance posture — without overclaiming.

**Decision: Mode (fast/judge) is per-request, not a server-side global**
Context: Some callers need throughput (batch jobs); others need accuracy (interactive, compliance-sensitive).
Decision: `mode` is a field on DetectionRequest and AnonymisationRequest. `judge` is the default. The LLM is only invoked when mode = `judge` and a judge model is configured.
Consequences: Callers opt out explicitly by setting `mode: fast`. When PRIVEIL_JUDGE_MODEL is unset, judge silently degrades to fast — no config change required on the client side.

**Decision: Refiner is internal; Assessment is the only LLM-facing endpoint**
Context: Exposing an endpoint that lets callers "judge" detector accuracy couples them to an internal implementation detail and reveals that AI is involved in routine detection.
Decision: The Refiner is invoked transparently inside `/detect` and `/anonymise`. The only public LLM endpoint is `/assess`, which answers a genuinely different question: how sensitive is this content and how should it be handled?
Consequences: The public API surface is stable regardless of whether the underlying LLM changes, is disabled, or is replaced. Assessment is explicitly an LLM feature — callers know what they are getting.

**Decision: Checksum validation on AU financial identifiers**
Context: TFN, ABN, Medicare, and ACN all have publicly published checksum algorithms from the issuing authority (ATO, ASIC, DVA). Without checksum validation, pattern-only recognisers produce unacceptably high false positive rates on nine-digit sequences.
Decision: Each recogniser implements the authority's checksum. A failed checksum returns no match; the entity is dropped. A passing checksum boosts the score to 1.0.
Consequences: Near-zero false positives on AU financial identifiers in structured financial text. Any TFN that passes is cryptographically consistent with the ATO's algorithm, though not guaranteed to be a real issued number. Checksum validation is a precision improvement, not an anonymisation technique.

---

## Goals and Success Criteria

**What "good" looks like:**
- A TFN, BSB, or Medicare number in any realistic Australian financial document is detected and pseudonymised correctly, without the caller writing any detection logic.
- Clean financial text (interest rates, loan amounts, product codes) produces zero entities — no noise that burdens downstream systems.
- Mode = `judge` removes the false positives that pattern matching alone cannot; mode = `fast` is suitable for high-volume preprocessing where a small FP rate is acceptable.
- Callers understand what they have and have not received. A caller who receives a pseudonymised document knows they still have sensitive data that requires appropriate controls.
- The service adds no friction to callers who don't want the LLM — `PRIVEIL_JUDGE_MODEL` unset means the service runs purely on presidio with no degraded behaviour, just no LLM features.

**How we know the domain is struggling:**
- False positive rate on clean financial text rises — rates, amounts, dates being flagged as entities.
- Callers treat pseudonymised output as anonymous and remove downstream privacy controls — this is a documentation and communication failure.
- Checksum-valid but contextually wrong detections that the Refiner does not catch (e.g. a 9-digit product code that happens to pass TFN checksum).
- `entity_map` drift — the audit map diverges from what was actually pseudonymised in the text (indicates a bug in entity map construction).
- Assessment regulatory flags that are consistently wrong for a document type — indicates the assessor system prompt needs tuning.

---

## Further Reading

The limitations described above are well-documented in the privacy engineering literature. These are the primary sources that informed this document:

- Damien Desfontaines, *[What anonymization techniques can you trust?](https://desfontain.es/blog/trustworthy-anonymization.html)* (2023) — the foundational overview of why pseudonymisation, masking, and rule-based techniques fail as anonymisation.
- Damien Desfontaines, *[Five stages of accepting provably robust anonymization](https://desfontain.es/blog/five-stages.html)* (2024) — an honest account of why the industry continues to use techniques that researchers know to be insufficient, and what a path forward looks like.
- Katharine Jarmul, *[Probably Private](https://probablyprivate.com/)* — newsletter covering probabilistic privacy, AI privacy, and the practical gap between claimed and actual privacy guarantees.
- Latanya Sweeney, *k-anonymity: A Model for Protecting Privacy* (2002) — the original paper on k-anonymity, useful context for understanding what early formalisms tried to achieve and why they fell short.
