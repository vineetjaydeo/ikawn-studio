# iKawn Studio

Open-source, self-hostable, **bring-your-own-key** studio for **talking-head reels** (9:16).
Photo or your own video + script → voice (stock or your clone) → lip-synced talking head → word-timed burned-in captions → MP4.
Cheap 480p previews; pay for HD/FHD only on the take you approve. You see the cost **before** (estimate) and **after** (actual) every video, and a max-spend cap refuses anything above your limit.

![demo](samples/demo.gif)

*Demo: 4 s, 480p, made in the web UI from the fictional sample face in `samples/`. Real cost: $0.1571.*

## Quick start (5 minutes)
You need a [Runware](https://runware.ai) API key (pay-as-you-go; you pay Runware directly, iKawn Studio never sees your money).

**Docker**
```bash
cp .env.example .env            # paste RUNWARE_API_KEY=...
docker build -t ikawn-studio .
docker run --env-file .env -p 8000:8000 ikawn-studio
```
**Python 3.11+ with ffmpeg installed**
```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export RUNWARE_API_KEY=...       # or paste the key in the web page instead
cd studio && uvicorn app:app --port 8000
```
Open http://localhost:8000 → add a photo (or a video of you) → write the script → **Generate 480p preview** → if you like it, **Final HD 720p / FHD 1080p**.

No key yet? `STUDIO_PROVIDER=mock uvicorn app:app` runs the whole pipeline offline for $0 and returns a sample clip.

## Bring your own key (BYOK)
- Paste your key in the page: it is kept in your browser (localStorage) and sent only as the `X-Runware-Key` header on your own requests. The server never stores it.
- Or set `RUNWARE_API_KEY` on your own machine/server.
- Public hosts: set `IKAWN_BYOK_ONLY=1` so the server's key is never used and the file-based agent API is turned off. The host pays nothing for generation.

## What it costs
Runware list prices, checked 1 Nov 2026; the real 4 s demo above billed $0.1571, matching the $0.0385/s rate.

| 30 s talking head | Cost |
|---|---|
| Photo → talking head (`heygen:avatar@4`, free stock/clone TTS) | **≈ $1.16** at 480p, 720p or 1080p |
| Your own video → lip-sync (`pixverse:lipsync@1`) | ≈ $0.41 |
| Your own video → lip-sync, higher quality (`sync:lipsync-2@1`) | ≈ $1.32 |
| Captions, 9:16 export, Whisper | $0 (runs locally) |

For comparison, Higgsfield Speak 2.0 is listed at about 14 credits per 5 s at 720p ([Higgsfield's pricing explainer](https://higgsfield.ai/blog/higgsfield-pricing-explained), Oct 2026). On the Plus plan ($49 for 1,000 credits) a 30 s clip is about 84 credits, roughly $4, and needs a monthly subscription. Prices change; check before you compare.

## Models
| Step | Model id | Runware list price |
|---|---|---|
| Photo → talking head (default) | `heygen:avatar@4` | $0.0385/s, any resolution |
| Photo → talking head (alt) | `prunaai:p-video@avatar` (720p+) · `klingai:avatar@2.0-standard` | $0.025 · $0.044 per s |
| Video → video lip-sync | `pixverse:lipsync@1` (cheapest) · `sync:lipsync-2@1` · `sync:lipsync-2-pro@1` · `sync:3@0` | $0.0136 · $0.044 · $0.0733 · $0.133 per s |
| TTS + voice cloning | `heygen:voice@1.0-turbo-free` · `heygen:voice@1.0` | free · $0.00003/char |
| Optional: your ElevenLabs voices | `elevenlabs:eleven_multilingual_v2` etc. (`ELEVENLABS_API_KEY`) | your ElevenLabs credits |
| Prompt → full edited video (agent API) | `heygen:video-agent@0` | $0.097/s, 720p |
| Upscale | `bytedance:50@1` | ≈ $0.021/s (outputs 4K) |

## What to record
**Photo (talking head from a still)**
- Front-facing, shoulders up, sharp, at least 1080 px tall.
- Neutral expression, mouth closed, even soft light, plain background (it is kept as-is).

**Base video (lip-sync onto your own footage)**
- 10–30 s, vertical 9:16, 1080×1920 (720p minimum), 25–30 fps.
- Face front-on, filling about 40% of the frame; mouth never covered; few head turns.
- Even front light, static background, include a few closed-mouth pauses, no other faces.
- Output keeps the base video's resolution, so record at 1080p if you want FHD.

**Voice sample (clone your voice)**
- 60–180 s (first 3 min used), one speaker, quiet room, no music, natural pace, WAV or high-bitrate MP3.
- Record in the language you will script in.

Only use faces and voices you own or have permission to use.

## Captions
Word timings come from local [faster-whisper](https://github.com/SYSTRAN/faster-whisper) on CPU (free), with spelling taken from your script so brand names stay right. Without it (or with `IKAWN_CAPTIONS=proportional`) captions are timed proportionally from the script.

## Pronunciation
iKawn is pronounced "eye-kon". The voice step respells words before text-to-speech, while captions keep your script's spelling.
Default map: `iKawn → Eye-kon`. Add your own (whole word, case-insensitive):
```bash
IKAWN_PRONOUNCE="Runware=Run-ware;Nikhil=Nick-hill"     # or IKAWN_PRONOUNCE_FILE=pronounce.json  {"Word": "respelling"}
```

## API
`GET /healthz` · `GET /api/models` · `POST /api/estimate` (form: `script`, `model`) · `POST /api/make` (multipart: `script`, `base` photo/video, `model`, `language` en/hi/mr, `voice` | `voice_sample` | `voice_id`, `tier` 480p/720p/1080p, `mode` regenerate/upscale, `preview_remote`, `max_spend`; header `X-Runware-Key`).
Errors: 400 bad request, 401 missing key (BYOK-only host), 402 over max spend, 502 provider error.

## For agents
CLI, JSON HTTP API (`/v1/<tool>`) and an MCP server with persistent avatars, max-spend guard and a cost ledger: see [AGENTS.md](AGENTS.md).

## Hosting for free
- **Hugging Face Spaces (Docker, free CPU):** see `deploy/huggingface/` (Space README header + Dockerfile on port 7860, BYOK-only).
- **Render (free web service):** `render.yaml` (sleeps when idle, 512 MB RAM, so Whisper is off there).

## Configuration
All settings are in [.env.example](.env.example).

## Roadmap
- Timeline editor and plain-language editing ("make it faster, add captions").
- B-roll, caption styles, long-form 16:9, batch jobs.
- More providers (fal.ai) and local open lip-sync models for zero cost on your own GPU.

## License
MIT © 2026 iKawn Inc.
