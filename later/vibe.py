"""Natural-language edit -> timeline ops.
Ops: {"op":"speed","factor":1.5} {"op":"trim","clip":0,"in":0.5,"out":4}
     {"op":"caption","text":"..","start":0,"end":2} {"op":"auto_captions","text":".."}
     {"op":"music","src":".."} {"op":"beat_cut","bpm":120} {"op":"reverse_order"}"""
import json, os, re, urllib.request
SYSTEM = ("You convert video edit instructions into a JSON list of ops for a short-form 9:16 timeline. "
          "Allowed ops: " + __doc__.split("Ops:")[1] + " Reply ONLY with JSON: {\"ops\":[...]}.")
def _llm(instr, tl):
    base, key = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1"), os.environ.get("LLM_API_KEY")
    if not key: return None
    body = {"model": os.environ.get("LLM_MODEL", "gpt-4o-mini"), "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"Timeline: {json.dumps(tl)[:3000]}\nInstruction: {instr}"}]}
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", json.dumps(body).encode(),
                                 {"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    return json.loads(json.load(urllib.request.urlopen(req, timeout=60))["choices"][0]["message"]["content"])["ops"]
def _rules(instr):
    s, ops = instr.lower(), []
    if re.search(r"fast|speed up|quicker", s): ops.append({"op": "speed", "factor": 1.5})
    if re.search(r"slow|slow-mo|slower", s): ops.append({"op": "speed", "factor": 0.75})
    m = re.search(r"caption[s]?\s*[:\"']\s*(.+?)[\"']?$", instr, re.I)
    if m: ops.append({"op": "auto_captions", "text": m.group(1)})
    elif "caption" in s: ops.append({"op": "auto_captions", "text": None})
    m = re.search(r"(\d+)\s*bpm", s)
    if "beat" in s: ops.append({"op": "beat_cut", "bpm": int(m.group(1)) if m else 120})
    m = re.search(r"trim (?:to )?(\d+(?:\.\d+)?)\s*s", s)
    if m: ops.append({"op": "trim", "clip": 0, "in": 0, "out": float(m.group(1))})
    return ops
def plan(instr, tl):
    try: ops = _llm(instr, tl)
    except Exception: ops = None
    return ops if ops is not None else _rules(instr), ("llm" if ops is not None else "rules")
def apply(tl, ops, default_caption="Made with iKawn Studio"):
    tl = json.loads(json.dumps(tl))
    for o in ops:
        k = o.get("op")
        if k == "speed":
            for c in tl["clips"]: c["speed"] = round(c.get("speed", 1) * o["factor"], 3)
        elif k == "trim": tl["clips"][o.get("clip", 0)].update({"in": o.get("in", 0), "out": o["out"]})
        elif k == "caption": tl.setdefault("captions", []).append({k2: o[k2] for k2 in ("text", "start", "end")})
        elif k == "auto_captions":
            words = (o.get("text") or default_caption).split(); n = max(1, len(words) // 3 + (len(words) % 3 > 0))
            dur = total_duration(tl); seg = dur / n
            tl["captions"] = [{"text": " ".join(words[i*3:i*3+3]), "start": round(i*seg, 2), "end": round((i+1)*seg, 2)} for i in range(n)]
        elif k == "music": tl["music"] = {"src": o["src"], "volume": o.get("volume", 0.6)}
        elif k == "beat_cut":  # split each clip into beat-length segments (2 beats), keep alternate ones for punchy cuts
            beat = 60 / o.get("bpm", 120) * 2; new = []
            for c in tl["clips"]:
                a, b = c.get("in", 0), c.get("out") or c.get("dur", 5); t = a; keep = True
                while t < b - 0.05:
                    if keep: new.append({**c, "in": round(t, 3), "out": round(min(t + beat, b), 3)})
                    t += beat; keep = not keep
            tl["clips"] = new or tl["clips"]
        elif k == "reverse_order": tl["clips"].reverse()
    return tl
def total_duration(tl):
    return sum(((c.get("out") or c.get("dur", 5)) - c.get("in", 0)) / c.get("speed", 1) for c in tl["clips"])
