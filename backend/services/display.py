import json


def format_metadata(metadata, empty_text: str) -> str:
    """Render a JSONB metadata value (psycopg2 decodes it to a dict) as pretty-printed text."""
    return json.dumps(metadata, indent=2) if metadata else empty_text
