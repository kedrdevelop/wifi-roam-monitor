import os
import sys
import webview
from wifi_engine import WifiMonitor

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


def main():
    target_ssid = "MyWifi"
    if len(sys.argv) > 1:
        target_ssid = sys.argv[1]

    monitor = WifiMonitor(target_ssid=target_ssid)
    monitor.start()

    api = RoamingApi(monitor)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    ui_path = os.path.join(script_dir, "ui", "index.html")

    window = webview.create_window(
        title=f"Wi-Fi Roaming Sentinel — [{target_ssid}]",
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
