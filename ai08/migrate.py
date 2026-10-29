import os
from pathlib import Path
import psycopg
from psycopg import sql

def migrate():
    dsn=os.environ.get("DATABASE_ADMIN_URL")
    username=os.environ.get("AI08_DB_USER")
    password=os.environ.get("AI08_DB_PASSWORD")
    if not dsn or not username or not password:
        raise RuntimeError("DATABASE_ADMIN_URL, AI08_DB_USER and AI08_DB_PASSWORD are required")
    source=Path(__file__).resolve().parent.parent/"database"/"migrations"/"001_ai08.sql"
    with psycopg.connect(dsn) as connection:
        connection.execute(source.read_text(encoding="utf-8"))
        exists=connection.execute("SELECT 1 FROM pg_roles WHERE rolname=%s",(username,)).fetchone()
        if not exists:
            connection.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(sql.Identifier(username),sql.Literal(password)))
        else:
            superuser=connection.execute("SELECT rolsuper FROM pg_roles WHERE rolname=%s",(username,)).fetchone()[0]
            if superuser:
                raise ValueError("AI08_DB_USER must not be a superuser")
            connection.execute(sql.SQL("ALTER ROLE {} LOGIN PASSWORD {}").format(sql.Identifier(username),sql.Literal(password)))
        connection.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(connection.info.dbname),sql.Identifier(username)))
        connection.execute(sql.SQL("REVOKE USAGE ON SCHEMA raw,mock FROM {}").format(sql.Identifier(username)))
        connection.execute(sql.SQL("REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA raw,mock FROM {}").format(sql.Identifier(username)))
        connection.execute(sql.SQL("GRANT USAGE ON SCHEMA processed TO {}").format(sql.Identifier(username)))
        connection.execute(sql.SQL("GRANT SELECT,INSERT,UPDATE,DELETE ON TABLE processed.ai08_embeddings,processed.ai08_events,processed.ai08_reviews,processed.ai08_inference_queue,processed.ai08_signal_outbox TO {}").format(sql.Identifier(username)))

if __name__=="__main__":
    migrate()
