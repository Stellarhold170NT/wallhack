"""Per-node ring buffer with drop-oldest semantics (D-07).

Thread safety: runs within a single asyncio event loop, so no locks are needed.
Do NOT use threading.Lock — this is asyncio-only code.
"""

from collections import deque
from .frame import CSIFrame


class NodeBuffer:
    """Bounded ring buffer for CSI frames per node.

    When capacity is exceeded, the oldest frame is dropped
    to make room for the newest (D-07: Drop Oldest strategy).
    """

    def __init__(self, node_id: int, capacity: int = 500) -> None:
        self._node_id = node_id
        self._capacity = capacity
        self._deque: deque[CSIFrame] = deque(maxlen=capacity)
        self._drop_count = 0

    @property
    def node_id(self) -> int:
        return self._node_id

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def drop_count(self) -> int:
        return self._drop_count

    def push(self, frame: CSIFrame) -> None:
        """Append a frame. If at capacity, the oldest frame is evicted."""
        if len(self._deque) >= self._capacity:
            self._drop_count += 1
        self._deque.append(frame)

    def get_all(self) -> list[CSIFrame]:
        """Return all buffered frames in insertion order (shallow copy)."""
        return list(self._deque)

    def __len__(self) -> int:
        return len(self._deque)

    def last_sequence(self) -> int | None:
        """Return the sequence number of the most recent frame, or None if empty."""
        if not self._deque:
            return None
        return self._deque[-1].sequence
