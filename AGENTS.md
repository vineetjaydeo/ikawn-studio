# AGENTS.md — iKawn Studio (agent-first talking-head tool)

Build persistent **avatars** (face + voice + looks) once, then make many short talking-head videos with them.
Every surface prints/returns JSON. The same 10 tools are exposed three ways (`studio/tools.py` is the source of truth):

| Surface | How |
|---|---|
| CLI | `cd studio && python cli.py <group> <cmd> ...` (exit 0 ok, 2 bad request, 3 spend limit) |
| HTTP | `uvicorn app:app --port 8931` → `GET /v1/tools`, `POST /v1/<tool>` with a JSON body (400 bad request, 402 spend limit, 502 provider) |
| MCP (stdio) | `python studio/mcp_server.py` — `{"command":"python","args":["studio/mcp_server.py"],"env":{"RUNWARE_API_KEY":"..."}}` |

Key: `RUNWARE_API_KEY` from env (export it, or `set -a; . ../.env; set +a`). Never print it. Offline test mode: `STUDIO_PROVIDER=mock` ($0, returns a sample clip). Data: `$IKAWN_HOME` (default `./data`, gitignored).

## Rules for agents
1. **Always `video_estimate` (or `dry_run: true`) first.** It is free and offline.
2. `video_create` refuses with `spend_limit` if the estimate > `max_spend` (default `$0.50`, env `IKAWN_MAX_SPEND`), and stops mid-run if actual cost passes it.
3. Default `quality: preview` (480p). Only go `hd`/`fhd` after the human approves the preview.
4. Every estimate, refusal, dry run, step and final cost is appended to `data/ledger.jsonl`. Read it with `ledger`.
5. Use only photos/videos/voice the person owns or consented to.

## Data model — `data/avatars/<id>/avatar.json`
```json
{"id":"maya","name":"Maya","languages":["en","hi","mr"],"default_look":"default",
 "voice":{"kind":"cloned|stock","voice_id":"<heygen voice id>","model":"heygen:voice@1.0","sample":"assets/voice_sample.mp3"},
 "looks":{"default":{"id":"default","photo":"assets/default_photo.jpg","video":"assets/default_video.mp4","video_seconds":12.0,"description":""}}}
```

## Tools
| Tool | Args (required in **bold**) | Cost |
|---|---|---|
| `avatar_create` | **name**, photo, video, languages[], look | free |
| `avatar_list` / `avatar_show` | — / **aid** | free |
| `look_add` | **aid**, **look**, photo, video, description | free |
| `voice_set` | **aid**, **voice_id**, model | free |
| `voice_clone` | **aid**, **sample** (audio path; first 3 min used), dry_run | $0 (HeyGen Voice Turbo Free) |
| `video_estimate` | **avatar**, script, lang, quality, look, audio, engine, tts_model | free, offline |
| `video_create` | **avatar**, script \| audio, lang, quality `preview\|hd\|fhd`, look, engine, tts_model, max_spend, dry_run, captions | see below |
| `video_agent` | **prompt**, seconds (5–300), aspect `9:16\|16:9`, avatar, look, photo, heygen_avatar, max_spend, dry_run | $0.097/s (heygen:video-agent@0) |
| `ledger` | limit | free |
| `models` | — | free |

File paths (photo, video, sample, audio) are paths on the machine running the tool.

CLI equivalents:
```bash
python cli.py avatar create "Maya" --photo me.jpg --video me_talking.mp4 --languages en,hi,mr
python cli.py avatar look add maya studio --photo me_studio.jpg
python cli.py avatar voice clone maya --sample my_voice_60s.mp3      # or: avatar voice set maya --voice-id <id>
python cli.py video estimate --avatar maya --script "..." --lang hi
python cli.py video create --avatar maya --look default --script-file s.txt --lang hi --quality preview --max-spend 0.30 [--dry-run]
python cli.py video create --avatar maya --audio marathi_take.mp3 --lang mr      # Marathi: bring your own audio
python cli.py ledger
```

## Pipeline chosen by `video_create`
1. **Voice:** your own `audio`, or TTS with the avatar's voice. Preview uses `heygen:voice@1.0-turbo-free` ($0), hd/fhd use `heygen:voice@1.0` ($0.00003/char).
2. **Picture:** look has a base video → **`pixverse:lipsync@1`** video-to-video ($0.0136/s, keeps base-video resolution). Photo only → **`heygen:avatar@4`** ($0.0385/s, any tier 360p–1080p, so hd/fhd are re-generated at the same price; no upscale needed).
   Override with `engine`: `sync:lipsync-2@1` ($0.044/s), `sync:lipsync-2-pro@1` ($0.0733/s), `prunaai:p-video@avatar`, `klingai:avatar@2.0-standard`.
3. Captions (word timings from local Whisper when installed, else proportional) + 9:16 export via ffmpeg (free). Output: `data/videos/<job>_<quality>.mp4`.

Example costs for 30 s: video lip-sync preview ≈ $0.41; photo avatar ≈ $1.16 (+≈$0.014 TTS at hd for ~450 chars).

## Languages
| | en | hi | mr |
|---|---|---|---|
| HeyGen Voice 1.0 / Turbo / Turbo Free (clone) | ✓ | ✓ | not listed |
| HeyGen Avatar IV built-in speech (`mr-IN`) | ✓ | ✓ | ✓ (stock voices only) |
| Own recorded audio (`audio`) | ✓ | ✓ | ✓ |
For Marathi in your own voice today: record the line and pass `audio`.

## ElevenLabs voices (BYOK, optional)
Set `ELEVENLABS_API_KEY` (never print it). Point an avatar at an ElevenLabs cloned voice:
`python cli.py avatar voice set maya --voice-id <eleven voice id> --model elevenlabs:eleven_multilingual_v2`
Models: `elevenlabs:eleven_multilingual_v2` (default, most stable for cloned voices), `elevenlabs:eleven_v3` (more expressive), `elevenlabs:eleven_flash_v2_5` (cheapest).
Billed in ElevenLabs credits (shown as `elevenlabs_chars` in the ledger, $0 Runware). Raw voice saved as `data/videos/<job>_voice.mp3`.
