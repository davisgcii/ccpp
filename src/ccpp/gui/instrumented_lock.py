"""Instrumented lock for debugging race conditions.

This module provides an RLock wrapper that logs:
- Lock contention (when a thread blocks waiting for another)
- Long lock holds (when a thread holds the lock too long)
- Lock acquisition/release with caller identification

This is critical for debugging race conditions like the one
documented in docs/stream.md where the timer and on_user_type
were racing for the lock.
"""

import logging
import threading
import time
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger(__name__)

# Thresholds for logging
BLOCK_THRESHOLD_MS = 100  # Log if blocked waiting > 100ms
HOLD_THRESHOLD_MS = 1000  # Log if held > 1s


class InstrumentedRLock:
    """An RLock that logs contention and long holds.

    Usage:
        lock = InstrumentedRLock("state")

        # Option 1: Context manager with caller name
        with lock.acquire_ctx("on_user_type"):
            # ... do work ...

        # Option 2: Manual acquire/release
        lock.acquire("timer")
        try:
            # ... do work ...
        finally:
            lock.release("timer")

        # Option 3: Standard context manager (uses thread name as caller)
        with lock:
            # ... do work ...
    """

    def __init__(self, name: str = "lock"):
        """Initialize the instrumented lock.

        Args:
            name: Name for this lock (used in log messages)
        """
        self._lock = threading.RLock()
        self._name = name
        self._holder: Optional[str] = None
        self._holder_thread: Optional[int] = None
        self._acquire_time: Optional[float] = None
        self._acquire_count = 0  # For reentrant locks
        self._meta_lock = threading.Lock()  # Protects metadata

    def acquire(self, caller: Optional[str] = None, blocking: bool = True) -> bool:
        """Acquire the lock with instrumentation.

        Args:
            caller: Name of the caller (for logging)
            blocking: Whether to block waiting for the lock

        Returns:
            True if lock was acquired, False otherwise
        """
        if caller is None:
            caller = threading.current_thread().name

        thread_id = threading.current_thread().ident
        start_time = time.time()

        # Check if we're already the holder (reentrant)
        with self._meta_lock:
            if self._holder_thread == thread_id:
                # Reentrant acquisition
                self._lock.acquire(blocking)
                self._acquire_count += 1
                return True

            # Log if another thread holds the lock
            if self._holder is not None:
                logger.debug(
                    f"[LOCK:{self._name}] {caller} waiting, held_by={self._holder}"
                )

        # Try to acquire
        acquired = self._lock.acquire(blocking)

        if acquired:
            wait_time_ms = (time.time() - start_time) * 1000

            with self._meta_lock:
                self._holder = caller
                self._holder_thread = thread_id
                self._acquire_time = time.time()
                self._acquire_count = 1

            # Log if we had to wait
            if wait_time_ms > BLOCK_THRESHOLD_MS:
                logger.debug(
                    f"[LOCK:{self._name}] {caller} acquired after {wait_time_ms:.0f}ms blocked"
                )

        return acquired

    def release(self, caller: Optional[str] = None) -> None:
        """Release the lock with instrumentation.

        Args:
            caller: Name of the caller (for logging)
        """
        if caller is None:
            caller = threading.current_thread().name

        with self._meta_lock:
            self._acquire_count -= 1

            if self._acquire_count == 0:
                # Final release
                hold_time_ms = 0
                if self._acquire_time is not None:
                    hold_time_ms = (time.time() - self._acquire_time) * 1000

                # Log long holds
                if hold_time_ms > HOLD_THRESHOLD_MS:
                    logger.debug(
                        f"[LOCK:{self._name}] {caller} released after {hold_time_ms:.0f}ms hold"
                    )

                self._holder = None
                self._holder_thread = None
                self._acquire_time = None

        self._lock.release()

    @contextmanager
    def acquire_ctx(self, caller: str):
        """Context manager for lock acquisition with caller name.

        Args:
            caller: Name of the caller (for logging)

        Yields:
            None
        """
        self.acquire(caller)
        try:
            yield
        finally:
            self.release(caller)

    def __enter__(self):
        """Standard context manager entry."""
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Standard context manager exit."""
        self.release()
        return False

    @property
    def holder(self) -> Optional[str]:
        """Get the current lock holder name."""
        with self._meta_lock:
            return self._holder

    @property
    def is_held(self) -> bool:
        """Check if the lock is currently held."""
        with self._meta_lock:
            return self._holder is not None
