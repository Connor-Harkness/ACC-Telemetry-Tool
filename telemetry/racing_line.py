"""Racing line visualization using matplotlib.

Draws a top-down 2-D track map from world-position data and colours the
racing line by speed.  Multiple laps can be overlaid on the same axes.
"""

from typing import List, Optional

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes
from matplotlib.collections import LineCollection
from matplotlib.figure import Figure

from telemetry.models import LapData


class RacingLineVisualizer:
    """Visualize the racing line for one or more laps on a top-down track map.

    Args:
        figsize: Width and height of the figure in inches (default: ``(10, 8)``).
        title: Optional figure title.
    """

    def __init__(
        self,
        figsize: tuple = (10, 8),
        title: str = "Racing Line",
    ) -> None:
        self._figsize = figsize
        self._title = title
        self._fig: Optional[Figure] = None
        self._ax: Optional[Axes] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def plot_lap(
        self,
        lap: LapData,
        label: Optional[str] = None,
        colormap: str = "plasma",
    ) -> None:
        """Overlay the racing line for *lap* on the track map.

        The line is segmented and colour-mapped according to speed so that
        fast sections appear in a different colour from slow corners.

        Args:
            lap: The :class:`~telemetry.models.LapData` to visualize.
            label: Legend label for this lap.  Defaults to
                ``"<track> – <lap_time_str>"``.
            colormap: Matplotlib colormap name used to encode speed
                (default: ``"plasma"``).
        """
        self._ensure_axes()

        samples = lap.samples
        if len(samples) < 2:
            return

        x = np.array([s.pos_x for s in samples])
        z = np.array([s.pos_z for s in samples])
        speeds = np.array([s.speed for s in samples])

        # Build a collection of line segments coloured by speed
        points = np.column_stack([x, z]).reshape(-1, 1, 2)
        segments = np.concatenate([points[:-1], points[1:]], axis=1)
        speed_norm = plt.Normalize(speeds.min(), speeds.max())
        lc = LineCollection(segments, cmap=colormap, norm=speed_norm, linewidth=2)
        lc.set_array(speeds[:-1])

        if label is None:
            lap_time_str = _ms_to_time_str(lap.lap_time)
            label = f"{lap.track} – {lap_time_str}"
        lc.set_label(label)

        self._ax.add_collection(lc)

        # Adjust axis limits to fit the new data
        self._ax.autoscale_view()

    def plot_laps(
        self,
        laps: List[LapData],
        colormap: str = "plasma",
    ) -> None:
        """Overlay multiple laps on the same track map.

        Args:
            laps: List of :class:`~telemetry.models.LapData` objects.
            colormap: Matplotlib colormap name (default: ``"plasma"``).
        """
        for lap in laps:
            self.plot_lap(lap, colormap=colormap)

    def add_colorbar(self, label: str = "Speed (km/h)") -> None:
        """Add a colorbar to the current figure.

        Args:
            label: Colorbar axis label (default: ``"Speed (km/h)"``).
        """
        self._ensure_axes()
        mappable = None
        for artist in self._ax.get_children():
            if isinstance(artist, LineCollection):
                mappable = artist
                break
        if mappable is not None:
            self._fig.colorbar(mappable, ax=self._ax, label=label)

    def show(self) -> None:
        """Display the figure in an interactive window."""
        self._ensure_axes()
        self._ax.legend(loc="upper right", fontsize=8)
        plt.tight_layout()
        plt.show()

    def save(self, path: str, dpi: int = 150) -> None:
        """Save the figure to *path*.

        Args:
            path: Output file path (extension determines format, e.g. ``.png``).
            dpi: Resolution in dots per inch (default: 150).
        """
        self._ensure_axes()
        self._ax.legend(loc="upper right", fontsize=8)
        plt.tight_layout()
        self._fig.savefig(path, dpi=dpi)

    def clear(self) -> None:
        """Remove all plotted lines and reset the axes."""
        if self._ax is not None:
            self._ax.cla()
            self._setup_axes()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_axes(self) -> None:
        if self._fig is None or self._ax is None:
            self._fig, self._ax = plt.subplots(figsize=self._figsize)
            self._setup_axes()

    def _setup_axes(self) -> None:
        self._ax.set_title(self._title)
        self._ax.set_xlabel("X position (m)")
        self._ax.set_ylabel("Z position (m)")
        self._ax.set_aspect("equal")
        self._ax.grid(True, linestyle="--", alpha=0.4)


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _ms_to_time_str(ms: int) -> str:
    """Convert milliseconds to a ``M:SS.mmm`` string.

    Args:
        ms: Time in milliseconds.

    Returns:
        Formatted string, e.g. ``"1:32.456"``.
    """
    if ms <= 0:
        return "in-progress"
    total_seconds, millis = divmod(ms, 1000)
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes}:{seconds:02d}.{millis:03d}"
