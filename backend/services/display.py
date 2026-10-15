import json


def format_metadata(metadata, empty_text: str) -> str:
    """Render a JSONB metadata value as display-ready, pretty-printed text."""
    if not metadata:
        return empty_text
    try:
        parsed = json.loads(metadata) if isinstance(metadata, str) else metadata
        return json.dumps(parsed, indent=2)
    except (TypeError, ValueError):
        return str(metadata)
