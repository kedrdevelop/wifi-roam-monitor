import os
import sys
import glob
import argparse
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


def compute_packet_loss_analysis(df):
    """Compute packet loss metrics, rolling loss curve, jitter, and contiguous drop bursts."""
    has_exact_counts = (
        "ping_sent" in df.columns
        and "ping_dropped" in df.columns
        and df["ping_sent"].notna().any()
    )
    has_event_col = "event_type" in df.columns
    has_status_col = "ping_status" in df.columns

    is_drop_event = (df["event_type"] == "DROP") if has_event_col else pd.Series(False, index=df.index)
    is_drop_status = (df["ping_status"] == "DROP") if has_status_col else pd.Series(False, index=df.index)
    is_drop_any = is_drop_event | is_drop_status

    if has_exact_counts:
        total_pings = int(df["ping_sent"].dropna().max())
        dropped_pings = int(df["ping_dropped"].dropna().max()) if df["ping_dropped"].notna().any() else 0
        loss_pct = (dropped_pings / total_pings * 100.0) if total_pings > 0 else 0.0
        drop_markers_df = df[is_drop_event] if is_drop_event.any() else df[is_drop_status]
        is_exact = True
    else:
        total_pings = len(df)
        dropped_pings = int(is_drop_any.sum())
        loss_pct = (dropped_pings / total_pings * 100.0) if total_pings > 0 else 0.0
        drop_markers_df = df[is_drop_any]
        is_exact = False

    # Rolling packet loss (%) over a ~20s window (use logged column if available, else compute)
    if "packet_loss_pct" in df.columns and df["packet_loss_pct"].notna().any():
        rolling_loss = pd.to_numeric(df["packet_loss_pct"], errors="coerce").ffill().fillna(0.0).to_numpy()
    else:
        times = df["elapsed_sec"].fillna(0.0).to_numpy()
        flags = is_drop_any.astype(float).to_numpy()
        rolling_loss = np.zeros(len(df), dtype=float)
        window_sec = 20.0
        left = 0
        for right in range(len(df)):
            while times[right] - times[left] > window_sec:
                left += 1
            rolling_loss[right] = flags[left:right + 1].mean() * 100.0

    # Jitter (ms) series (use logged column if available, else estimate from RTT diffs)
    if "jitter_ms" in df.columns and df["jitter_ms"].notna().any():
        jitter_series = pd.to_numeric(df["jitter_ms"], errors="coerce")
    else:
        valid_rtt = df["ping_rtt_ms"].dropna()
        if len(valid_rtt) >= 2:
            diffs = valid_rtt.diff().abs()
            jitter_est = diffs.rolling(window=15, min_periods=1).mean()
            jitter_series = jitter_est.reindex(df.index).ffill()
        else:
            jitter_series = pd.Series(np.nan, index=df.index)

    # Group drop events/samples into contiguous drop bursts
    roam_times = df.loc[df["event_type"] == "ROAM", "elapsed_sec"].dropna().to_numpy() if has_event_col else np.array([])
    bursts = []
    active_burst = None

    for idx, row in df.iterrows():
        t = float(row["elapsed_sec"]) if pd.notna(row["elapsed_sec"]) else 0.0
        row_is_drop = bool(is_drop_any.loc[idx])
        rssi_val = row["rssi_dbm"] if "rssi_dbm" in df.columns and pd.notna(row["rssi_dbm"]) else np.nan
        is_exact_drop_row = bool(is_drop_event.loc[idx]) if has_exact_counts else row_is_drop

        if row_is_drop:
            if active_burst is None:
                active_burst = {
                    "start_sec": t,
                    "end_sec": t,
                    "count": 1 if is_exact_drop_row else 0,
                    "sample_count": 1,
                    "rssi_vals": [rssi_val] if pd.notna(rssi_val) else [],
                }
            elif t - active_burst["end_sec"] <= 2.5:
                active_burst["end_sec"] = t
                if is_exact_drop_row:
                    active_burst["count"] += 1
                active_burst["sample_count"] += 1
                if pd.notna(rssi_val):
                    active_burst["rssi_vals"].append(rssi_val)
            else:
                bursts.append(active_burst)
                active_burst = {
                    "start_sec": t,
                    "end_sec": t,
                    "count": 1 if is_exact_drop_row else 0,
                    "sample_count": 1,
                    "rssi_vals": [rssi_val] if pd.notna(rssi_val) else [],
                }
        else:
            if active_burst is not None:
                active_burst["recovery_sec"] = t
                bursts.append(active_burst)
                active_burst = None

    if active_burst is not None:
        bursts.append(active_burst)

    formatted_bursts = []
    for b in bursts:
        start_s = b["start_sec"]
        raw_end = b["end_sec"]
        rec_s = b.get("recovery_sec")
        dur_s = max(0.8, (rec_s - start_s) if rec_s is not None else (raw_end - start_s + 0.8))
        span_end = max(raw_end, start_s + 0.5)
        near_roam = bool(len(roam_times) > 0 and np.any((roam_times >= start_s - 2.0) & (roam_times <= span_end + 3.0)))
        pkt_count = b["count"] if b["count"] > 0 else b["sample_count"]
        min_rssi = min(b["rssi_vals"]) if b["rssi_vals"] else None
        formatted_bursts.append({
            "start_sec": start_s,
            "end_sec": span_end,
            "duration_sec": dur_s,
            "packets": pkt_count,
            "min_rssi": min_rssi,
            "near_roam": near_roam,
        })

    return {
        "is_exact": is_exact,
        "total_pings": total_pings,
        "dropped_pings": dropped_pings,
        "loss_pct": loss_pct,
        "drop_markers_df": drop_markers_df,
        "rolling_loss": rolling_loss,
        "jitter_series": jitter_series,
        "bursts": formatted_bursts,
    }


def print_summary_table(df, log_filename, loss_info):
    """Print a clean statistical summary of the telemetry session."""
    total_rows = len(df)
    duration_sec = df["elapsed_sec"].max() - df["elapsed_sec"].min() if total_rows > 1 else 0.0

    ssid_series = df["ssid"].dropna() if "ssid" in df.columns else pd.Series(dtype=str)
    ssid = ssid_series.iloc[0] if not ssid_series.empty else "Unknown"
    unique_bssids = [
        b for b in (df["connected_bssid"].dropna().unique() if "connected_bssid" in df.columns else [])
        if str(b).strip() and str(b).strip() != "00:00:00:00:00:00"
    ]

    # RSSI stats
    rssi_valid = df["rssi_dbm"].dropna() if "rssi_dbm" in df.columns else pd.Series(dtype=float)
    min_rssi = f"{rssi_valid.min():.0f}" if not rssi_valid.empty else "N/A"
    avg_rssi = f"{rssi_valid.mean():.1f}" if not rssi_valid.empty else "N/A"
    max_rssi = f"{rssi_valid.max():.0f}" if not rssi_valid.empty else "N/A"

    # Ping & jitter stats
    ping_valid = df["ping_rtt_ms"].dropna() if "ping_rtt_ms" in df.columns else pd.Series(dtype=float)
    avg_ping = f"{ping_valid.mean():.1f}" if not ping_valid.empty else "N/A"
    med_ping = f"{ping_valid.median():.1f}" if not ping_valid.empty else "N/A"
    max_ping = f"{ping_valid.max():.1f}" if not ping_valid.empty else "N/A"

    jitter_valid = loss_info["jitter_series"].dropna()
    avg_jitter = f"{jitter_valid.mean():.1f}" if not jitter_valid.empty else "N/A"
    max_jitter = f"{jitter_valid.max():.1f}" if not jitter_valid.empty else "N/A"

    # Roaming events
    roams = df[df["event_type"] == "ROAM"] if "event_type" in df.columns else df.iloc[0:0]
    roam_count = len(roams)
    bursts = loss_info["bursts"]

    print("=" * 68)
    print(f" WI-FI ROAMING SESSION SUMMARY: {os.path.basename(log_filename)}")
    print("=" * 68)
    print(f" Target SSID         : {ssid}")
    print(f" Unique APs (BSSIDs) : {len(unique_bssids)} ({', '.join([str(b)[-8:].upper() for b in unique_bssids])})")
    print(f" Total Duration      : {duration_sec:.1f} s ({duration_sec / 60:.1f} min)")
    print(f" Telemetry Records   : {total_rows}")
    print("-" * 68)
    print(f" Signal Strength     : Min: {min_rssi} dBm | Mean: {avg_rssi} dBm | Max: {max_rssi} dBm")
    print(f" Gateway Ping RTT    : Median: {med_ping} ms | Mean: {avg_ping} ms | Max: {max_ping} ms")
    print(f" Ping Jitter         : Mean: {avg_jitter} ms | Max: {max_jitter} ms")
    if loss_info["is_exact"]:
        print(
            f" Packet Loss (ICMP)  : {loss_info['dropped_pings']} / {loss_info['total_pings']} packets "
            f"({loss_info['loss_pct']:.2f}% loss) in {len(bursts)} burst(s)"
        )
    else:
        print(
            f" Packet Drops (Est.) : {loss_info['dropped_pings']} / {loss_info['total_pings']} samples "
            f"({loss_info['loss_pct']:.1f}% sample drop rate) in {len(bursts)} burst(s)"
        )
    print(f" Roam Handover Count : {roam_count}")
    print("-" * 68)

    if bursts:
        print(" PACKET DROP BURSTS:")
        for idx, b in enumerate(bursts, 1):
            rssi_txt = f"{b['min_rssi']:.0f} dBm" if b["min_rssi"] is not None else "N/A"
            ctx = "During Roam" if b["near_roam"] else "No Roam (Link Stall)"
            unit = "pkts" if loss_info["is_exact"] else "samples"
            print(
                f"  #{idx} [t={b['start_sec']:.1f}s, ~{b['duration_sec']:.1f}s] "
                f"{b['packets']} {unit} | Min RSSI: {rssi_txt} | {ctx}"
            )
    else:
        print(" No packet drops recorded during this session.")

    print("-" * 68)
    if roam_count > 0:
        print(" ROAMING TRANSITION DETAILS:")
        for idx, (_, r) in enumerate(roams.iterrows(), 1):
            t_str = str(r.get("timestamp_iso", ""))[11:19]
            from_b = str(r.get("from_bssid", ""))[-8:].upper()
            to_b = str(r.get("connected_bssid", ""))[-8:].upper()
            from_ch = r.get("from_channel", "")
            to_ch = r.get("channel", "")
            lat = r.get("roam_latency_ms", "N/A")
            print(f"  #{idx} [{t_str} at {r['elapsed_sec']:.1f}s] {from_b} (Ch {from_ch}) -> {to_b} (Ch {to_ch}) | Latency: {lat} ms")
    else:
        print(" No roaming transitions occurred during this session.")
    print("=" * 68)


def render_roam_charts(df, log_filename, loss_info, output_path=None, show_gui=True):
    """Render and save a high-resolution 4-panel telemetry & packet-loss analysis chart."""
    plt.style.use("seaborn-v0_8-darkgrid" if "seaborn-v0_8-darkgrid" in plt.style.available else "default")

    fig, (ax1, ax2, ax3, ax4) = plt.subplots(
        4,
        1,
        figsize=(13, 11.5),
        sharex=True,
        gridspec_kw={"height_ratios": [1.9, 1.3, 1.15, 0.85]},
    )
    fig.patch.set_facecolor("#0b0f19")

    for ax in (ax1, ax2, ax3, ax4):
        ax.set_facecolor("#111827")
        ax.tick_params(colors="#94a3b8", labelsize=10)
        ax.grid(color="#334155", linestyle="--", linewidth=0.6, alpha=0.6)
        for spine in ax.spines.values():
            spine.set_color("#334155")

    bursts = loss_info["bursts"]
    roams = df[df["event_type"] == "ROAM"] if "event_type" in df.columns else df.iloc[0:0]

    # Shade packet drop intervals across all panels for immediate visual correlation
    for b_idx, b in enumerate(bursts):
        for ax in (ax1, ax2, ax3, ax4):
            lbl = "Drop Interval" if (ax is ax2 and b_idx == 0) else None
            ax.axvspan(b["start_sec"], b["end_sec"], color="#f43f5e", alpha=0.14, zorder=1, label=lbl)

    # 1. Top Panel: Signal Strength (RSSI dBm)
    ax1.set_ylabel("RSSI (dBm)", color="#f8fafc", fontsize=11, fontweight="bold")
    ax1.set_title(
        f"Wi-Fi Roaming & Packet Loss Analysis — [{os.path.basename(log_filename)}]",
        color="#f8fafc",
        fontsize=14,
        fontweight="bold",
        pad=12,
    )

    ax1.axhspan(-60, -30, color="#10b981", alpha=0.08, label="Good Signal (>= -65 dBm)")
    ax1.axhspan(-75, -65, color="#f59e0b", alpha=0.08, label="Fair Signal (-65 to -75 dBm)")
    ax1.axhspan(-95, -75, color="#f43f5e", alpha=0.08, label="Poor Signal (< -75 dBm)")
    ax1.axhline(-72, color="#f59e0b", linestyle=":", linewidth=1.2, label="Roam Target (-72 dBm)")

    unique_bssids = [
        b for b in (df["connected_bssid"].dropna().unique() if "connected_bssid" in df.columns else [])
        if str(b).strip() and str(b).strip() != "00:00:00:00:00:00"
    ]
    palette = ["#38bdf8", "#a855f7", "#ec4899", "#10b981", "#f97316", "#eab308"]
    bssid_color_map = {b: palette[i % len(palette)] for i, b in enumerate(unique_bssids)}

    ax1.plot(df["elapsed_sec"], df["rssi_dbm"], color="#38bdf8", linewidth=1.8, alpha=0.85, zorder=2)

    for bssid in unique_bssids:
        sub = df[df["connected_bssid"] == bssid]
        label_text = f"AP {str(bssid)[-8:].upper()}"
        ax1.scatter(sub["elapsed_sec"], sub["rssi_dbm"], color=bssid_color_map[bssid], s=25, alpha=0.9, label=label_text, zorder=3)

    for _, r in roams.iterrows():
        rx = r["elapsed_sec"]
        ry = r["rssi_dbm"]
        ax1.axvline(rx, color="#f43f5e", linestyle="--", linewidth=1.5, alpha=0.85, zorder=4)
        if pd.notna(ry):
            ax1.scatter(rx, ry, color="#f43f5e", marker="D", s=90, edgecolors="#ffffff", linewidth=1.5, zorder=5)
            lat_text = f"Roam ({r['roam_latency_ms']}ms)" if pd.notna(r.get("roam_latency_ms")) else "Roam"
            y_offset = -18 if ry > -45 else 10
            ax1.annotate(
                lat_text,
                (rx, ry),
                textcoords="offset points",
                xytext=(8, y_offset),
                color="#f43f5e",
                fontsize=9,
                fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.2", fc="#1e293b", ec="#f43f5e", alpha=0.85),
            )

    ax1.set_ylim(-95, -35)
    ax1.legend(loc="lower right", facecolor="#172033", edgecolor="#334155", labelcolor="#cbd5e1", fontsize=9)

    # 2. Second Panel: Gateway Ping Latency & Jitter
    ax2.set_ylabel("Gateway Ping (ms)", color="#f8fafc", fontsize=11, fontweight="bold")
    ax2.plot(df["elapsed_sec"], df["ping_rtt_ms"], color="#10b981", linewidth=1.4, alpha=0.9, label="Ping RTT (ms)", zorder=2)

    jitter_valid = loss_info["jitter_series"].dropna()
    if not jitter_valid.empty:
        ax2.plot(
            df.loc[jitter_valid.index, "elapsed_sec"],
            jitter_valid,
            color="#38bdf8",
            linewidth=1.1,
            linestyle="-.",
            alpha=0.85,
            label="Jitter (ms)",
            zorder=3,
        )

    drop_df = loss_info["drop_markers_df"]
    if not drop_df.empty:
        ax2.scatter(
            drop_df["elapsed_sec"],
            [0] * len(drop_df),
            color="#f43f5e",
            marker="x",
            s=65,
            linewidth=2,
            label=f"Packet Drop ({len(drop_df)})",
            zorder=4,
            clip_on=False,
        )

    valid_pings = df["ping_rtt_ms"].dropna()
    if not valid_pings.empty:
        mean_p = valid_pings.mean()
        ax2.axhline(mean_p, color="#10b981", linestyle=":", alpha=0.6, label=f"Mean Ping ({mean_p:.1f} ms)")

    for rx in roams["elapsed_sec"]:
        ax2.axvline(rx, color="#f43f5e", linestyle="--", linewidth=1.2, alpha=0.5, zorder=1)

    ax2.legend(loc="upper right", facecolor="#172033", edgecolor="#334155", labelcolor="#cbd5e1", fontsize=9)

    # 3. Third Panel: Packet Loss Analysis (%)
    ax3.set_ylabel("Packet Loss (%)", color="#f8fafc", fontsize=11, fontweight="bold")
    rolling_loss = loss_info["rolling_loss"]
    x_vals = df["elapsed_sec"].to_numpy()

    ax3.plot(x_vals, rolling_loss, color="#fb7185", linewidth=1.8, label="Rolling Loss (%, ~20s window)", zorder=3)
    ax3.fill_between(x_vals, 0, rolling_loss, color="#f43f5e", alpha=0.25, zorder=2)

    ax3.axhline(1.0, color="#10b981", linestyle=":", linewidth=1.1, alpha=0.8, label="Good VoIP Limit (1%)")
    ax3.axhline(3.0, color="#f59e0b", linestyle=":", linewidth=1.1, alpha=0.8, label="Poor / Glitches (3%)")

    max_loss = float(np.nanmax(rolling_loss)) if len(rolling_loss) > 0 else 0.0
    y_top = max(5.0, min(105.0, max_loss * 1.25))
    ax3.set_ylim(0, y_top)

    if not drop_df.empty:
        drop_x = drop_df["elapsed_sec"].to_numpy()
        ax3.vlines(
            drop_x,
            0,
            y_top * 0.22,
            colors="#f43f5e",
            linewidth=1.5,
            alpha=0.85,
            label="Lost Packet Event",
            zorder=4,
        )

    for rx in roams["elapsed_sec"]:
        ax3.axvline(rx, color="#f43f5e", linestyle="--", linewidth=1.2, alpha=0.5, zorder=1)

    if loss_info["is_exact"]:
        loss_badge_text = (
            f"Session Loss: {loss_info['loss_pct']:.2f}% "
            f"({loss_info['dropped_pings']}/{loss_info['total_pings']} pkts) | Bursts: {len(bursts)}"
        )
    else:
        loss_badge_text = (
            f"Sample Drop Rate: {loss_info['loss_pct']:.1f}% "
            f"({loss_info['dropped_pings']}/{loss_info['total_pings']} samples) | Bursts: {len(bursts)}"
        )
    badge_color = "#10b981" if loss_info["dropped_pings"] == 0 else ("#f59e0b" if loss_info["loss_pct"] <= 2.0 else "#f43f5e")
    ax3.text(
        0.015,
        0.86,
        loss_badge_text,
        transform=ax3.transAxes,
        color=badge_color,
        fontsize=9.5,
        fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.3", fc="#172033", ec=badge_color, alpha=0.9),
    )

    ax3.legend(loc="upper right", facecolor="#172033", edgecolor="#334155", labelcolor="#cbd5e1", fontsize=9)

    # 4. Bottom Panel: Wi-Fi Channel & Band
    ax4.set_ylabel("Channel", color="#f8fafc", fontsize=11, fontweight="bold")
    ax4.set_xlabel("Elapsed Time (seconds)", color="#f8fafc", fontsize=11, fontweight="bold")

    ch_df = df[df["channel"] > 0] if "channel" in df.columns else df
    ax4.step(ch_df["elapsed_sec"], ch_df["channel"], color="#a855f7", where="post", linewidth=2.0, label="Wi-Fi Channel")
    for bssid in unique_bssids:
        sub = ch_df[ch_df["connected_bssid"] == bssid]
        ax4.scatter(sub["elapsed_sec"], sub["channel"], color=bssid_color_map[bssid], s=20, alpha=0.8, zorder=3)

    for rx in roams["elapsed_sec"]:
        ax4.axvline(rx, color="#f43f5e", linestyle="--", linewidth=1.2, alpha=0.5, zorder=1)

    ax4.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax4.legend(loc="upper right", facecolor="#172033", edgecolor="#334155", labelcolor="#cbd5e1", fontsize=9)

    plt.tight_layout()

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

    try:
        df = pd.read_csv(log_path)
    except Exception as e:
        print(f"[-] Failed to read CSV log: {e}")
        sys.exit(1)

    if df.empty:
        print(f"[-] Log file {log_path} is empty.")
        sys.exit(1)

    numeric_cols = [
        "elapsed_sec",
        "rssi_dbm",
        "ping_rtt_ms",
        "channel",
        "link_quality",
        "roam_latency_ms",
        "jitter_ms",
        "packet_loss_pct",
        "ping_sent",
        "ping_dropped",
        "ping_seq",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.sort_values("elapsed_sec").reset_index(drop=True)

    base_name = os.path.splitext(os.path.basename(log_path))[0]
    reports_dir = os.path.join(script_dir, "reports")
    out_img = args.output if args.output else os.path.join(reports_dir, f"analysis_{base_name}.png")

    loss_info = compute_packet_loss_analysis(df)
    print_summary_table(df, log_path, loss_info)
    render_roam_charts(df, log_path, loss_info, output_path=out_img, show_gui=not args.no_gui)


if __name__ == "__main__":
    main()
