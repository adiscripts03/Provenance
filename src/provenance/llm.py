"""Central LLM Gateway for Provenance.

AGENTS.md Rule: All LLM calls go through ONE module (src/provenance/llm.py)
using the OpenAI-compatible API of Ollama. Model name and base URL come
from environment variables. Validate all model outputs with Pydantic;
retry once on failure, then fallback safely.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any, Optional, Type, TypeVar
from openai import OpenAI
from pydantic import BaseModel, ValidationError

from provenance.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

def detect_local_ollama_and_gemma(
    base_url: str = "http://localhost:11434",
    required_model: str = "gemma4:12b",
    timeout: float = 2.0,
) -> bool:
    """Detect whether local Ollama is running and has the required Gemma model installed."""

    url = base_url.rstrip("/")
    if url.endswith("/v1"):
        url = url[:-3]
    tags_url = f"{url}/api/tags"

    try:
        req = urllib.request.Request(tags_url, headers={"User-Agent": "Provenance/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status != 200:
                return False
            payload = json.loads(response.read().decode("utf-8"))
            models = payload.get("models", [])
            for m in models:
                name = m.get("name", "")
                model_field = m.get("model", "")
                if required_model in (name, model_field) or name.startswith(required_model) or required_model in name:
                    return True
            return False
    except Exception:
        return False

class LLMValidationError(Exception):
    """Raised when LLM output repeatedly fails Pydantic schema validation."""
    pass

class LLMGateway:
    """Singleton gateway managing all OpenAI-compatible completions.

    If local Ollama with Gemma is detected, uses local Ollama.
    Otherwise, automatically falls back to Groq (openai/gpt-oss-120b).
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        api_key: Optional[str] = None,
    ):
        self.temperature = temperature if temperature is not None else settings.temperature

        explicit_model = model or os.getenv("LLM_MODEL")
        explicit_base_url = base_url or os.getenv("OLLAMA_BASE_URL")
        groq_api_key = api_key or os.getenv("GROQ_API_KEY") or settings.groq_api_key

        auto_detect = os.getenv("AUTO_DETECT_LOCAL")
        if auto_detect is not None:
            should_detect = auto_detect.lower() in ("true", "1", "yes")
        else:
            should_detect = settings.auto_detect_local

        is_local_available = False
        if should_detect:
            check_url = explicit_base_url or settings.ollama_base_url
            target_model = explicit_model or settings.llm_model
            is_local_available = detect_local_ollama_and_gemma(
                base_url=check_url,
                required_model=target_model,
            )

        if is_local_available:
            self.provider = "ollama"
            self.base_url = explicit_base_url or settings.ollama_base_url
            self.model = explicit_model or settings.llm_model
            self.api_key = "ollama"
            logger.info("LLMGateway: Local Ollama with model '%s' detected. Using local inference.", self.model)
        elif groq_api_key:
            self.provider = "groq"
            self.base_url = os.getenv("GROQ_BASE_URL", settings.groq_base_url)
            self.model = os.getenv("GROQ_MODEL", settings.groq_model)
            self.api_key = groq_api_key
            logger.info("LLMGateway: Local Ollama/Gemma not detected. Falling back to Groq model '%s'.", self.model)
        else:

            self.provider = "ollama"
            self.base_url = explicit_base_url or settings.ollama_base_url
            self.model = explicit_model or settings.llm_model
            self.api_key = "ollama"
            logger.warning(
                "LLMGateway: Local Ollama/Gemma not detected and GROQ_API_KEY not set. Defaulting to '%s' at %s.",
                self.model,
                self.base_url,
            )

        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key, timeout=90.0)

    def generate_chat(
        self,
        messages: list[dict[str, str]],
        json_mode: bool = True,
        temperature: Optional[float] = None,
    ) -> str:
        """Execute a chat completion request to the LLM."""
        temp = temperature if temperature is not None else self.temperature
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temp,
        }
        if self.provider == "ollama":
            kwargs["reasoning_effort"] = "none"

        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    def generate_structured(
        self,
        user_prompt: str,
        response_model: Type[T],
        system_prompt: Optional[str] = None,
        max_retries: int = 1,
    ) -> T:
        """Generate and validate a structured Pydantic object from the LLM.

        Retries once with validation feedback on failure.
        """
        sys_prompt = system_prompt or (
            "You are an evidence-first enterprise compliance AI. "
            "You must return ONLY a valid JSON object matching the requested schema. "
            "Never include explanations or markdown fences outside the JSON object."
        )

        schema_json = json.dumps(response_model.model_json_schema(), indent=2)
        prompt_with_schema = (
            f"{user_prompt}\n\n"
            f"You MUST strictly follow this JSON schema:\n"
            f"```json\n{schema_json}\n```\n"
            f"Return ONLY valid JSON."
        )

        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": prompt_with_schema},
        ]

        attempt = 0
        last_error = ""

        while attempt <= max_retries:
            try:
                raw_output = self.generate_chat(messages, json_mode=True)

                clean_json = raw_output.strip()
                if clean_json.startswith("```json"):
                    clean_json = clean_json[7:]
                if clean_json.startswith("```"):
                    clean_json = clean_json[3:]
                if clean_json.endswith("```"):
                    clean_json = clean_json[:-3]
                clean_json = clean_json.strip()

                return response_model.model_validate_json(clean_json)

            except (ValidationError, json.JSONDecodeError) as exc:
                last_error = str(exc)
                logger.warning(
                    "LLM schema validation failed on attempt %d/%d: %s",
                    attempt + 1,
                    max_retries + 1,
                    last_error,
                )
                attempt += 1
                if attempt <= max_retries:

                    messages.append({"role": "assistant", "content": raw_output})
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                f"Your previous response failed schema validation with error: {last_error}\n"
                                f"Please fix the error and output valid JSON strictly matching the schema."
                            ),
                        }
                    )

        raise LLMValidationError(f"Failed to generate valid {response_model.__name__} after {max_retries + 1} attempts: {last_error}")

llm_gateway = LLMGateway()
