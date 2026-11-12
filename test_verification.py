from app import RoamingApi
from wifi_engine import WifiMonitor
import time

def run_checks():
    # Test Auto-Detection Mode (default: tracks any currently connected Wi-Fi network)
    print("--- Testing Auto-Detection Mode ---")
    m = WifiMonitor()
    m.start()
    api = RoamingApi(m)
    time.sleep(1.2)
    st = api.get_state()
    
    print("Auto SSID Mode:", st["auto_ssid"])
    print("Detected Connected SSID:", st["connected_ssid"])
    print("Effective Target SSID:", st["effective_ssid"])
    print("Connected BSSID:", st["connected_bssid"])
    print("Active AP:", st["active_ap"])
    print("Visible APs count:", len(st["visible_aps"]))
    
    for ap in st["visible_aps"]:
        print(f"  AP: {ap['bssid']} | Ch {ap['channel']} ({ap['band']}) | {ap['rssi']} dBm | Connected: {ap['is_connected']}")
        
    print("Gateway:", st["gateway"], "| Ping:", st["ping_ms"], "ms | Status:", st["ping_status"])
    print("Trigger scan:", api.trigger_scan())
    print("Clear events:", api.clear_events())

    # Test Session Recording
    print("\n--- Testing Telemetry Session Recording ---")
    rec_start = api.start_recording()
    print("Start recording response:", rec_start)
    assert rec_start["success"] is True, "Failed to start recording"
    time.sleep(1.2)  # Collect ~3-4 samples
    rec_stop = api.stop_recording()
    print("Stop recording response:", rec_stop)
    assert rec_stop["success"] is True, "Failed to stop recording"
    assert rec_stop["records_count"] > 0, "No records written to CSV"
    print(f"Verified CSV file created at: {rec_stop['file_path']} with {rec_stop['records_count']} records.")
    
    m.close()
    print("ALL API VERIFICATION CHECKS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_checks()
