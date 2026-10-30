# AI-08 Integration Handoff

## Scope

Backend-only AI-08 Topics, Trends, Narratives, Misinformation and Bias.
Python 3.13, FastAPI, PostgreSQL 16.
One shared database and exactly three project-data schemas: raw, mock, processed.
AI-08 owns its five processed.ai08_* tables.
No shared schema resets, model training, or frontend work are authorized.

## Implemented API Routes

- `POST /v1/ai08/infer`
- `POST /v1/ai08/review`
- `GET /v1/ai08/evaluation`
- `GET /v1/ai08/events/{event_id}`

Current OpenAPI bearer-security declaration on all four routes: not present; authentication work pending.
Do not expose an unauthenticated development API publicly.

## Current Input and Output Contracts

Approved source types in current code: tv, print, digital.
Approved languages in current code: Urdu, English, Pashto, Roman Urdu.
Required embeddings must be supplied or resolvable; model integration is not yet configured.
Timestamp units, model identity and deployment contracts require upstream agreement.

### Enriched Record ? Incoming Data

| Field | Requirement |
|---|---|
| `record_id` | required |
| `source_type` | required |
| `source_id` | required |
| `segment_id` | optional/defaulted |
| `channel` | optional/defaulted |
| `outlet` | optional/defaulted |
| `t_start` | required |
| `t_end` | required |
| `language` | required |
| `text` | required |
| `entities` | optional/defaulted |
| `tags` | optional/defaulted |
| `keywords` | optional/defaulted |
| `sentiment` | optional/defaulted |
| `target_sentiment` | optional/defaulted |
| `embedding` | optional/defaulted |
| `embedding_ref` | optional/defaulted |
| `account_id` | optional/defaulted |
| `evidence_uri` | optional/defaulted |

### Inference Request

| Field | Requirement |
|---|---|
| `records` | required |
| `mention_counts` | optional/defaulted |
| `embedding_vectors` | optional/defaulted |
| `reference_claims` | optional/defaulted |
| `config` | optional/defaulted |

### Reference Claim

| Field | Requirement |
|---|---|
| `claim` | required |
| `source_id` | required |
| `evidence_uri` | required |
| `refutes` | optional/defaulted |

### Analyst Review Feedback

| Field | Requirement |
|---|---|
| `event_id` | required |
| `decision` | required |
| `reviewer` | required |
| `time` | required |
| `corrected_value` | optional/defaulted |

### Output Event Envelope ? 15 Fields

| Field | Requirement |
|---|---|
| `event_id` | required |
| `schema` | required |
| `source_type` | required |
| `source_id` | required |
| `segment_id` | required |
| `t_start` | required |
| `t_end` | required |
| `module` | required |
| `model` | required |
| `language` | required |
| `confidence` | required |
| `payload` | required |
| `evidence_uri` | required |
| `review_status` | required |
| `created_at` | required |


## AI-08.05 ? Misinformation and Bias

- Local synthetic risk/evidence tests pass.
- Risk flags are analyst-review signals, not factual truth verdicts.
- Required externally: reviewed reference claims, labelled examples, evidence rules and calibration methodology.
- Pending: agreed thresholds and real-data performance evaluation.

## AI-08.06 ? Analyst Validation

- Local accept, reject, correct and persistence workflows are implemented.
- Required from AI-17: approved review-event schema, identity/authorization contract and delivery mechanism.
- Map actual AI-17 fields to ReviewFeedback only after the contract is supplied.
- Integration must verify event IDs, idempotency, review conflicts and error handling.

## AI-08.07 ? Coordination

- Local account-based coordination tests pass.
- Required from AI-11: approved records with account identifiers, source types, timestamps and evidence references.
- Confirm account identity, time units, duplicates and missing-field behavior using actual upstream samples.
- Coordination is a risk indicator, not proof of coordinated misconduct.

## AI-08.08 ? Evaluation

- Local review-based precision calculation is tested.
- No labelled reviews must produce an undefined precision rather than an invented score.
- Required: approved labelled evaluation set, metric definitions, target and reviewer agreement process.
- Real-world precision, recall and calibration are not yet verified.

## Integration Dependencies

| Provider | Required handoff | State |
|---|---|---|
| AI-06 | Final enriched-record and embedding sample | Pending upstream verification |
| AI-07 | Agreed sentiment/target-sentiment output contract | Pending upstream verification |
| AI-11 | Account and coordination input sample | Pending upstream verification |
| AI-17 | Review feedback and identity contract | Pending upstream verification |
| Model team | Approved trained artifacts, versions and interfaces | Pending handoff |

## Release Gates

- Verify all module mappings with real upstream contract samples.
- Validate access control before non-local API deployment.
- Run full Python and PostgreSQL integration tests.
- Run representative labelled-data evaluation before performance claims.
- Verify Docker runtime when the infrastructure blocker is resolved.
- Obtain team approval before changing shared integration interfaces.

## Current Verification Baseline

- 40 automated tests passed, including four live PostgreSQL tests.
- Eight new targeted tests cover AI-08.05 through AI-08.08.
- The external integrations and real calibration remain pending.
