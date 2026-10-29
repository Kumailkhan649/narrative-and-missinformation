# AI-08 backend — Python 3.13 and PostgreSQL 16

Backend-only Topics, Trends and Misinformation development implementation. No frontend, training code, external inference API or model weights included. Only incoming embeddings or vectors supplied by AI-06 are accepted. Models are reserved behind `ai08/providers.py`; actual team-trained artifacts are not loaded yet.

## Shared database architecture

Exactly one PostgreSQL 16 database and three schemas, `raw`, `mock` and `processed`. The AI-08 tables are prefixed `ai08_` so other modules can use the same database without table-name collisions. Original input storage is `raw.ai08_source_records`; synthetic test data belongs in `mock.ai08_fixtures`; embeddings, events, reviews, near-line queue and output outbox belong in `processed`. Inference only writes to `processed`. There are no automatic raw/mock writes. The migration creates only additive AI-08 objects and grants the AI-08 runtime role access to AI-08 tables; it does not reset existing schemas or databases. Do not mount a second module's separate database volume for a shared deployment.

## Windows / Docker workflow

Use Docker Desktop with Docker Compose. At the project root, copy `.env.example` to `.env` and replace all placeholder credentials consistently, including both URLs. Never commit `.env`. Run `docker compose up -d --build`; PostgreSQL starts first, migration completes before API starts. The local endpoint is `http://127.0.0.1:8001/docs`. Do not publish this unauthenticated development API beyond localhost. For integration testing, run `& .\tests\run_all.ps1` as one PowerShell command. This runs unit/API tests plus PostgreSQL 16 integration tests, then the code quality check. Do not use `docker compose down -v` on an existing shared database.

## Explicit model contract

`ai08/providers.py` reserves inference and embedding-provider interfaces for trained models from collaborators. Inputs must already contain finite embeddings or resolvable references. The previously downloaded BGE-M3 was a separate local smoke test; it is not an embedded AI-08 dependency or automatically selected model. `models/` is reserved and mounted read-only. The deployed model format, training, thresholds, precision target, reference corpus and real input event schemas require team approval. Missing embeddings return 422 via the API. For now only synthetic data may be used unless authorized.

## API and event contract

`POST /v1/ai08/infer` accepts enriched records and returns 15-field `analytics.signals.v1` envelopes. The local review, evaluation and event-read endpoints remain to exercise AI-08.06 and AI-08.08; their final integration with AI-17 is pending. Risk flags are review signals, not verified misinformation verdicts. Synthetic rule thresholds are uncalibrated. Near-line processing has local persisted queue/outbox methods, not a real event broker. Final `nlp.enriched`, `analytics.signals` payload, AI-07, AI-11 and AI-17 integration must be checked with the other teams.

## Testing scope

`python -m unittest discover -s tests -v` without `DATABASE_URL` runs unit/API tests and marks PostgreSQL integration tests skipped. `docker compose run --rm --no-deps ai08 python -m unittest discover -s tests -v` after migrations runs both, using `DATABASE_URL`. Docker and PostgreSQL live tests must pass in your environment before this build can be called database-verified. `python tools/check_no_comments.py` enforces zero comments/docstrings in backend Python files.
