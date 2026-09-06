"""AegisX-TTS: CPU-first streaming text-to-speech untuk id, en, ms, jv."""

from aegisx_tts.core.model import Synth
from aegisx_tts.core.speaker import ConsentMeta, SpeakerProfile, SpeakerSource, save_speaker

__all__ = [
    "ConsentMeta",
    "SpeakerProfile",
    "SpeakerSource",
    "Synth",
    "save_speaker",
]

__version__ = "0.1.0.dev1"
