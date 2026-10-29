import os
import unittest
from ai08.service import AI08Service
from ai08.contracts import EnrichedRecord,InferRequest,ReferenceClaim,ReviewFeedback
if os.environ.get("DATABASE_URL"):
    from psycopg import connect
    from psycopg.types.json import Jsonb

@unittest.skipUnless(os.environ.get("DATABASE_URL") and os.environ.get("AI08_TEST_DATABASE")=="1","Explicit local PostgreSQL test mode not enabled")
class PostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service=AI08Service()

    def test_database_version_and_three_schemas(self):
        with connect(os.environ["DATABASE_URL"]) as connection:
            version=int(connection.execute("SHOW server_version_num").fetchone()[0])
            self.assertGreaterEqual(version,160000)
            self.assertLess(version,170000)
            rows=connection.execute("SELECT nspname FROM pg_catalog.pg_namespace WHERE nspname IN ('raw','mock','processed')").fetchall()
            self.assertEqual({row[0] for row in rows},{"raw","mock","processed"})

    def test_isolated_mock_and_processed_data(self):
        with connect(os.environ["DATABASE_URL"]) as connection:
            privileges=connection.execute("SELECT has_schema_privilege(current_user,'raw','USAGE'),has_schema_privilege(current_user,'mock','USAGE'),has_schema_privilege(current_user,'processed','USAGE')").fetchone()
            self.assertEqual(privileges,(False,False,True))
            self.assertFalse(connection.execute("SELECT has_table_privilege(current_user,'processed.ai08_events','TRUNCATE')").fetchone()[0])

    def test_inference_review_and_embedding_persistence(self):
        import uuid
        identifier=uuid.uuid4().hex
        claim="According to the synthetic report spending rose 50 percent"
        items=[EnrichedRecord(record_id=f"{identifier}-a",source_type="tv",source_id=f"{identifier}-tv",t_start=1760000000000,t_end=1760000000100,language="English",text=claim,embedding=[1,0]),EnrichedRecord(record_id=f"{identifier}-b",source_type="digital",source_id=f"{identifier}-digital",t_start=1760000002000,t_end=1760000002100,language="English",text=claim,embedding=[1,0])]
        reference=ReferenceClaim(claim="Synthetic contradiction",source_id="synthetic-reference",evidence_uri="synthetic:ref",refutes=[claim])
        request=InferRequest(records=items,reference_claims=[reference])
        events=[]
        try:
            events=self.service.infer(request)
            flag=next(event for event in events if event.payload.get("type")=="potential_misinformation")
            self.service.review(ReviewFeedback(event_id=flag.event_id,decision="accept",reviewer="synthetic-reviewer",time=1760000100000))
            second=AI08Service()
            self.assertEqual(second.store.get(flag.event_id).review_status,"accepted")
            self.assertEqual(next(event for event in second.infer(request) if event.event_id==flag.event_id).review_status,"accepted")
            with connect(os.environ["DATABASE_URL"]) as connection:
                row=connection.execute("SELECT dimensions,embedding FROM processed.ai08_embeddings WHERE record_id=%s",(items[0].record_id,)).fetchone()
                self.assertEqual(row[0],2)
                self.assertEqual(row[1],[1,0])
        finally:
            with connect(os.environ["DATABASE_URL"]) as connection:
                for event in events:
                    connection.execute("DELETE FROM processed.ai08_signal_outbox WHERE event_id=%s",(event.event_id,))
                    connection.execute("DELETE FROM processed.ai08_reviews WHERE event_id=%s",(event.event_id,))
                    connection.execute("DELETE FROM processed.ai08_events WHERE event_id=%s",(event.event_id,))
                for item in items:
                    connection.execute("DELETE FROM processed.ai08_embeddings WHERE record_id=%s",(item.record_id,))

    def test_failed_transaction_rolls_back(self):
        import uuid
        key=uuid.uuid4().hex
        try:
            with connect(os.environ["DATABASE_URL"]) as connection:
                connection.execute("INSERT INTO processed.ai08_inference_queue(request_id,content) VALUES (%s,%s)",(key,Jsonb({"synthetic":True})))
                raise RuntimeError("deliberate synthetic rollback")
        except RuntimeError:
            pass
        with connect(os.environ["DATABASE_URL"]) as connection:
            self.assertIsNone(connection.execute("SELECT request_id FROM processed.ai08_inference_queue WHERE request_id=%s",(key,)).fetchone())
