from __future__ import annotations

from io import BytesIO

from flask import current_app
from huggingface_hub import InferenceClient
from PIL import Image


class HuggingFaceImageProvider:
    def __init__(self, *, token: str, provider: str, model_id: str):
        self.client = InferenceClient(provider=provider, api_key=token)
        self.model_id = model_id

    def image_to_image(
        self,
        *,
        image_bytes: bytes,
        prompt: str,
        negative_prompt: str,
    ) -> bytes:
        result = self.client.image_to_image(
            image=image_bytes,
            prompt=prompt,
            negative_prompt=negative_prompt,
            model=self.model_id,
        )

        if isinstance(result, bytes):
            return self._normalize_png(result)

        if hasattr(result, "read"):
            return self._normalize_png(result.read())

        if isinstance(result, Image.Image):
            return self._normalize_png(result)

        raise RuntimeError(f"Unexpected image generation response type: {type(result)!r}")

    @staticmethod
    def _normalize_png(value: bytes | Image.Image) -> bytes:
        if isinstance(value, Image.Image):
            image = value
        else:
            image = Image.open(BytesIO(value))
        output = BytesIO()
        image.convert("RGBA").save(output, format="PNG")
        return output.getvalue()


def get_image_provider() -> HuggingFaceImageProvider:
    if current_app.config["AI_PROVIDER"] != "huggingface":
        raise RuntimeError(f"Unsupported AI_PROVIDER: {current_app.config['AI_PROVIDER']}")

    token = current_app.config["HF_TOKEN"]
    if not token:
        raise RuntimeError("HF_TOKEN is not configured")

    return HuggingFaceImageProvider(
        token=token,
        provider=current_app.config["HF_PROVIDER"],
        model_id=current_app.config["HF_MODEL_ID"],
    )
