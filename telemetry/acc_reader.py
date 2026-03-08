"""ACC shared memory reader.

Wraps the ``pyaccsharedmemory`` library and exposes a clean polling interface
that returns :class:`~telemetry.models.TelemetrySample` objects.
"""

import time
from typing import Optional

try:
    from pyaccsharedmemory import accSharedMemory
    _ACC_AVAILABLE = True
except Exception:  # pragma: no cover – Windows-only shared memory
    _ACC_AVAILABLE = False

from telemetry.models import TelemetrySample


class ACCReader:
    """Poll ACC shared memory at a configurable rate and yield telemetry samples.

    The reader works as a context manager so that the underlying shared memory
    handle is always closed cleanly::

        with ACCReader(poll_hz=20) as reader:
            sample = reader.read()

    Args:
        poll_hz: Desired polling frequency in Hz (default: 20).  The reader
            will sleep between calls to :meth:`read` so that the effective rate
            does not exceed this value.
    """

    def __init__(self, poll_hz: float = 20) -> None:
        self._poll_hz = poll_hz
        self._interval = 1.0 / poll_hz
        self._sm: Optional[object] = None
        self._last_read: float = 0.0

    # ------------------------------------------------------------------
    # Context-manager helpers
    # ------------------------------------------------------------------

    def __enter__(self) -> "ACCReader":
        self.connect()
        return self

    def __exit__(self, *_) -> None:
        self.disconnect()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Open a connection to ACC shared memory."""
        if not _ACC_AVAILABLE:
            return
        self._sm = accSharedMemory()

    def disconnect(self) -> None:
        """Close the shared memory handle."""
        if self._sm is not None:
            try:
                self._sm.close()
            except Exception:
                pass
            self._sm = None

    def read(self) -> Optional[TelemetrySample]:
        """Read the latest telemetry from ACC.

        Respects the configured polling rate by sleeping if called too quickly.
        Returns ``None`` when ACC is not running or shared memory is unavailable.

        Returns:
            A :class:`~telemetry.models.TelemetrySample` on success, or
            ``None`` if ACC is not active.
        """
        # Rate limiting
        now = time.monotonic()
        elapsed = now - self._last_read
        if elapsed < self._interval:
            time.sleep(self._interval - elapsed)
        self._last_read = time.monotonic()

        if self._sm is None:
            return None

        try:
            data = self._sm.read_shared_memory()
        except Exception:
            return None

        if data is None:
            return None

        return self._build_sample(data)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_sample(data) -> TelemetrySample:
        """Convert raw ACC_map data into a :class:`~telemetry.models.TelemetrySample`.

        Args:
            data: An ``ACC_map`` instance returned by ``read_shared_memory()``.

        Returns:
            A populated :class:`~telemetry.models.TelemetrySample`.
        """
        phys = data.Physics
        gfx = data.Graphics

        # Determine the player's car coordinate entry
        pos_x = pos_y = pos_z = 0.0
        try:
            player_id = gfx.player_car_id
            coords = gfx.car_coordinates
            if coords and 0 <= player_id < len(coords):
                vec = coords[player_id]
                pos_x = vec.x
                pos_y = vec.y
                pos_z = vec.z
        except Exception:
            pass

        return TelemetrySample(
            timestamp=time.monotonic(),
            lap_number=gfx.completed_lap,
            lap_time=gfx.current_time,
            speed=phys.speed_kmh,
            throttle=phys.gas,
            brake=phys.brake,
            steering=phys.steer_angle,
            gear=phys.gear,
            rpm=phys.rpm,
            pos_x=pos_x,
            pos_y=pos_y,
            pos_z=pos_z,
        )
