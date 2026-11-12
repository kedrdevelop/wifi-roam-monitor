# Wi-Fi Roaming Sentinel

**Wi-Fi Roaming Sentinel** is a real-time Wi-Fi roaming diagnostic and telemetry monitor for Windows, engineered to analyze seamless handover behavior in multi-AP environments (Mesh and Enterprise 802.11k/v/r wireless networks sharing a single SSID).

The application monitors transitions between Access Points (BSSIDs), measures handover latency with millisecond precision, continuously tests default gateway reachability, and logs network events in a responsive desktop dashboard.

---

## Key Features

- **Automatic Network Detection**: Automatically discovers and monitors whichever Wi-Fi network the computer is currently connected to, adapting dynamically if you switch networks.
- **Active AP Telemetry**: Real-time tracking of current BSSID, RSSI (dBm), operating channel, frequency band (2.4 GHz / 5 GHz / 6 GHz), and link transmission rates (Rx/Tx).
- **Session Telemetry Recording**: One-click Start/Stop logging to standalone CSV files (`logs/roam_session_*.csv`) ready for automated analysis in Python (pandas) and MATLAB (`readtable`).
- **Handover Latency Measurement**: Accurate detection of roaming events and calculation of transitional handover latency between APs.
- **Continuous Gateway Ping Monitor**: Background ICMP telemetry to detect packet drops, link disruptions, or latency spikes during AP transitions.
- **SSID Access Point Scanner**: Live discovery of all visible Access Points broadcasting the active network, along with signal strength indicators and band badges.
- **Roaming Event Log**: Chronological audit trail of handover transitions detailing timestamps, source and target BSSIDs, channel shifts, and latency grades.
- **Audio Feedback**: Synthesized Web Audio alerts for handover events and network drops.
- **Native Windows WLAN API**: Direct integration with `wlanapi.dll` using Python `ctypes` — operates without third-party drivers or promiscuous capture requirements.
- **Modern Desktop Dashboard**: Dark-mode interface powered by `pywebview` with zero browser overhead.

---

## Prerequisites

- **Operating System**: Windows 10 / 11 (64-bit)
- **Python**: 3.10 or higher
- A Wi-Fi adapter supported by native Windows WLAN services

---

## Getting Started

### 1. Installation

Clone the repository and install required Python packages:

```powershell
git clone https://github.com/kedrdevelop/wifi-roam-monitor.git
cd wifi-roam-monitor
pip install -r requirements.txt
```

### 2. Running the Application

Launch in default **Auto Mode** (automatically monitors whichever network you are connected to):
```powershell
python app.py
```

Or lock onto a specific target network SSID:
```powershell
python app.py "YourNetworkSSID"
```

Alternatively, double-click `start.bat` to launch immediately.

---

## Analyzing Recorded Logs

Telemetry logs are saved in the `logs/` directory in structured CSV format.

### Python (pandas & matplotlib)
```python
import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv("logs/roam_session_2026-11-12_12-25-17.csv")

plt.figure(figsize=(10, 5))
plt.plot(df["elapsed_sec"], df["rssi_dbm"], label="RSSI (dBm)", color="#0ea5e9")
roams = df[df["event_type"] == "ROAM"]
plt.scatter(roams["elapsed_sec"], roams["rssi_dbm"], color="#f43f5e", s=80, label="Roam Handover", zorder=5)
plt.xlabel("Elapsed Time (seconds)")
plt.ylabel("Signal Strength (dBm)")
plt.title("Wi-Fi Roaming Signal & Transitions")
plt.grid(True, alpha=0.3)
plt.legend()
plt.show()
```

### MATLAB
```matlab
T = readtable('logs/roam_session_2026-11-12_12-25-17.csv');

figure;
plot(T.elapsed_sec, T.rssi_dbm, 'b-', 'LineWidth', 1.5);
hold on;
roamIdx = strcmp(T.event_type, 'ROAM');
plot(T.elapsed_sec(roamIdx), T.rssi_dbm(roamIdx), 'ro', 'MarkerSize', 8, 'MarkerFaceColor', 'r');
xlabel('Elapsed Time (s)');
ylabel('RSSI (dBm)');
title('Wi-Fi Roaming Profile');
grid on;
legend('RSSI (dBm)', 'Roam Event');
```

---

## Project Structure

```text
├── app.py                 # Application entry point & PyWebView JS API bridge
├── wifi_engine.py         # Native Windows WLAN API engine & telemetry monitor
├── test_verification.py   # Headless validation script for WLAN API functionality
├── start.bat              # One-click Windows launcher batch script
├── requirements.txt       # Python package dependencies
├── LICENSE                # License and usage terms
├── analysis/              # Log analysis & visualization toolkit
│   ├── analyze.py         # Automated statistical analyzer & multi-panel chart renderer
│   ├── run_analysis.bat   # One-click analysis launcher (activates local venv)
│   ├── requirements.txt   # Analysis dependencies (pandas, matplotlib, seaborn)
│   └── README.md          # Analysis guide & usage instructions
├── logs/                  # Recorded CSV telemetry sessions (git-ignored)
├── ui/
│   └── index.html         # Desktop dashboard interface (HTML/CSS/JS)
└── README.md              # Project documentation
```

---

## License

Copyright (c) 2026 Viacheslav Kedrov. All rights reserved.

This source code is made available publicly for portfolio showcase, code review, and personal evaluation purposes only. Commercial use, reproduction, or distribution without prior written permission is strictly prohibited. See [LICENSE](LICENSE) for full details.
