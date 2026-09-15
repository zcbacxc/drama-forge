# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Cancellation token for long-running graph executions."""

from __future__ import annotations

import threading


class CancellationToken:
    """Thread-safe cooperative cancellation flag.

    Workers and the scheduler poll ``is_cancelled``; cancellation is
    cooperative — an in-flight provider call is not aborted mid-socket.
    """

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        """Request cancellation."""
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        """Whether cancellation has been requested."""
        return self._event.is_set()

    def reset(self) -> None:
        """Clear the cancellation flag (tests / reuse)."""
        self._event.clear()
