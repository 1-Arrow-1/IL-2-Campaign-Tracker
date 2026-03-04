"""
JobStore: thread-safe in-memory store for background job state.

Jobs represent long-running async operations (career debrief parse, language apply).
Clients poll GET /api/jobs/status/<job_id> at ~1 s intervals.

Usage:
    from campaign_service_record.core.job_store import job_store

    job = job_store.create('CAREER_DEBRIEF_PARSE', extra_key='42')
    job.status = 'running'
    job.message = 'Parsing mission 3/47…'
    job.progress_current = 3
    job.progress_total = 47

    # Later:
    result = job_store.get(job.id)

Job types (constants on this module):
    CAREER_DEBRIEF_PARSE
    LANGUAGE_APPLY
"""

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Optional


# ---------------------------------------------------------------------------
# Job type constants
# ---------------------------------------------------------------------------

CAREER_DEBRIEF_PARSE = 'CAREER_DEBRIEF_PARSE'
LANGUAGE_APPLY       = 'LANGUAGE_APPLY'


# ---------------------------------------------------------------------------
# Job dataclass
# ---------------------------------------------------------------------------

@dataclass
class Job:
    """Represents a single background task and its current state."""

    id: str
    type: str
    extra_key: str = ''          # secondary dedup key (e.g. career_id as str)

    status: str = 'pending'      # pending | running | done | error
    started_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    message: str = ''
    progress_current: int = 0
    progress_total: int = 0      # 0 = indeterminate

    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            'id':               self.id,
            'type':             self.type,
            'status':           self.status,
            'started_at':       self.started_at,
            'updated_at':       self.updated_at,
            'message':          self.message,
            'progress_current': self.progress_current,
            'progress_total':   self.progress_total,
            'error':            self.error,
        }


# ---------------------------------------------------------------------------
# JobStore
# ---------------------------------------------------------------------------

class JobStore:
    """Thread-safe in-memory store for Job objects."""

    def __init__(self):
        self._lock: threading.Lock = threading.Lock()
        self._jobs: Dict[str, Job] = {}
        self._poll_count: int = 0

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def create(self, job_type: str, extra_key: str = '') -> Job:
        """
        Create and store a new Job.

        Args:
            job_type:  One of the module-level type constants.
            extra_key: Optional secondary dedup key (e.g. str(career_id)).

        Returns:
            The new Job object.  Callers mutate it directly; the store holds
            the same object (no copies).
        """
        job_id = uuid.uuid4().hex[:8]
        job = Job(id=job_id, type=job_type, extra_key=extra_key)
        with self._lock:
            self._jobs[job_id] = job
        return job

    def cleanup_done(self, max_age_s: float = 1800.0) -> None:
        """
        Remove finished jobs (status done/error) older than max_age_s seconds.

        Called periodically from the status poll endpoint so memory doesn't
        grow unboundedly in a long-running session.
        """
        cutoff = time.time() - max_age_s
        with self._lock:
            stale = [
                jid for jid, j in self._jobs.items()
                if j.status in ('done', 'error') and j.updated_at < cutoff
            ]
            for jid in stale:
                del self._jobs[jid]

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(self, job_id: str) -> Optional[Job]:
        """Return the Job with the given id, or None."""
        with self._lock:
            return self._jobs.get(job_id)

    def find_running(self, job_type: str, extra_key: str = '') -> Optional[Job]:
        """
        Return the first job of the given type+extra_key that is still
        pending or running, or None.

        Used to prevent duplicate background jobs being started.
        """
        with self._lock:
            for job in self._jobs.values():
                if (job.type == job_type
                        and job.extra_key == extra_key
                        and job.status in ('pending', 'running')):
                    return job
        return None

    def increment_poll(self) -> int:
        """Increment and return the poll counter (used to trigger cleanup)."""
        with self._lock:
            self._poll_count += 1
            return self._poll_count


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

job_store = JobStore()
