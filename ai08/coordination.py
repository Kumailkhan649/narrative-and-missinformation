def shingles(text,size=3):
    compact=" ".join(text.casefold().split())
    return {compact[i:i+size] for i in range(max(1,len(compact)-size+1))}

def detect_coordination(records,config):
    social=sorted((r for r in records if r.source_type=="digital" and r.account_id),key=lambda r:(r.t_start,r.record_id))
    window=config.coordination_window_minutes*60000
    candidates=[]
    parts={r.record_id:shingles(r.text) for r in social}
    for index,anchor in enumerate(social):
        matched=[anchor]
        for record in social[index+1:]:
            if record.t_start-anchor.t_start>window:
                break
            left=parts[anchor.record_id]
            right=parts[record.record_id]
            union=left|right
            score=len(left&right)/len(union) if union else 0.0
            if score>=config.coordination_similarity:
                matched.append(record)
        if len({r.account_id for r in matched})>=config.coordination_min_accounts:
            candidates.append(matched)
    selected=[]
    for group in sorted(candidates,key=lambda item:(-len(item),item[0].t_start)):
        ids={r.record_id for r in group}
        if not any(ids<={r.record_id for r in existing} for existing in selected):
            selected.append(group)
    groups=[]
    for component in selected:
        accounts={r.account_id for r in component}
        if len(accounts)>=config.coordination_min_accounts:
            groups.append({"accounts":sorted(accounts),"record_ids":sorted(r.record_id for r in component),"t_start":min(r.t_start for r in component),"t_end":max(r.t_end for r in component),"confidence":min(1.0,len(accounts)/config.coordination_min_accounts),"members":component})
    return groups
