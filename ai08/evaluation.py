def flag_precision(reviews):
    latest={}
    for review in sorted(reviews,key=lambda item:item["time"]):
        latest[review["event_id"]]=review["decision"]
    confirmed=sum(value=="accept" for value in latest.values())
    rejected=sum(value=="reject" for value in latest.values())
    corrected=sum(value=="correct" for value in latest.values())
    denominator=confirmed+rejected
    return {"confirmed":confirmed,"rejected":rejected,"corrected":corrected,"reviewed":len(latest),"precision":confirmed/denominator if denominator else None,"target":"not agreed"}
