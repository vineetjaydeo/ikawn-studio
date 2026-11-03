#!/usr/bin/env python3
"""ikawn CLI - every command prints JSON. Run from studio/: python cli.py <cmd> ..."""
import argparse, json, sys
import core, tools
def main(argv=None):
    p = argparse.ArgumentParser(prog="ikawn"); sp = p.add_subparsers(dest="g", required=True)
    av = sp.add_parser("avatar").add_subparsers(dest="c", required=True)
    c = av.add_parser("create"); c.add_argument("name"); c.add_argument("--photo"); c.add_argument("--video"); c.add_argument("--languages", default="en"); c.add_argument("--look", default="default")
    av.add_parser("list"); s = av.add_parser("show"); s.add_argument("aid")
    lk = av.add_parser("look"); lk.add_argument("op", choices=["add"]); lk.add_argument("aid"); lk.add_argument("look"); lk.add_argument("--photo"); lk.add_argument("--video"); lk.add_argument("--description", default="")
    vo = av.add_parser("voice"); vo.add_argument("op", choices=["clone", "set"]); vo.add_argument("aid"); vo.add_argument("--sample"); vo.add_argument("--voice-id"); vo.add_argument("--model", default="heygen:voice@1.0"); vo.add_argument("--dry-run", action="store_true")
    vd = sp.add_parser("video").add_subparsers(dest="c", required=True)
    for n in ("estimate", "create"):
        x = vd.add_parser(n); x.add_argument("--avatar", required=True); x.add_argument("--look"); x.add_argument("--script"); x.add_argument("--script-file")
        x.add_argument("--lang", default="en"); x.add_argument("--quality", default="preview", choices=list(core.QUALITY)); x.add_argument("--audio"); x.add_argument("--engine"); x.add_argument("--tts-model")
        if n == "create": x.add_argument("--max-spend", type=float, default=core.DEFAULT_MAX_SPEND); x.add_argument("--dry-run", action="store_true"); x.add_argument("--no-captions", action="store_true")
    ag = vd.add_parser("agent", help="HeyGen Video Agent via Runware: prompt -> full video ($0.097/s, 720p)")
    ag.add_argument("--prompt"); ag.add_argument("--prompt-file"); ag.add_argument("--seconds", type=int, default=15)
    ag.add_argument("--aspect", default="9:16", choices=["9:16", "16:9"]); ag.add_argument("--avatar", help="local avatar id: use its look photo as presenter")
    ag.add_argument("--look"); ag.add_argument("--photo", help="photo path/URL to animate as presenter"); ag.add_argument("--heygen-avatar", help="HeyGen stock avatar id")
    ag.add_argument("--max-spend", type=float, default=core.DEFAULT_MAX_SPEND); ag.add_argument("--dry-run", action="store_true")
    lg = sp.add_parser("ledger"); lg.add_argument("--limit", type=int, default=50); sp.add_parser("models"); sp.add_parser("schema")
    a = p.parse_args(argv)
    try:
        if a.g == "avatar":
            if a.c == "create": r = tools.call("avatar_create", dict(name=a.name, photo=a.photo, video=a.video, languages=a.languages, look=a.look))
            elif a.c == "list": r = core.avatar_list()
            elif a.c == "show": r = core.avatar_get(a.aid)
            elif a.c == "look": r = core.look_add(a.aid, a.look, a.photo, a.video, a.description)
            elif a.op == "clone": r = core.voice_clone(a.aid, a.sample, dry_run=a.dry_run)
            else: r = core.voice_set(a.aid, a.voice_id, a.model)
        elif a.g == "video" and a.c == "agent":
            prompt = open(a.prompt_file).read().strip() if a.prompt_file else a.prompt
            r = core.agent_create(prompt, a.seconds, a.aspect, a.avatar, a.look, a.photo, a.heygen_avatar, max_spend=a.max_spend, dry_run=a.dry_run)
        elif a.g == "video":
            script = open(a.script_file).read().strip() if a.script_file else a.script
            kw = dict(avatar=a.avatar, script=script, lang=a.lang, quality=a.quality, look=a.look, audio=a.audio, engine=a.engine, tts_model=a.tts_model)
            r = core.plan(**kw) if a.c == "estimate" else core.video_create(**kw, max_spend=a.max_spend, dry_run=a.dry_run, captions=not a.no_captions)
        elif a.g == "ledger": r = core.ledger_read(a.limit)
        elif a.g == "models": r = tools.call("models", {})
        else: r = tools.schema()
        print(json.dumps(r, indent=2)); return 0
    except core.SpendLimit as e: print(json.dumps({"error": "spend_limit", "detail": str(e)})); return 3
    except (KeyError, ValueError, FileNotFoundError) as e: print(json.dumps({"error": "bad_request", "detail": str(e)})); return 2
if __name__ == "__main__": sys.exit(main())
