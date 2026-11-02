"""Structured JSON telemetry and lifecycle observability engine."""

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

from models.schemas import TelemetryEvent
from security.logging_filter import SensitiveDataRedactor
from security.sandbox import validate_safe_path


class TelemetryRecorder:
    """Emits structured JSON events across the agent lifecycle."""

    def __init__(self, logs_dir: Path, allowed_dirs: List[Path], trace_id: Optional[str] = None):
        self.logs_dir = validate_safe_path(logs_dir, allowed_dirs)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        now = datetime.now(timezone.utc)
        self.date_str = now.strftime("%Y-%m-%d")
        self.trace_id = trace_id or f"trace_{now.strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"
        self.telemetry_file = self.logs_dir / f"telemetry_{self.date_str}.jsonl"

    def record_step(
        self,
        agent_step: str,
        tool_name: Optional[str] = None,
        latency_ms: float = 0.0,
        token_usage: Optional[Dict[str, int]] = None,
        validation_status: str = "SUCCESS",
        details: Optional[Dict[str, Any]] = None,
    ) -> TelemetryEvent:
        """Create, sanitize, and record a structured telemetry event."""
        # Clean details of any secrets
        safe_details = None
        if details:
            try:
                raw_json = json.dumps(details)
                cleaned_json = SensitiveDataRedactor.redact(raw_json)
                safe_details = json.loads(cleaned_json)
            except Exception:
                safe_details = {"status": "unserializable"}

        event = TelemetryEvent(
            trace_id=self.trace_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            agent_step=agent_step,
            tool_name=tool_name,
            latency_ms=round(latency_ms, 2),
            token_usage=token_usage,
            validation_status=validation_status,
            details=safe_details,
        )

        try:
            line = event.model_dump_json() + "\n"
            with open(self.telemetry_file, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            # Observability must never crash the primary application flow
            pass

        return event

