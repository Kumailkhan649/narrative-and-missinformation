from collections import defaultdict
from .narratives import normalize

def narrative_flags(narratives,references,config):
    results=[]
    for narrative in narratives:
        matches=[]
        text_set={normalize(c) for c in narrative["example_claims"]}
        for reference in references:
            if any(normalize(claim) in text_set for claim in reference.refutes):
                matches.append({"source_id":reference.source_id,"claim":reference.claim,"evidence_uri":reference.evidence_uri})
        if not matches:
            continue
        members=narrative["members"]
        evidence=[{"record_id":r.record_id,"excerpt":r.text[:300],"time":r.t_start,"evidence_uri":r.evidence_uri} for r in members]
        results.append({"flag_id":f"flag-{narrative['narrative_id']}","type":"potential_misinformation","risk_score":config.contradiction_risk,"confidence":narrative["confidence"],"supporting_evidence":evidence,"contradicting_sources":matches,"review_status":"pending","members":members})
    return results

def bias_flags(records,config,assignments=None):
    targets=defaultdict(list)
    period=config.evolution_window_hours*3600000
    for record in records:
        for target,value in record.target_sentiment.items():
            group=(target.casefold(),(assignments or {}).get(record.record_id),record.t_start//period)
            targets[group].append((record,value))
    flags=[]
    for (target,topic_id,window),entries in sorted(targets.items()):
        by_source=defaultdict(list)
        for record,value in entries:
            by_source[record.source_id].append((record,value))
        means={source:sum(value for _,value in values)/len(values) for source,values in by_source.items()}
        if len(means)<2:
            continue
        difference=max(means.values())-min(means.values())
        if difference<config.bias_deviation:
            continue
        members=list({r.record_id:r for r,_ in entries}.values())
        flags.append({"flag_id":f"bias-{target}-{topic_id}-{window}","type":"possible_tone_bias","target":target,"topic_id":topic_id,"window":window,"risk_score":min(1.0,difference/2),"confidence":min(1.0,len(entries)/10),"source_mean_sentiment":means,"supporting_evidence":[{"record_id":r.record_id,"source_id":r.source_id,"target_sentiment":value,"excerpt":r.text[:300],"time":r.t_start,"evidence_uri":r.evidence_uri} for r,value in entries],"contradicting_sources":[],"review_status":"pending","members":members})
    return flags
