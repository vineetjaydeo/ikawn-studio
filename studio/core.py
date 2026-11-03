"""iKawn Studio core: avatar profiles, cost planning, max-spend guard, audit ledger.
Shared by the CLI (cli.py), the JSON HTTP API (app.py) and the MCP server (mcp_server.py)."""
import base64, datetime, json, mimetypes, os, re, shutil, uuid, urllib.request
from providers.runware import MODELS, TTS
import render

HOME = os.path.abspath(os.environ.get("IKAWN_HOME", os.path.join(os.path.dirname(__file__), "..", "data")))
AVATARS, OUT, LEDGER = os.path.join(HOME, "avatars"), os.path.join(HOME, "videos"), os.path.join(HOME, "ledger.jsonl")
QUALITY = {"preview": "480p", "hd": "720p", "fhd": "1080p"}
LANGS = {"en": "en-US", "hi": "hi-IN", "mr": "mr-IN"}
# TTS language support per Runware docs (Nov 2026). Marathi: no Runware TTS lists it -> supply recorded audio.
TTS_LANGS = {"heygen:voice@1.0": {"en", "hi"}, "heygen:voice@1.0-turbo": {"en", "hi"}, "heygen:voice@1.0-turbo-free": {"en", "hi"},
             "xai:tts@0": {"en", "hi"}, "minimax:speech@2.8": {"en", "hi"},
             **{m: {"en", "hi"} for m in ("elevenlabs:eleven_multilingual_v2", "elevenlabs:eleven_v3", "elevenlabs:eleven_flash_v2_5")}}
DEFAULT_TTS = {"preview": "heygen:voice@1.0-turbo-free", "hd": "heygen:voice@1.0", "fhd": "heygen:voice@1.0"}
DEFAULT_LIPSYNC, DEFAULT_PHOTO = "pixverse:lipsync@1", "heygen:avatar@4"
DEFAULT_MAX_SPEND = float(os.environ.get("IKAWN_MAX_SPEND", "0.50"))
WPS = 2.6

class SpendLimit(Exception): pass
def _now(): return datetime.datetime.now().astimezone().isoformat(timespec="seconds")
def _slug(s): return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:32] or uuid.uuid4().hex[:8]
def _apath(aid): return os.path.join(AVATARS, aid, "avatar.json")

def ledger(event, **kw):
    os.makedirs(HOME, exist_ok=True); row = {"ts": _now(), "event": event, **kw}
    with open(LEDGER, "a") as f: f.write(json.dumps(row) + "\n")
    return row
def ledger_read(limit=50):
    if not os.path.exists(LEDGER): return {"rows": [], "total_actual_usd": 0}
    rows = [json.loads(l) for l in open(LEDGER) if l.strip()]
    return {"rows": rows[-limit:], "total_actual_usd": round(sum(r.get("actual_usd") or 0 for r in rows), 4)}

# ---------- avatars ----------
def avatar_get(aid):
    if not os.path.exists(_apath(aid)): raise KeyError(f"no avatar '{aid}'")
    return json.load(open(_apath(aid)))
def _save(a): a["updated"] = _now(); json.dump(a, open(_apath(a["id"]), "w"), indent=2); return a
def avatar_list(): return [avatar_get(d) for d in sorted(os.listdir(AVATARS))] if os.path.isdir(AVATARS) else []
def _copy_asset(aid, src, name):
    ext = os.path.splitext(src)[1].lower() or ".bin"; dst = os.path.join(AVATARS, aid, "assets", name + ext)
    os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copyfile(src, dst); return os.path.relpath(dst, os.path.join(AVATARS, aid))

def avatar_create(name, photo=None, video=None, languages=("en",), look="default"):
    if not (photo or video): raise ValueError("need --photo and/or --video")
    aid = _slug(name)
    if os.path.exists(_apath(aid)): raise ValueError(f"avatar '{aid}' exists")
    os.makedirs(os.path.join(AVATARS, aid), exist_ok=True)
    a = {"id": aid, "name": name, "created": _now(), "languages": list(languages), "default_look": look,
         "voice": None, "looks": {}}
    _save(a); look_add(aid, look, photo, video); return avatar_get(aid)

def look_add(aid, look, photo=None, video=None, description=""):
    a = avatar_get(aid)
    if not (photo or video): raise ValueError("look needs a photo and/or base video")
    l = {"id": _slug(look), "description": description}
    if photo: l["photo"] = _copy_asset(aid, photo, f"{_slug(look)}_photo")
    if video: l["video"] = _copy_asset(aid, video, f"{_slug(look)}_video"); l["video_seconds"] = render.duration(os.path.join(AVATARS, aid, l["video"]))
    a["looks"][l["id"]] = l; a.setdefault("default_look", l["id"]); return _save(a)

def voice_set(aid, voice_id, model="heygen:voice@1.0", kind="stock"):
    a = avatar_get(aid); a["voice"] = {"kind": kind, "voice_id": voice_id, "model": model, "set": _now()}; return _save(a)

def voice_clone(aid, sample, dry_run=False, max_spend=DEFAULT_MAX_SPEND):
    """Clone with HeyGen Voice Turbo Free ($0, inputs.audio, first 3 min used). Saves outputs.voiceId to the avatar."""
    a = avatar_get(aid); a_rel = _copy_asset(aid, sample, "voice_sample"); model = "heygen:voice@1.0-turbo-free"
    est = {"steps": [{"op": "voice_clone", "model": model, "usd": 0.0}], "total_usd": 0.0}
    if dry_run: return {"dry_run": True, "estimate": est, "sample": a_rel}
    from providers import get_provider
    p = get_provider()
    _, vid = p.tts("Hello, this is my voice.", model=model, clone_sample=_datauri(os.path.join(AVATARS, aid, a_rel)))
    ledger("voice_clone", avatar=aid, model=model, estimate_usd=0.0, actual_usd=round(p.cost, 6))
    if not vid: raise RuntimeError("no voiceId returned")
    a = voice_set(aid, vid, "heygen:voice@1.0", "cloned"); a["voice"]["sample"] = a_rel; return _save(a)

# ---------- planning ----------
def _datauri(path):
    return f"data:{mimetypes.guess_type(path)[0] or 'application/octet-stream'};base64," + base64.b64encode(open(path, "rb").read()).decode()

def plan(avatar, script=None, lang="en", quality="preview", look=None, audio=None, engine=None, tts_model=None, seconds=None):
    """Pure function: decide pipeline + cost. No network."""
    a = avatar_get(avatar); look = look or a["default_look"]; l = a["looks"].get(look)
    if not l: raise KeyError(f"no look '{look}' on {avatar}; have {list(a['looks'])}")
    if quality not in QUALITY: raise ValueError(f"quality must be one of {list(QUALITY)}")
    if not (script or audio): raise ValueError("need script or audio")
    tier, warnings, steps = QUALITY[quality], [], []
    secs = seconds or (render.duration(audio) if audio else max(2.0, len(script.split()) / WPS))
    if not audio:
        v = a.get("voice") or {"voice_id": "7e48c8d406b04a8089c5eb3cd057cb2e", "model": "heygen:voice@1.0", "kind": "stock-default"}
        tm = tts_model or (v["model"] if (quality != "preview" or v["model"].startswith("elevenlabs:")) else DEFAULT_TTS["preview"])
        if lang not in TTS_LANGS.get(tm, set()):
            warnings.append(f"{tm} does not list '{lang}' in Runware docs; output may be wrong. For Marathi, pass --audio with a recording.")
        if v["kind"] == "stock-default": warnings.append("avatar has no voice; using stock HeyGen voice Jonah. Run `avatar voice clone`.")
        steps.append({"op": "tts", "model": tm, "voice_id": v["voice_id"], "chars": len(script), "usd": round(TTS.get(tm, 0.0) * len(script), 5)})
    eng = engine or (DEFAULT_LIPSYNC if l.get("video") else DEFAULT_PHOTO)
    kind = MODELS[eng][1]
    if kind == "lipsync" and not l.get("video"): raise ValueError(f"{eng} needs a look with a base video")
    if kind == "avatar" and not l.get("photo"): raise ValueError(f"{eng} needs a look with a photo")
    rates = MODELS[eng][2]; rt = tier if tier in rates else min(rates, key=lambda k: int(k[:-1]))
    if rt != tier: warnings.append(f"{eng} has no {tier}; using {rt}")
    steps.append({"op": kind, "model": eng, "seconds": round(secs, 1), "tier": rt, "usd_per_s": rates[rt], "usd": round(rates[rt] * secs, 4)})
    if kind == "lipsync" and l.get("video_seconds") and secs > l["video_seconds"]:
        warnings.append(f"script ~{secs:.0f}s is longer than base video {l['video_seconds']:.0f}s; lip-sync model will loop/bounce it")
    if kind == "lipsync" and quality != "preview":
        warnings.append("lip-sync output keeps the base video's resolution; record the base video at 1080p for hd/fhd")
    steps.append({"op": "captions+export", "tier": tier, "usd": 0.0})
    return {"avatar": avatar, "look": look, "lang": lang, "quality": quality, "tier": tier, "seconds": round(secs, 1),
            "steps": steps, "total_usd": round(sum(s["usd"] for s in steps), 4), "warnings": warnings}

def video_create(avatar, script=None, lang="en", quality="preview", look=None, audio=None, engine=None,
                 tts_model=None, max_spend=DEFAULT_MAX_SPEND, dry_run=False, captions=True):
    pl = plan(avatar, script, lang, quality, look, audio, engine, tts_model)
    job = uuid.uuid4().hex[:10]; pl["job"], pl["max_spend_usd"] = job, max_spend
    if pl["total_usd"] > max_spend:
        ledger("refused", job=job, avatar=avatar, estimate_usd=pl["total_usd"], max_spend_usd=max_spend, actual_usd=0)
        raise SpendLimit(f"estimate ${pl['total_usd']} > max_spend ${max_spend}")
    if dry_run:
        ledger("dry_run", job=job, avatar=avatar, estimate_usd=pl["total_usd"], actual_usd=0, plan=pl["steps"])
        m = [x for x in pl["steps"] if x["op"] in ("avatar", "lipsync")][0]
        if m["op"] == "avatar": pl["request"] = avatar_request(avatar, pl["look"], quality, m["model"])
        return {"dry_run": True, **pl}
    from providers import get_provider
    a = avatar_get(avatar); l = a["looks"][pl["look"]]; root = os.path.join(AVATARS, avatar); p = get_provider(); spent = []
    def step(name, fn):
        before = p.cost
        try: r = fn()
        finally:
            spent.append({"op": name, "actual_usd": round(p.cost - before, 6)})
            ledger("step", job=job, avatar=avatar, op=name, actual_usd=round(p.cost - before, 6))
        if p.cost > max_spend: raise SpendLimit(f"actual ${p.cost:.4f} passed max_spend ${max_spend} after {name}; stopping")
        return r
    try:
        s = {x["op"]: x for x in pl["steps"]}
        if audio: audio_url = _datauri(audio)
        else:
            t = s["tts"]
            if t["model"].startswith("elevenlabs:"):
                from providers.elevenlabs import ElevenLabs; el = ElevenLabs(); os.makedirs(OUT, exist_ok=True)
                audio_url, _ = el.tts(script, t["voice_id"], t["model"], lang, out_path=os.path.join(OUT, f"{job}_voice.mp3"))
                ledger("step", job=job, avatar=avatar, op="tts", model=t["model"], elevenlabs_chars=el.chars, actual_usd=0)
            else: audio_url, _ = step("tts", lambda: p.tts(script, t["voice_id"], t["model"], lang))
        m = [x for x in pl["steps"] if x["op"] in ("avatar", "lipsync")][0]
        if m["op"] == "lipsync": remote = step("lipsync", lambda: p.lipsync(_datauri(os.path.join(root, l["video"])), audio_url, m["model"]))
        else: remote = step("avatar", lambda: p.avatar(_datauri(os.path.join(root, l["photo"])), audio_url, m["model"], m["tier"]))
        os.makedirs(OUT, exist_ok=True); raw = os.path.join(OUT, f"{job}_raw.mp4"); urllib.request.urlretrieve(remote, raw)
        final = os.path.join(OUT, f"{job}_{quality}.mp4")
        cap = render.export(raw, script or "", final, pl["tier"], lang=lang, captions=captions)
        res = {"job": job, "file": final, "remote": remote, "estimate_usd": pl["total_usd"], "actual_usd": round(p.cost, 6),
               "seconds": render.duration(final), "captions": cap, "steps": spent, "warnings": pl["warnings"]}
        ledger("video_done", job=job, avatar=avatar, estimate_usd=pl["total_usd"], actual_usd=round(p.cost, 6), file=final)
        return res
    except Exception as e:
        ledger("video_failed", job=job, avatar=avatar, estimate_usd=pl["total_usd"], actual_usd=round(p.cost, 6), error=str(e)[:300]); raise

# ---------- HeyGen Video Agent (prompt -> full video) ----------
AGENT_MODEL = "heygen:video-agent@0"
def _redact(t):
    """Copy of a task with data URIs shortened, for dry-run display."""
    def r(v):
        if isinstance(v, dict): return {k: r(x) for k, x in v.items()}
        if isinstance(v, list): return [r(x) for x in v]
        if isinstance(v, str) and v.startswith("data:"): return v[:40] + f"...<{len(v)} chars>"
        return v
    return r(t)

def agent_plan(prompt, seconds=15, aspect="9:16", avatar=None, look=None, photo=None, heygen_avatar=None):
    """Pure: cost + exact Runware request for heygen:video-agent@0. No network."""
    from providers.runware import Runware
    image, src = None, None
    if avatar:
        a = avatar_get(avatar); lk = a["looks"].get(look or a["default_look"])
        if not lk or not lk.get("photo"): raise ValueError(f"avatar {avatar} look needs a photo for the video agent")
        photo = os.path.join(AVATARS, avatar, lk["photo"])
    if photo:
        if not os.path.exists(photo): raise FileNotFoundError(photo)
        image, src = (photo if photo.startswith("http") else _datauri(photo)), photo
    task = Runware.video_agent_task(prompt, seconds, aspect, image, heygen_avatar)
    rate = MODELS[AGENT_MODEL][2]["720p"]; secs = task["duration"]
    return {"engine": AGENT_MODEL, "seconds": secs, "aspect": aspect, "tier": "720p", "usd_per_s": rate,
            "total_usd": round(rate * secs, 4), "presenter": src or heygen_avatar or "agent-chosen",
            "request": _redact(task), "_task": task,
            "warnings": ["Video Agent writes its own script/voice unless you put the exact words in the prompt (\"speaking exactly: ...\").",
                         "~8 min per request; output is 720p only."]}

def agent_create(prompt, seconds=15, aspect="9:16", avatar=None, look=None, photo=None, heygen_avatar=None,
                 max_spend=DEFAULT_MAX_SPEND, dry_run=False):
    pl = agent_plan(prompt, seconds, aspect, avatar, look, photo, heygen_avatar); task = pl.pop("_task")
    job = uuid.uuid4().hex[:10]; pl["job"], pl["max_spend_usd"] = job, max_spend
    if pl["total_usd"] > max_spend:
        ledger("refused", job=job, engine=AGENT_MODEL, estimate_usd=pl["total_usd"], max_spend_usd=max_spend, actual_usd=0)
        raise SpendLimit(f"estimate ${pl['total_usd']} > max_spend ${max_spend}")
    if dry_run:
        ledger("dry_run", job=job, engine=AGENT_MODEL, estimate_usd=pl["total_usd"], actual_usd=0)
        return {"dry_run": True, **pl}
    from providers import get_provider
    p = get_provider()
    try:
        remote = p._run(task, timeout=1800)["videoURL"]
        os.makedirs(OUT, exist_ok=True); final = os.path.join(OUT, f"{job}_agent.mp4"); urllib.request.urlretrieve(remote, final)
        ledger("video_done", job=job, engine=AGENT_MODEL, estimate_usd=pl["total_usd"], actual_usd=round(p.cost, 6), file=final)
        return {"job": job, "file": final, "remote": remote, "estimate_usd": pl["total_usd"], "actual_usd": round(p.cost, 6)}
    except Exception as e:
        ledger("video_failed", job=job, engine=AGENT_MODEL, estimate_usd=pl["total_usd"], actual_usd=round(p.cost, 6), error=str(e)[:300]); raise

def avatar_request(avatar, look=None, quality="preview", engine=DEFAULT_PHOTO, audio_url="<tts audioURL>"):
    """Pure: the exact Runware task heygen:avatar@4 (or another photo engine) would receive. No network."""
    from providers.runware import Runware
    a = avatar_get(avatar); lk = a["looks"].get(look or a["default_look"])
    if not lk or not lk.get("photo"): raise ValueError("look needs a photo")
    return _redact(Runware.avatar_task(_datauri(os.path.join(AVATARS, avatar, lk["photo"])), audio_url, engine, QUALITY[quality]))
