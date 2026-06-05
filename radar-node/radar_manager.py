import time
import subprocess
import os
import sys

# ==========================================
# CONFIGURATION
# ==========================================
PING_HOST = "8.8.8.8"
MAX_WAIT_SECONDS = 60

# Paths
RADAR_SCRIPT = os.path.join(os.path.dirname(__file__), "node_client.py")
CONFIG_SERVER_SCRIPT = os.path.join(os.path.dirname(__file__), "config_server.py")
CONFIG_FILE = "/home/pi/realm-node/config/sensor_config.json"

# ==========================================
# NETWORK / INTERFACE HELPERS
# ==========================================
def configure_wifi_from_config():
    """
    If the config file has Wi-Fi credentials saved from the setup portal,
    register them with NetworkManager now (while NM is running) then clear
    them from the file so we don't re-apply on every boot.
    """
    if not os.path.exists(CONFIG_FILE):
        return

    try:
        import json
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
    except Exception as e:
        print(f"Could not read config file: {e}")
        return

    ssid = config.pop("wifi_ssid", "").strip()
    password = config.pop("wifi_password", "").strip()

    if not ssid:
        return  # Nothing to configure

    print(f"Configuring Wi-Fi for SSID: {ssid}")

    # Remove any stale connection profile with this name first
    subprocess.run(["nmcli", "connection", "delete", ssid], capture_output=True)

    if password:
        result = subprocess.run(
            ["nmcli", "connection", "add", "type", "wifi",
             "con-name", ssid, "ssid", ssid,
             "wifi-sec.key-mgmt", "wpa-psk",
             "wifi-sec.psk", password],
            capture_output=True, text=True
        )
    else:
        result = subprocess.run(
            ["nmcli", "connection", "add", "type", "wifi",
             "con-name", ssid, "ssid", ssid],
            capture_output=True, text=True
        )

    if result.returncode == 0:
        print(f"Wi-Fi profile created for: {ssid}")
        # Persist config without the credentials
        try:
            import json
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"Warning: could not update config file: {e}")
    else:
        print(f"Failed to create Wi-Fi profile: {result.stderr}")
def run(cmd):
    """Run a shell command, swallowing output. Returns True on success."""
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return result.returncode == 0
    except Exception as e:
        print(f"Command {cmd} raised: {e}")
        return False

def enter_client_mode():
    """Hand wlan0 to wpa_supplicant / NetworkManager for normal Wi-Fi client use."""
    print("Switching to CLIENT mode...")
    run(["systemctl", "stop", "hostapd"])
    run(["systemctl", "stop", "hostapd@wlan0"])
    time.sleep(1)
    run(["rfkill", "unblock", "wifi"])
    run(["systemctl", "start", "wpa_supplicant"])
    run(["systemctl", "start", "NetworkManager"])
    time.sleep(3)
    print("CLIENT mode ready.")

def enter_ap_mode():
    """Hand wlan0 to hostapd for Access Point / setup portal use."""
    print("Switching to AP (setup) mode...")
    run(["systemctl", "stop", "NetworkManager"])
    run(["systemctl", "stop", "wpa_supplicant"])
    run([ "rm", "-f", "/var/run/hostapd/wlan0"])
    time.sleep(1)
    run(["ip", "link", "set", "wlan0", "down"])
    run(["rfkill", "unblock", "wifi"])
    run(["ip", "link", "set", "wlan0", "up"])
    time.sleep(1)
    run(["systemctl", "start", "hostapd"])
    time.sleep(2)

    result = subprocess.run(
        ["systemctl", "is-active", "hostapd"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    if result.stdout.decode().strip() == "active":
        print("AP mode ready — hostapd is running.")
    else:
        print("WARNING: hostapd did not start cleanly. Check 'journalctl -u hostapd -n 20'.")

def check_internet():
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "1", PING_HOST],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        return result.returncode == 0
    except Exception:
        return False

# ==========================================
# MAIN
# ==========================================
def main():
    print("Starting network check...")
    configure_wifi_from_config()  # Apply any credentials saved by the setup portal
    enter_client_mode()

    connected = False
    start_time = time.time()

    while time.time() - start_time < MAX_WAIT_SECONDS:
        if check_internet():
            connected = True
            break
        print("Waiting for network...")
        time.sleep(2)

    if connected:
        print("Network found! Starting Normal Mode.")
        try:
            subprocess.run(["python3", RADAR_SCRIPT])
        except Exception as e:
            print(f"Failed to start radar script: {e}")
    else:
        print("No network found. Entering Setup Mode.")
        enter_ap_mode()
        try:
            subprocess.run(["sudo", "python3", CONFIG_SERVER_SCRIPT])
        except Exception as e:
            print(f"Failed to start config server: {e}")

if __name__ == "__main__":
    main()
