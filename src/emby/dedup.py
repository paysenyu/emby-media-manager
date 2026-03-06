"""
Media deduplication service.
Scores multi-version Emby items against user-configured rules and
executes deletion of non-kept versions via the StrmAssistant DeleteVersion API.
"""
import re
import logging
from typing import Any, Dict, List, Union

logger = logging.getLogger(__name__)

# ── Default rule configuration ─────────────────────────────────────────────

DEFAULT_RULES = [
    {"rule_id": "subtitle",   "enabled": True,  "order": 0, "params": None},
    {"rule_id": "resolution", "enabled": True,  "order": 1, "params": {"priority": ["2160", "1080", "720", "480"]}},
    {"rule_id": "hdr",        "enabled": True,  "order": 2, "params": {"priority": ["DV", "HDR", "SDR"]}},
    {"rule_id": "codec",      "enabled": False, "order": 3, "params": {"priority": ["AV1", "hevc", "h264", "mpeg4"]}},
    {"rule_id": "bit_depth",  "enabled": False, "order": 4, "params": {"prefer": "high"}},
    {"rule_id": "quality",    "enabled": True,  "order": 5, "params": {"priority": ["Remux", "BluRay", "WEB-DL", "WEBRip", "HDTV"]}},
    {"rule_id": "bitrate",    "enabled": True,  "order": 6, "params": {"prefer": "high"}},
    {"rule_id": "frame_rate", "enabled": False, "order": 7, "params": {"prefer": "high"}},
    {"rule_id": "file_size",  "enabled": True,  "order": 8, "params": {"prefer": "large"}},
    {"rule_id": "duration",   "enabled": False, "order": 9, "params": {"prefer": "longest"}},
]

_CHINESE_LANGS = {"zh", "chi", "zho", "zh-cn", "zh-tw", "zh-hk", "chs", "cht"}

_QUALITY_RE = re.compile(
    r"remux|blu.?ray|web.?dl|webrip|hdtv",
    re.IGNORECASE,
)

_QUALITY_ORDER = ["remux", "blu-ray", "bluray", "web-dl", "webdl", "webrip", "hdtv"]


def _rule_id(rule) -> str:
    """Accept both ORM objects and plain dicts."""
    return rule.rule_id if hasattr(rule, "rule_id") else rule["rule_id"]


def _rule_enabled(rule) -> bool:
    return rule.enabled if hasattr(rule, "enabled") else rule.get("enabled", True)


def _rule_params(rule) -> Any:
    return rule.params if hasattr(rule, "params") else rule.get("params")


def _rule_order(rule) -> int:
    return rule.order if hasattr(rule, "order") else rule.get("order", 0)


# ── Stream helpers ─────────────────────────────────────────────────────────

def _video_stream(source: Dict) -> Dict:
    for s in source.get("MediaStreams", []):
        if s.get("Type") == "Video":
            return s
    return {}


def _has_chinese_sub(source: Dict) -> bool:
    for s in source.get("MediaStreams", []):
        if s.get("Type") == "Subtitle":
            lang = (s.get("Language") or "").lower().strip()
            if lang in _CHINESE_LANGS:
                return True
    return False


def _resolution_score(source: Dict, priority: List[str]) -> int:
    vs = _video_stream(source)
    h = vs.get("Height", 0) or 0
    # Map height to a label
    if h >= 2000:
        label = "2160"
    elif h >= 900:
        label = "1080"
    elif h >= 600:
        label = "720"
    elif h >= 400:
        label = "480"
    else:
        label = str(h)
    try:
        # Higher index in priority list = lower score
        idx = next(i for i, p in enumerate(priority) if p == label)
        return len(priority) - idx
    except StopIteration:
        return 0


def _hdr_score(source: Dict, priority: List[str]) -> int:
    vs = _video_stream(source)
    vr = (vs.get("VideoRange") or vs.get("VideoRangeType") or "").upper()
    # Detect DV / HDR / SDR
    if "DOV" in vr or "DV" in vr or "DOLBY" in vr:
        label = "DV"
    elif "HDR" in vr:
        label = "HDR"
    else:
        label = "SDR"
    try:
        idx = next(i for i, p in enumerate(priority) if p == label)
        return len(priority) - idx
    except StopIteration:
        return 0


def _codec_score(source: Dict, priority: List[str]) -> int:
    vs = _video_stream(source)
    codec = (vs.get("Codec") or "").lower()
    try:
        idx = next(i for i, p in enumerate(priority) if p.lower() == codec)
        return len(priority) - idx
    except StopIteration:
        return 0


def _quality_score(source: Dict, priority: List[str]) -> int:
    name = (source.get("Name") or source.get("Path") or "")
    name_lower = name.lower()
    for i, kw in enumerate(priority):
        if kw.lower().replace("-", "").replace(".", "") in name_lower.replace("-", "").replace(".", ""):
            return len(priority) - i
    return 0


# ── Main scoring function ──────────────────────────────────────────────────

def _score_version(source: Dict, rules) -> tuple:
    """
    Build a comparable score tuple for *source* given the ordered rule list.
    Larger tuple == higher preference == should be kept.
    Tiebreaker: file size (last element).
    """
    scores = []
    for rule in sorted(rules, key=_rule_order):
        if not _rule_enabled(rule):
            continue
        rid = _rule_id(rule)
        params = _rule_params(rule) or {}

        vs = _video_stream(source)

        if rid == "subtitle":
            scores.append(1 if _has_chinese_sub(source) else 0)

        elif rid == "resolution":
            priority = params.get("priority", ["2160", "1080", "720", "480"])
            scores.append(_resolution_score(source, priority))

        elif rid == "hdr":
            priority = params.get("priority", ["DV", "HDR", "SDR"])
            scores.append(_hdr_score(source, priority))

        elif rid == "codec":
            priority = params.get("priority", ["AV1", "hevc", "h264", "mpeg4"])
            scores.append(_codec_score(source, priority))

        elif rid == "bit_depth":
            bd = vs.get("BitDepth") or 0
            prefer = params.get("prefer", "high")
            scores.append(bd if prefer == "high" else -bd)

        elif rid == "quality":
            priority = params.get("priority", ["Remux", "BluRay", "WEB-DL", "WEBRip", "HDTV"])
            scores.append(_quality_score(source, priority))

        elif rid == "bitrate":
            br = vs.get("BitRate") or 0
            prefer = params.get("prefer", "high")
            scores.append(br if prefer == "high" else -br)

        elif rid == "frame_rate":
            fr = vs.get("RealFrameRate") or vs.get("AverageFrameRate") or 0
            prefer = params.get("prefer", "high")
            scores.append(fr if prefer == "high" else -fr)

        elif rid == "file_size":
            sz = source.get("Size") or 0
            prefer = params.get("prefer", "large")
            scores.append(sz if prefer == "large" else -sz)

        elif rid == "duration":
            ticks = source.get("RunTimeTicks") or 0
            prefer = params.get("prefer", "longest")
            scores.append(ticks if prefer == "longest" else -ticks)

    # Tiebreaker: always prefer larger file
    scores.append(source.get("Size") or 0)
    return tuple(scores)


# ── Service class ──────────────────────────────────────────────────────────

class DedupService:
    """High-level deduplication operations."""

    def score_version(self, source: Dict, rules) -> tuple:
        return _score_version(source, rules)

    def compute_preview(self, items: List[Dict], rules) -> List[Dict]:
        """
        Given a list of multi-version Emby items and a rule set, return a
        preview list with each version annotated as keep=True/False.
        """
        preview = []
        for item in items:
            sources = item.get("MediaSources", [])
            if len(sources) < 2:
                continue

            scored = []
            for src in sources:
                sc = _score_version(src, rules)
                vs = _video_stream(src)
                h = vs.get("Height", 0) or 0
                w = vs.get("Width", 0) or 0
                scored.append({
                    "id": src.get("Id", ""),
                    "name": src.get("Name", ""),
                    "path": src.get("Path", ""),
                    "size": src.get("Size") or 0,
                    "resolution": f"{w}x{h}" if w and h else "unknown",
                    "codec": (vs.get("Codec") or "").lower(),
                    "hdr": (vs.get("VideoRange") or vs.get("VideoRangeType") or "SDR").upper(),
                    "bitrate": vs.get("BitRate") or 0,
                    "has_chinese_sub": _has_chinese_sub(src),
                    "_score": sc,
                    "keep": False,
                })

            # Mark the highest-scored version as keep
            best_idx = max(range(len(scored)), key=lambda i: scored[i]["_score"])
            scored[best_idx]["keep"] = True

            # Remove internal score field before returning
            for v in scored:
                v.pop("_score", None)

            # Compute size to be freed (sum of deleted versions)
            freed = sum(v["size"] for v in scored if not v["keep"])

            preview.append({
                "item_id": item.get("Id", ""),
                "title": item.get("Name", ""),
                "year": item.get("ProductionYear"),
                "versions": scored,
                "freed_bytes": freed,
            })

        return preview

    def execute_dedup(self, preview: List[Dict], client) -> Dict[str, Any]:
        """
        Delete all non-kept versions using the StrmAssistant DeleteVersion API.
        Calls delete_version once per version (version_id as path param).
        Returns {"deleted": int, "errors": [str]}.
        """
        deleted = 0
        errors = []

        for item in preview:
            item_id = item.get("item_id", "")
            to_delete = [v["id"] for v in item.get("versions", []) if not v.get("keep")]
            if not to_delete:
                continue

            for version_id in to_delete:
                try:
                    ok = client.delete_version(version_id)
                    if ok:
                        deleted += 1
                        logger.info(f"Deleted version {version_id} from item {item_id} ({item.get('title')})")
                    else:
                        msg = f"delete_version returned False for version {version_id} of item {item_id}"
                        errors.append(msg)
                        logger.warning(msg)
                except Exception as exc:
                    msg = f"Error deleting version {version_id} of item {item_id}: {exc}"
                    errors.append(msg)
                    logger.error(msg)

        return {"deleted": deleted, "errors": errors}