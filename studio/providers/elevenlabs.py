"""ElevenLabs TTS (BYOK: ELEVENLABS_API_KEY). Uses the account's own cloned voices.
Billed in the user's ElevenLabs credits (1 credit/char on multilingual_v2/v3), not USD via Runware."""
import base64, json, os, urllib.request, urllib.error
from pronounce import spoken
API = "https://api.elevenlabs.io/v1"
MODELS = {"elevenlabs:eleven_multilingual_v2": "eleven_multilingual_v2",  # most stable for cloned voices, en/hi
          "elevenlabs:eleven_v3": "eleven_v3",                              # most expressive, less stable on short IVC clones
          "elevenlabs:eleven_flash_v2_5": "eleven_flash_v2_5"}             # cheapest/fastest (0.5 credit/char)
DEFAULT = "elevenlabs:eleven_multilingual_v2"

class ElevenLabs:
    def __init__(self): self.key = os.environ["ELEVENLABS_API_KEY"]; self.chars = 0
    def _req(self, path, body=None):
        r = urllib.request.Request(API + path, json.dumps(body).encode() if body else None,
                                   {"xi-api-key": self.key, "Content-Type": "application/json"})
        try: return urllib.request.urlopen(r, timeout=180)
        except urllib.error.HTTPError as e: raise RuntimeError(f"elevenlabs {e.code}: {e.read().decode()[:500]}")
    def voices(self):
        return [{"name": v["name"], "voice_id": v["voice_id"], "category": v["category"]}
                for v in json.load(self._req("/voices"))["voices"]]
    def tts(self, text, voice_id, model=DEFAULT, language="en", out_path=None, settings=None):
        """Returns (data URI of mp3, mp3 bytes)."""
        body = {"text": spoken(text), "model_id": MODELS.get(model, model),
                "voice_settings": settings or {"stability": 0.5, "similarity_boost": 0.85, "style": 0.0, "use_speaker_boost": True}}
        if language and model != "elevenlabs:eleven_v3": body["language_code"] = language
        mp3 = self._req(f"/text-to-speech/{voice_id}?output_format=mp3_44100_128", body).read()
        self.chars += len(text)
        if out_path: open(out_path, "wb").write(mp3)
        return "data:audio/mpeg;base64," + base64.b64encode(mp3).decode(), mp3
