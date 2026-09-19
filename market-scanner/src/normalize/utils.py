from datetime import datetime
import re

def normalize_name(name: str) -> str:
    name = name.lower()
    name = re.sub(r'[^a-z0-9 ]', '', name)
    return name.strip()

def parse_utc(ts: str) -> str:
    if ts is None:
        return None
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return dt.isoformat()

def minutes_diff(t1: str, t2: str) -> float:
    if not t1 or not t2:
        return 999
    dt1 = datetime.fromisoformat(t1)
    dt2 = datetime.fromisoformat(t2)
    return abs((dt1 - dt2).total_seconds()) / 60
