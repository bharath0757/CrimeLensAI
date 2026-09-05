"""Compatibility adapter for the canonical extraction pipeline."""

from app.extractors.pipeline import run_extraction


def extract_entities_from_text(
    text: str,
    source_field: str = "fir_text",
) -> list[dict]:
    """Return the production extractor response as plain dictionaries."""
    return [
        entity.model_dump()
        for entity in run_extraction(text=text, source_field=source_field)
    ]
