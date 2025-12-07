# TORRENT PLUGIN - REAL-TIME UPDATES + BETTER TRACKERS
import os
import subprocess
import threading
import time
import shutil
import json
import socket
import random
import signal
import base64
import urllib.parse
import requests
import atexit
from datetime import datetime

# Global variables
aria2_process = None
aria2_port = 6800
active_torrents = {}
monitor_threads = {}
# Flag untuk menghentikan semua thread
STOP_MONITORING = threading.Event()

# --- UTILITY FUNCTIONS (RPC & ARIA2 CONTROL) ---

def test_aria2_connection():
    """Test koneksi ke aria2 RPC"""
    try:
        response = requests.post(
            f"http://localhost:{aria2_port}/jsonrpc",
            json={"jsonrpc": "2.0", "id": "test", "method": "aria2.getVersion"},
            timeout=1
        )
        # Cek status kode dan pastikan respons JSON valid
        return response.status_code == 200 and 'result' in response.json()
    except (requests.exceptions.RequestException, json.JSONDecodeError):
        return False

def get_super_tracker_list():
    """Daftar tracker super lengkap dan acak"""
    # ... (Daftar tracker tidak diubah, tetap lengkap)
    trackers = [
        # UDP Trackers (fastest)
        "udp://tracker.opentrackr.org:1337/announce",
        "udp://open.tracker.cl:1337/announce",
        "udp://9.rarbg.com:2810/announce",
        "udp://tracker.openbittorrent.com:6969/announce",
        "udp://tracker.torrent.eu.org:451/announce",
        "udp://open.stealth.si:80/announce",
        "udp://opentracker.i2p.rocks:6969/announce",
        "udp://tracker.dler.org:6969/announce",
        "udp://tracker.moeking.me:6969/announce",
        "udp://exodus.desync.com:6969/announce",
        "udp://tracker.bitsearch.to:1337/announce",
        "udp://movies.zsw.ca:6969/announce",
        "udp://open.demonii.com:1337/announce",
        
        # HTTP/HTTPS Trackers (reliable)
        "http://tracker.files.fm:6969/announce",
        "https://tracker.foreverpirates.co:443/announce",
        "http://tracker3.ctix.cn:6969/announce",
        "http://tracker1.520.jp:443/announce",
        "https://tracker.gbitt.info:443/announce",
        "http://vps02.net.orel.ru:80/announce",
        "https://tracker.lilithraws.cf:443/announce",
        
        # Additional working trackers
        "udp://tracker.internetwarriors.net:1337/announce",
        "udp://tracker.leechers-paradise.org:6969/announce",
        "udp://tracker.coppersurfer.tk:6969/announce",
        "udp://tracker.zer0day.to:1337/announce",
        "udp://tracker.leechers-paradise.org:6969/announce",
        "udp://coppersurfer.tk:6969/announce",
        
        # WS Trackers
        "wss://tracker.openwebtorrent.com:443/announce",
        "wss://tracker.btorrent.xyz:443/announce",
        
        # Asia-specific trackers
        "udp://tracker.uw0.xyz:6969/announce",
        "http://tracker.bt4g.com:1515/announce",
        "https://tr.burnabyhighstar.com:443/announce",
    ]
    random.shuffle(trackers)
    return ",".join(trackers[:50])

def kill_all_aria2():
    """Kill semua proses aria2 yang sedang berjalan"""
    try:
        # Mencoba kill berdasarkan nama proses
        subprocess.run(["pkill", "-9", "-f", "aria2c"],
                       stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
        
        # Mencoba kill berdasarkan port (lebih spesifik)
        subprocess.run(["fuser", "-k", f"{aria2_port}/tcp"],
                       stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
        
        time.sleep(0.5)
        return True
    except:
        return False

def ensure_aria2_running(app):
    """Pastikan aria2 berjalan dengan konfigurasi optimal"""
    global aria2_process
    
    # Cek apakah aria2 sudah berjalan dan merespons
    if test_aria2_connection():
        # Lakukan force reload settings jika sudah berjalan
        send_rpc_request("aria2.forceSave", app=app)
        app.show_message(f"✓ Aria2 RPC already running on port {aria2_port}", 2)
        return True

    # Kill existing aria2 yang mungkin error (redundansi)
    kill_all_aria2()
    
    if not shutil.which("aria2c"):
        app.show_message("❌ Install aria2: sudo apt install aria2", 4)
        return False
    
    tracker_list = get_super_tracker_list()
    config_dir = os.path.expanduser("~/.cache/zeta/aria2")
    os.makedirs(config_dir, exist_ok=True)
    config_path = os.path.join(config_dir, "aria2.conf")
    session_file = os.path.join(config_dir, "aria2.session")
    open(session_file, 'a').close() # Buat session file jika belum ada
    
    # Konfigurasi Aria2 yang optimal
    config_content = f"""# Aria2 Config - Optimized for Torrent
enable-rpc=true
rpc-listen-all=true
rpc-listen-port={aria2_port}
rpc-allow-origin-all=true
continue=true

# TORRENT SETTINGS
bt-tracker={tracker_list}
enable-dht=true
enable-dht6=true
dht-listen-port=6881-6999
bt-enable-lpd=true
bt-max-peers=200
seed-ratio=0.0
seed-time=0

# CONNECTION SETTINGS
max-concurrent-downloads=5
max-connection-per-server=16
split=64
min-split-size=1M
connect-timeout=10

# DISK CACHE
disk-cache=128M
file-allocation=falloc

# LOGGING
log-level=warn
console-log-level=error
"""
    
    with open(config_path, 'w') as f:
        f.write(config_content)
    
    cmd = [
        "aria2c",
        f"--conf-path={config_path}",
        f"--input-file={session_file}",
        f"--save-session={session_file}",
        "--daemon=true",
        "--enable-color=false",
    ]
    
    try:
        app.show_message("Starting aria2 with optimized settings...", 2)
        
        # Start process baru
        aria2_process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            # Gunakan os.setsid untuk memastikan proses menjadi daemon yang lepas dari parent
            preexec_fn=os.setsid
        )
        
        # Tunggu dan cek koneksi (maksimal 5 detik)
        for _ in range(5):
            time.sleep(1)
            if test_aria2_connection():
                app.show_message(f"✅ Aria2 started successfully on port {aria2_port}", 2)
                return True
        
        # Jika timeout
        app.show_message("❌ Aria2 startup timeout. Check log files or manual start.", 4)
        return False
        
    except Exception as e:
        app.show_message(f"Start error: {str(e)[:40]}", 4)
        return False

def send_rpc_request(method, params=None, app=None):
    """Kirim request ke aria2 dengan retry logic"""
    if params is None:
        params = []
    
    url = f"http://localhost:{aria2_port}/jsonrpc"
    payload = {
        "jsonrpc": "2.0",
        "id": str(time.time()),
        "method": method,
        "params": params
    }
    
    max_retries = 2
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=payload, timeout=5)
            
            if response.status_code == 200:
                result = response.json()
                if "result" in result:
                    return result["result"]
                elif "error" in result:
                    # Log error spesifik dari aria2
                    if app and attempt == max_retries - 1:
                         app.show_message(f"RPC Error: {method} -> {result['error'].get('message', 'Unknown Error')[:40]}", 3)
                    return None
            
        except requests.exceptions.ConnectionError:
            if attempt == max_retries - 1 and app:
                # Jika koneksi gagal setelah semua retry, coba restart aria2
                app.show_message("Cannot connect to aria2. Attempting restart...", 3)
                if ensure_aria2_running(app):
                    # Coba ulang request setelah restart
                    return send_rpc_request(method, params, app)
        
        except Exception as e:
             if app and attempt == max_retries - 1:
                app.show_message(f"Request failed: {str(e)[:30]}", 3)
                
        time.sleep(0.5)
        
    return None

# --- UI & LOGIC FUNCTIONS ---

def get_magnet_from_clipboard():
    """Ambil magnet link dari clipboard"""
    # ... (Fungsi ini tidak diubah, berfungsi baik)
    clipboard_commands = [
        ["xclip", "-selection", "clipboard", "-o"],
        ["xsel", "-b", "-o"],
        ["wl-paste", "--no-newline"],
        ["pbpaste"]
    ]
    
    for cmd in clipboard_commands:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=1)
            if result.returncode == 0:
                text = result.stdout.strip()
                if text.startswith("magnet:") and "xt=urn:btih:" in text:
                    return text
        except:
            continue
    
    return None

def extract_filename_from_magnet(magnet):
    """Extract filename dari magnet link"""
    # ... (Fungsi ini tidak diubah, berfungsi baik)
    try:
        if "&dn=" in magnet:
            name_part = magnet.split("&dn=")[1].split("&")[0]
            return urllib.parse.unquote(name_part)
        elif "dn=" in magnet:
            name_part = magnet.split("dn=")[1].split("&")[0]
            return urllib.parse.unquote(name_part)
    except:
        pass
    
    if "xt=urn:btih:" in magnet:
        hash_part = magnet.split("xt=urn:btih:")[1].split("&")[0]
        if len(hash_part) >= 8:
            return f"torrent_{hash_part[:8]}"
    
    return "magnet_download"

def format_size(bytes_size):
    """Format bytes dengan lebih akurat"""
    # ... (Fungsi ini tidak diubah, berfungsi baik)
    if bytes_size == 0:
        return "0 B"
    
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    unit_index = 0
    
    while bytes_size >= 1024 and unit_index < len(units) - 1:
        bytes_size /= 1024.0
        unit_index += 1
    
    if unit_index == 0:
        return f"{int(bytes_size)} {units[unit_index]}"
    else:
        # Gunakan 1 desimal untuk KB/s dan 2 desimal untuk MB/GB/TB
        if unit_index == 1:
             return f"{bytes_size:.1f} {units[unit_index]}"
        return f"{bytes_size:.2f} {units[unit_index]}"

def start_download(app):
    """Start download torrent/magnet dengan optimasi"""
    global active_torrents
    
    if not test_aria2_connection() and not ensure_aria2_running(app):
        app.show_message("Failed to connect or start aria2", 4)
        return True
    
    source = None
    filename = ""
    is_magnet = False
    
    # 1. Cek file .torrent yang dipilih
    sel = getattr(app.current_panel, 'get_selected', lambda: None)()
    current_path = getattr(app.current_panel, 'path', '.')

    if sel and sel.lower().endswith(".torrent"):
        full_path = os.path.join(current_path, sel)
        if os.path.exists(full_path):
            source = full_path
            filename = sel.replace(".torrent", "")
            is_magnet = False
    
    # 2. Cek magnet dari clipboard
    if not source:
        magnet = get_magnet_from_clipboard()
        if magnet:
            source = magnet
            filename = extract_filename_from_magnet(magnet)
            is_magnet = True
            app.show_message(f"Using magnet: {filename[:50]}", 2)
        else:
            app.show_message("Pilih file .torrent atau copy magnet link ke clipboard!", 3)
            return True
    
    # Setup UI sebelum request RPC
    app.bg_task = "Torrent"
    app.bg_progress = 0
    app.bg_current = f"🔄 Starting: {filename[:40]}"
    app.bg_done = False
    app.bg_paused = False
    
    save_dir = current_path
    
    # Add ke aria2
    if is_magnet:
        params = {
            "dir": save_dir,
            "bt-save-metadata": "true",
            "follow-torrent": "mem",
            "seed-time": "0",
            # Tambahkan entry point dht secara eksplisit untuk magnet
            "dht-entry-point": "dht.transmissionbt.com:6881"
        }
        result = send_rpc_request("aria2.addUri", [[source], params], app)
    else:
        # Untuk torrent file, b64 encode file content
        try:
            with open(source, 'rb') as f:
                torrent_data = f.read()
        except Exception as e:
            app.show_message(f"Failed to read torrent file: {e}", 4)
            app.bg_task = None
            return True
            
        torrent_b64 = base64.b64encode(torrent_data).decode('ascii')
        
        params = {
            "dir": save_dir,
            "follow-torrent": "mem",
            "seed-time": "0"
        }
        result = send_rpc_request("aria2.addTorrent", [torrent_b64, [], params], app)
    
    if not result:
        app.show_message("Failed to add torrent to download queue", 4)
        app.bg_task = None
        return True
    
    gid = result
    active_torrents[gid] = {
        "filename": filename,
        "start_time": time.time(),
        "is_magnet": is_magnet,
    }
    
    app.show_message(f"✅ Added: {filename[:50]} (GID: {gid[:4]}...)", 2)
    
    # Start real-time monitoring dalam thread
    if gid not in monitor_threads or not monitor_threads[gid].is_alive():
        monitor_thread = threading.Thread(
            target=real_time_monitor,
            args=(gid, filename, app),
            daemon=True
        )
        monitor_threads[gid] = monitor_thread
        monitor_thread.start()
    
    return True

def real_time_monitor(gid, filename, app):
    """Real-time monitoring dengan update cepat, lebih robust"""
    start_time = time.time()
    phase = "initializing"
    
    # Perbaikan: Monitor thread harus berhenti jika GID tidak lagi aktif
    while not STOP_MONITORING.is_set() and gid in active_torrents:
        try:
            # Menggunakan Event.wait() agar thread bisa dihentikan cepat
            if app.bg_paused:
                STOP_MONITORING.wait(1)
                continue
            
            # Dapatkan status
            status = send_rpc_request(
                "aria2.tellStatus",
                [gid, ["status", "totalLength", "completedLength", "downloadSpeed", "uploadSpeed", 
                       "connections", "numSeeders", "errorCode", "errorMessage"]],
                app
            )
            
            if not status or status.get('status') in ["removed", "error"]:
                # Error atau dihapus dari antrian
                error_msg = status.get('errorMessage', 'Removed/Error')
                if status.get('status') == "error" and error_msg:
                     app.show_message(f"❌ Torrent Error: {error_msg[:60]}", 4)
                app.bg_done = True
                break
            
            # Parse data
            current_status = status.get("status", "")
            total = int(status.get("totalLength", 0))
            completed = int(status.get("completedLength", 0))
            speed = int(status.get("downloadSpeed", 0))
            connections = int(status.get("connections", 0))
            seeders = int(status.get("numSeeders", 0))
            
            # Update phase
            if total == 0 and current_status == "active":
                phase = "fetching_metadata"
            elif speed == 0 and completed < total:
                phase = "waiting_for_peers"
            elif current_status == "active":
                phase = "downloading"
            elif current_status == "complete":
                phase = "completed"
            
            # Hitung progress
            progress = (completed / total) * 100 if total > 0 else 0
            app.bg_progress = progress
            
            # --- Format Display ---
            display_parts = []
            
            # Filename & Status
            status_map = {"active": "⬇️", "waiting": "⏳", "paused": "⏸️", "complete": "✅"}
            status_emoji = status_map.get(current_status, "❓")

            name_display = filename[:25] + ("..." if len(filename) > 25 else "")
            display_parts.append(f"{status_emoji} {name_display}")
            
            # Progress Bar & Size
            if total > 0:
                bar_length = 10
                filled = int((progress / 100) * bar_length)
                bar = "█" * filled + "░" * (bar_length - filled)
                completed_str = format_size(completed)
                total_str = format_size(total)
                display_parts.append(f"[{bar}] {progress:.1f}% ({completed_str}/{total_str})")
            else:
                # Handle metadata phase
                display_parts.append("📡 Getting metadata...")
            
            # Speed & Peers
            speed_str = f"⚡{format_size(speed)}/s" if speed > 0 else "Idle"
            display_parts.append(f"{speed_str} | 👥{connections} | 🌱{seeders}")

            app.bg_current = " | ".join(display_parts)
            
            # Check completion
            if current_status == "complete":
                app.bg_done = True
                app.bg_progress = 100
                app.bg_current = f"✅ {filename[:30]} - COMPLETED"
                app.show_message(f"🎉 Download complete: {filename}", 4)
                
                # Refresh file list
                try:
                    time.sleep(1)
                    app.current_panel.refresh_files()
                except:
                    pass
                break
            
            # Stuck detection & Re-announce
            current_time = time.time()
            if phase == "fetching_metadata" and (current_time - start_time) > 60:
                app.show_message("⚠ Taking too long to fetch metadata. Trying re-announce...", 3)
                send_rpc_request("aria2.forceAnnounce", [gid], app)
            
            # Dynamic Update Interval
            interval = 1.0 # Default
            if phase == "downloading" and speed > 2 * 1024 * 1024: # Fast DL (>2MB/s)
                interval = 0.5
            elif phase == "fetching_metadata" or phase == "waiting_for_peers":
                interval = 3.0
            
            STOP_MONITORING.wait(interval)
            
        except Exception as e:
            app.show_message(f"Monitor error: {str(e)[:40]}", 3)
            STOP_MONITORING.wait(2)
    
    # Cleanup saat monitor berhenti
    if gid in active_torrents:
        del active_torrents[gid]
    if gid in monitor_threads:
        del monitor_threads[gid]
    
    # Hanya reset UI jika ini adalah torrent yang aktif di UI
    if app.bg_task == "Torrent" and app.bg_done:
        app.bg_task = None
        app.bg_progress = 0

def control(action, app):
    """Control torrents"""
    # Perbaikan: Pastikan hanya beroperasi jika ada torrent aktif
    if not active_torrents:
        # Cek status global untuk torrent yang mungkin berjalan di background
        stats = send_rpc_request("aria2.getGlobalStat", [], app)
        if not stats or int(stats.get('numActive', 0)) == 0:
            app.show_message("No active torrents to control", 2)
            return True
            
    methods = {
        "pause": "aria2.pauseAll",
        "resume": "aria2.unpauseAll",
        # Perbaikan: Gunakan removeAll bukan forceRemoveAll (lebih aman)
        "stop": "aria2.removeAll" 
    }
    
    method = methods.get(action)
    if not method:
        return True
    
    result = send_rpc_request(method, [], app)
    
    if result is not None:
        if action == "pause":
            app.bg_paused = True
            app.show_message("⏸️ All torrents paused", 2)
        elif action == "resume":
            app.bg_paused = False
            app.show_message("▶️ All torrents resumed", 2)
        elif action == "stop":
            # Set flag untuk semua thread monitor
            STOP_MONITORING.set() 
            for t in monitor_threads.values():
                if t.is_alive():
                    # Memberi waktu pada thread untuk cleanup
                    pass 
            
            # Reset UI dan state global
            active_torrents.clear()
            monitor_threads.clear()
            app.bg_done = True
            app.bg_task = None
            app.bg_current = ""
            app.bg_progress = 0
            
            app.show_message("⏹️ All torrents stopped and removed", 2)
            
            try:
                app.current_panel.refresh_files()
            except:
                pass
            
            # Reset flag STOP_MONITORING
            STOP_MONITORING.clear() 
    else:
        app.show_message(f"Failed to {action}", 3)
    
    return True

def show_status(app):
    """Show debug status"""
    # ... (Fungsi ini tidak diubah, berfungsi baik)
    try:
        stats = send_rpc_request("aria2.getGlobalStat", [], app)
        
        if stats:
            status_text = [
                f"Active: {stats.get('numActive', 'N/A')}",
                f"Waiting: {stats.get('numWaiting', 'N/A')}",
                f"Stopped: {stats.get('numStopped', 'N/A')}",
                f"DL Speed: {format_size(int(stats.get('downloadSpeed', 0)))}/s",
                f"UL Speed: {format_size(int(stats.get('uploadSpeed', 0)))}/s",
                f"Threads: {threading.active_count()}"
            ]
            app.show_message(" | ".join(status_text), 3)
        else:
            app.show_message("Cannot get aria2 status (RPC failed)", 3)
    except:
        app.show_message("Status check failed", 3)
    
    return True

# --- SETUP & CLEANUP ---

def setup(app):
    """Setup plugin dengan keybindings dan start aria2"""
    # Register shortcuts
    app.register_plugin_key(ord('D'), lambda: start_download(app))
    app.register_plugin_key(ord('p'), lambda: control("pause", app))
    app.register_plugin_key(ord('r'), lambda: control("resume", app))
    app.register_plugin_key(ord('x'), lambda: control("stop", app))
    app.register_plugin_key(ord('s'), lambda: show_status(app))
    
    # Setup background task variables
    # Perbaikan: Inisialisasi properti yang mungkin belum ada
    if not hasattr(app, 'bg_task'): app.bg_task = None
    if not hasattr(app, 'bg_progress'): app.bg_progress = 0
    if not hasattr(app, 'bg_current'): app.bg_current = ""
    if not hasattr(app, 'bg_done'): app.bg_done = False
    if not hasattr(app, 'bg_paused'): app.bg_paused = False
    
    app.show_message("Torrent Plugin Loaded → D=download p=pause r=resume x=stop s=status", 3)
    
    # Start aria2 dengan konfigurasi yang lebih baik
    if ensure_aria2_running(app):
        app.show_message(f"✓ Aria2 RPC ready on port {aria2_port}", 2)

def cleanup():
    """Cleanup saat exit"""
    global aria2_process
    
    # Hentikan semua thread monitor
    STOP_MONITORING.set()
    for t in monitor_threads.values():
        if t.is_alive():
            # Beri waktu pada thread untuk selesai secara damai
            t.join(timeout=1)

    # Kirim perintah shutdown RPC ke aria2 (lebih bersih)
    send_rpc_request("aria2.shutdown", [])
    time.sleep(1) # Beri waktu untuk shutdown
    
    if aria2_process:
        try:
            # Gunakan os.killpg untuk membunuh seluruh grup proses daemon
            os.killpg(os.getpgid(aria2_process.pid), signal.SIGTERM)
            aria2_process.wait(timeout=1)
        except:
            # Jika SIGTERM gagal, coba SIGKILL
            try:
                os.killpg(os.getpgid(aria2_process.pid), signal.SIGKILL)
            except:
                pass

atexit.register(cleanup)
