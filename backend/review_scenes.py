"""Local shot boundaries and evidence-constrained review edit decisions."""
import os
import re


def detect(job, command, duration_ms):
    from .worker import FORMATS
    output = command([
        os.getenv('DUBISUB_FFMPEG', 'ffmpeg'), '-v', 'error', '-nostdin',
        '-protocol_whitelist', 'file,pipe', '-format_whitelist', FORMATS,
        '-i', job['path'], '-an', '-vf',
        "scale=160:-2,fps=2,select='gt(scene,0.35)',metadata=print:file=-",
        '-f', 'null', '-'], job, timeout=3600)
    points = {0, duration_ms}
    for value in re.findall(r'pts_time:([\d.]+)', output):
        point = round(float(value) * 1000)
        if 0 < point < duration_ms:
            points.add(point)
    return sorted(points)


def select_ranges(ranges, boundaries, source_duration_ms):
    """Retain every cited interval; split at real cuts, never infer new events."""
    merged = []
    for row in sorted(ranges, key=lambda r: r['start_ms']):
        start = max(0, int(row['start_ms']))
        end = min(source_duration_ms, int(row['end_ms']))
        if end <= start:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(end, merged[-1][1])
        else:
            merged.append([start, end])
    return [{'start_ms': a, 'end_ms': b}
            for start, end in merged
            for a, b in zip([start] + [p for p in boundaries if start < p < end],
                            [p for p in boundaries if start < p < end] + [end])]


def select_shots(ranges, boundaries, source_duration_ms, output_duration_ms):
    """Represent every disjoint citation, with a bounded number of readable shots."""
    blocks=select_ranges(ranges,[],source_duration_ms)
    groups=[select_ranges([block],boundaries,source_duration_ms) for block in blocks]
    budget=max(len(groups),output_duration_ms//800)
    counts=[1]*len(groups)
    while sum(counts)<budget:
        candidates=[i for i,g in enumerate(groups) if counts[i]<len(g)]
        if not candidates:break
        index=max(candidates,key=lambda i:len(groups[i])/counts[i])
        counts[index]+=1
    selected=[]
    for group,count in zip(groups,counts):
        indices=[len(group)//2] if count==1 else [round(i*(len(group)-1)/(count-1)) for i in range(count)]
        selected.extend(group[i] for i in indices)
    return selected,sum(map(len,groups))-len(selected)
