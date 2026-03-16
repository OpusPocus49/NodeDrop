from __future__ import annotations

from datetime import datetime

from core.models import Peer, TransferJob


def format_bytes(value: int) -> str:
    """
    Human-readable byte formatting.
    """
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(max(0, value))
    unit_index = 0

    while size >= 1024.0 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1

    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"

    return f"{size:.2f} {units[unit_index]}"


def format_percent(value: float) -> str:
    clamped = max(0.0, min(100.0, value))
    return f"{clamped:.1f} %"


def format_speed(value_bps: float) -> str:
    if value_bps <= 0:
        return "-"

    return f"{format_bytes(int(value_bps))}/s"


def format_duration(value_seconds: float | None) -> str:
    if value_seconds is None:
        return "-"

    total_seconds = max(0, int(round(value_seconds)))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def format_peer_status(peer: Peer) -> str:
    return "En ligne" if peer.is_online else "Hors ligne"


def format_peer_endpoint(peer: Peer) -> str:
    return f"{peer.ip_address}:{peer.tcp_port}"


def format_transfer_summary(job: TransferJob) -> str:
    return (
        f"{job.status.value} — "
        f"{format_bytes(job.transferred_bytes)} / {format_bytes(job.total_bytes)}"
    )


def format_remote_endpoint(display_name: str | None, ip_address: str | None) -> str:
    if display_name and ip_address:
        return f"{display_name} ({ip_address})"

    if display_name:
        return display_name

    if ip_address:
        return ip_address

    return "-"


def format_timestamp(value: datetime | None) -> str:
    if value is None:
        return "-"
    return value.astimezone().strftime("%Y-%m-%d %H:%M:%S")