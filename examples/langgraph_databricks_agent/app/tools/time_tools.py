from datetime import datetime, timezone

from langchain_core.tools import tool


@tool
def current_utc_time() -> str:
    """Get the current UTC time in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()
