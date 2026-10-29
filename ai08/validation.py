import hashlib
import json
from .contracts import ReviewFeedback

def apply_feedback(store,feedback:ReviewFeedback):
    value=json.dumps(feedback.model_dump(),ensure_ascii=False,sort_keys=True,separators=(",",":"))
    review_id=hashlib.sha256(value.encode("utf-8")).hexdigest()
    return store.apply_decision(review_id,feedback)
