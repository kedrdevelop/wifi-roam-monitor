import ctypes
from ctypes import wintypes
import time
import threading
import subprocess
import socket
import re

wlan = ctypes.windll.wlanapi

# Windows Native WiFi API Structs
class GUID(ctypes.Structure):
    _fields_ = [
        ('Data1', wintypes.DWORD),
        ('Data2', wintypes.WORD),
        ('Data3', wintypes.WORD),
        ('Data4', ctypes.c_byte * 8)
    ]

class WLAN_INTERFACE_INFO(ctypes.Structure):
    _fields_ = [
        ('InterfaceGuid', GUID),
        ('strInterfaceDescription', wintypes.WCHAR * 256),
        ('isState', wintypes.DWORD)
    ]

class WLAN_INTERFACE_INFO_LIST(ctypes.Structure):
    _fields_ = [
        ('dwNumberOfItems', wintypes.DWORD),
        ('dwIndex', wintypes.DWORD),
        ('InterfaceInfo', WLAN_INTERFACE_INFO * 1)
    ]

class DOT11_SSID(ctypes.Structure):
    _fields_ = [
        ('uSSIDLength', wintypes.DWORD),
        ('ucSSID', ctypes.c_char * 32)
    ]

class WLAN_ASSOCIATION_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ('dot11Ssid', DOT11_SSID),
        ('dot11BssType', wintypes.DWORD),
        ('dot11Bssid', ctypes.c_ubyte * 6),
        ('dot11PhyType', wintypes.DWORD),
        ('uDot11PhyIndex', wintypes.ULONG),
        ('wlanSignalQuality', wintypes.ULONG),
        ('ulRxRate', wintypes.ULONG),
        ('ulTxRate', wintypes.ULONG)
    ]

class WLAN_CONNECTION_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ('isState', wintypes.DWORD),
        ('wlanConnectionMode', wintypes.DWORD),
        ('strProfileName', wintypes.WCHAR * 256),
        ('wlanAssociationAttributes', WLAN_ASSOCIATION_ATTRIBUTES),
        ('wlanSecurityAttributes', ctypes.c_byte * 64)
    ]

class WLAN_BSS_ENTRY(ctypes.Structure):
    _fields_ = [
        ('dot11Ssid', DOT11_SSID),
        ('uPhyId', wintypes.ULONG),
        ('dot11Bssid', ctypes.c_ubyte * 6),
        ('dot11BssType', wintypes.DWORD),
        ('dot11BssPhyType', wintypes.DWORD),
        ('lRssi', ctypes.c_long),
        ('uLinkQuality', wintypes.ULONG),
        ('bInRegDomain', wintypes.BOOLEAN),
        ('usBeaconPeriod', wintypes.USHORT),
        ('ullTimestamp', ctypes.c_ulonglong),
        ('ullHostTimestamp', ctypes.c_ulonglong),
        ('usCapabilityInformation', wintypes.USHORT),
        ('ulChCenterFrequency', wintypes.ULONG),
        ('wlanRateSet', ctypes.c_byte * 256),
        ('ulIeOffset', wintypes.ULONG),
        ('ulIeSize', wintypes.ULONG)
    ]

class WLAN_BSS_LIST(ctypes.Structure):
    _fields_ = [
        ('dwTotalSize', wintypes.DWORD),
        ('dwNumberOfItems', wintypes.DWORD),
        ('wlanBssEntries', WLAN_BSS_ENTRY * 1)
    ]

def freq_to_channel(freq_khz):
    """Convert center frequency in kHz to Wi-Fi channel and band label."""
    freq_mhz = freq_khz / 1000.0
    if 2412 <= freq_mhz <= 2472:
        ch = int((freq_mhz - 2407) / 5)
        return ch, "2.4 GHz"
    elif freq_mhz == 2484:
        return 14, "2.4 GHz"
    elif 5180 <= freq_mhz <= 5885:
        ch = int((freq_mhz - 5000) / 5)
        return ch, "5 GHz"
    elif 5925 <= freq_mhz <= 7125:
        ch = int((freq_mhz - 5950) / 5)
        return ch, "6 GHz"
    return 0, "Unknown"

def get_default_gateway():
    """Discover IPv4 default gateway address via route command."""
    try:
        output = subprocess.check_output(['route', 'print', '0.0.0.0'], text=True, stderr=subprocess.DEVNULL)
        for line in output.splitlines():
            parts = line.strip().split()
            if len(parts) >= 5 and parts[0] == '0.0.0.0' and parts[1] == '0.0.0.0':
                return parts[2]
    except Exception:
        pass
    return "192.168.1.1"


class WifiMonitor:
    """Manages Native WiFi queries, AP filtering, and roaming detection."""

    def __init__(self, target_ssid=None):
        self.auto_ssid = (target_ssid is None or str(target_ssid).strip() == "" or str(target_ssid).strip().lower() == "auto")
        self.target_ssid = None if self.auto_ssid else str(target_ssid).strip()
        self.handle = wintypes.HANDLE()
        self.guid = None
        self.connected_bssid = ""
        self.connected_ssid = ""
        self.connected_info = {}
        self.visible_aps = []
        self.roam_events = []
        self.gateway = get_default_gateway()
        self.last_ping_ms = None
        self.ping_status = "Unknown"
        self.lock = threading.Lock()
        self.running = False
        
        # Roaming transition tracking state
        self.last_seen_bssid = ""
        self.last_seen_channel = 0
        self.last_seen_rssi = 0
        self.roam_count = 0
        self.last_roam_time = None
        self.last_handover_latency_ms = None
        
        # Ping drop measurement state
        self.drop_start_time = None
        self.recent_pings = []

        self._init_wlan()

    def _init_wlan(self):
        """Open WLAN handle and detect interface GUID."""
        negotiated = wintypes.DWORD()
        ret = wlan.WlanOpenHandle(2, None, ctypes.byref(negotiated), ctypes.byref(self.handle))
        if ret != 0:
            raise RuntimeError(f"WlanOpenHandle failed with error code: {ret}")

        pIfList = ctypes.POINTER(WLAN_INTERFACE_INFO_LIST)()
        ret = wlan.WlanEnumInterfaces(self.handle, None, ctypes.byref(pIfList))
        if ret == 0 and pIfList.contents.dwNumberOfItems > 0:
            raw_guid = pIfList.contents.InterfaceInfo[0].InterfaceGuid
            self.guid = GUID()
            ctypes.memmove(ctypes.byref(self.guid), ctypes.byref(raw_guid), ctypes.sizeof(GUID))
            wlan.WlanFreeMemory(pIfList)
        else:
            if pIfList:
                wlan.WlanFreeMemory(pIfList)
            raise RuntimeError("No Wi-Fi interface found on the system.")

    def close(self):
        """Clean up handles."""
        self.running = False
        if self.handle:
            wlan.WlanCloseHandle(self.handle, None)
            self.handle = None

    def trigger_scan(self):
        """Request the driver to scan for wireless networks."""
        if self.handle and self.guid:
            wlan.WlanScan(self.handle, ctypes.byref(self.guid), None, None, None)

    def query_connected(self):
        """Query currently associated BSSID, link speed, and signal quality."""
        if not self.handle or not self.guid:
            return None

        dataSize = wintypes.DWORD()
        ppData = ctypes.c_void_p()
        opcode = wintypes.DWORD()
        ret = wlan.WlanQueryInterface(
            self.handle,
            ctypes.byref(self.guid),
            7,  # wlan_intf_opcode_current_connection
            None,
            ctypes.byref(dataSize),
            ctypes.byref(ppData),
            ctypes.byref(opcode)
        )

        if ret != 0 or not ppData:
            return {
                "connected": False,
                "ssid": "",
                "bssid": "",
                "quality": 0,
                "rx_rate": 0,
                "tx_rate": 0
            }

        try:
            conn_attr = WLAN_CONNECTION_ATTRIBUTES.from_address(ppData.value)
            assoc = conn_attr.wlanAssociationAttributes
            ssid = assoc.dot11Ssid.ucSSID[:assoc.dot11Ssid.uSSIDLength].decode('utf-8', errors='ignore')
            bssid = ':'.join(f'{b:02x}' for b in assoc.dot11Bssid)
            
            return {
                "connected": True,
                "ssid": ssid,
                "bssid": bssid.lower(),
                "quality": assoc.wlanSignalQuality,
                "rx_rate": assoc.ulRxRate / 1000.0,
                "tx_rate": assoc.ulTxRate / 1000.0
            }
        finally:
            wlan.WlanFreeMemory(ppData)

    def query_visible_aps(self, filter_ssid=None):
        """Extract all visible BSS entries filtered for the active or target SSID."""
        if not self.handle or not self.guid:
            return []

        pBssList = ctypes.POINTER(WLAN_BSS_LIST)()
        ret = wlan.WlanGetNetworkBssList(
            self.handle,
            ctypes.byref(self.guid),
            None,
            3,  # dot11_BSS_type_any
            False,
            None,
            ctypes.byref(pBssList)
        )

        if ret != 0 or not pBssList:
            return []

        effective_ssid = filter_ssid
        if effective_ssid is None:
            if not self.auto_ssid and self.target_ssid:
                effective_ssid = self.target_ssid
            else:
                effective_ssid = self.connected_ssid

        results = []
        try:
            bssList = pBssList.contents
            pEntries = ctypes.cast(bssList.wlanBssEntries, ctypes.c_void_p).value
            entry_size = ctypes.sizeof(WLAN_BSS_ENTRY)

            for i in range(bssList.dwNumberOfItems):
                entry = WLAN_BSS_ENTRY.from_address(pEntries + i * entry_size)
                ssid = entry.dot11Ssid.ucSSID[:entry.dot11Ssid.uSSIDLength].decode('utf-8', errors='ignore')

                if effective_ssid:
                    if ssid.lower() != effective_ssid.lower():
                        continue
                elif not ssid:
                    continue

                bssid = ':'.join(f'{b:02x}' for b in entry.dot11Bssid).lower()
                ch, band = freq_to_channel(entry.ulChCenterFrequency)
                
                results.append({
                    "bssid": bssid,
                    "ssid": ssid,
                    "rssi": entry.lRssi,  # Exact dBm
                    "quality": entry.uLinkQuality,
                    "channel": ch,
                    "band": band,
                    "freq_mhz": entry.ulChCenterFrequency / 1000.0
                })
        finally:
            wlan.WlanFreeMemory(pBssList)

        # Sort by signal strength (highest RSSI first)
        results.sort(key=lambda x: x["rssi"], reverse=True)
        return results

    def _ping_worker(self):
        """Continuously probes the gateway to measure packet latency and detect drops during roam."""
        while self.running:
            t0 = time.perf_counter()
            try:
                res = subprocess.run(
                    ['ping', '-n', '1', '-w', '300', self.gateway],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True
                )
                dt = (time.perf_counter() - t0) * 1000.0

                success = False
                rtt = None
                if res.returncode == 0:
                    for line in res.stdout.splitlines():
                        match = re.search(r'(?:time|Zeit|время)[=<](\d+)\s*ms', line, re.IGNORECASE)
                        if match:
                            rtt = int(match.group(1))
                            success = True
                            break
                    if not success and 'TTL=' in res.stdout.upper():
                        success = True
                        rtt = max(1, int(dt))

                now = time.time()
                with self.lock:
                    if success:
                        self.last_ping_ms = rtt if rtt is not None else int(dt)
                        self.ping_status = "OK"
                        if self.drop_start_time is not None:
                            drop_duration = (now - self.drop_start_time) * 1000.0
                            self.last_handover_latency_ms = round(drop_duration, 1)
                            self.drop_start_time = None
                    else:
                        self.ping_status = "DROP"
                        self.last_ping_ms = None
                        if self.drop_start_time is None:
                            self.drop_start_time = now

                    self.recent_pings.append({
                        "time": now,
                        "success": success,
                        "rtt": self.last_ping_ms
                    })
                    if len(self.recent_pings) > 20:
                        self.recent_pings.pop(0)

            except Exception:
                pass

            time.sleep(0.15)

    def _monitor_worker(self):
        """Polls connected BSSID at 100ms interval and triggers background scans periodically."""
        scan_counter = 0
        while self.running:
            try:
                conn = self.query_connected()
                curr_bssid = conn.get("bssid", "") if conn else ""
                curr_ssid = conn.get("ssid", "") if conn else ""
                is_connected = conn.get("connected", False) if conn else False

                with self.lock:
                    if is_connected and curr_ssid:
                        if curr_ssid != self.connected_ssid:
                            self.connected_ssid = curr_ssid
                            new_gw = get_default_gateway()
                            if new_gw:
                                self.gateway = new_gw
                            if self.last_seen_bssid != "":
                                self.last_seen_bssid = ""
                    elif not is_connected:
                        self.connected_ssid = ""
                        self.connected_bssid = ""
                        self.last_seen_bssid = ""

                aps = self.query_visible_aps()

                scan_counter += 1
                if scan_counter >= 35:
                    scan_counter = 0
                    self.trigger_scan()

                with self.lock:
                    self.connected_info = conn
                    self.connected_bssid = curr_bssid

                    matched_active_ap = None
                    for ap in aps:
                        is_active = (ap["bssid"] == curr_bssid and curr_bssid != "")
                        ap["is_connected"] = is_active
                        if is_active:
                            matched_active_ap = ap

                    self.visible_aps = aps

                    if curr_bssid and curr_bssid != self.last_seen_bssid:
                        now_str = time.strftime("%H:%M:%S")
                        curr_ch = matched_active_ap["channel"] if matched_active_ap else 0
                        curr_rssi = matched_active_ap["rssi"] if matched_active_ap else 0

                        if self.last_seen_bssid != "":
                            latency = self.last_handover_latency_ms
                            if latency is None or latency == 0:
                                latency = self.last_ping_ms if self.last_ping_ms else 25

                            self.roam_count += 1
                            self.last_roam_time = now_str
                            self.last_handover_latency_ms = latency

                            event = {
                                "id": self.roam_count,
                                "time": now_str,
                                "old_bssid": self.last_seen_bssid,
                                "new_bssid": curr_bssid,
                                "old_channel": self.last_seen_channel,
                                "new_channel": curr_ch,
                                "old_rssi": self.last_seen_rssi,
                                "new_rssi": curr_rssi,
                                "latency_ms": latency
                            }
                            self.roam_events.insert(0, event)

                        self.last_seen_bssid = curr_bssid
                        self.last_seen_channel = curr_ch
                        self.last_seen_rssi = curr_rssi

            except Exception:
                pass

            time.sleep(0.1)

    def start(self):
        """Start background polling and ping monitoring threads."""
        self.running = True
        self.t_mon = threading.Thread(target=self._monitor_worker, daemon=True)
        self.t_ping = threading.Thread(target=self._ping_worker, daemon=True)
        self.t_mon.start()
        self.t_ping.start()

    def get_state(self):
        """Thread-safe snapshot of all telemetry for the UI."""
        with self.lock:
            active_ap = None
            for ap in self.visible_aps:
                if ap["bssid"] == self.connected_bssid and self.connected_bssid != "":
                    active_ap = ap
                    break

            effective_ssid = self.target_ssid if not self.auto_ssid else self.connected_ssid

            return {
                "target_ssid": self.target_ssid,
                "auto_ssid": self.auto_ssid,
                "connected_ssid": self.connected_ssid,
                "effective_ssid": effective_ssid,
                "connected_bssid": self.connected_bssid,
                "connected_info": self.connected_info,
                "active_ap": active_ap,
                "visible_aps": self.visible_aps,
                "roam_count": self.roam_count,
                "last_roam_time": self.last_roam_time,
                "last_handover_latency_ms": self.last_handover_latency_ms,
                "roam_events": self.roam_events[:50],
                "gateway": self.gateway,
                "ping_ms": self.last_ping_ms,
                "ping_status": self.ping_status
            }
