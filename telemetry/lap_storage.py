"""Lap storage – save and load laps to/from disk.

Supports both **JSON** and **CSV** formats.  JSON preserves full fidelity
(including metadata); CSV provides a flat, spreadsheet-friendly layout.
"""

import csv
import json
import os
from typing import List, Literal

from telemetry.models import LapData, TelemetrySample

# Fields written/read by CSV storage (in column order)
_CSV_FIELDS = [
    "timestamp",
    "lap_number",
    "lap_time",
    "speed",
    "throttle",
    "brake",
    "steering",
    "gear",
    "rpm",
    "pos_x",
    "pos_y",
    "pos_z",
    "is_valid",
]


class LapStorage:
    """Save and load :class:`~telemetry.models.LapData` objects to/from disk.

    Args:
        directory: Directory where lap files are stored.  Created
            automatically if it does not exist.
    """

    def __init__(self, directory: str = "laps") -> None:
        self.directory = directory
        os.makedirs(directory, exist_ok=True)

    # ------------------------------------------------------------------
    # Saving
    # ------------------------------------------------------------------

    def save(
        self,
        lap: LapData,
        filename: str,
        fmt: Literal["json", "csv"] = "json",
    ) -> str:
        """Persist a lap to disk.

        Args:
            lap: The :class:`~telemetry.models.LapData` to save.
            filename: Base filename **without** extension.
            fmt: ``"json"`` (default) or ``"csv"``.

        Returns:
            Absolute path to the written file.
        """
        if fmt == "csv":
            return self._save_csv(lap, filename)
        return self._save_json(lap, filename)

    def _save_json(self, lap: LapData, filename: str) -> str:
        path = os.path.join(self.directory, f"{filename}.json")
        payload = {
            "track": lap.track,
            "car_model": lap.car_model,
            "lap_time": lap.lap_time,
            "date": lap.date,
            "is_valid": lap.is_valid,
            "samples": [vars(s) for s in lap.samples],
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        return os.path.abspath(path)

    def _save_csv(self, lap: LapData, filename: str) -> str:
        path = os.path.join(self.directory, f"{filename}.csv")
        with open(path, "w", newline="", encoding="utf-8") as fh:
            # Metadata header rows
            fh.write(f"# track,{lap.track}\n")
            fh.write(f"# car_model,{lap.car_model}\n")
            fh.write(f"# lap_time,{lap.lap_time}\n")
            fh.write(f"# date,{lap.date}\n")
            fh.write(f"# is_valid,{lap.is_valid}\n")
            writer = csv.DictWriter(fh, fieldnames=_CSV_FIELDS)
            writer.writeheader()
            for s in lap.samples:
                writer.writerow({f: getattr(s, f) for f in _CSV_FIELDS})
        return os.path.abspath(path)

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load(self, path: str) -> LapData:
        """Load a previously saved lap from *path*.

        The format is inferred from the file extension (``.json`` or
        ``.csv``).

        Args:
            path: Path to the lap file.

        Returns:
            The reconstructed :class:`~telemetry.models.LapData`.

        Raises:
            ValueError: If the file extension is not recognised.
            FileNotFoundError: If *path* does not exist.
        """
        if path.endswith(".csv"):
            return self._load_csv(path)
        if path.endswith(".json"):
            return self._load_json(path)
        raise ValueError(f"Unsupported file format: {path!r}")

    def _load_json(self, path: str) -> LapData:
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
        samples = [TelemetrySample(**s) for s in payload.get("samples", [])]
        return LapData(
            track=payload.get("track", ""),
            car_model=payload.get("car_model", ""),
            lap_time=payload.get("lap_time", 0),
            date=payload.get("date", ""),
            is_valid=payload.get("is_valid", True),
            samples=samples,
        )

    def _load_csv(self, path: str) -> LapData:
        meta: dict = {}
        samples: List[TelemetrySample] = []
        with open(path, newline="", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("#"):
                    # Format: "# key,value"
                    content = line[1:].strip()
                    key, value = content.split(",", 1)
                    meta[key.strip()] = value.strip()
                    continue
                # Hand off the remaining lines to csv.DictReader
                remaining = line + fh.read()
                reader = csv.DictReader(remaining.splitlines())
                for row in reader:
                    samples.append(
                        TelemetrySample(
                            timestamp=float(row["timestamp"]),
                            lap_number=int(row["lap_number"]),
                            lap_time=int(row["lap_time"]),
                            speed=float(row["speed"]),
                            throttle=float(row["throttle"]),
                            brake=float(row["brake"]),
                            steering=float(row["steering"]),
                            gear=int(row["gear"]),
                            rpm=int(row["rpm"]),
                            pos_x=float(row["pos_x"]),
                            pos_y=float(row["pos_y"]),
                            pos_z=float(row["pos_z"]),
                            is_valid=row.get("is_valid", "True") == "True",
                        )
                    )
                break
        return LapData(
            track=meta.get("track", ""),
            car_model=meta.get("car_model", ""),
            lap_time=int(meta.get("lap_time", 0)),
            date=meta.get("date", ""),
            is_valid=meta.get("is_valid", "True") == "True",
            samples=samples,
        )

    # ------------------------------------------------------------------
    # Directory listing
    # ------------------------------------------------------------------

    def list_laps(self) -> List[str]:
        """Return a sorted list of saved lap file paths in :attr:`directory`.

        Returns:
            List of absolute file paths for all ``.json`` and ``.csv``
            files in the storage directory.
        """
        entries = []
        for name in sorted(os.listdir(self.directory)):
            if name.endswith((".json", ".csv")):
                entries.append(os.path.abspath(os.path.join(self.directory, name)))
        return entries
