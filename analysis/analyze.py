import os
import sys
import glob
import argparse
from datetime import datetime
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker


def find_latest_log(logs_dir):
    """Locate the most recent CSV log file in the logs directory."""
    csv_files = glob.glob(os.path.join(logs_dir, "*.csv"))
    if not csv_files:
        return None
    return max(csv_files, key=os.path.getmtime)


def print_summary_table(df, log_filename):
    """Print a clean statistical summary of the telemetry session."""
    total_samples = len(df)
    duration_sec = df["elapsed_sec"].max() - df["elapsed_sec"].min() if total_samples > 1 else 0.0
    
    ssid = df["ssid"].iloc[0] if "ssid" in df.columns and not df["ssid"].empty else "Unknown"
    unique_bssids = df["connected_bssid"].dropna().unique() if "connected_bssid" in df.columns else []
    
    # RSSI stats
    rssi_valid = df["rssi_dbm"].dropna()
    min_rssi = rssi_valid.min() if not rssi_valid.empty else "N/A"
    avg_rssi = f"{rssi_valid.mean():.1f}" if not rssi_valid.empty else "N/A"
    max_rssi = rssi_valid.max() if not rssi_valid.empty else "N/A"

    # Ping stats
    ping_valid = df["ping_rtt_ms"].dropna()
    avg_ping = f"{ping_valid.mean():.1f}" if not ping_valid.empty else "N/A"
    med_ping = f"{ping_valid.median():.1f}" if not ping_valid.empty else "N/A"
    max_ping = f"{ping_valid.max():.1f}" if not ping_valid.empty else "N/A"

    # Packet drops
    drop_count = (df["ping_status"] == "DROP").sum() if "ping_status" in df.columns else 0
    drop_pct = (drop_count / total_samples * 100.0) if total_samples > 0 else 0.0

    # Roaming events
    roams = df[df["event_type"] == "ROAM"]
    roam_count = len(roams)

    print("=" * 65)
    print(f" WI-FI ROAMING SESSION SUMMARY: {os.path.basename(log_filename)}")
    print("=" * 65)
    print(f" Target SSID         : {ssid}")
    print(f" Unique APs (BSSIDs) : {len(unique_bssids)} ({', '.join([b[-8:].upper() for b in unique_bssids])})")
    print(f" Total Duration      : {duration_sec:.1f} s ({duration_sec / 60:.1f} min)")
    print(f" Total Samples       : {total_samples}")
    print("-" * 65)
    print(f" Signal Strength     : Min: {min_rssi} dBm | Mean: {avg_rssi} dBm | Max: {max_rssi} dBm")
    print(f" Gateway Ping RTT    : Median: {med_ping} ms | Mean: {avg_ping} ms | Max: {max_ping} ms")
    print(f" Packet Drops        : {drop_count} ({drop_pct:.1f}% loss rate)")
    print(f" Roam Handover Count : {roam_count}")
    print("-" * 65)

    if roam_count > 0:
        print(" ROAMING TRANSITION DETAILS:")
        for idx, (_, r) in enumerate(roams.iterrows(), 1):
            t_str = r.get("timestamp_iso", "")[11:19]
            from_b = str(r.get("from_bssid", ""))[-8:].upper()
            to_b = str(r.get("connected_bssid", ""))[-8:].upper()
            from_ch = r.get("from_channel", "")
            to_ch = r.get("channel", "")
            lat = r.get("roam_latency_ms", "N/A")
            print(f"  #{idx} [{t_str} at {r['elapsed_sec']:.1f}s] {from_b} (Ch {from_ch}) -> {to_b} (Ch {to_ch}) | Latency: {lat} ms")
    else:
        print(" No roaming transitions occurred during this session.")
    print("=" * 65)


def render_roam_charts(df, log_filename, output_path=None, show_gui=True):
    """Render and save a high-resolution multi-panel telemetry analysis chart."""
    plt.style.use("seaborn-v0_8-darkgrid" if "seaborn-v0_8-darkgrid" in plt.style.available else "default")
    
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(13, 9), sharex=True, gridspec_kw={"height_ratios": [2.2, 1.4, 1.0]})
    fig.patch.set_facecolor("#0b0f19")

    for ax in (ax1, ax2, ax3):
        ax.set_facecolor("#111827")
        ax.tick_params(colors="#94a3b8", labelsize=10)
        ax.grid(color="#334155", linestyle="--", linewidth=0.6, alpha=0.6)
        for spine in ax.spines.values():
            spine.set_color("#334155")

    # 1. Top Panel: Signal Strength (RSSI dBm)
    ax1.set_ylabel("RSSI (dBm)", color="#f8fafc", fontsize=11, fontweight="bold")
    ax1.set_title(f"Wi-Fi Roaming Telemetry Analysis — [{os.path.basename(log_filename)}]", color="#f8fafc", fontsize=14, fontweight="bold", pad=12)

    # Shaded quality zones
    ax1.axhspan(-60, -30, color="#10b981", alpha=0.08, label="Good Signal (>= -65 dBm)")
    ax1.axhspan(-75, -65, color="#f59e0b", alpha=0.08, label="Fair Signal (-65 to -75 dBm)")
    ax1.axhspan(-95, -75, color="#f43f5e", alpha=0.08, label="Poor Signal (< -75 dBm)")
    ax1.axhline(-72, color="#f59e0b", linestyle=":", linewidth=1.2, label="Roam Target (-72 dBm)")

    # Color code signal points by BSSID
    unique_bssids = df["connected_bssid"].dropna().unique()
    palette = ["#38bdf8", "#a855f7", "#ec4899", "#10b981", "#f97316", "#eab308"]
    bssid_color_map = {b: palette[i % len(palette)] for i, b in enumerate(unique_bssids)}

    # Plot continuous signal line
    ax1.plot(df["elapsed_sec"], df["rssi_dbm"], color="#38bdf8", linewidth=1.8, alpha=0.85, zorder=2)

    # Scatter points colored by active BSSID
    for bssid in unique_bssids:
        sub = df[df["connected_bssid"] == bssid]
        label_text = f"AP {bssid[-8:].upper()}"
        ax1.scatter(sub["elapsed_sec"], sub["rssi_dbm"], color=bssid_color_map[bssid], s=25, alpha=0.9, label=label_text, zorder=3)

    # Highlight Roam Handover Events
    roams = df[df["event_type"] == "ROAM"]
    for _, r in roams.iterrows():
        rx = r["elapsed_sec"]
        ry = r["rssi_dbm"]
        ax1.axvline(rx, color="#f43f5e", linestyle="--", linewidth=1.5, alpha=0.85, zorder=4)
        ax1.scatter(rx, ry, color="#f43f5e", marker="D", s=90, edgecolors="#ffffff", linewidth=1.5, zorder=5)
        lat_text = f"Roam ({r['roam_latency_ms']}ms)" if pd.notna(r.get("roam_latency_ms")) else "Roam"
        ax1.annotate(lat_text, (rx, ry), textcoords="offset points", xytext=(8, 10),
                     color="#f43f5e", fontsize=9, fontweight="bold",
                     bbox=dict(boxstyle="round,pad=0.2", fc="#1e293b", ec="#f43f5e", alpha=0.85))

    ax1.set_ylim(-95, -35)
    ax1.legend(loc="lower right", facecolor="#172033", edgecolor="#334155", labelcolor="#cbd5e1", fontsize=9)

    # 2. Middle Panel: Gateway Ping Latency & Packet Drops
    ax2.set_ylabel("Gateway Ping (ms)", color="#f8fafc", fontsize=11, fontweight="bold")
    ax2.plot(df["elapsed_sec"], df["ping_rtt_ms"], color="#10b981", linewidth=1.4, alpha=0.9, label="Ping RTT (ms)", zorder=2)
    
    # Mark packet drops
    drops = df[df["ping_status"] == "DROP"]
    if not drops.empty:
        ax2.scatter(drops["elapsed_sec"], [0] * len(drops), color="#f43f5e", marker="x", s=60, linewidth=2, label="Packet Drop (DROP)", zorder=4)

    # Mark average latency line
    valid_pings = df["ping_rtt_ms"].dropna()
    if not valid_pings.empty:
        mean_p = valid_pings.mean()
        ax2.axhline(mean_p, color="#10b981", linestyle=":", alpha=0.6, label=f"Mean Ping ({mean_p:.1f} ms)")

    # Roam vertical markers in ping graph
    for rx in roams["elapsed_sec"]:
        ax2.axvline(rx, color="#f43f5e", linestyle="--", linewidth=1.2, alpha=0.5, zorder=1)

    ax2.legend(loc="upper right", facecolor="#172033", edgecolor="#334155", labelcolor="#cbd5e1", fontsize=9)

    # 3. Bottom Panel: Wi-Fi Channel & Band
    ax3.set_ylabel("Channel", color="#f8fafc", fontsize=11, fontweight="bold")
    ax3.set_xlabel("Elapsed Time (seconds)", color="#f8fafc", fontsize=11, fontweight="bold")
    
    # Plot channel step
    ax3.step(df["elapsed_sec"], df["channel"], color="#a855f7", where="post", linewidth=2.0, label="Wi-Fi Channel")
    for bssid in unique_bssids:
        sub = df[df["connected_bssid"] == bssid]
        ax3.scatter(sub["elapsed_sec"], sub["channel"], color=bssid_color_map[bssid], s=20, alpha=0.8, zorder=3)

    for rx in roams["elapsed_sec"]:
        ax3.axvline(rx, color="#f43f5e", linestyle="--", linewidth=1.2, alpha=0.5, zorder=1)

    ax3.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax3.legend(loc="upper right", facecolor="#172033", edgecolor="#334155", labelcolor="#cbd5e1", fontsize=9)

    plt.tight_layout()

    # Save report
    if output_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        plt.savefig(output_path, dpi=200, facecolor=fig.get_facecolor(), bbox_inches="tight")
        print(f"\n[+] High-resolution analysis plot saved to:\n    {os.path.abspath(output_path)}")

    if show_gui:
        try:
            plt.show()
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description="Wi-Fi Roaming Sentinel — Telemetry Log Analysis & Rendering")
    parser.add_argument("log_file", nargs="?", default=None, help="Path to CSV session log file (defaults to most recent log in ../logs/)")
    parser.add_argument("--no-gui", action="store_true", help="Do not open interactive plot window (render to image only)")
    parser.add_argument("--output", "-o", default=None, help="Custom output image file path")
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    logs_dir = os.path.join(project_root, "logs")

    log_path = args.log_file
    if not log_path:
        log_path = find_latest_log(logs_dir)
        if not log_path:
            print(f"[-] No CSV log files found in: {logs_dir}")
            print("    Please run the application and record a session first.")
            sys.exit(1)

    if not os.path.isabs(log_path):
        log_path = os.path.abspath(log_path)

    if not os.path.exists(log_path):
        print(f"[-] Log file not found: {log_path}")
        sys.exit(1)

    # Load data
    try:
        df = pd.read_csv(log_path)
    except Exception as e:
        print(f"[-] Failed to read CSV log: {e}")
        sys.exit(1)

    if df.empty:
        print(f"[-] Log file {log_path} is empty.")
        sys.exit(1)

    # Convert numeric fields
    for col in ["elapsed_sec", "rssi_dbm", "ping_rtt_ms", "channel", "link_quality", "roam_latency_ms"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Generate output image path
    base_name = os.path.splitext(os.path.basename(log_path))[0]
    reports_dir = os.path.join(script_dir, "reports")
    out_img = args.output if args.output else os.path.join(reports_dir, f"analysis_{base_name}.png")

    # 1. Print summary
    print_summary_table(df, log_path)

    # 2. Render charts
    render_roam_charts(df, log_path, output_path=out_img, show_gui=not args.no_gui)


if __name__ == "__main__":
    main()

