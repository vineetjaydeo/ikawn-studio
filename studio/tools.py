"""Single tool registry -> CLI, HTTP (POST /v1/<tool>) and MCP all expose the same surface."""
import core, providers.runware as rw
def _models(): return {"engines": {k: {"label": v[0], "kind": v[1], "usd_per_s": v[2]} for k, v in rw.MODELS.items() if v[1] in ("avatar", "lipsync", "agent")},
                       "tts_usd_per_char": rw.TTS, "tts_langs": {k: sorted(v) for k, v in core.TTS_LANGS.items()}, "quality": core.QUALITY}
S, N, B = {"type": "string"}, {"type": "number"}, {"type": "boolean"}
TOOLS = {
 "avatar_create": (core.avatar_create, "Create a persistent avatar from a local photo and/or base video (paths on the server).",
    {"name": S, "photo": S, "video": S, "languages": {"type": "array", "items": S}, "look": S}, ["name"]),
 "avatar_list": (core.avatar_list, "List avatars.", {}, []),
 "avatar_show": (core.avatar_get, "Show one avatar profile.", {"aid": S}, ["aid"]),
 "look_add": (core.look_add, "Add a look (outfit/setting) = photo and/or base video.", {"aid": S, "look": S, "photo": S, "video": S, "description": S}, ["aid", "look"]),
 "voice_set": (core.voice_set, "Attach a stock or existing HeyGen voice_id to the avatar.", {"aid": S, "voice_id": S, "model": S}, ["aid", "voice_id"]),
 "voice_clone": (core.voice_clone, "Clone voice from an audio sample (HeyGen Voice Turbo Free, $0); saves voice_id.", {"aid": S, "sample": S, "dry_run": B}, ["aid", "sample"]),
 "video_estimate": (core.plan, "Cost + pipeline plan, no network, no spend.",
    {"avatar": S, "script": S, "lang": S, "quality": {"enum": ["preview", "hd", "fhd"]}, "look": S, "audio": S, "engine": S, "tts_model": S}, ["avatar"]),
 "video_create": (core.video_create, "Render a talking-head video. Refuses if estimate > max_spend; logs actual cost to ledger.",
    {"avatar": S, "script": S, "lang": S, "quality": {"enum": ["preview", "hd", "fhd"]}, "look": S, "audio": S, "engine": S,
     "tts_model": S, "max_spend": N, "dry_run": B, "captions": B}, ["avatar"]),
 "video_agent": (core.agent_create, "HeyGen Video Agent (heygen:video-agent@0, $0.097/s, 720p, 5-300 s): prompt -> full edited video. Optional presenter: avatar(+look) photo, photo path/URL, or heygen_avatar stock id. Use dry_run first.",
    {"prompt": S, "seconds": {"type": "integer"}, "aspect": {"enum": ["9:16", "16:9"]}, "avatar": S, "look": S, "photo": S, "heygen_avatar": S,
     "max_spend": N, "dry_run": B}, ["prompt"]),
 "ledger": (core.ledger_read, "Audit ledger rows + total actual spend.", {"limit": {"type": "integer"}}, []),
 "models": (_models, "Engines, prices, language support.", {}, []),
}
def call(name, args):
    fn = TOOLS[name][0]; args = dict(args or {})
    if "languages" in args and isinstance(args["languages"], str): args["languages"] = args["languages"].split(",")
    return fn(**args)
def schema():
    return [{"name": k, "description": v[1], "inputSchema": {"type": "object", "properties": v[2], "required": v[3]}} for k, v in TOOLS.items()]
