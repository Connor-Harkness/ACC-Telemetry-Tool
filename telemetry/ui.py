"""Simple Tkinter desktop UI for the ACC Telemetry Tool.

Provides buttons to start/stop recording, save/load laps, replay a lap, and
show the racing line plot.  The UI polls ACC in a background thread so the
main event loop is never blocked.

Usage::

    from telemetry.ui import TelemetryApp
    app = TelemetryApp()
    app.run()
"""

import os
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from telemetry.acc_reader import ACCReader
from telemetry.lap_recorder import LapRecorder
from telemetry.lap_storage import LapStorage
from telemetry.models import LapData, TelemetrySample
from telemetry.racing_line import RacingLineVisualizer
from telemetry.replay import ReplaySystem


class TelemetryApp:
    """Main Tkinter application window.

    Args:
        poll_hz: ACC polling rate in Hz (default: 20).
        storage_dir: Directory used to load/save lap files (default: ``"laps"``).
    """

    def __init__(self, poll_hz: float = 20, storage_dir: str = "laps") -> None:
        self._poll_hz = poll_hz
        self._storage = LapStorage(storage_dir)
        self._reader: Optional[ACCReader] = None
        self._recorder: Optional[LapRecorder] = None
        self._loaded_lap: Optional[LapData] = None
        self._polling = False
        self._poll_thread: Optional[threading.Thread] = None

        self._root = tk.Tk()
        self._root.title("ACC Telemetry Tool")
        self._root.resizable(False, False)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        pad = {"padx": 8, "pady": 6}

        # Status bar
        self._status_var = tk.StringVar(value="Disconnected")
        status_bar = ttk.Label(
            self._root,
            textvariable=self._status_var,
            relief="sunken",
            anchor="w",
        )
        status_bar.pack(side="bottom", fill="x")

        # Telemetry live display
        info_frame = ttk.LabelFrame(self._root, text="Live Telemetry")
        info_frame.pack(fill="x", **pad)

        self._telem_vars: dict = {}
        fields = [
            ("Speed (km/h)", "speed"),
            ("Throttle", "throttle"),
            ("Brake", "brake"),
            ("Gear", "gear"),
            ("RPM", "rpm"),
            ("Lap", "lap_number"),
            ("Lap Time (ms)", "lap_time"),
        ]
        for row, (label, key) in enumerate(fields):
            ttk.Label(info_frame, text=label + ":").grid(
                row=row, column=0, sticky="w", padx=4, pady=2
            )
            var = tk.StringVar(value="–")
            ttk.Label(info_frame, textvariable=var, width=14, anchor="e").grid(
                row=row, column=1, sticky="e", padx=4, pady=2
            )
            self._telem_vars[key] = var

        # Control buttons
        btn_frame = ttk.LabelFrame(self._root, text="Controls")
        btn_frame.pack(fill="x", **pad)

        buttons = [
            ("▶  Start Recording", self._on_start_recording),
            ("■  Stop Recording", self._on_stop_recording),
            ("💾  Save Lap", self._on_save_lap),
            ("📂  Load Lap", self._on_load_lap),
            ("⏯  Replay Lap", self._on_replay_lap),
            ("🗺  Show Racing Line", self._on_show_racing_line),
        ]
        for col, (text, cmd) in enumerate(buttons):
            ttk.Button(btn_frame, text=text, command=cmd, width=20).grid(
                row=col // 2, column=col % 2, padx=6, pady=4, sticky="ew"
            )

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def _on_start_recording(self) -> None:
        if self._polling:
            self._set_status("Already recording.")
            return
        self._reader = ACCReader(poll_hz=self._poll_hz)
        self._reader.connect()
        self._recorder = LapRecorder()
        self._recorder.start()
        self._polling = True
        self._poll_thread = threading.Thread(
            target=self._poll_loop, daemon=True
        )
        self._poll_thread.start()
        self._set_status("Recording…")

    def _on_stop_recording(self) -> None:
        self._polling = False
        if self._recorder:
            self._recorder.stop()
        if self._reader:
            self._reader.disconnect()
        self._set_status("Recording stopped.")

    def _on_save_lap(self) -> None:
        if not self._recorder or not self._recorder.completed_laps:
            messagebox.showinfo("Save Lap", "No completed laps to save.")
            return
        lap = self._recorder.completed_laps[-1]
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("CSV files", "*.csv")],
            title="Save Lap",
            initialdir=self._storage.directory,
        )
        if not filename:
            return
        fmt = "csv" if filename.endswith(".csv") else "json"
        base = os.path.splitext(os.path.basename(filename))[0]
        saved = self._storage.save(lap, base, fmt=fmt)
        self._set_status(f"Saved: {saved}")

    def _on_load_lap(self) -> None:
        filename = filedialog.askopenfilename(
            filetypes=[("Lap files", "*.json *.csv"), ("All files", "*.*")],
            title="Load Lap",
            initialdir=self._storage.directory,
        )
        if not filename:
            return
        try:
            self._loaded_lap = self._storage.load(filename)
            info = (
                f"Loaded: {self._loaded_lap.track} | "
                f"{self._loaded_lap.car_model} | "
                f"{len(self._loaded_lap.samples)} samples"
            )
            self._set_status(info)
        except Exception as exc:
            messagebox.showerror("Load Lap", f"Failed to load lap:\n{exc}")

    def _on_replay_lap(self) -> None:
        lap = self._loaded_lap
        if lap is None:
            messagebox.showinfo("Replay Lap", "No lap loaded.  Use 'Load Lap' first.")
            return
        replay = ReplaySystem(lap)

        def _run() -> None:
            def _update(sample: TelemetrySample) -> None:
                self._update_telem_display(sample)

            replay.play(_update, real_time=True)
            self._set_status("Replay finished.")

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        self._set_status("Replaying…")

    def _on_show_racing_line(self) -> None:
        lap = self._loaded_lap
        if lap is None:
            messagebox.showinfo(
                "Racing Line", "No lap loaded.  Use 'Load Lap' first."
            )
            return
        viz = RacingLineVisualizer(title=f"Racing Line – {lap.track}")
        viz.plot_lap(lap)
        viz.add_colorbar()
        viz.show()

    # ------------------------------------------------------------------
    # Background polling loop
    # ------------------------------------------------------------------

    def _poll_loop(self) -> None:
        """Run in a daemon thread; polls ACC and feeds samples to recorder."""
        while self._polling:
            if self._reader is None:
                time.sleep(0.05)
                continue
            sample = self._reader.read()
            if sample is None:
                self._set_status("Waiting for ACC…")
                continue
            # Update metadata from first sample if available
            if (
                self._recorder
                and not self._recorder.track
                and hasattr(self._reader, "_sm")
                and self._reader._sm is not None
            ):
                try:
                    data = self._reader._sm.read_shared_memory()
                    if data is not None:
                        self._recorder.track = data.Static.track
                        self._recorder.car_model = data.Static.car_model
                except Exception:
                    pass

            if self._recorder:
                self._recorder.process_sample(sample)

            self._update_telem_display(sample)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _update_telem_display(self, sample: TelemetrySample) -> None:
        """Thread-safe update of the live telemetry labels."""
        def _update():
            self._telem_vars["speed"].set(f"{sample.speed:.1f}")
            self._telem_vars["throttle"].set(f"{sample.throttle:.2f}")
            self._telem_vars["brake"].set(f"{sample.brake:.2f}")
            self._telem_vars["gear"].set(str(sample.gear))
            self._telem_vars["rpm"].set(str(sample.rpm))
            self._telem_vars["lap_number"].set(str(sample.lap_number))
            self._telem_vars["lap_time"].set(str(sample.lap_time))

        self._root.after(0, _update)

    def _set_status(self, message: str) -> None:
        """Thread-safe status bar update."""
        self._root.after(0, lambda: self._status_var.set(message))

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Start the Tkinter main event loop."""
        self._root.mainloop()
