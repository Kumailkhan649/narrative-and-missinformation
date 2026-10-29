import unittest
from fastapi.testclient import TestClient
from ai08.api import app,get_service
from ai08.service import AI08Service
from tests.support import MemoryEventStore

@unittest.skipIf(TestClient is None,"FastAPI test dependencies unavailable")
class APITests(unittest.TestCase):
    def setUp(self):
        self.service=AI08Service(store=MemoryEventStore())
        app.dependency_overrides[get_service]=lambda:self.service

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_infer_contract(self):
        payload={"records":[{"record_id":"api-1","source_type":"tv","source_id":"source-1","t_start":1760000000000,"t_end":1760000001000,"language":"Urdu","text":"منصوبے کا بجٹ 50 فیصد بڑھا","embedding":[1.0,0.0]}]}
        response=TestClient(app).post("/v1/ai08/infer",json=payload)
        self.assertEqual(response.status_code,200,response.text)
        self.assertGreaterEqual(len(response.json()),1)
        self.assertEqual(len(response.json()[0]),15)
        self.assertEqual(response.json()[0]["schema"],"analytics.signals.v1")

    def test_missing_embedding_is_422(self):
        payload={"records":[{"record_id":"api-2","source_type":"tv","source_id":"source-1","t_start":1760000000000,"t_end":1760000001000,"language":"Urdu","text":"خبر 50 فیصد"}]}
        response=TestClient(app).post("/v1/ai08/infer",json=payload)
        self.assertEqual(response.status_code,422)

    def test_invalid_language_is_422(self):
        payload={"records":[{"record_id":"api-3","source_type":"tv","source_id":"source-1","t_start":1760000000000,"t_end":1760000001000,"language":"French","text":"خبر 50 فیصد","embedding":[1.0,0.0]}]}
        response=TestClient(app).post("/v1/ai08/infer",json=payload)
        self.assertEqual(response.status_code,422)

    def test_review_endpoint_and_event_lookup(self):
        claim="According to report spending rose 50 percent"
        record={"source_type":"tv","t_start":1760000000000,"t_end":1760000001000,"language":"English","text":claim,"embedding":[1.0,0.0]}
        payload={"records":[{**record,"record_id":"api-a","source_id":"s1"},{**record,"record_id":"api-b","source_id":"s2"}],"reference_claims":[{"claim":"Report refutes it","source_id":"reference","evidence_uri":"reference:1","refutes":[claim]}]}
        client=TestClient(app)
        response=client.post("/v1/ai08/infer",json=payload)
        self.assertEqual(response.status_code,200,response.text)
        flag=next(item for item in response.json() if item["payload"].get("type")=="potential_misinformation")
        reviewed=client.post("/v1/ai08/review",json={"event_id":flag["event_id"],"decision":"accept","reviewer":"analyst","time":1760001000000})
        self.assertEqual(reviewed.status_code,200,reviewed.text)
        self.assertEqual(reviewed.json()["review_status"],"accepted")
        self.assertEqual(client.get(f"/v1/ai08/events/{flag['event_id']}").json()["review_status"],"accepted")
        self.assertEqual(client.get("/v1/ai08/evaluation").json()["precision"],1.0)

    def test_review_missing_event_is_404(self):
        response=TestClient(app).post("/v1/ai08/review",json={"event_id":"missing","decision":"reject","reviewer":"analyst","time":1760001000000})
        self.assertEqual(response.status_code,404)
