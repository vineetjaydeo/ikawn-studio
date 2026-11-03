"""Pronunciation map for TTS: spoken text gets respellings, captions keep the script spelling.
Defaults below; add your own with IKAWN_PRONOUNCE="Word=respelling;Other=respelling" or a JSON file at
IKAWN_PRONOUNCE_FILE ({"Word": "respelling"}). Matching is whole-word and case-insensitive."""
import json, os, re
DEFAULT = {"iKawn": "Eye-kon"}
def mapping():
    m = dict(DEFAULT)
    f = os.environ.get("IKAWN_PRONOUNCE_FILE")
    if f and os.path.exists(f): m.update(json.load(open(f)))
    for pair in filter(None, os.environ.get("IKAWN_PRONOUNCE", "").split(";")):
        if "=" in pair: k, v = pair.split("=", 1); m[k.strip()] = v.strip()
    return m
def spoken(text, extra=None):
    m = {**mapping(), **(extra or {})}
    for k in sorted(m, key=len, reverse=True):
        text = re.sub(rf"(?<!\w){re.escape(k)}(?!\w)", m[k], text, flags=re.I)
    return text
