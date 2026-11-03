import os
"""Runware adapter. All ids verified via Runware modelSearch + docs on 1 Nov 2026."""
import json, os, time, uuid, urllib.error, urllib.request
from pronounce import spoken
API = "https://api.runware.ai/v1"
# id -> (label, kind, $/s by tier). Prices from runware.ai/docs/models/<slug> (Nov 2026).
MODELS = {
 "heygen:avatar@4":                 ("HeyGen Avatar IV (photo avatar)", "avatar", {"480p": .0385, "720p": .0385, "1080p": .0385}),
 "heygen:video-agent@0":            ("HeyGen Video Agent (prompt -> full video)", "agent", {"720p": .097}),
 "prunaai:p-video@avatar":          ("P-Video Avatar (cheap, 720p+)",   "avatar", {"720p": .025, "1080p": .045}),
 "klingai:avatar@2.0-standard":     ("Kling Avatar 2.0 Std",            "avatar", {"720p": .044}),
 "sync:lipsync-2@1":                ("Sync lipsync-2 (video-to-video)",  "lipsync", {"480p": .044, "720p": .044, "1080p": .044}),
 "pixverse:lipsync@1":              ("PixVerse LipSync (cheapest v2v)",  "lipsync", {"480p": .0136, "720p": .0136, "1080p": .0136}),
 "sync:3@0":                        ("Sync sync-3 (best angles)",        "lipsync", {"480p": .133, "720p": .133, "1080p": .133}),
 "sync:lipsync-2-pro@1":            ("Sync lipsync-2-pro",               "lipsync", {"480p": .0733, "720p": .0733, "1080p": .0733}),
 "xai:grok-imagine@video-1.5-lite": ("Grok Imagine Video 1.5 Lite",     "broll",  {"480p": .02, "720p": .03, "1080p": .14}),
 "bytedance:seedance@2.0-mini":     ("Seedance 2.0 Mini",               "broll",  {"480p": .036}),
 "bytedance:seedance@2.5":          ("Seedance 2.5 (latest)",           "broll",  {"480p": .102}),
}
TTS = {"heygen:voice@1.0-turbo-free": 0.0, "heygen:voice@1.0-turbo": 0.000004, "heygen:voice@1.0": 0.00003,
       "xai:tts@0": 0.000015, "minimax:speech@2.8": 0.00006}  # $/char
UPSCALER = ("bytedance:50@1", {"720p": .0212, "1080p": .0212})  # $/s. No output-size control: our 6.6 s test went to 4K and cost $0.139 (~$0.021/s), not the $0.00265/s 720p list rate
AGENT_SIZES = {"9:16": (720, 1280), "16:9": (1280, 720)}  # only sizes heygen:video-agent@0 accepts
SIZE_916 = {"480p": (480, 854), "720p": (720, 1280), "1080p": (1080, 1920)}

def estimate(kind_model, seconds, tier):
    rates = MODELS[kind_model][2]
    return round(rates.get(tier, max(rates.values())) * seconds, 4)

class Runware:
    def __init__(self, key=None):
        self.key = key or os.environ.get("RUNWARE_API_KEY") or ""; self.cost = 0.0
        if not self.key: raise RuntimeError("missing Runware API key: set RUNWARE_API_KEY or paste your key in the UI (BYOK)")
    def _post(self, tasks):
        req = urllib.request.Request(API, json.dumps(tasks).encode(),
            {"Content-Type": "application/json", "Authorization": f"Bearer {self.key}"})
        for attempt in range(4):
            try: out = json.load(urllib.request.urlopen(req, timeout=180)); break
            except urllib.error.HTTPError as e: raise RuntimeError(e.read().decode()[:800])
            except urllib.error.URLError:  # TLS/connect failure: request never reached the API
                if attempt == 3: raise
                time.sleep(3 * (attempt + 1))
        if out.get("errors"): raise RuntimeError(out["errors"])
        return out.get("data", [])
    def _run(self, task, timeout=900):
        tid = str(uuid.uuid4()); task.update(taskUUID=tid, deliveryMethod="async", includeCost=True)
        self._post([task]); t0, delay = time.time(), 5
        while time.time() - t0 < timeout:
            time.sleep(delay); delay = min(delay * 1.4, 20)
            for d in self._post([{"taskType": "getResponse", "taskUUID": tid}]):
                if d.get("status") == "success":
                    self.cost += d.get("cost") or 0; return d
        raise TimeoutError(tid)
    def tts(self, text, voice="7e48c8d406b04a8089c5eb3cd057cb2e", model="heygen:voice@1.0-turbo-free", language="en", clone_sample=None):
        """Stock voice via `voice`, or clone from `clone_sample` (URL/data URI, first 3 min used).
        Returns (audioURL, voiceId) - reuse voiceId later to skip re-uploading the sample."""
        t = {"taskType": "audioInference", "model": model, "outputType": "URL", "outputFormat": "MP3",
             "speech": {"text": spoken(text), "language": language}}
        if clone_sample: t["inputs"] = {"audio": clone_sample}
        else: t["speech"]["voice"] = voice
        d = self._run(t); return d["audioURL"], (d.get("outputs") or {}).get("voiceId")
    # Zero-shot cloned TTS (ids/params verified on runware.ai/docs/models/*.md, 1 Nov 2026).
    CLONE_TTS = {"runware:dia2@2b": "compute-billed (~$0.006+/run)",
                 "bytedance:seed-audio@1.0": "$0.00263/s output",
                 "fishaudio:s2.1@pro": "$0.000015/byte output"}
    def clone_tts(self, text, ref_audio, model="fishaudio:s2.1@pro", ref_text=None, fmt="MP3"):
        """ref_audio: URL / UUID / data URI (Seed needs URL or UUID). Fish needs ref_text (exact transcript)."""
        t = {"taskType": "audioInference", "model": model, "outputType": "URL", "outputFormat": fmt}
        text = spoken(text)
        if model.startswith("runware:dia2"):
            t.update(speech={"text": text if text.startswith("[S1]") else "[S1] " + text}, inputs={"audios": [ref_audio]})
        elif model.startswith("bytedance:seed-audio"):
            t.update(positivePrompt=f"Speak exactly in the voice, accent and tone of @Audio1, clean close-mic, no music or effects. Dialogue: \"{text}\"",
                     inputs={"referenceAudios": [ref_audio]})
        elif model.startswith("fishaudio:"):
            t.update(speech={"text": text}, inputs={"referenceVoices": [{"audio": ref_audio, "text": ref_text}]})
        else: raise ValueError(model)
        d = self._run(t, timeout=600); return d.get("audioURL"), d.get("cost")
    def lipsync(self, base_video, audio_url, model="sync:lipsync-2@1", settings=None):
        """Video-to-video: re-sync the mouth in an existing clip of the speaker to new audio."""
        inp = {"video": base_video, "audio": audio_url} if model.startswith("sync") else {"referenceVideos": [base_video], "audio": audio_url}
        t = {"taskType": "videoInference", "model": model, "outputFormat": "MP4", "inputs": inp}
        if settings: t["settings"] = settings  # e.g. sync:3@0 {"mode": "lips", "syncMode": "cut_off"}
        return self._run(t)["videoURL"]
    @staticmethod
    def avatar_task(image, audio_url, model="heygen:avatar@4", tier="480p"):
        """Pure: build the videoInference task for photo + audio -> talking head (no network)."""
        w, h = SIZE_916[tier]
        if os.environ.get("IKAWN_ASPECT") == "16:9": w, h = h, w  # landscape source photos
        # default 9:16; with only `resolution` HeyGen returned 16:9 with white side bars
        t = {"taskType": "videoInference", "model": model, "outputFormat": "MP4", "inputs": {"audio": audio_url}}
        if model.startswith("heygen"): t.update(width=w, height=h)
        else: t["resolution"] = tier
        if model.startswith("heygen"): t["inputs"]["image"] = image
        else: t["inputs"]["frameImages"] = [{"image": image, "frame": "first"}]
        return t
    def avatar(self, image, audio_url, model="heygen:avatar@4", tier="480p"):
        return self._run(self.avatar_task(image, audio_url, model, tier))["videoURL"]
    @staticmethod
    def video_agent_task(prompt, seconds=15, aspect="9:16", image=None, heygen_avatar=None, model="heygen:video-agent@0"):
        """Pure: HeyGen Video Agent task (runware.ai/docs/models/heygen-video-agent). Prompt -> scripted, edited,
        captioned multi-scene video. Optional inputs.image (photo to animate as presenter) or inputs.avatar (HeyGen stock id).
        duration 5-300 s; only 720x1280 / 1280x720."""
        if not prompt or len(prompt) > 10000: raise ValueError("prompt must be 1-10000 chars")
        seconds = int(round(seconds))
        if not 5 <= seconds <= 300: raise ValueError("video agent duration must be 5-300 s")
        if aspect not in AGENT_SIZES: raise ValueError(f"aspect must be one of {list(AGENT_SIZES)}")
        if image and heygen_avatar: raise ValueError("pass either a photo or a HeyGen avatar id, not both")
        w, h = AGENT_SIZES[aspect]
        t = {"taskType": "videoInference", "model": model, "positivePrompt": prompt, "width": w, "height": h,
             "duration": seconds, "outputType": "URL", "outputFormat": "MP4"}
        if image: t["inputs"] = {"image": image}
        elif heygen_avatar: t["inputs"] = {"avatar": heygen_avatar}
        return t
    def video_agent(self, prompt, seconds=15, aspect="9:16", image=None, heygen_avatar=None, timeout=1800):
        # docs: ~8 min per request end to end, so poll longer than the default 900 s
        return self._run(self.video_agent_task(prompt, seconds, aspect, image, heygen_avatar), timeout=timeout)["videoURL"]
    def broll(self, prompt, model="xai:grok-imagine@video-1.5-lite", seconds=5, tier="480p"):
        w, h = SIZE_916[tier]
        return self._run({"taskType": "videoInference", "model": model, "positivePrompt": prompt + ", vertical 9:16",
                          "duration": seconds, "width": w, "height": h, "outputFormat": "MP4"})["videoURL"]
    def image(self, prompt):
        r = self._post([{"taskType": "imageInference", "taskUUID": str(uuid.uuid4()), "model": "runware:100@1", "positivePrompt": prompt,
                         "width": 576, "height": 1024, "steps": 4, "outputType": "URL", "includeCost": True}])[0]
        self.cost += r.get("cost") or 0; return r["imageURL"]
    def upscale(self, video_url):
        return self._run({"taskType": "upscale", "model": UPSCALER[0], "inputs": {"video": video_url}, "outputFormat": "MP4"})["videoURL"]
