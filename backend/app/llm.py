"""Provider adapters for evidence-grounded meeting intelligence."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from dotenv import load_dotenv


class ProviderNotConfiguredError(RuntimeError):
    """Raised when a production provider key has not been configured."""


class ProviderRequestError(RuntimeError):
    """Raised when a configured provider cannot complete an API request."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _load_local_environment() -> None:
    """Load the project-local ignored .env without overriding deployment secrets."""
    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)


class GroqJsonGenerator:
    """Turn the provider-neutral NLP prompt contract into validated JSON text."""

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    @classmethod
    def from_environment(cls) -> "GroqJsonGenerator":
        _load_local_environment()
        api_key = os.getenv("GROQ_API_KEY", "").strip()
        if not api_key:
            raise ProviderNotConfiguredError(
                "GROQ_API_KEY is not configured. Add it to the root .env file and restart the API."
            )
        return cls(api_key, os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip())

    def __call__(self, messages: list[dict[str, str]]) -> str:
        # Imported only when a configured user explicitly requests generation,
        # keeping offline checks independent of a provider installation or key.
        try:
            from groq import Groq

            response = Groq(api_key=self.api_key).chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.1,
            )
        except Exception as exc:
            provider_status = getattr(exc, "status_code", None)
            if provider_status == 401:
                message = "Groq rejected the configured credentials. Check GROQ_API_KEY."
            elif provider_status == 404:
                message = f"Groq could not find model '{self.model}'. Check GROQ_MODEL."
            elif provider_status == 429:
                message = "Groq rate limit or account quota was reached. Try again later or check the Groq account."
            elif provider_status == 413:
                message = "Groq rejected the prompt because its request body is too large. The transcript could not be split small enough to retry."
            elif provider_status is not None:
                message = f"Groq request failed with status {provider_status}. Check the model and Groq account."
            elif exc.__class__.__name__ == "ModuleNotFoundError":
                message = "The Groq client is not installed. Install the backend requirements and restart the API."
            else:
                message = "Could not reach Groq. Check the API server's network connection and try again."
            raise ProviderRequestError(message, status_code=provider_status) from exc
        content = response.choices[0].message.content
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Groq returned an empty response")
        return content
