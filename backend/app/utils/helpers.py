"""
General utility helpers.

TODO (Backend Dev):
- generate_scan_id() — unique scan identifier
- format_file_size(bytes) — human-readable size
- sanitize_filename(name) — safe filename
"""

import uuid


def generate_scan_id() -> str:
    """Generate a unique scan identifier."""
    return str(uuid.uuid4())
