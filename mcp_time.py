import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, available_timezones
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("time", instructions="""
Time and timezone conversion tools. Supports IANA timezone names
(e.g., 'Asia/Jakarta', 'America/New_York', 'Europe/London').
""")

DEFAULT_TIMEZONE = os.environ.get("LOCAL_TIMEZONE", None)

def _resolve_tz(tz: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz)
    except KeyError:
        raise ValueError(f"Unknown timezone: {tz}")

@mcp.tool(
    name="get_current_time",
    description="Get current time in a specific timezone or system timezone."
)
async def get_current_time(timezone: str = None) -> str:
    tz_str = timezone or DEFAULT_TIMEZONE or "UTC"
    try:
        tz = _resolve_tz(tz_str)
    except ValueError as e:
        return f"(error: {e})"
    now = datetime.now(tz)
    is_dst = bool(now.dst())
    return json.dumps({
        "timezone": tz_str,
        "datetime": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "weekday": now.strftime("%A"),
        "is_dst": is_dst,
        "utc_offset": now.strftime("%z")
    }, indent=2)

@mcp.tool(
    name="convert_time",
    description="Convert time between timezones. Time in HH:MM 24-hour format."
)
async def convert_time(source_timezone: str, time: str, target_timezone: str) -> str:
    try:
        src_tz = _resolve_tz(source_timezone)
        dst_tz = _resolve_tz(target_timezone)
    except ValueError as e:
        return f"(error: {e})"
    try:
        parts = time.split(":")
        hour, minute = int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return "(error: invalid time format, use HH:MM)"
    now = datetime.now(src_tz)
    source_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    target_dt = source_dt.astimezone(dst_tz)
    diff_hours = (target_dt.utcoffset().total_seconds() - source_dt.utcoffset().total_seconds()) / 3600
    return json.dumps({
        "source": {
            "timezone": source_timezone,
            "datetime": source_dt.isoformat(),
            "is_dst": bool(source_dt.dst())
        },
        "target": {
            "timezone": target_timezone,
            "datetime": target_dt.isoformat(),
            "is_dst": bool(target_dt.dst())
        },
        "time_difference": f"{diff_hours:+.1f}h"
    }, indent=2)

@mcp.tool(
    name="list_timezones",
    description="List available IANA timezone names, optionally filtered by search query."
)
async def list_timezones(query: str = None) -> str:
    tzones = sorted(available_timezones())
    if query:
        q = query.lower()
        tzones = [t for t in tzones if q in t.lower()]
        if not tzones:
            return "(no matching timezones)"
    if len(tzones) > 50:
        return f"Found {len(tzones)} timezones (showing first 50):\n" + "\n".join(tzones[:50])
    return "\n".join(tzones)

import json

if __name__ == "__main__":
    mcp.run(transport="stdio")
