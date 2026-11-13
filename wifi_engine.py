import os
import csv
from datetime import datetime
import ctypes
from ctypes import wintypes
import time
import threading
import subprocess
import socket
import struct
import re

wlan = ctypes.windll.wlanapi
iphlpapi = ctypes.windll.iphlpapi

# Configure Windows ICMP API signatures for 64-bit handle safety
iphlpapi.IcmpCreateFile.argtypes = []
iphlpapi.IcmpCreateFile.restype = wintypes.HANDLE
iphlpapi.IcmpSendEcho.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    ctypes.c_void_p,
    wintypes.WORD,
    ctypes.c_void_p,
    ctypes.c_void_p,
    wintypes.DWORD,
    wintypes.DWORD,
]
iphlpapi.IcmpSendEcho.restype = wintypes.DWORD
iphlpapi.IcmpCloseHandle.argtypes = [wintypes.HANDLE]
iphlpapi.IcmpCloseHandle.restype = wintypes.BOOL
iphlpapi.GetAdaptersInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.ULONG)]
iphlpapi.GetAdaptersInfo.restype = wintypes.DWORD

INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
IF_TYPE_IEEE80211 = 71
WLAN_INTERFACE_STATE_CONNECTED = 1
_IPV4_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")

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

class IP_ADDR_STRING(ctypes.Structure):
    _fields_ = [
        ('Next', ctypes.c_void_p),
        ('IpAddress', ctypes.c_char * 16),
        ('IpMask', ctypes.c_char * 16),
        ('Context', wintypes.DWORD),
    ]

class IP_ADAPTER_INFO(ctypes.Structure):
    _fields_ = [
        ('Next', ctypes.c_void_p),
        ('ComboIndex', wintypes.DWORD),
        ('AdapterName', ctypes.c_char * 260),
        ('Description', ctypes.c_char * 132),
        ('AddressLength', wintypes.UINT),
        ('Address', ctypes.c_ubyte * 8),
        ('Index', wintypes.DWORD),
        ('Type', wintypes.UINT),
        ('DhcpEnabled', wintypes.UINT),
        ('CurrentIpAddress', ctypes.c_void_p),
        ('IpAddressList', IP_ADDR_STRING),
        ('GatewayList', IP_ADDR_STRING),
        ('DhcpServer', IP_ADDR_STRING),
        ('HaveWins', wintypes.BOOL),
        ('PrimaryWinsServer', IP_ADDR_STRING),
        ('SecondaryWinsServer', IP_ADDR_STRING),
        ('LeaseObtained', ctypes.c_int64),
        ('LeaseExpires', ctypes.c_int64),
    ]

def guid_to_str(guid):
    """Convert a Windows GUID structure to standard uppercase braced string."""
    if not guid:
        return ""
    d4 = [b & 0xFF for b in guid.Data4]
    return (
        f"{{{guid.Data1:08X}-{guid.Data2:04X}-{guid.Data3:04X}-"
        f"{d4[0]:02X}{d4[1]:02X}-{''.join(f'{x:02X}' for x in d4[2:])}}}"
    )

def _is_valid_ipv4(ip_str):
    """Return True if ip_str is a valid non-placeholder IPv4 address."""
    if not ip_str or ip_str in ("0.0.0.0", "127.0.0.1", "255.255.255.255"):
        return False
    if not _IPV4_RE.match(ip_str):
        return False
    try:
        socket.inet_aton(ip_str)
        return True
    except OSError:
        return False

def _first_valid_ip_in_list(addr_struct):
    """Extract the first valid IPv4 string from an IP_ADDR_STRING linked list."""
    raw = addr_struct.IpAddress.decode("ascii", errors="ignore").strip("\x00 ")
    if _is_valid_ipv4(raw):
        return raw
    curr_ptr = addr_struct.Next
    while curr_ptr:
        node = IP_ADDR_STRING.from_address(curr_ptr)
        raw = node.IpAddress.decode("ascii", errors="ignore").strip("\x00 ")
        if _is_valid_ipv4(raw):
            return raw
        curr_ptr = node.Next
    return None

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

def get_default_gateway(interface_guid=None):
    """Discover IPv4 gateway via native iphlpapi GetAdaptersInfo with route print fallback."""
    target_guid_str = guid_to_str(interface_guid).upper() if interface_guid else ""

    # Stage 1: Native Windows iphlpapi GetAdaptersInfo (locale-independent, VPN-resilient)
    try:
        buf_len = wintypes.ULONG(0)
        ret = iphlpapi.GetAdaptersInfo(None, ctypes.byref(buf_len))
        # ERROR_BUFFER_OVERFLOW = 111
        if ret == 111 and buf_len.value > 0:
            buf = (ctypes.c_ubyte * buf_len.value)()
            ret = iphlpapi.GetAdaptersInfo(ctypes.byref(buf), ctypes.byref(buf_len))
            if ret == 0:
                matched_guid_gw = None
                wifi_gw = None
                dhcp_fallback_gw = None
                any_gw = None

                curr_ptr = ctypes.addressof(buf)
                while curr_ptr:
                    info = IP_ADAPTER_INFO.from_address(curr_ptr)
                    adapter_name = info.AdapterName.decode("ascii", errors="ignore").strip("\x00 ").upper()
                    gw_ip = _first_valid_ip_in_list(info.GatewayList)
                    local_ip = _first_valid_ip_in_list(info.IpAddressList)
                    dhcp_ip = _first_valid_ip_in_list(info.DhcpServer)
                    is_target = bool(target_guid_str and adapter_name == target_guid_str)
                    is_wifi = (info.Type == IF_TYPE_IEEE80211)

                    if is_target and gw_ip and not matched_guid_gw:
                        matched_guid_gw = gw_ip
                    if is_wifi and gw_ip and not wifi_gw:
                        wifi_gw = gw_ip
                    if (is_target or is_wifi) and local_ip and dhcp_ip and not dhcp_fallback_gw:
                        dhcp_fallback_gw = dhcp_ip
                    if gw_ip and not any_gw:
                        any_gw = gw_ip

                    curr_ptr = info.Next

                for candidate in (matched_guid_gw, wifi_gw, dhcp_fallback_gw, any_gw):
                    if candidate:
                        return candidate
    except Exception:
        pass

    # Stage 2: Locale-safe route print fallback
    try:
        output = subprocess.check_output(
            ['route', 'print', '0.0.0.0'],
            encoding='ascii',
            errors='ignore',
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        best_gw = None
        best_metric = float('inf')
        for line in output.splitlines():
            parts = line.strip().split()
            if len(parts) >= 4 and parts[0] == '0.0.0.0' and parts[1] == '0.0.0.0':
                # Require at least gateway IP + interface IP (localized "On-link" has only 1 IP token)
                ip_tokens = [tok for tok in parts[2:] if _is_valid_ipv4(tok)]
                if len(ip_tokens) >= 2:
                    gw = ip_tokens[0]
                    try:
                        metric = int(parts[-1])
                    except ValueError:
                        metric = 9999
                    if metric < best_metric:
                        best_metric = metric
                        best_gw = gw
        if best_gw:
            return best_gw
    except Exception:
        pass
    return None

def icmp_ping(ip_str, timeout_ms=800):
    """Send a single ICMP echo request via native iphlpapi with ping.exe fallback."""
    if not _is_valid_ipv4(ip_str):
        return False, None

    # Stage 1: Native Windows ICMP API (no subprocess overhead, locale-independent)
    try:
        handle = iphlpapi.IcmpCreateFile()
        if handle and handle != INVALID_HANDLE_VALUE:
            try:
                dest_addr = struct.unpack("<I", socket.inet_aton(ip_str))[0]
                payload = b"WifiRoamSentinelPingPayload32byt"
                reply_buf = ctypes.create_string_buffer(256)
                ret = iphlpapi.IcmpSendEcho(
                    handle,
                    dest_addr,
                    payload,
                    len(payload),
                    None,
                    reply_buf,
                    len(reply_buf),
                    int(timeout_ms),
                )
                if ret > 0:
                    _addr, status, rtt = struct.unpack_from("<III", reply_buf.raw, 0)
                    if status == 0:
                        return True, max(1, int(rtt))
                return False, None
            finally:
                iphlpapi.IcmpCloseHandle(handle)
    except Exception:
        pass

    # Stage 2: Locale-independent ping.exe fallback
    t0 = time.perf_counter()
    try:
        res = subprocess.run(
            ['ping', '-n', '1', '-w', str(int(timeout_ms)), ip_str],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            encoding='ascii',
            errors='ignore',
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        dt = (time.perf_counter() - t0) * 1000.0
        if res.returncode == 0 and 'TTL=' in res.stdout.upper():
            for line in res.stdout.splitlines():
                if 'TTL=' in line.upper():
                    match = re.search(r'[=<]\s*(\d+)', line)
                    if match:
                        return True, max(1, int(match.group(1)))
            return True, max(1, int(dt))
    except Exception:
        pass
    return False, None


class SessionLogger:
    """Manages recording telemetry data to CSV files for Python/MATLAB analysis."""

    HEADERS = [
        "timestamp_iso",
        "elapsed_sec",
        "event_type",
        "ssid",
        "connected_bssid",
        "channel",
        "band",
        "rssi_dbm",
        "link_quality",
        "rx_rate_mbps",
        "tx_rate_mbps",
        "gateway_ip",
        "ping_rtt_ms",
        "ping_status",
        "roam_latency_ms",
        "from_bssid",
        "from_channel",
        "visible_aps_count"
    ]

    def __init__(self, logs_dir="logs"):
        self.logs_dir = os.path.abspath(logs_dir)
        self.is_recording = False
        self.file_handle = None
        self.csv_writer = None
        self.file_path = ""
        self.filename = ""
        self.start_time = None
        self.record_count = 0
        self.lock = threading.Lock()

    def start(self):
        with self.lock:
            if self.is_recording:
                return {"success": False, "message": "Already recording", "file_path": self.file_path}

            try:
                os.makedirs(self.logs_dir, exist_ok=True)
                now = datetime.now()
                self.filename = f"roam_session_{now.strftime('%Y-%m-%d_%H-%M-%S')}.csv"
                self.file_path = os.path.join(self.logs_dir, self.filename)
                
                self.file_handle = open(self.file_path, mode="w", newline="", encoding="utf-8")
                self.csv_writer = csv.DictWriter(self.file_handle, fieldnames=self.HEADERS)
                self.csv_writer.writeheader()
                self.file_handle.flush()

                self.is_recording = True
                self.start_time = time.perf_counter()
                self.record_count = 0
                return {"success": True, "file_path": self.file_path, "filename": self.filename}
            except Exception as e:
                return {"success": False, "message": str(e)}

    def stop(self):
        with self.lock:
            if not self.is_recording:
                return {"success": False, "message": "Not recording"}

            self.is_recording = False
            duration = round(time.perf_counter() - self.start_time, 2) if self.start_time else 0.0
            count = self.record_count
            saved_path = self.file_path
            saved_name = self.filename

            try:
                if self.file_handle:
                    self.file_handle.flush()
                    self.file_handle.close()
            except Exception:
                pass
            finally:
                self.file_handle = None
                self.csv_writer = None

            return {
                "success": True,
                "file_path": saved_path,
                "filename": saved_name,
                "duration_sec": duration,
                "records_count": count
            }

    def log_entry(self, entry_dict):
        with self.lock:
            if not self.is_recording or not self.csv_writer:
                return

            try:
                elapsed = round(time.perf_counter() - self.start_time, 3) if self.start_time else 0.0
                row = {
                    "timestamp_iso": datetime.now().isoformat(timespec="milliseconds"),
                    "elapsed_sec": f"{elapsed:.3f}",
                    "event_type": entry_dict.get("event_type", "SAMPLE"),
                    "ssid": entry_dict.get("ssid", ""),
                    "connected_bssid": entry_dict.get("connected_bssid", ""),
                    "channel": entry_dict.get("channel", ""),
                    "band": entry_dict.get("band", ""),
                    "rssi_dbm": entry_dict.get("rssi_dbm", ""),
                    "link_quality": entry_dict.get("link_quality", ""),
                    "rx_rate_mbps": entry_dict.get("rx_rate_mbps", ""),
                    "tx_rate_mbps": entry_dict.get("tx_rate_mbps", ""),
                    "gateway_ip": entry_dict.get("gateway_ip", ""),
                    "ping_rtt_ms": entry_dict.get("ping_rtt_ms", ""),
                    "ping_status": entry_dict.get("ping_status", ""),
                    "roam_latency_ms": entry_dict.get("roam_latency_ms", ""),
                    "from_bssid": entry_dict.get("from_bssid", ""),
                    "from_channel": entry_dict.get("from_channel", ""),
                    "visible_aps_count": entry_dict.get("visible_aps_count", 0)
                }
                self.csv_writer.writerow(row)
                self.file_handle.flush()
                self.record_count += 1
            except Exception:
                pass

    def get_state(self):
        with self.lock:
            duration = round(time.perf_counter() - self.start_time, 1) if (self.is_recording and self.start_time) else 0.0
            return {
                "is_recording": self.is_recording,
                "file_path": self.file_path if self.is_recording else "",
                "filename": self.filename if self.is_recording else "",
                "records_count": self.record_count if self.is_recording else 0,
                "duration_sec": duration
            }


class WifiMonitor:
    """Manages Native WiFi queries, AP filtering, and roaming detection."""

    def __init__(self, target_ssid=None, logs_dir="logs"):
        self.auto_ssid = (target_ssid is None or str(target_ssid).strip() == "" or str(target_ssid).strip().lower() == "auto")
        self.target_ssid = None if self.auto_ssid else str(target_ssid).strip()
        self.handle = wintypes.HANDLE()
        self.guid = None
        self.connected_bssid = ""
        self.connected_ssid = ""
        self.connected_info = {}
        self.visible_aps = []
        self.roam_events = []
        self.gateway = None
        self.last_ping_ms = None
        self.ping_status = "Unknown"
        self.consecutive_drops = 0
        self.lock = threading.RLock()
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
        self.last_drop_end_time = None
        self.last_drop_duration_ms = None
        self.recent_pings = []

        # Session logger for CSV export
        self.logger = SessionLogger(logs_dir=logs_dir)
        self.log_sample_counter = 0

        self._init_wlan()
        self.gateway = get_default_gateway(self.guid)

    def _init_wlan(self):
        """Open WLAN handle and detect connected (or primary) Wi-Fi interface GUID."""
        negotiated = wintypes.DWORD()
        ret = wlan.WlanOpenHandle(2, None, ctypes.byref(negotiated), ctypes.byref(self.handle))
        if ret != 0:
            raise RuntimeError(f"WlanOpenHandle failed with error code: {ret}")

        pIfList = ctypes.POINTER(WLAN_INTERFACE_INFO_LIST)()
        ret = wlan.WlanEnumInterfaces(self.handle, None, ctypes.byref(pIfList))
        if ret == 0 and pIfList.contents.dwNumberOfItems > 0:
            num_items = pIfList.contents.dwNumberOfItems
            base_ptr = ctypes.cast(pIfList.contents.InterfaceInfo, ctypes.c_void_p).value
            entry_size = ctypes.sizeof(WLAN_INTERFACE_INFO)

            selected_guid = pIfList.contents.InterfaceInfo[0].InterfaceGuid
            for i in range(num_items):
                info = WLAN_INTERFACE_INFO.from_address(base_ptr + i * entry_size)
                if info.isState == WLAN_INTERFACE_STATE_CONNECTED:
                    selected_guid = info.InterfaceGuid
                    break

            self.guid = GUID()
            ctypes.memmove(ctypes.byref(self.guid), ctypes.byref(selected_guid), ctypes.sizeof(GUID))
            wlan.WlanFreeMemory(pIfList)
        else:
            if pIfList:
                wlan.WlanFreeMemory(pIfList)
            raise RuntimeError("No Wi-Fi interface found on the system.")

    def close(self):
        """Clean up handles and finalize active recording."""
        self.running = False
        if hasattr(self, 'logger') and self.logger.is_recording:
            self.logger.stop()
        if self.handle:
            wlan.WlanCloseHandle(self.handle, None)
            self.handle = None

    def trigger_scan(self):
        """Request the driver to scan for wireless networks."""
        if self.handle and self.guid:
            ret = wlan.WlanScan(self.handle, ctypes.byref(self.guid), None, None, None)
            return ret == 0
        return False

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
            gw = self.gateway
            if not gw:
                with self.lock:
                    self.ping_status = "NO_GW"
                    self.last_ping_ms = None
                time.sleep(0.5)
                continue

            try:
                success, rtt = icmp_ping(gw, timeout_ms=800)

                now = time.time()
                with self.lock:
                    if success:
                        self.consecutive_drops = 0
                        self.last_ping_ms = rtt
                        self.ping_status = "OK"
                        if self.drop_start_time is not None:
                            drop_duration = round((now - self.drop_start_time) * 1000.0, 1)
                            self.last_drop_duration_ms = drop_duration
                            self.last_drop_end_time = now
                            self.last_handover_latency_ms = drop_duration
                            self.drop_start_time = None
                    else:
                        self.consecutive_drops += 1
                        self.ping_status = "DROP"
                        self.last_ping_ms = None
                        if self.drop_start_time is None:
                            self.drop_start_time = now

                    self.recent_pings.append({
                        "time": now,
                        "success": success,
                        "rtt": self.last_ping_ms
                    })
                    if len(self.recent_pings) > 50:
                        self.recent_pings.pop(0)

                # If drops occur consecutively, check if gateway IP changed
                if not success and self.consecutive_drops >= 2:
                    fresh_gw = get_default_gateway(self.guid)
                    if fresh_gw and fresh_gw != self.gateway:
                        with self.lock:
                            self.gateway = fresh_gw

            except Exception:
                pass

            time.sleep(0.4)

    def _monitor_worker(self):
        """Polls connected BSSID at 100ms interval and tracks network state."""
        scan_counter = 0
        gw_check_counter = 0
        while self.running:
            try:
                conn = self.query_connected()
                curr_bssid = conn.get("bssid", "") if conn else ""
                curr_ssid = conn.get("ssid", "") if conn else ""
                is_connected = conn.get("connected", False) if conn else False

                # Periodically re-verify default gateway every ~2.5s (25 ticks)
                gw_check_counter += 1
                if gw_check_counter >= 25 or not self.gateway:
                    gw_check_counter = 0
                    fresh_gw = get_default_gateway(self.guid)
                    if fresh_gw != self.gateway:
                        with self.lock:
                            self.gateway = fresh_gw

                with self.lock:
                    if is_connected and curr_ssid:
                        if curr_ssid != self.connected_ssid:
                            self.connected_ssid = curr_ssid
                            fresh_gw = get_default_gateway(self.guid)
                            if fresh_gw:
                                self.gateway = fresh_gw
                            if self.last_seen_bssid != "":
                                self.last_seen_bssid = ""
                    elif not is_connected:
                        self.connected_ssid = ""
                        self.connected_bssid = ""
                        self.last_seen_bssid = ""

                aps = self.query_visible_aps()

                # Background scan every ~15 seconds (150 ticks) instead of aggressive 3.5s
                # to prevent off-channel dwell from dropping Wi-Fi pings
                scan_counter += 1
                if scan_counter >= 150:
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
                            now_ts = time.time()
                            if self.drop_start_time is not None:
                                latency = round((now_ts - self.drop_start_time) * 1000.0, 1)
                            elif self.last_drop_end_time is not None and (now_ts - self.last_drop_end_time) <= 5.0:
                                latency = self.last_drop_duration_ms
                                self.last_drop_end_time = None
                            else:
                                latency = self.last_ping_ms if self.last_ping_ms is not None else 0

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

                            # Log roam transition to CSV if recording
                            if self.logger.is_recording:
                                self.logger.log_entry({
                                    "event_type": "ROAM",
                                    "ssid": self.connected_ssid,
                                    "connected_bssid": curr_bssid,
                                    "channel": curr_ch,
                                    "band": matched_active_ap["band"] if matched_active_ap else "",
                                    "rssi_dbm": curr_rssi,
                                    "link_quality": matched_active_ap.get("quality", "") if matched_active_ap else "",
                                    "rx_rate_mbps": conn.get("rx_rate", "") if conn else "",
                                    "tx_rate_mbps": conn.get("tx_rate", "") if conn else "",
                                    "gateway_ip": self.gateway or "",
                                    "ping_rtt_ms": self.last_ping_ms if self.last_ping_ms is not None else "",
                                    "ping_status": self.ping_status,
                                    "roam_latency_ms": latency,
                                    "from_bssid": self.last_seen_bssid,
                                    "from_channel": self.last_seen_channel,
                                    "visible_aps_count": len(aps)
                                })

                            # On roam, immediately refresh gateway (possible VLAN/subnet change)
                            fresh_gw = get_default_gateway(self.guid)
                            if fresh_gw:
                                self.gateway = fresh_gw

                        self.last_seen_bssid = curr_bssid
                        self.last_seen_channel = curr_ch
                        self.last_seen_rssi = curr_rssi

                # Periodic telemetry logging (every ~300ms = 3 ticks) when recording
                if self.logger.is_recording:
                    self.log_sample_counter += 1
                    if self.log_sample_counter >= 3:
                        self.log_sample_counter = 0
                        self.logger.log_entry({
                            "event_type": "SAMPLE",
                            "ssid": self.connected_ssid,
                            "connected_bssid": curr_bssid,
                            "channel": matched_active_ap["channel"] if matched_active_ap else "",
                            "band": matched_active_ap["band"] if matched_active_ap else "",
                            "rssi_dbm": matched_active_ap["rssi"] if matched_active_ap else "",
                            "link_quality": matched_active_ap.get("quality", "") if matched_active_ap else "",
                            "rx_rate_mbps": conn.get("rx_rate", "") if conn else "",
                            "tx_rate_mbps": conn.get("tx_rate", "") if conn else "",
                            "gateway_ip": self.gateway or "",
                            "ping_rtt_ms": self.last_ping_ms if self.last_ping_ms is not None else "",
                            "ping_status": self.ping_status,
                            "roam_latency_ms": "",
                            "from_bssid": "",
                            "from_channel": "",
                            "visible_aps_count": len(aps)
                        })

            except Exception:
                pass

            time.sleep(0.1)

    def start_recording(self):
        """Begin saving telemetry log entries to a CSV file."""
        return self.logger.start()

    def stop_recording(self):
        """Stop logging and finalize the active CSV file."""
        return self.logger.stop()

    def get_recording_state(self):
        """Get current recording status and file info."""
        return self.logger.get_state()

    def get_call_quality_metrics(self):
        """Calculate real-time packet loss, jitter, and VoIP/Teams suitability rating."""
        with self.lock:
            pings = list(self.recent_pings)

        if not pings:
            return {
                "packet_loss_pct": 0.0,
                "total_packets": 0,
                "dropped_packets": 0,
                "jitter_ms": 0.0,
                "avg_ping_ms": 0.0,
                "rating": "WAITING",
                "rating_color": "var(--text-muted)",
                "summary": "Waiting for network telemetry..."
            }

        total = len(pings)
        dropped = sum(1 for p in pings if not p["success"])
        loss_pct = (dropped / total) * 100.0

        successful_rtts = [p["rtt"] for p in pings if p["success"] and p["rtt"] is not None]
        avg_ping = sum(successful_rtts) / len(successful_rtts) if successful_rtts else 0.0

        jitter = 0.0
        if len(successful_rtts) >= 2:
            diffs = [abs(successful_rtts[i] - successful_rtts[i - 1]) for i in range(1, len(successful_rtts))]
            jitter = sum(diffs) / len(diffs)

        if loss_pct == 0.0 and jitter < 15.0:
            rating = "EXCELLENT"
            rating_color = "var(--emerald-500)"
            summary = "Teams: Flawless Voice & Video"
        elif loss_pct <= 1.0 and jitter < 30.0:
            rating = "GOOD"
            rating_color = "var(--emerald-500)"
            summary = "Teams: Clear & Stable Audio"
        elif loss_pct <= 3.0 or jitter < 50.0:
            rating = "FAIR"
            rating_color = "var(--amber-500)"
            summary = "Teams: Minor Stutter / Glitches"
        else:
            rating = "POOR"
            rating_color = "var(--rose-500)"
            summary = "Teams: High Loss / Robot Voice"

        return {
            "packet_loss_pct": round(loss_pct, 1),
            "total_packets": total,
            "dropped_packets": dropped,
            "jitter_ms": round(jitter, 1),
            "avg_ping_ms": round(avg_ping, 1),
            "rating": rating,
            "rating_color": rating_color,
            "summary": summary
        }

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
                "ping_status": self.ping_status,
                "recording": self.logger.get_state(),
                "call_quality": self.get_call_quality_metrics()
            }
