from datetime import datetime, timezone

def format_file_size(size_bytes: int) -> str:
    if not size_bytes:
        return '0 B'
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"

def format_duration(seconds: int) -> str:
    if not seconds:
        return '00:00:00'
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

def safe_get(d: dict, *keys, default=None):
    for key in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(key, default)
    return d

def utcnow() -> datetime:
    return datetime.now(timezone.utc)
