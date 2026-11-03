"""iKawn Studio HTTP server: web UI (/), creator API (/api/*), agent JSON API (/v1/*).
BYOK: the Runware key comes from the request (header X-Runware-Key or form field api_key) or, for
self-hosting, from RUNWARE_API_KEY. Set IKAWN_BYOK_ONLY=1 on public hosts so the server's own key is never used
and the /v1 agent API (which reads server-side files) is disabled."""
import os, uuid, urllib.request, base64
from starlette.concurrency import run_in_threadpool
from fastapi import FastAPI, UploadFile, File, Form, Header, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from providers import get_provider
from providers.runware import MODELS
import pricing, render
VERSION = "0.1.0"
MEDIA = os.environ.get("STUDIO_MEDIA", os.path.join(os.path.dirname(__file__), "..", "media")); os.makedirs(MEDIA, exist_ok=True)
WEB = os.path.join(os.path.dirname(__file__), "..", "web")
BYOK_ONLY = os.environ.get("IKAWN_BYOK_ONLY", "0") == "1"
MAX_SPEND = float(os.environ.get("IKAWN_MAX_SPEND", "0.50"))
MAX_UPLOAD = int(os.environ.get("IKAWN_MAX_UPLOAD_MB", "60")) * 1024 * 1024
app = FastAPI(title="iKawn Studio", version=VERSION); app.mount("/media", StaticFiles(directory=MEDIA), name="media")
LANGS = {"en": "English", "hi": "Hindi", "mr": "Marathi"}
DEFAULT_VOICE = "7e48c8d406b04a8089c5eb3cd057cb2e"
def save(url, ext):
    p = os.path.join(MEDIA, uuid.uuid4().hex[:10] + ext); urllib.request.urlretrieve(url, p); return p
def datauri(raw, mime): return f"data:{mime};base64," + base64.b64encode(raw).decode()
def err(code, msg, status): return JSONResponse({"error": code, "detail": msg}, status)
@app.get("/")
def index(): return FileResponse(os.path.join(WEB, "index.html"))
@app.get("/healthz")
def healthz(): return {"ok": True, "version": VERSION, "byok_only": BYOK_ONLY, "server_key": bool(os.environ.get("RUNWARE_API_KEY")) and not BYOK_ONLY,
                       "provider": os.environ.get("STUDIO_PROVIDER", "runware"), "max_spend_usd": MAX_SPEND}
@app.get("/api/models")
def models(): return {"image": {k: v[0] for k, v in MODELS.items() if v[1] == "avatar"},
                      "video": {k: v[0] for k, v in MODELS.items() if v[1] == "lipsync"}, "languages": LANGS,
                      "byok_only": BYOK_ONLY, "max_spend_usd": MAX_SPEND}
@app.post("/api/estimate")
def estimate(script: str = Form(...), model: str = Form("heygen:avatar@4")):
    if model not in MODELS: return err("bad_request", f"unknown model {model}", 400)
    return pricing.estimate(script, model)
def _cost(script, model, tier, mode, upscaling):
    e = pricing.estimate(script, model)
    if tier == "480p": return e["preview_480p"]
    return e["final"][tier]["upscale_preview" if upscaling else "regenerate"]
@app.post("/api/make")
async def make(script: str = Form(...), base: UploadFile = File(...), model: str = Form("heygen:avatar@4"),
               language: str = Form("en"), voice: str = Form(DEFAULT_VOICE),
               voice_sample: UploadFile | None = File(None), voice_id: str = Form(None),
               tier: str = Form("480p"), mode: str = Form("regenerate"), preview_remote: str = Form(None),
               max_spend: float = Form(None), api_key: str = Form(None), x_runware_key: str | None = Header(None)):
    """base = photo (image-to-talking-head) or video (video-to-video lip-sync).
    tier=480p preview; 720p/1080p final via mode=regenerate or mode=upscale (+preview_remote).
    Refused with 402 if the estimate is above max_spend (default IKAWN_MAX_SPEND)."""
    key = (x_runware_key or api_key or "").strip() or None
    if BYOK_ONLY and not key and os.environ.get("STUDIO_PROVIDER", "runware") == "runware":
        return err("missing_key", "This host is bring-your-own-key: paste your Runware API key.", 401)
    if tier not in render.TIERS: return err("bad_request", f"tier must be one of {list(render.TIERS)}", 400)
    if not script.strip(): return err("bad_request", "script is empty", 400)
    raw, ctype = await base.read(), base.content_type or ""
    if len(raw) > MAX_UPLOAD: return err("bad_request", f"upload larger than {MAX_UPLOAD // 2**20} MB", 413)
    is_video = ctype.startswith("video")
    if is_video and (model not in MODELS or MODELS[model][1] != "lipsync"): model = "pixverse:lipsync@1"
    if not is_video and (model not in MODELS or MODELS[model][1] != "avatar"): model = "heygen:avatar@4"
    upscaling = tier != "480p" and mode == "upscale" and bool(preview_remote)
    limit = MAX_SPEND if max_spend is None else max_spend
    est = _cost(script, model, tier, mode, upscaling)
    if est > limit: return err("spend_limit", f"estimate ${est:.3f} > max spend ${limit:.2f}; raise max spend to continue", 402)
    sample_raw = await voice_sample.read() if voice_sample else None
    sample_type = voice_sample.content_type if voice_sample else None
    return await run_in_threadpool(_make, script, raw, ctype, model, language, voice, sample_raw, sample_type, voice_id, tier,
                                   upscaling, preview_remote, key, est, limit)
def _make(script, raw, ctype, model, language, voice, sample_raw, sample_type, voice_id, tier, upscaling, preview_remote, key, est, limit):
    p = None
    try:
        p = get_provider(key=key)
        new_voice = None
        if upscaling: remote = p.upscale(preview_remote)
        else:
            sample = datauri(sample_raw, sample_type or "audio/mpeg") if sample_raw else None
            audio, new_voice = p.tts(script, voice_id or voice, language=language, clone_sample=None if voice_id else sample)
            if p.cost > limit: raise RuntimeError(f"spend ${p.cost:.4f} passed max spend after TTS; stopped")
            if ctype.startswith("video"): remote = p.lipsync(datauri(raw, ctype), audio, model)
            else:
                rates = MODELS[model][2]
                remote = p.avatar(datauri(raw, ctype or "image/jpeg"), audio, model, tier if tier in rates else min(rates, key=lambda k: int(k[:-1])))
        raw_path = save(remote, ".mp4"); out = raw_path.replace(".mp4", f"_{tier}_captioned.mp4")
        cap = render.export(raw_path, script, out, tier, lang=language)
        return {"url": "/media/" + os.path.basename(out), "remote": remote, "cost": round(p.cost, 4), "estimate": est,
                "seconds": render.duration(out), "voice_id": new_voice, "captions": cap, "model": model}
    except Exception as e:
        msg = str(e)
        if key: msg = msg.replace(key, "***")
        return JSONResponse({"error": "provider_error", "detail": msg[:500], "cost": round(p.cost, 4) if p else 0}, 502)

# ---------- agent-first JSON API: POST /v1/<tool> with a JSON body; GET /v1/tools for schemas ----------
import core, tools
@app.get("/v1/tools")
def v1_tools():
    if BYOK_ONLY: return err("disabled", "agent API is disabled on BYOK-only hosts; run your own copy", 403)
    return tools.schema()
@app.post("/v1/{name}")
async def v1_call(name: str, req: Request):
    if BYOK_ONLY: return err("disabled", "agent API is disabled on BYOK-only hosts; run your own copy", 403)
    if name not in tools.TOOLS: return JSONResponse({"error": "unknown_tool", "tools": list(tools.TOOLS)}, 404)
    body = await req.json() if (await req.body()) else {}
    try: return await run_in_threadpool(tools.call, name, body)
    except core.SpendLimit as e: return JSONResponse({"error": "spend_limit", "detail": str(e)}, 402)
    except (KeyError, ValueError, TypeError, FileNotFoundError) as e: return JSONResponse({"error": "bad_request", "detail": str(e)}, 400)
    except Exception as e: return JSONResponse({"error": "provider_error", "detail": str(e)[:500]}, 502)
