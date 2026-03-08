"""Data models for ACC telemetry."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class TelemetrySample:
    """A single telemetry sample captured from ACC shared memory.

    Attributes:
        timestamp: Monotonic timestamp in seconds when the sample was captured.
        lap_number: Current lap number reported by ACC.
        lap_time: Current lap time in milliseconds.
        speed: Car speed in km/h.
        throttle: Throttle input in the range [0.0, 1.0].
        brake: Brake input in the range [0.0, 1.0].
        steering: Steering angle in radians (negative = left, positive = right).
        gear: Current gear (0 = reverse, 1 = neutral, 2+ = gears 1, 2, …).
        rpm: Engine RPM.
        pos_x: Car world position on the X axis (metres).
        pos_y: Car world position on the Y axis (metres, vertical).
        pos_z: Car world position on the Z axis (metres).
        is_valid: ``True`` when ACC has not invalidated the lap at this point
            (e.g. no track-limits cut has been recorded).
    """

    timestamp: float
    lap_number: int
    lap_time: int
    speed: float
    throttle: float
    brake: float
    steering: float
    gear: int
    rpm: int
    pos_x: float
    pos_y: float
    pos_z: float
    is_valid: bool = True


@dataclass
class LapData:
    """A complete recorded lap including metadata and all telemetry samples.

    Attributes:
        track: Track name as reported by ACC.
        car_model: Car model name as reported by ACC.
        lap_time: Total lap time in milliseconds (0 if lap is still in progress).
        date: ISO-8601 date/time string recording when the lap was captured.
        is_valid: ``True`` when no sample during the lap was flagged as invalid
            by ACC (i.e. no track-limits violation occurred).  Every lap is
            always recorded; this flag simply indicates its validity.
        samples: Ordered list of :class:`TelemetrySample` objects for this lap.
    """

    track: str
    car_model: str
    lap_time: int
    date: str
    is_valid: bool = True
    samples: List[TelemetrySample] = field(default_factory=list)
