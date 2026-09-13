"""
Simulated Cloud Region Server.

This is a lightweight FastAPI server that impersonates a cloud region.
Run three instances on different ports to simulate us-east-1, eu-north-1, ap-south-1.

Usage:
  python regions/server.py --region us-east-1 --port 9001
  python regions/server.py --region eu-north-1 --port 9002
  python regions/server.py --region ap-south-1 --port 9003

Or via environment variables:
  REGION_ID=eu-north-1 REGION_PORT=9002 python regions/server.py

IMPORTANT: These servers are SIMULATED. They do NOT represent real cloud infrastructure.
All responses include "simulated": true.
"""
from __future__ import annotations
import argparse
import os
from datetime import datetime, timezone

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


def create_region_app(region_id: str) -> FastAPI:
    """Factory — creates a FastAPI app for one simulated region."""

    # Region display names
    NAMES = {
        "us-east-1":  "US East (N. Virginia)",
        "eu-north-1": "EU North (Stockholm)",
        "ap-south-1": "Asia Pacific (Mumbai)",
    }
    region_name = NAMES.get(region_id, region_id)

    # Track availability for demo purposes
    _state = {"available": True}

    app = FastAPI(
        title=f"Eco-Router Region: {region_id}",
        description=f"Simulated region server for {region_name}. NOT real cloud infrastructure.",
    )

    @app.get("/health")
    async def health():
        """Health check — used by Eco-Router to determine routing eligibility."""
        if not _state["available"]:
            return JSONResponse(
                status_code=503,
                content={
                    "region": region_id,
                    "name": region_name,
                    "status": "unavailable",
                    "simulated": True,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
        return {
            "region": region_id,
            "name": region_name,
            "status": "healthy",
            "simulated": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @app.post("/admin/unavailable")
    async def mark_unavailable():
        """Mark this region as unavailable (for failover demos)."""
        _state["available"] = False
        return {"region": region_id, "status": "unavailable", "simulated": True}

    @app.post("/admin/available")
    async def mark_available():
        """Restore region to available (for failover demos)."""
        _state["available"] = True
        return {"region": region_id, "status": "available", "simulated": True}

    @app.api_route(
        "/{path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    )
    async def handle_workload(path: str, request: Request):
        """
        Accept any workload forwarded by Eco-Router.
        Returns a response identifying this simulated region.
        """
        if not _state["available"]:
            return JSONResponse(
                status_code=503,
                content={
                    "region": region_id,
                    "status": "unavailable",
                    "simulated": True,
                },
            )

        body = None
        if request.method in ("POST", "PUT", "PATCH"):
            try:
                body = await request.json()
            except Exception:
                body = (await request.body()).decode("utf-8", errors="replace")

        return {
            "region": region_id,
            "region_name": region_name,
            "status": "success",
            "message": f"Workload processed by simulated {region_name} region",
            "simulated": True,
            "path": f"/{path}",
            "method": request.method,
            "received_body": body,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "eco_router_note": (
                "This response was served by a SIMULATED region. "
                "Eco-Router selected this region based on its current carbon intensity."
            ),
        }

    return app


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Eco-Router Simulated Region Server")
    parser.add_argument(
        "--region",
        default=os.getenv("REGION_ID", "us-east-1"),
        help="Region ID (e.g. eu-north-1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("REGION_PORT", "9001")),
        help="Port to listen on",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("REGION_HOST", "127.0.0.1"),
        help="Host to bind to",
    )
    args = parser.parse_args()

    print(f"[ECO-ROUTER] Starting simulated region: {args.region} on {args.host}:{args.port}")
    print("   [SIMULATED] NOT real cloud infrastructure")

    region_app = create_region_app(args.region)
    uvicorn.run(region_app, host=args.host, port=args.port, log_level="warning")
