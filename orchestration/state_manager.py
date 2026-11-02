"""Resilient checkpoint persistence, idempotency tracking, and audit ledger across pipeline boundaries."""

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List

from models.schemas import CheckpointState
from security.sandbox import validate_safe_path


class StateManager:
    """Manages atomic state persistence, catch-up audit ledger, and idempotency keys to enable resumable workflows."""

    def __init__(self, state_dir: Path, allowed_dirs: List[Path], ledger_file: Optional[Path] = None):
        self.state_dir = validate_safe_path(state_dir, allowed_dirs)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.allowed_dirs = allowed_dirs
        
        if ledger_file:
            self.ledger_file = validate_safe_path(ledger_file, allowed_dirs)
        else:
            default_ledger = self.state_dir.parent / "dispatch_ledger.json"
            try:
                self.ledger_file = validate_safe_path(default_ledger, allowed_dirs)
            except Exception:
                # Fallback to within state_dir if parent is outside allowed_dirs (e.g. in test tempdir)
                self.ledger_file = validate_safe_path(self.state_dir / "dispatch_ledger.json", allowed_dirs)
        
        self.state: Optional[CheckpointState] = None
        self._date_str: Optional[str] = None

    def get_checkpoint_file(self, date_str: str) -> Path:
        filename = f"checkpoint_{date_str}.json"
        return self.state_dir / filename

    def initialize_run(self, trace_id: str, date_str: str, resume: bool = True) -> CheckpointState:
        """Load an existing checkpoint or initialize a fresh run state."""
        self._date_str = date_str
        file_path = self.get_checkpoint_file(date_str)

        if resume and file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                self.state = CheckpointState.model_validate(raw)
                return self.state
            except Exception:
                pass

        # Fresh state
        self.state = CheckpointState(
            trace_id=trace_id,
            current_step="INIT",
            completed_steps=[],
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        self.save()
        return self.state

    def save(self) -> None:
        """Atomically persist current state to disk to prevent corruption on crash."""
        if not self.state or not self._date_str:
            return

        self.state.updated_at = datetime.now(timezone.utc).isoformat()
        target_path = self.get_checkpoint_file(self._date_str)

        data_str = self.state.model_dump_json(indent=2)
        temp_file = tempfile.NamedTemporaryFile(
            mode="w",
            dir=str(self.state_dir),
            delete=False,
            encoding="utf-8",
            prefix="tmp_ckpt_",
        )
        try:
            temp_file.write(data_str)
            temp_file.flush()
            temp_file.close()
            os.replace(temp_file.name, str(target_path))
        except Exception:
            if os.path.exists(temp_file.name):
                os.remove(temp_file.name)
            raise

    def is_step_done(self, step_name: str) -> bool:
        if not self.state:
            return False
        return step_name in self.state.completed_steps

    def mark_step_done(
        self,
        step_name: str,
        brief_data: Optional[Dict[str, Any]] = None,
        generated_reports: Optional[Dict[str, str]] = None,
    ) -> None:
        if not self.state:
            return

        if step_name not in self.state.completed_steps:
            self.state.completed_steps.append(step_name)
        self.state.current_step = step_name

        if brief_data is not None:
            self.state.brief_data = brief_data
        if generated_reports is not None:
            self.state.generated_reports.update(generated_reports)

        self.save()

    def generate_idempotency_key(self, recipient: str, content: str) -> str:
        """Compute a deterministic hash token to ensure side-effects are not duplicated."""
        hasher = hashlib.sha256()
        hasher.update((self._date_str or "").encode("utf-8"))
        hasher.update(recipient.lower().strip().encode("utf-8"))
        hasher.update(content[:500].encode("utf-8"))
        return hasher.hexdigest()

    def is_recipient_dispatched(self, recipient: str) -> bool:
        if not self.state:
            return False
        return recipient in self.state.dispatched_recipients

    def record_recipient_dispatch(self, recipient: str, idempotency_key: str, success: bool) -> None:
        if not self.state:
            return

        if success:
            if recipient not in self.state.dispatched_recipients:
                self.state.dispatched_recipients.append(recipient)
            if recipient in self.state.failed_recipients:
                self.state.failed_recipients.remove(recipient)
            self.state.idempotency_keys[recipient] = idempotency_key
        else:
            if recipient not in self.state.failed_recipients:
                self.state.failed_recipients.append(recipient)

        self.save()

    # =========================================================================
    # Persistent Audit Ledger & Automated Catch-Up Engine
    # =========================================================================

    def load_ledger(self) -> Dict[str, Any]:
        """Atomically load the dispatch audit ledger from disk."""
        if not self.ledger_file.exists():
            return {"dispatches": {}}
        try:
            with open(self.ledger_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "dispatches" in data:
                    return data
                return {"dispatches": {}}
        except Exception:
            return {"dispatches": {}}

    def save_ledger(self, ledger_data: Dict[str, Any]) -> None:
        """Atomically write dispatch audit ledger to disk."""
        ledger_dir = self.ledger_file.parent
        ledger_dir.mkdir(parents=True, exist_ok=True)
        data_str = json.dumps(ledger_data, indent=2)

        temp_file = tempfile.NamedTemporaryFile(
            mode="w",
            dir=str(ledger_dir),
            delete=False,
            encoding="utf-8",
            prefix="tmp_ledger_",
        )
        try:
            temp_file.write(data_str)
            temp_file.flush()
            temp_file.close()
            os.replace(temp_file.name, str(self.ledger_file))
        except Exception:
            if os.path.exists(temp_file.name):
                os.remove(temp_file.name)
            raise

    def record_ledger_entry(
        self,
        date_str: str,
        target_recipients: List[str],
        delivered: List[str],
        failed: List[str],
        report_paths: Dict[str, str],
        idempotency_keys: Dict[str, str],
        trace_id: Optional[str] = None,
    ) -> None:
        """Record or update a daily dispatch entry in the audit ledger."""
        ledger = self.load_ledger()
        dispatches = ledger.setdefault("dispatches", {})

        existing = dispatches.get(date_str, {})
        existing_delivered = set(existing.get("delivered_recipients", []))
        existing_delivered.update(delivered)

        status = "DELIVERED" if set(target_recipients).issubset(existing_delivered) else (
            "PARTIAL" if existing_delivered else "FAILED"
        )

        existing_idempotency = existing.get("idempotency_keys", {})
        existing_idempotency.update(idempotency_keys)

        existing_reports = existing.get("report_paths", {})
        existing_reports.update(report_paths)

        dispatches[date_str] = {
            "date": date_str,
            "status": status,
            "target_recipients": target_recipients,
            "delivered_recipients": sorted(list(existing_delivered)),
            "failed_recipients": sorted(list(set(failed) - existing_delivered)),
            "report_paths": existing_reports,
            "idempotency_keys": existing_idempotency,
            "trace_id": trace_id or existing.get("trace_id", ""),
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

        self.save_ledger(ledger)

    def is_recipient_delivered_for_date(self, date_str: str, recipient: str) -> bool:
        """Check whether a specific recipient has already received the report for date_str."""
        if self._date_str == date_str and self.is_recipient_dispatched(recipient):
            return True

        ledger = self.load_ledger()
        entry = ledger.get("dispatches", {}).get(date_str)
        if entry:
            delivered = entry.get("delivered_recipients", [])
            if recipient in delivered:
                return True

        ckpt_path = self.get_checkpoint_file(date_str)
        if ckpt_path.exists():
            try:
                with open(ckpt_path, "r", encoding="utf-8") as f:
                    ckpt_data = json.load(f)
                if recipient in ckpt_data.get("dispatched_recipients", []):
                    return True
            except Exception:
                pass

        return False

    def is_date_fully_dispatched(self, date_str: str, required_recipients: List[str]) -> bool:
        """Check if all required recipients have received the report for date_str."""
        if not required_recipients:
            return False
        return all(self.is_recipient_delivered_for_date(date_str, r) for r in required_recipients)

    def get_undelivered_recipients_for_date(self, date_str: str, required_recipients: List[str]) -> List[str]:
        """Return the sublist of required recipients who have NOT received the brief for date_str."""
        return [r for r in required_recipients if not self.is_recipient_delivered_for_date(date_str, r)]

    def find_missed_dates(
        self,
        lookback_days: int = 7,
        required_recipients: Optional[List[str]] = None,
        reference_date: Optional[str] = None,
    ) -> List[str]:
        """
        Identify dates in the lookback window that have missed or incomplete report deliveries.
        Returns a chronologically sorted list of date strings (YYYY-MM-DD).
        """
        recipients = required_recipients or []
        if not recipients:
            return []

        if reference_date:
            try:
                ref_dt = datetime.strptime(reference_date, "%Y-%m-%d").date()
            except ValueError:
                ref_dt = datetime.now(timezone.utc).date()
        else:
            ref_dt = datetime.now(timezone.utc).date()

        missed = []
        for offset in range(lookback_days, 0, -1):
            check_date = ref_dt - timedelta(days=offset)
            date_str = check_date.strftime("%Y-%m-%d")

            if not self.is_date_fully_dispatched(date_str, recipients):
                missed.append(date_str)

        return sorted(missed)
