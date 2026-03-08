"""Replay system for saved laps.

Allows scrubbing through a :class:`~telemetry.models.LapData` frame-by-frame
or at real-time speed, driven by a caller-supplied callback.
"""

import time
from typing import Callable, List, Optional

from telemetry.models import LapData, TelemetrySample


class ReplaySystem:
    """Frame-by-frame playback of a saved :class:`~telemetry.models.LapData`.

    Usage example::

        def on_frame(sample: TelemetrySample) -> None:
            print(sample.speed)

        replay = ReplaySystem(lap)
        replay.play(on_frame)

    Args:
        lap: The :class:`~telemetry.models.LapData` to replay.
    """

    def __init__(self, lap: LapData) -> None:
        self._lap = lap
        self._samples: List[TelemetrySample] = lap.samples
        self._index: int = 0

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def current_index(self) -> int:
        """Index of the next frame to be delivered."""
        return self._index

    @property
    def total_frames(self) -> int:
        """Total number of frames in the loaded lap."""
        return len(self._samples)

    @property
    def is_finished(self) -> bool:
        """``True`` once all frames have been delivered."""
        return self._index >= len(self._samples)

    # ------------------------------------------------------------------
    # Playback control
    # ------------------------------------------------------------------

    def seek(self, index: int) -> None:
        """Jump to a specific frame index (scrubbing).

        Args:
            index: Target frame index.  Clamped to the valid range.
        """
        self._index = max(0, min(index, len(self._samples)))

    def seek_by_time(self, lap_time_ms: int) -> None:
        """Seek to the frame closest to *lap_time_ms* milliseconds.

        Args:
            lap_time_ms: Target lap time in milliseconds.
        """
        if not self._samples:
            return
        closest = min(
            range(len(self._samples)),
            key=lambda i: abs(self._samples[i].lap_time - lap_time_ms),
        )
        self._index = closest

    def next_frame(self) -> Optional[TelemetrySample]:
        """Advance one frame and return the sample, or ``None`` if finished.

        Returns:
            The next :class:`~telemetry.models.TelemetrySample`, or
            ``None`` when the replay has ended.
        """
        if self.is_finished:
            return None
        sample = self._samples[self._index]
        self._index += 1
        return sample

    def play(
        self,
        callback: Callable[[TelemetrySample], None],
        real_time: bool = True,
    ) -> None:
        """Replay all remaining frames, calling *callback* for each one.

        Args:
            callback: Invoked once per frame with the
                :class:`~telemetry.models.TelemetrySample` as its argument.
            real_time: When ``True`` (default) the replay pauses between
                frames to match the original capture timestamps.  Set to
                ``False`` to iterate as fast as possible (useful for
                post-processing).
        """
        prev_ts: Optional[float] = None

        while not self.is_finished:
            sample = self.next_frame()
            if sample is None:
                break

            if real_time and prev_ts is not None:
                gap = sample.timestamp - prev_ts
                if gap > 0:
                    time.sleep(gap)

            callback(sample)
            prev_ts = sample.timestamp

    def reset(self) -> None:
        """Rewind the replay to the first frame."""
        self._index = 0
