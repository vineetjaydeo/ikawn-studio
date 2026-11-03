CAMERA = {
 "static": "locked-off static camera",
 "dolly-in": "slow smooth dolly-in push toward the subject",
 "dolly-out": "slow dolly-out pull back revealing the scene",
 "orbit": "smooth 180-degree orbit around the subject",
 "crane-up": "crane shot rising up and over the subject",
 "handheld": "handheld camera with subtle natural shake",
 "fpv-drone": "fast FPV drone fly-through",
 "whip-pan": "quick whip pan transition",
 "zoom-in": "dramatic crash zoom in",
}
STYLE = {
 "none": "", "cinematic": "cinematic film look, anamorphic, shallow depth of field, color graded",
 "ugc": "authentic UGC smartphone footage, natural light", "anime": "anime style, vibrant cel shading",
 "product": "premium studio product commercial, soft key light, glossy reflections",
 "vhs": "retro VHS look, grain, chromatic aberration",
}
def build_prompt(prompt, camera="static", style="none"):
    parts = [prompt.strip(), CAMERA.get(camera, ""), STYLE.get(style, ""), "vertical 9:16 framing"]
    return ", ".join(p for p in parts if p)
