"""ACC Telemetry Tool – example script.

Demonstrates the complete workflow:

1. Connect to ACC and record a lap.
2. Save the lap to disk (JSON).
3. Load the saved lap back.
4. Plot the racing line coloured by speed.

Because ACC only runs on Windows you can still run this script on other
platforms: it will generate a synthetic demo lap so you can see the
visualisation without real hardware.
"""

import math
import os
import time
from datetime import datetime, timezone

from telemetry.acc_reader import ACCReader, _ACC_AVAILABLE
from telemetry.lap_recorder import LapRecorder
from telemetry.lap_storage import LapStorage
from telemetry.models import LapData, TelemetrySample
from telemetry.racing_line import RacingLineVisualizer
from telemetry.replay import ReplaySystem


# ---------------------------------------------------------------------------
# Demo helper – generate a fake oval lap when ACC is not available
# ---------------------------------------------------------------------------

def _generate_demo_lap(num_samples: int = 400) -> LapData:
    """Return a synthetic :class:`~telemetry.models.LapData` shaped like an oval.

    The last quarter of the lap is marked invalid to simulate a track-limits
    cut, demonstrating that invalid laps are still fully recorded.

    Args:
        num_samples: Number of samples to generate.

    Returns:
        A :class:`~telemetry.models.LapData` with simulated telemetry.
    """
    samples = []
    base_ts = time.monotonic()
    # Simulate a track-limits cut in the last quarter of the lap
    cut_start = int(num_samples * 0.75)
    for i in range(num_samples):
        angle = 2 * math.pi * i / num_samples
        # Simple oval: stretch X axis
        pos_x = 300.0 * math.cos(angle)
        pos_z = 150.0 * math.sin(angle)
        # Speed varies with curvature – slower in tighter corners
        curvature = abs(math.sin(angle))
        speed = 200.0 - 80.0 * curvature
        # Lap becomes invalid once the simulated cut begins
        is_valid = i < cut_start

        samples.append(
            TelemetrySample(
                timestamp=base_ts + i * 0.05,
                lap_number=1,
                lap_time=int(i * 50),          # 50 ms per sample
                speed=speed,
                throttle=max(0.0, 1.0 - curvature),
                brake=max(0.0, curvature - 0.3),
                steering=math.sin(angle) * 0.3,
                gear=max(1, int(speed / 40)),
                rpm=int(speed * 40 + 2000),
                pos_x=pos_x,
                pos_y=0.0,
                pos_z=pos_z,
                is_valid=is_valid,
            )
        )

    return LapData(
        track="demo_oval",
        car_model="demo_car",
        lap_time=num_samples * 50,
        date=datetime.now(timezone.utc).isoformat(),
        is_valid=False,  # cut occurred → overall lap is invalid
        samples=samples,
    )


# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------

def main() -> None:
    storage = LapStorage(directory="laps")

    # ------------------------------------------------------------------
    # Step 1 – Record a lap (or generate demo data)
    # ------------------------------------------------------------------
    if _ACC_AVAILABLE:
        print("ACC shared memory is available.  Recording one lap…")
        print("(Drive the car across the start/finish line to complete the lap.)")

        recorder = LapRecorder()

        with ACCReader(poll_hz=20) as reader:
            # Populate track/car from first successful read
            for _ in range(10):
                sample = reader.read()
                if sample is not None:
                    try:
                        data = reader._sm.read_shared_memory()
                        if data is not None:
                            recorder.track = data.Static.track
                            recorder.car_model = data.Static.car_model
                    except Exception:
                        pass
                    break

            recorder.start()
            print(f"Track: {recorder.track or '(unknown)'}  "
                  f"Car: {recorder.car_model or '(unknown)'}")
            print("Recording… press Ctrl+C to stop early.")

            try:
                while not recorder.completed_laps:
                    sample = reader.read()
                    if sample is not None:
                        recorder.process_sample(sample)
            except KeyboardInterrupt:
                recorder.save_current_lap()
                print("Recording interrupted – partial lap saved.")

        if not recorder.completed_laps:
            print("No complete lap recorded.")
            return

        lap = recorder.completed_laps[-1]
        print(f"Recorded lap: {len(lap.samples)} samples, "
              f"lap time = {lap.lap_time} ms, "
              f"valid = {lap.is_valid}")
    else:
        print("ACC shared memory not available (non-Windows or ACC not running).")
        print("Generating a synthetic demo lap instead.\n")
        lap = _generate_demo_lap()
        print(f"Generated demo lap: {len(lap.samples)} samples, "
              f"lap time = {lap.lap_time} ms, "
              f"valid = {lap.is_valid}")

    # ------------------------------------------------------------------
    # Step 2 – Save the lap
    # ------------------------------------------------------------------
    save_path = storage.save(lap, filename="example_lap", fmt="json")
    print(f"\nLap saved to: {save_path}")

    # ------------------------------------------------------------------
    # Step 3 – Load the lap back
    # ------------------------------------------------------------------
    loaded_lap = storage.load(save_path)
    print(f"Lap loaded:  {loaded_lap.track} | {loaded_lap.car_model} | "
          f"{len(loaded_lap.samples)} samples | "
          f"valid = {loaded_lap.is_valid}")

    # ------------------------------------------------------------------
    # Step 4 – Quick replay preview (first 5 frames, no real-time sleep)
    # ------------------------------------------------------------------
    print("\nFirst 5 replay frames:")
    replay = ReplaySystem(loaded_lap)
    for _ in range(5):
        frame = replay.next_frame()
        if frame:
            print(
                f"  t={frame.lap_time:6d} ms  "
                f"speed={frame.speed:6.1f} km/h  "
                f"pos=({frame.pos_x:7.1f}, {frame.pos_z:7.1f})"
            )

    # ------------------------------------------------------------------
    # Step 5 – Plot the racing line
    # ------------------------------------------------------------------
    print("\nPlotting racing line…")
    viz = RacingLineVisualizer(title=f"Racing Line – {loaded_lap.track}")
    viz.plot_lap(loaded_lap)
    viz.add_colorbar()

    # Save to file so the plot is visible even in headless environments
    plot_path = os.path.join("laps", "racing_line.png")
    viz.save(plot_path)
    print(f"Racing line saved to: {os.path.abspath(plot_path)}")

    # Show interactively if a display is available
    try:
        viz.show()
    except Exception:
        print("(No display available for interactive plot.)")


if __name__ == "__main__":
    main()
