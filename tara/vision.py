import os
import re
import json
import base64
import logging
from abc import ABC, abstractmethod
from typing import Optional, Any
from tara.config import config

logger = logging.getLogger("tara.vision")


class VisionProvider(ABC):
    """Abstract interface for Vision API providers."""

    @abstractmethod
    def analyze(self, image_base64: str, mime_type: str, question: Optional[str] = None) -> Optional[dict[str, Any]]:
        """Process an image and return structured analysis."""
        pass


class OllamaVisionProvider(VisionProvider):
    """
    Primary Vision Provider utilizing local Ollama vision models (Moondream, LLaVA, Llama-3.2-Vision).
    Zero cloud dependencies, private, and fast on Apple Silicon M1.
    """

    def __init__(self, default_model: str = "moondream:latest"):
        self.url = f"{config.ollama_host}/api/generate"
        self.models = [default_model, "moondream", "llama3.2-vision", "llava"]

    def analyze(self, image_base64: str, mime_type: str, question: Optional[str] = None) -> Optional[dict[str, Any]]:
        import requests

        user_query = question or "Describe what is visible on this screen in detail, identify any open applications, windows, or errors."
        prompt_text = (
            f"{user_query}\n\n"
            "Provide a thorough breakdown of visible elements, active windows/applications, and any notable issues or details."
        )

        for model in self.models:
            try:
                payload = {
                    "model": model,
                    "prompt": prompt_text,
                    "images": [image_base64],
                    "stream": False,
                    "options": {"temperature": 0.2}
                }
                resp = requests.post(self.url, json=payload, timeout=45)
                if resp.status_code == 200:
                    data = resp.json()
                    raw_text = data.get("response", "").strip()
                    if raw_text:
                        logger.info(f"Ollama vision inference succeeded with model '{model}'")
                        return self._parse_structured_output(raw_text)
            except Exception as e:
                logger.debug(f"Ollama vision attempt with model '{model}' failed: {e}")
                continue

        return None

    def _parse_structured_output(self, raw_text: str) -> dict[str, Any]:
        """Convert raw model response into structured dictionary."""
        lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
        issues = []
        suggestions = []
        desc_lines = []

        for line in lines:
            lower = line.lower()
            if any(k in lower for k in ["error", "issue", "bug", "warning", "exception", "failed"]):
                issues.append(line.strip("- *# "))
            elif any(k in lower for k in ["suggest", "recommend", "fix", "consider", "solution"]):
                suggestions.append(line.strip("- *# "))
            else:
                desc_lines.append(line)

        description = "\n".join(desc_lines) if desc_lines else raw_text

        return {
            "description": description,
            "issues": issues,
            "suggestions": suggestions
        }


class GroqVisionProvider(VisionProvider):
    """Optional secondary fallback Vision Provider for Groq API (active models only)."""

    def __init__(self):
        self.client = None
        if config.groq_api_key and config.groq_api_key != "your_groq_api_key_here":
            try:
                from groq import Groq
                self.client = Groq(api_key=config.groq_api_key)
            except Exception as e:
                logger.warning(f"Groq vision client initialization failed: {e}")

        # Active Groq models
        self.models = [
            "meta-llama/llama-3.2-11b-vision-instruct",
            "llama-3.2-11b-vision-instruct",
            "meta-llama/llama-3.2-90b-vision-instruct"
        ]

    def analyze(self, image_base64: str, mime_type: str, question: Optional[str] = None) -> Optional[dict[str, Any]]:
        if not self.client:
            return None

        user_query = question or "Analyze this screen image. Describe what you see, identify open windows and any errors."
        prompt_instruction = (
            f"{user_query}\n\n"
            "Respond in structured JSON with keys: \"description\", \"issues\", \"suggestions\"."
        )

        for model in self.models:
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt_instruction},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{mime_type};base64,{image_base64}"
                                    }
                                }
                            ]
                        }
                    ],
                    temperature=0.2,
                    max_tokens=1024,
                    response_format={"type": "json_object"}
                )

                content = response.choices[0].message.content
                if content:
                    data = json.loads(content)
                    return {
                        "description": data.get("description", ""),
                        "issues": data.get("issues", []),
                        "suggestions": data.get("suggestions", [])
                    }
            except Exception as e:
                logger.debug(f"Groq vision attempt with model '{model}' failed: {e}")
                continue

        return None


class VisionEngine:
    """
    Central Vision Engine for TARA.
    Primary: Local Ollama (Moondream)
    Secondary: Cloud Groq (Optional)
    """

    def __init__(self, primary_provider: Optional[VisionProvider] = None):
        self.primary_provider = primary_provider or OllamaVisionProvider(default_model="moondream:latest")
        self.fallback_provider = GroqVisionProvider()

    def analyze_image(self, image_path: str, question: Optional[str] = None) -> dict[str, Any]:
        """
        Analyze an image file and return structured insights.
        """
        if not image_path or not os.path.exists(image_path):
            return {
                "description": f"Image file not found: {image_path}",
                "issues": ["File does not exist or invalid path provided."],
                "suggestions": ["Please verify the image file path and try again."]
            }

        try:
            ext = os.path.splitext(image_path)[1].lower()
            mime_type = "image/png" if ext == ".png" else "image/jpeg"

            with open(image_path, "rb") as f:
                image_bytes = f.read()

            if len(image_bytes) == 0:
                return {
                    "description": "Image file is empty (0 bytes).",
                    "issues": ["Empty file received."],
                    "suggestions": ["Ensure screenshot capture was successful."]
                }

            image_b64 = base64.b64encode(image_bytes).decode("utf-8")

            # 1. Primary: Local Ollama (Moondream)
            result = self.primary_provider.analyze(image_b64, mime_type, question)
            if result:
                return result

            # 2. Secondary: Groq Vision (Optional Fallback)
            result = self.fallback_provider.analyze(image_b64, mime_type, question)
            if result:
                return result

            # 3. Graceful Fallback
            return {
                "description": "Visual input received, but local vision service (Moondream) is currently unreachable.",
                "issues": ["Ollama vision endpoint timed out or is offline."],
                "suggestions": ["Ensure Ollama is running (`ollama serve`) and `moondream` is installed."]
            }

        except Exception as e:
            logger.error(f"Vision analysis failed: {e}")
            return {
                "description": f"Failed to analyze image due to an error: {e}",
                "issues": [str(e)],
                "suggestions": ["Inspect image format and permissions."]
            }
