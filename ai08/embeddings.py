import numpy as np

def cosine(left,right):
    left=np.asarray(left,dtype=float)
    right=np.asarray(right,dtype=float)
    if left.shape!=right.shape or not left.size:
        raise ValueError("embedding dimensions mismatch")
    denominator=float(np.linalg.norm(left)*np.linalg.norm(right))
    return float(np.dot(left,right)/denominator) if denominator else 0.0

def resolve_embeddings(records,external_vectors,model_path=None):
    resolved={}
    for record in records:
        vector=record.embedding
        if vector is None and record.embedding_ref:
            vector=external_vectors.get(record.embedding_ref)
        if vector is None:
            raise ValueError("missing embeddings; AI-06 vectors or an approved model adapter are required")
        resolved[record.record_id]=vector
    dimensions={len(v) for v in resolved.values()}
    if len(dimensions)!=1 or not dimensions or 0 in dimensions:
        raise ValueError("embeddings must share one nonzero dimension")
    if any(not np.isfinite(v).all() for v in (np.asarray(x,dtype=float) for x in resolved.values())):
        raise ValueError("embeddings must be finite")
    return resolved
