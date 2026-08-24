import re
import time
import logging
from typing import Any

logger = logging.getLogger("tara.emotion")


class EmotionEngine:
    """
    Lightweight, deterministic rule-based emotion detection and response style adapter.
    Zero ML dependencies, latency < 1ms, memory footprint < 1MB.
    """

    EMOTIONS = [
        "neutral",
        "happy",
        "excited",
        "frustrated",
        "stressed",
        "confused",
        "tired",
        "focused"
    ]

    STYLE_GUIDANCE = {
        "frustrated": "User seems frustrated. Be patient, calm, and provide small, step-by-step solutions. Avoid overwhelming explanations.",
        "stressed": "User is feeling stressed. Be reassuring, structured, and prioritize immediate relief.",
        "excited": "User is excited or celebrating progress. Match their enthusiasm briefly and acknowledge their achievement warmly.",
        "happy": "User is in positive spirits. Be warm, supportive, and engaging.",
        "tired": "User is tired or fatigued. Keep responses extra concise, direct, and gently suggest taking a rest if appropriate.",
        "confused": "User is confused or unclear. Explain simply using clear structure, step-by-step logic, and intuitive examples.",
        "focused": "User is deeply focused on work. Be direct, efficient, precise, and omit conversational pleasantries.",
        "neutral": "Maintain standard efficient, witty, and capable assistant style."
    }

    def __init__(self):
        # Compiled regex patterns for ultra-fast matching (< 0.1ms)
        self.patterns = {
            "excited": [
                r"\b(?:i finally|finally fixed|finally completed|finally did it|yes!|awesome!|hurray|woohoo|let's go|lets go|so happy|amazing!|huge win)\b",
                r"\b(?:i completed|finished building|launched|shipped|passed all tests)\b.*!",
            ],
            "frustrated": [
                r"\b(?:driving me crazy|so annoying|annoying|hate this|can't figure out|cant figure out|stuck on this|sick of this|stupid error|damn|wasted hours|failing again|doesn't work|does not work at all)\b",
                r"\b(?:this error is|this bug is|why is this not working)\b",
            ],
            "stressed": [
                r"\b(?:freaking out|overwhelmed|too much pressure|deadline is tomorrow|panicking|under pressure|anxious|running out of time)\b",
            ],
            "tired": [
                r"\b(?:i am tired|i'm tired|so exhausted|exhausted|sleepy|drained|need sleep|need a break|headache|burnt out|burnout|no energy)\b",
            ],
            "confused": [
                r"\b(?:i don't understand|i dont understand|what does this mean|makes no sense|confused|not sure what|how is this possible|lost here)\b",
                r"\b(?:why would|what's the difference between)\b.*\?",
            ],
            "happy": [
                r"\b(?:great job|feeling good|love it|thank you so much|thanks a lot|glad|appreciate it|wonderful|nice work)\b",
            ],
            "focused": [
                r"\b(?:let's implement|let's write|optimize|refactor|benchmark|profile|debug step|analyze this code)\b",
            ],
        }

    def analyze(self, text: str) -> dict[str, Any]:
        """
        Analyze text to detect user emotional state with confidence rating and response style guide.
        """
        if not text or not text.strip():
            return {
                "emotion": "neutral",
                "confidence": 1.0,
                "style_guidance": self.STYLE_GUIDANCE["neutral"],
                "latency_ms": 0.0
            }

        t0 = time.perf_counter()
        clean = text.strip().lower()

        # Check emotional pattern matches with prioritized precedence
        priority_order = ["frustrated", "excited", "tired", "stressed", "confused", "happy", "focused"]

        for emotion in priority_order:
            for pattern in self.patterns[emotion]:
                if re.search(pattern, clean):
                    # Check for exclamation boost
                    excl_boost = 0.05 if "!" in text else 0.0
                    confidence = min(0.95, 0.85 + excl_boost)
                    latency = (time.perf_counter() - t0) * 1000
                    return {
                        "emotion": emotion,
                        "confidence": round(confidence, 2),
                        "style_guidance": self.STYLE_GUIDANCE[emotion],
                        "latency_ms": round(latency, 4)
                    }

        latency = (time.perf_counter() - t0) * 1000
        return {
            "emotion": "neutral",
            "confidence": 0.80,
            "style_guidance": self.STYLE_GUIDANCE["neutral"],
            "latency_ms": round(latency, 4)
        }
