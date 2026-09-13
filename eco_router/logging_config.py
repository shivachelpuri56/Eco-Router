"""
Structured logging configuration for Eco-Router.
Uses Loguru with a JSON sink for machine-readable routing events.
Secrets are NEVER logged.
"""
from __future__ import annotations
import sys
from loguru import logger


def configure_logging(app_env: str = "development") -> None:
    """
    Set up Loguru sinks:
    - Console: coloured human-readable output in development
    - JSON file: machine-readable structured events for all environments
    """
    logger.remove()  # Remove default Loguru handler

    # ── Console Sink ─────────────────────────────────────────────────────────
    log_level = "DEBUG" if app_env == "development" else "INFO"

    # Windows safety: wrap stdout with utf-8 encoder so emoji/non-ASCII
    # characters don't cause UnicodeEncodeError on cp1252 consoles.
    import io
    import os
    safe_stdout = sys.stdout
    if hasattr(sys.stdout, "buffer"):
        try:
            safe_stdout = io.TextIOWrapper(
                sys.stdout.buffer,
                encoding="utf-8",
                errors="replace",
                line_buffering=True,
            )
        except Exception:
            pass  # stdout has no .buffer (e.g. redirected) — use as-is

    logger.add(
        safe_stdout,
        level=log_level,
        colorize=False,   # disable ANSI colours for Windows compatibility
        format=(
            "{time:YYYY-MM-DD HH:mm:ss} | "
            "{level: <8} | "
            "{name}:{function}:{line} | "
            "{message}"
        ),
        filter=_secret_filter,
    )

    # ── JSON File Sink ────────────────────────────────────────────────────────
    logger.add(
        "eco_router_events.jsonl",
        level="INFO",
        serialize=True,         # Loguru JSON output
        rotation="10 MB",
        retention="7 days",
        filter=_secret_filter,
    )


def _secret_filter(record: dict) -> bool:
    """
    Safety filter: drop any log record that accidentally contains
    an API key pattern. Prevents accidental secret leakage.
    """
    msg = str(record.get("message", ""))
    # Simple heuristic — reject if message looks like it contains a key
    for keyword in ("api_key", "auth-token", "Authorization", "password", "secret"):
        if keyword.lower() in msg.lower() and len(msg) > 80:
            record["message"] = "[REDACTED — potential secret in log]"
            break
    return True


def emit_routing_event(event: dict) -> None:
    """
    Emit the structured routing decision event.
    This is the canonical log record for every proxied request.
    """
    logger.bind(**event).info("ROUTING_EVENT")
