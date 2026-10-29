from collections import Counter

def topic_evolution(topics,config):
    width=config.evolution_window_hours*3600000
    step=config.evolution_step_hours*3600000
    results=[]
    for topic in topics:
        members=topic["members"]
        first=min(r.t_start for r in members)
        last=max(r.t_start for r in members)
        start=first-first%step
        while start<=last:
            current=[r for r in members if start<=r.t_start<start+width]
            scored=[r.sentiment for r in current if r.sentiment is not None]
            negative=sum(value<0 for value in scored)
            by_channel=Counter(r.channel or r.outlet or r.source_id for r in current)
            results.append({"topic_id":topic["topic_id"],"t_start":start,"t_end":start+width,"count":len(current),"mean_sentiment":sum(scored)/len(scored) if scored else None,"negative_share":negative/len(scored) if scored else None,"channels":dict(sorted(by_channel.items()))})
            start+=step
    return results
