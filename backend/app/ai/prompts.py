from __future__ import annotations

from typing import Any

from ..models.enums import GeneratedImageType

REQUIRED_GENERATION_TYPES = (
    GeneratedImageType.WHITE_BG,
    GeneratedImageType.THEME_MARBLE,
    GeneratedImageType.THEME_VELVET,
    GeneratedImageType.CREATIVE_BEACH,
    GeneratedImageType.CREATIVE_STUDIO,
    GeneratedImageType.MODEL_FRONT,
    GeneratedImageType.MODEL_SIDE,
    GeneratedImageType.MODEL_CLOSEUP,
)

MODEL_VARIANTS = {
    GeneratedImageType.MODEL_FRONT,
    GeneratedImageType.MODEL_SIDE,
    GeneratedImageType.MODEL_CLOSEUP,
}

GENERATION_LABELS = {
    GeneratedImageType.WHITE_BG: "white background",
    GeneratedImageType.THEME_MARBLE: "theme marble",
    GeneratedImageType.THEME_VELVET: "theme velvet",
    GeneratedImageType.CREATIVE_BEACH: "creative beach",
    GeneratedImageType.CREATIVE_STUDIO: "creative studio",
    GeneratedImageType.MODEL_FRONT: "model front",
    GeneratedImageType.MODEL_SIDE: "model side",
    GeneratedImageType.MODEL_CLOSEUP: "model closeup",
}

GENERATION_ANGLES = {
    GeneratedImageType.MODEL_FRONT: "front view",
    GeneratedImageType.MODEL_SIDE: "45-degree side angle",
    GeneratedImageType.MODEL_CLOSEUP: "close-up detail shot",
}

NEGATIVE_PROMPT = (
    "cartoon, illustration, painting, 3d render, CGI, plastic look, blurry, low resolution, "
    "distorted product, altered branding, changed logo, wrong colors, duplicate product, extra objects, "
    "extra limbs, bad anatomy, deformed hands, warped fabric, noisy background, watermark, text, caption, "
    "frame, border, oversaturated, underexposed, cropped product, floating product"
)


def _task_context(task) -> str:
    description = (getattr(task, "description", "") or "").strip()
    if description:
        return f"{task.title}. {description}"
    return str(task.title)


def generation_label(image_type: GeneratedImageType) -> str:
    return GENERATION_LABELS[image_type]


def generation_angle(image_type: GeneratedImageType) -> str | None:
    return GENERATION_ANGLES.get(image_type)


def is_model_variant(image_type: GeneratedImageType) -> bool:
    return image_type in MODEL_VARIANTS


def build_positive_prompt(task, image_type: GeneratedImageType) -> str:
    context = _task_context(task)
    if image_type == GeneratedImageType.WHITE_BG:
        return (
            f"Photorealistic e-commerce product photo of {context}. "
            "Pure white #FFFFFF background, clean extraction, centered composition, soft natural shadow, "
            "sharp edges, accurate colors, premium catalog lighting, no props."
        )
    if image_type == GeneratedImageType.THEME_MARBLE:
        return (
            f"Photorealistic premium product photography of {context} on a polished marble surface. "
            "Natural studio daylight, elegant reflections, refined styling, realistic shadows, luxury editorial feel, "
            "product remains the hero."
        )
    if image_type == GeneratedImageType.THEME_VELVET:
        return (
            f"Photorealistic premium product photography of {context} on rich velvet fabric. "
            "Soft tactile texture, moody but natural lighting, elegant folds, realistic shadows, "
            "high-end fashion editorial style, product remains perfectly recognizable."
        )
    if image_type == GeneratedImageType.CREATIVE_BEACH:
        return (
            f"Photorealistic lifestyle scene featuring {context} at a beach sunset. "
            "Natural warm light, realistic environment, sophisticated composition, product still accurate and dominant, "
            "not cartoonish, not stylized."
        )
    if image_type == GeneratedImageType.CREATIVE_STUDIO:
        return (
            f"Photorealistic lifestyle scene featuring {context} in a modern studio set. "
            "Clean contemporary set design, premium fashion editorial lighting, realistic materials, "
            "product consistency preserved exactly."
        )
    if image_type == GeneratedImageType.MODEL_FRONT:
        return (
            f"Photorealistic human model wearing {context}, front view. "
            "Natural pose, realistic skin tones, authentic fabric drape, balanced proportions, "
            "e-commerce fashion quality, product fit and branding preserved exactly."
        )
    if image_type == GeneratedImageType.MODEL_SIDE:
        return (
            f"Photorealistic human model wearing {context}, 45-degree side angle. "
            "Natural stance, realistic body proportions, accurate garment shape and texture, "
            "high-end fashion catalog quality."
        )
    if image_type == GeneratedImageType.MODEL_CLOSEUP:
        return (
            f"Photorealistic close-up of a human model wearing {context}. "
            "Focus on fabric texture, seams, fit, stitching, and natural skin tones, "
            "premium editorial realism, no abstraction."
        )
    raise ValueError(f"Unsupported generation type: {image_type}")


def build_negative_prompt(task, image_type: GeneratedImageType) -> str:
    _ = task
    _ = image_type
    return NEGATIVE_PROMPT


def build_generation_metadata(
    *,
    task,
    image_type: GeneratedImageType,
    prompt: str,
    negative_prompt: str,
    source_url: str,
    source_sha256: str,
    provider: str,
    model_id: str,
    job_id: str | None,
) -> dict[str, Any]:
    return {
        "task_id": str(task.id),
        "task_title": task.title,
        "image_type": image_type.value,
        "angle": generation_angle(image_type),
        "provider": provider,
        "model_id": model_id,
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "source_url": source_url,
        "source_sha256": source_sha256,
        "job_id": job_id,
    }
