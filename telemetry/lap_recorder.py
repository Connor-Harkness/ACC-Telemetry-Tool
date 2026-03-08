"""Lap detection and recording.

Monitors a stream of :class:`~telemetry.models.TelemetrySample` objects,
detects lap boundaries and accumulates samples into complete
:class:`~telemetry.models.LapData` records.
"""

from datetime import datetime, timezone
from typing import List, Optional

from telemetry.models import LapData, TelemetrySample


class LapRecorder:
    """Detect lap transitions and buffer telemetry samples per lap.

    Feed samples one at a time via :meth:`process_sample`.  Completed laps
    are added to :attr:`completed_laps` automatically.  The in-progress lap
    buffer can be inspected at any time via :attr:`current_lap`.

    Args:
        track: Track name to embed in recorded :class:`~telemetry.models.LapData`.
        car_model: Car model name to embed in recorded lap data.
    """

    def __init__(self, track: str = "", car_model: str = "") -> None:
        self.track = track
        self.car_model = car_model

        # Completed laps available for saving
        self.completed_laps: List[LapData] = []

        # Buffer for the lap currently being recorded
        self._current_samples: List[TelemetrySample] = []
        self._current_lap_number: Optional[int] = None
        self._recording: bool = False
        # False as soon as any sample in the current lap is invalid
        self._lap_valid: bool = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_recording(self) -> bool:
        """``True`` if the recorder is actively buffering samples."""
        return self._recording

    @property
    def current_lap(self) -> List[TelemetrySample]:
        """Read-only view of the samples collected for the current lap."""
        return list(self._current_samples)

    def start(self) -> None:
        """Begin recording.  Clears any partially buffered lap data."""
        self._recording = True
        self._reset_buffer()

    def stop(self) -> None:
        """Stop recording.  The current partial lap is discarded."""
        self._recording = False
        self._reset_buffer()

    def process_sample(self, sample: TelemetrySample) -> Optional[LapData]:
        """Feed a telemetry sample into the recorder.

        Detects lap completion when the ``lap_number`` reported by ACC
        increments.  On completion the finished lap is packaged into a
        :class:`~telemetry.models.LapData`, appended to
        :attr:`completed_laps`, and returned.

        Args:
            sample: The latest :class:`~telemetry.models.TelemetrySample`.

        Returns:
            A finished :class:`~telemetry.models.LapData` if this sample
            triggered lap completion, otherwise ``None``.
        """
        if not self._recording:
            return None

        if self._current_lap_number is None:
            # First sample – initialise lap tracking
            self._current_lap_number = sample.lap_number

        if sample.lap_number != self._current_lap_number:
            # Lap number changed → the previous lap is complete
            finished = self._finalise_lap(lap_time=sample.lap_time)
            # Start buffering the new lap
            self._reset_buffer()
            self._current_lap_number = sample.lap_number
            self._current_samples.append(sample)
            if not sample.is_valid:
                self._lap_valid = False
            return finished

        self._current_samples.append(sample)
        if not sample.is_valid:
            self._lap_valid = False
        return None

    def save_current_lap(self) -> Optional[LapData]:
        """Package the current (possibly incomplete) lap buffer as a
        :class:`~telemetry.models.LapData` and append it to
        :attr:`completed_laps`.

        Returns:
            The packaged :class:`~telemetry.models.LapData`, or ``None``
            if the buffer is empty.
        """
        if not self._current_samples:
            return None
        lap = self._finalise_lap(lap_time=0)
        self._reset_buffer()
        return lap

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _finalise_lap(self, lap_time: int) -> LapData:
        lap = LapData(
            track=self.track,
            car_model=self.car_model,
            lap_time=lap_time,
            date=datetime.now(timezone.utc).isoformat(),
            is_valid=self._lap_valid,
            samples=list(self._current_samples),
        )
        self.completed_laps.append(lap)
        return lap

    def _reset_buffer(self) -> None:
        self._current_samples = []
        self._current_lap_number = None
        self._lap_valid = True
