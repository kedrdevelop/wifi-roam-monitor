import os
import sys
import webview
from wifi_engine import WifiMonitor

# Redirect stdout/stderr when running as a windowed application without a console
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")


def get_resource_path(relative_path: str) -> str:
    """Get absolute path to bundled resource (works in dev and PyInstaller onefile)."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)


def get_app_dir() -> str:
    """Get persistent directory where executable or script resides (for logs, reports)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


class RoamingApi:
    """Exposed JS bridge API for pywebview."""

    def __init__(self, monitor: WifiMonitor):
        self.monitor = monitor

    def get_state(self):
        """Retrieve live network and roaming state."""
        return self.monitor.get_state()

    def trigger_scan(self):
        """Request immediate Wi-Fi BSS scan."""
        self.monitor.trigger_scan()
        return True

    def clear_events(self):
        """Clear recorded roaming transitions history."""
        with self.monitor.lock:
            self.monitor.roam_events.clear()
            self.monitor.roam_count = 0
            self.monitor.last_handover_latency_ms = None
            self.monitor.last_roam_time = None
        return True

    def start_recording(self):
        """Start recording telemetry session to a CSV file."""
        return self.monitor.start_recording()

    def stop_recording(self):
        """Stop recording telemetry session and save CSV file."""
        return self.monitor.stop_recording()

    def open_logs_folder(self):
        """Open the logs directory in Windows Explorer."""
        logs_dir = os.path.abspath(self.monitor.logger.logs_dir)
        os.makedirs(logs_dir, exist_ok=True)
        try:
            os.startfile(logs_dir)
            return True
        except Exception:
            return False


def main():
    target_ssid = None
    if len(sys.argv) > 1 and sys.argv[1].strip():
        arg = sys.argv[1].strip()
        if arg.lower() not in ("--auto", "-a", "auto"):
            target_ssid = arg

    # Use persistent directory next to the executable for logs
    logs_dir = os.path.join(get_app_dir(), "logs")
    monitor = WifiMonitor(target_ssid=target_ssid, logs_dir=logs_dir)
    monitor.start()

    api = RoamingApi(monitor)

    ui_path = get_resource_path(os.path.join("ui", "index.html"))

    title_suffix = f" — [{target_ssid}]" if target_ssid else " — [Auto]"
    window = webview.create_window(
        title=f"Wi-Fi Roaming Sentinel{title_suffix}",
        url=ui_path,
        js_api=api,
        width=1120,
        height=740,
        min_size=(920, 600),
        background_color="#0b0f19"
    )

    try:
        webview.start(debug=False)
    finally:
        monitor.close()


if __name__ == "__main__":
    main()

