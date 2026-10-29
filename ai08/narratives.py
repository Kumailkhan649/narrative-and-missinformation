import re
from hashlib import sha256

CUES=("according to","claimed","claims","alleged","کے مطابق","دعویٰ","الزام","ke mutabiq","ki mutabiq","daawa","ilzam")

def normalize(text):
    return " ".join(re.findall(r"\w+",text.casefold(),flags=re.UNICODE))

def extract_claims(record):
    sentences=[s.strip() for s in re.split(r"[.!?؟۔\n]+",record.text) if s.strip()]
    return [sentence for sentence in sentences if any(ch.isdigit() for ch in sentence) or any(cue in sentence.casefold() for cue in CUES)]

def similarity(left,right):
    a=set(normalize(left).split())
    b=set(normalize(right).split())
    return len(a&b)/len(a|b) if a and b else 0.0

def track_narratives(records,vectors,config):
    groups=[]
    for record in sorted(records,key=lambda r:(r.t_start,r.record_id)):
        for claim in extract_claims(record):
            numbers=set(re.findall(r"\d+(?:[.,]\d+)*",claim))
            entities=set(x.casefold() for x in record.entities)
            best=-1
            best_score=0.0
            for index,group in enumerate(groups):
                if group["numbers"]!=numbers:
                    continue
                if entities and group["entities"] and not entities&group["entities"]:
                    continue
                lexical=similarity(claim,group["claims"][0])
                score=lexical
                if score>=config.narrative_similarity and score>best_score:
                    best=index
                    best_score=score
            if best<0:
                groups.append({"claims":[claim],"records":[record],"numbers":numbers,"entities":entities,"scores":[1.0]})
            else:
                groups[best]["claims"].append(claim)
                groups[best]["records"].append(record)
                groups[best]["entities"].update(entities)
                groups[best]["scores"].append(best_score)
    narratives=[]
    for group in groups:
        members=list({r.record_id:r for r in group["records"]}.values())
        members.sort(key=lambda r:(r.t_start,r.record_id))
        sources={r.source_id for r in members}
        if len(members)<config.narrative_min_mentions or len(sources)<config.narrative_min_sources:
            continue
        sentiments=[r.sentiment for r in members if r.sentiment is not None]
        timeline=[{"record_id":r.record_id,"source_type":r.source_type,"source_id":r.source_id,"time":r.t_start} for r in members]
        narrative_id="narrative-"+sha256(normalize(group["claims"][0]).encode("utf-8")).hexdigest()[:12]
        narratives.append({"narrative_id":narrative_id,"example_claims":list(dict.fromkeys(group["claims"]))[:5],"size":len(members),"origin":timeline[0],"spread_timeline":timeline,"source_types":sorted({r.source_type for r in members}),"channels":sorted({r.channel or r.outlet or r.source_id for r in members}),"first_seen":members[0].t_start,"last_seen":max(r.t_end for r in members),"mean_sentiment":sum(sentiments)/len(sentiments) if sentiments else None,"confidence":sum(group["scores"])/len(group["scores"]),"members":members})
    return narratives
