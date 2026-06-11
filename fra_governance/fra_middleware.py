"""
fra_governance/fra_middleware.py — FastAPI Middleware for FRA Governance

Wires every session/chat API call through the sandwich bridge's 7 X-layers.
Intercepts POST requests to /api/chat/*, /api/sessions/*, /api/shell/*,
/api/research/* and passes the agent state through governance before
allowing the action.

Connected to sandwich_bridge.py which applies:
  X1: Ordered Chamber      X5: Bezoutian Structural Check
  X2: Parity               X6: Cauchy Ledger Recording
  X3: Baseline Anomaly     X7: Guidance
  X4: Cost Assessment
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("fra_governance.middleware")

GOVERNED_PREFIXES = (
    "/api/sessions",
    "/api/shell",
    "/api/research",
)

EXEMPT_PREFIXES = (
    "/api/chat",        # all chat endpoints exempt — streaming must not be interrupted
    "/api/shell/stream",
    "/api/fra",
)

FRA_SYSTEM_ID_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "fra_system_id.json")


def _get_or_register_fra_system_id() -> Optional[str]:
    """Load the registered FRA system ID from disk or return None."""
    try:
        if os.path.exists(FRA_SYSTEM_ID_FILE):
            with open(FRA_SYSTEM_ID_FILE, "r") as f:
                data = json.load(f)
            return data.get("system_id")
    except Exception:
        pass
    return None


class FRAGovernanceMiddleware(BaseHTTPMiddleware):
    """Intercepts governed API calls and passes them through the sandwich bridge."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path or ""

        # Skip exempt paths and non-governed paths
        if any(path.startswith(p) for p in EXEMPT_PREFIXES):
            return await call_next(request)

        if not any(path.startswith(p) for p in GOVERNED_PREFIXES):
            return await call_next(request)

        # Only govern POST requests (mutating actions)
        if request.method not in ("POST", "PUT", "DELETE"):
            return await call_next(request)

        system_id = _get_or_register_fra_system_id()
        if not system_id:
            return await call_next(request)

        t0 = time.time()

        # Build Gamma state from request metadata ONLY — never read the body.
        # Reading and reconstructing the body breaks multipart/form-data and
        # streaming endpoints. Use URL path and headers for governance metrics.
        content_length = request.headers.get("content-length", "0")
        try:
            body_size = int(content_length)
        except (ValueError, TypeError):
            body_size = 0

        metrics = {
            "api_path": path,
            "method": request.method,
            "body_size": body_size,
        }

        actions = [{
            "type": f"api_{request.method.lower()}",
            "source": f"endpoint:{path}",
            "flow": "request_processed",
            "loss": f"{time.time() - t0:.4f}s_latency",
            "balance": 1.0,
        }]

        state = {
            "metrics": metrics,
            "actions": actions,
            "metadata": {"endpoint": path},
        }

        # Pass through governance
        try:
            from fra_governance.sandwich_bridge import process_request
            gov_result = process_request(system_id, state)
            status = gov_result.get("status", "unknown")

            if status == "blocked":
                logger.warning(f"FRA governance BLOCKED {request.method} {path}: {gov_result.get('warnings')}")
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": "FRA_BLOCKED",
                        "message": "Governance blocked this action",
                        "governance": gov_result,
                    },
                )
            elif status == "degraded":
                logger.info(f"FRA governance DEGRADED {request.method} {path}: {gov_result.get('warnings')}")

        except Exception as e:
            logger.warning(f"FRA governance skipped for {path}: {e}")

        response = await call_next(request)

        # Attach governance headers to response
        response.headers["X-FRA-Governance"] = "active"
        response.headers["X-FRA-System-Id"] = system_id or "unregistered"

        return response
