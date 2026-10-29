CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS mock;
CREATE SCHEMA IF NOT EXISTS processed;
CREATE TABLE IF NOT EXISTS processed.ai08_embeddings (
    record_id text PRIMARY KEY,
    model_name text NOT NULL,
    model_version text NOT NULL,
    dimensions integer NOT NULL CHECK (dimensions > 0),
    embedding double precision[] NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS processed.ai08_events (
    event_id text PRIMARY KEY,
    content jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS processed.ai08_reviews (
    review_id text PRIMARY KEY,
    event_id text NOT NULL REFERENCES processed.ai08_events(event_id),
    decision text NOT NULL CHECK (decision IN ('accept','reject','correct')),
    reviewer text NOT NULL,
    reviewed_at bigint NOT NULL,
    corrected_value jsonb
);
CREATE INDEX IF NOT EXISTS ai08_reviews_event_idx ON processed.ai08_reviews(event_id);
CREATE TABLE IF NOT EXISTS processed.ai08_inference_queue (
    request_id text PRIMARY KEY,
    content jsonb NOT NULL,
    processed boolean NOT NULL DEFAULT false,
    result_ids jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ai08_queue_pending_idx ON processed.ai08_inference_queue(created_at) WHERE processed = false;
CREATE TABLE IF NOT EXISTS processed.ai08_signal_outbox (
    event_id text PRIMARY KEY REFERENCES processed.ai08_events(event_id),
    published boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ai08_outbox_pending_idx ON processed.ai08_signal_outbox(created_at) WHERE published = false;
