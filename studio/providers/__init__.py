import os
def get_provider(name=None, key=None):
    name = (name or os.environ.get("STUDIO_PROVIDER", "runware")).lower()
    if name == "runware":
        from .runware import Runware; return Runware(key)
    if name == "mock":  # offline: returns local sample clips, $0. For tests/demos only.
        from .mock import Mock; return Mock()
    raise ValueError(f"{name}: only runware (and mock for tests) are implemented in v0.1 (fal adapter on roadmap)")
