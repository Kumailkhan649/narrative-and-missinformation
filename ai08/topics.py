from collections import Counter
from hashlib import sha256
import numpy as np
from .embeddings import cosine

def cluster_topics(records,vectors,config):
    clusters=[]
    assignments={}
    for record in sorted(records,key=lambda r:(r.t_start,r.record_id)):
        vector=np.asarray(vectors[record.record_id],dtype=float)
        similarities=[cosine(vector,cluster["centroid"]) for cluster in clusters]
        best=int(np.argmax(similarities)) if similarities else -1
        if best<0 or similarities[best]<config.topic_similarity:
            clusters.append({"centroid":vector.copy(),"members":[record],"scores":[1.0]})
            best=len(clusters)-1
        else:
            cluster=clusters[best]
            size=len(cluster["members"])
            cluster["centroid"]=(cluster["centroid"]*size+vector)/(size+1)
            cluster["members"].append(record)
            cluster["scores"].append(similarities[best])
        assignments[record.record_id]=best
    results=[]
    period=config.evolution_window_hours*3600000
    end=max(r.t_start for r in records)+1
    for index,cluster in enumerate(clusters):
        members=cluster["members"]
        topic_id="topic-"+sha256("|".join(sorted(r.record_id for r in members)).encode("utf-8")).hexdigest()[:12]
        common=Counter(x.casefold() for r in members for x in (r.keywords or r.tags))
        label=", ".join(word for word,_ in common.most_common(3)) or members[0].text[:80]
        latest=sum(end-period<=r.t_start<end for r in members)
        previous=sum(end-2*period<=r.t_start<end-period for r in members)
        emerging=latest>=config.emerging_min_count and (previous==0 or latest/previous>=config.emerging_ratio)
        results.append({"topic_id":topic_id,"label":label,"size":len(members),"member_record_ids":[r.record_id for r in members],"channels":sorted({r.channel or r.outlet or r.source_id for r in members}),"source_types":sorted({r.source_type for r in members}),"related_entities":sorted({e for r in members for e in r.entities}),"confidence":max(0.0,min(1.0,float(np.mean(cluster["scores"])))),"emerging":emerging,"previous_count":previous,"current_count":latest,"members":members})
        for record in members:
            assignments[record.record_id]=topic_id
    return results,assignments
