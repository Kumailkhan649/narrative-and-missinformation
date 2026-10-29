from collections import defaultdict
from datetime import datetime,timezone
from statistics import median
from .contracts import MentionCount

HOUR=3600000

def collect_mentions(records,mention_counts):
    if mention_counts:
        return mention_counts
    counts=defaultdict(lambda:[0,0])
    for record in records:
        bucket=record.t_start//HOUR*HOUR
        for subject in {"overall",*record.entities,*record.tags}:
            counts[(subject,bucket)][0]+=1
            counts[(subject,bucket)][1]+=int(record.sentiment is not None and record.sentiment<0)
    return [MentionCount(subject=subject,t_start=bucket,count=count,negative_count=negative) for (subject,bucket),(count,negative) in sorted(counts.items())]

def detect_spikes(records,mention_counts,config):
    grouped=defaultdict(dict)
    for item in collect_mentions(records,mention_counts):
        bucket=item.t_start//HOUR*HOUR
        observed=grouped[item.subject].setdefault(bucket,[0,0])
        observed[0]+=item.count
        observed[1]+=item.negative_count
    spikes=[]
    for subject,series in grouped.items():
        buckets=sorted(series)
        for bucket in buckets:
            stamp=datetime.fromtimestamp(bucket/1000,timezone.utc)
            historic=[past for past in buckets if past<bucket]
            same_day_hour=[past for past in historic if datetime.fromtimestamp(past/1000,timezone.utc).weekday()==stamp.weekday() and datetime.fromtimestamp(past/1000,timezone.utc).hour==stamp.hour]
            same_hour=[past for past in historic if datetime.fromtimestamp(past/1000,timezone.utc).hour==stamp.hour]
            selected=same_day_hour if len(same_day_hour)>=config.baseline_min_observations else same_hour
            baseline_type="day_of_week_and_hour" if selected is same_day_hour else "hour_of_day"
            if len(selected)<config.baseline_min_observations:
                continue
            for index,signal in ((0,"mention_spike"),(1,"negative_sentiment_spike")):
                observed=series[bucket][index]
                history=[series[past][index] for past in selected]
                expected=median(history)
                mad=median(abs(value-expected) for value in history)
                score=(observed-expected)/max(1.0,1.4826*mad)
                if observed>=config.spike_min_count and score>=config.spike_z_threshold:
                    spikes.append({"type":signal,"subject":subject,"t_start":bucket,"t_end":bucket+HOUR,"observed":observed,"expected":expected,"robust_z":score,"baseline":baseline_type,"history_observations":len(selected),"confidence":min(1.0,len(selected)/8)})
    return spikes
