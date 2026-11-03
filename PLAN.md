# iKawn Studio: plan

Goal: open-source, self-hostable, bring-your-own-key AI video studio with a "vibe" (natural-language) editor and built-in upscale. Short-form 9:16 (5–60 s) first, long-form later.

## 1. Prior art reviewed (GitHub API, 1 Nov 2026)
| Repo | Stars | License | Last push | Fit |
|---|---|---|---|---|
| [OpenCut-app/OpenCut](https://github.com/OpenCut-app/OpenCut) | ~97k | **MIT** | 2026-09-24 | Best open CapCut-style timeline editor (Next.js). **Recommended editor base.** |
| [fal-ai-community/video-starter-kit](https://github.com/fal-ai-community/video-starter-kit) | ~2.4k | **MIT** | 2026-10-21 | Next.js AI-video app w/ fal models + timeline. Reuse its generation panel/model catalog ideas. Uses Remotion for preview/export → check licensing. |
| [remotion-dev/remotion](https://github.com/remotion-dev/remotion) | ~69k | **Custom (not OSI)** | 2026-10-31 | Great React render engine, but companies >3 people need a paid licence. Avoid as a hard dependency for an MIT project; optional only. |
| [motion-canvas/motion-canvas](https://github.com/motion-canvas/motion-canvas) | ~20k | MIT | 2026-07-02 | Code-driven animation; good for animated captions/titles later. |
| [ffmpegwasm/ffmpeg.wasm](https://github.com/ffmpegwasm/ffmpeg.wasm) | ~18k | MIT | 2026-09-29 | In-browser export option (fallback; server ffmpeg is faster). |
| [Lightricks/LTX-Video](https://github.com/Lightricks/LTX-Video) | ~11k | Apache-2.0 | 2026-01-05 | Self-hosted open video model, future "local GPU" provider. |
| [hpcaitech/Open-Sora](https://github.com/hpcaitech/Open-Sora) | ~30k | Apache-2.0 | 2026-04-09 | Same, heavier. |
| Runware/sdk-js | 13 | none stated | 2026-10-14 | Use raw HTTP API instead (no licence on SDK repo). |
| "Open Higgsfield" clones (e.g. Anil-matcha/Open-Higgsfield-AI) | n/a | unverified (repo moved) | n/a | Not relied on. |

## 2. Recommended stack
- **v1 scope (V, 1 Nov): talking-head reels only** (see README). Timeline/vibe/b-roll moved to roadmap.
- **Frontend (later):** fork **OpenCut** (MIT). Add three panels: *Generate* (text/image→video, camera-move presets), *Upscale*, *Vibe edit* chat. They call the engine API below.
- **Engine (this repo, built now):** Python FastAPI service `studio/`:
  - `providers/`: adapter pattern, BYOK. Runware (verified ids), fal.ai (ids configurable).
  - `timeline.py`: JSON timeline (clips, trim, speed, captions, music) → ffmpeg 9:16 MP4.
  - `vibe.py`: natural language → timeline ops. LLM via any OpenAI-compatible key (`LLM_BASE_URL`, `LLM_API_KEY`); rule-based fallback with no key.
  - Presets: camera moves/styles as prompt fragments (`presets.py`).
- **MVP UI now:** single-file dark studio page served by the engine (`web/index.html`), good enough to demo and test the API. Replaced by the OpenCut fork later.
- Docker + `.env.example`, MIT.

## 3. Verified provider ids (Runware docs, 1 Nov 2026)
- Text/image→video: `bytedance:seedance@2.0` (`taskType: videoInference`, async + `getResponse` polling). 9:16 480p = `496x864` ($0.07/s), 720p = `720x1280` ($0.16/s). Image→video: `inputs.frameImages`.
- Alt: `alibaba:wan@3.0-prime` ($0.068/s 480p), `bytedance:seedance@2.5`.
- Video upscale: `taskType: upscale`, model `bytedance:50@1`, `inputs.video` ($0.00265/s at 720p).
- fal.ai: ids not yet verified; set via env.

## 4. Roadmap
1. **MVP (done here):** engine API, Runware T2V/I2V, upscale, timeline export, vibe edit, demo UI.
2. **Editor:** OpenCut fork + panels; drag-drop timeline; waveform & beat markers.
3. **Short-form polish:** auto-captions (Whisper), beat detection (librosa/aubio) for "cut to the beat", templates, safe-area guides, multi-shot prompts.
4. **Long-form:** project scenes/storyboard, shot list → batch generation, chapters, 16:9 + 4K, proxy editing, render queue (Redis/RQ), S3 storage.
5. **Providers:** fal verified, local LTX-Video/ComfyUI, Replicate; cost meter + budgets per project.
