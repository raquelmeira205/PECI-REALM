import http.server
import socketserver
import json
import urllib.parse
import os
import subprocess

PORT = 8080
CONFIG_FILE = "/home/pi/realm-node/config/sensor_config.json"

HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Radar Sensor Configuration</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary-light: #4ade80;
            --primary: #16a34a;
            --primary-dark: #14532d;
            --bg-color: #f0fdf4;
            --glass-bg: rgba(255, 255, 255, 0.8);
            --glass-border: rgba(255, 255, 255, 0.3);
            --text-main: #064e3b;
            --text-muted: #166534;
        }

        body {
            font-family: 'Inter', sans-serif;
            margin: 0;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            background: linear-gradient(135deg, #dcfce7 0%, #86efac 100%);
            color: var(--text-main);
        }

        .container {
            background: var(--glass-bg);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid var(--glass-border);
            padding: 2.5rem;
            border-radius: 24px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
            width: 100%;
            max-width: 400px;
            transform: translateY(0);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }

        .container:hover {
            transform: translateY(-5px);
            box-shadow: 0 25px 50px rgba(0, 0, 0, 0.15);
        }

        h1 {
            font-weight: 800;
            margin-top: 0;
            margin-bottom: 0.5rem;
            color: var(--primary-dark);
            text-align: center;
            font-size: 1.8rem;
        }

        p.subtitle {
            text-align: center;
            color: var(--text-muted);
            margin-bottom: 2rem;
            font-size: 0.9rem;
        }

        .form-group {
            margin-bottom: 1.5rem;
        }

        label {
            display: block;
            margin-bottom: 0.5rem;
            font-weight: 600;
            color: var(--primary-dark);
            font-size: 0.9rem;
        }

        input[type="text"], input[type="number"] {
            width: 100%;
            padding: 0.75rem 1rem;
            border-radius: 12px;
            border: 2px solid transparent;
            background: rgba(255, 255, 255, 0.9);
            color: var(--text-main);
            font-size: 1rem;
            box-sizing: border-box;
            transition: all 0.3s ease;
            box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.05);
        }

        input[type="text"]:focus, input[type="number"]:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(74, 222, 128, 0.3), inset 0 2px 4px rgba(0, 0, 0, 0.05);
        }

        button {
            width: 100%;
            padding: 1rem;
            border: none;
            border-radius: 12px;
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
            color: white;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 4px 6px rgba(22, 163, 74, 0.2);
            position: relative;
            overflow: hidden;
        }

        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 12px rgba(22, 163, 74, 0.3);
        }

        button:active {
            transform: translateY(0);
        }

        .success-overlay {
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            background: var(--glass-bg);
            backdrop-filter: blur(8px);
            border-radius: 24px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.5s ease;
        }

        .success-overlay.active {
            opacity: 1;
            pointer-events: all;
        }

        .success-icon {
            font-size: 3rem;
            color: var(--primary);
            margin-bottom: 1rem;
            animation: popIn 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards;
        }

        @keyframes popIn {
            0% { transform: scale(0); opacity: 0; }
            100% { transform: scale(1); opacity: 1; }
        }

    </style>
</head>
<body>

<div class="container" id="main-container">
    <h1>Sensor Setup</h1>
    <p class="subtitle">Configure your Wi-Fi and MQTT connection</p>
    
    <form id="configForm" onsubmit="submitForm(event)">
        <div class="form-group">
            <label for="wifi_ssid">Wi-Fi Network (SSID)</label>
            <input type="text" id="wifi_ssid" name="wifi_ssid" placeholder="e.g. MyHomeNetwork" required>
        </div>
        <div class="form-group">
            <label for="wifi_password">Wi-Fi Password</label>
            <input type="text" id="wifi_password" name="wifi_password" placeholder="Leave empty if open network">
        </div>
        <div class="form-group">
            <label for="mqtt_ip">MQTT Broker IP</label>
            <input type="text" id="mqtt_ip" name="mqtt_ip" placeholder="e.g. 192.168.1.50" required>
        </div>
        <div class="form-group">
            <label for="mqtt_port">MQTT Port</label>
            <input type="number" id="mqtt_port" name="mqtt_port" placeholder="e.g. 1883" value="1883" required>
        </div>
        <div class="form-group">
            <label for="base_topic">Base Topic</label>
            <input type="text" id="base_topic" name="base_topic" placeholder="e.g. building/floor1/radar" required>
        </div>
        <button type="submit">Save & Reboot</button>
    </form>

    <div class="success-overlay" id="successOverlay">
        <div class="success-icon">✓</div>
        <h2>Saved!</h2>
        <p>Sensor is rebooting...</p>
    </div>
</div>

<script>
    function submitForm(event) {
        event.preventDefault();
        
        const formData = new FormData(event.target);
        const data = new URLSearchParams(formData);

        fetch('/', {
            method: 'POST',
            body: data
        }).then(response => {
            if(response.ok) {
                document.getElementById('successOverlay').classList.add('active');
            }
        }).catch(err => {
            alert('Failed to save settings. Are you connected to the sensor?');
        });
    }
</script>

</body>
</html>
"""

class ConfigHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(HTML_CONTENT.encode('utf-8'))

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length).decode('utf-8')
        parsed_data = urllib.parse.parse_qs(post_data)
        
        wifi_ssid = parsed_data.get('wifi_ssid', [''])[0]
        wifi_password = parsed_data.get('wifi_password', [''])[0]

        config = {
            "mqtt_ip": parsed_data.get('mqtt_ip', [''])[0],
            "mqtt_port": int(parsed_data.get('mqtt_port', ['1883'])[0]),
            "base_topic": parsed_data.get('base_topic', [''])[0],
            "wifi_ssid": wifi_ssid,
            "wifi_password": wifi_password,
        }

        # Save to JSON — Wi-Fi will be configured on next boot by radar_manager.py
        # (NetworkManager is stopped in AP mode so nmcli is unavailable here)
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=4)
            print(f"Saved config to {CONFIG_FILE}")
            
            # Send success response
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Success")
            
            # Trigger reboot in the background so we can finish the HTTP response
            subprocess.Popen(["sudo", "reboot"])
            
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(f"Error: {e}".encode('utf-8'))

if __name__ == "__main__":
    # Ensure port 80 requires sudo
    try:
        with socketserver.TCPServer(("", PORT), ConfigHandler) as httpd:
            print(f"Serving configuration portal on port {PORT}")
            httpd.serve_forever()
    except PermissionError:
        print(f"Error: Permission denied. Please run this script with sudo to use port {PORT}.")
