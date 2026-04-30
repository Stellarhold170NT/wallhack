import socket
import struct
import threading
import time
from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit

# Configuration
UDP_IP = "0.0.0.0"
UDP_PORT = 5005
WEB_PORT = 8080

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# HTML Dashboard Template with 3 Charts
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>WiFi Wallhack Advanced Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.socket.io/4.0.0/socket.io.min.js"></script>
    <style>
        body { background: #0f172a; color: #f8fafc; font-family: 'Segoe UI', sans-serif; margin: 0; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #334155; padding-bottom: 10px; margin-bottom: 20px; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 20px; }
        .chart-container { background: #1e293b; padding: 15px; border-radius: 10px; border: 1px solid #334155; }
        .full-width { grid-column: span 2; }
        .glitch { color: #38bdf8; text-shadow: 0 0 10px #38bdf8; }
        .node-info { font-size: 0.9em; color: #94a3b8; margin-top: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 class="glitch">WIFI WALLHACK V1.1</h1>
            <div id="connection-status">Connecting...</div>
        </div>
        
        <div class="grid">
            <!-- Combined Chart -->
            <div class="chart-container full-width">
                <div style="display: flex; justify-content: space-between;">
                    <strong>COMBINED VIEW (NODE 1 & 2)</strong>
                    <div class="node-info" id="combined-status">Waiting for data...</div>
                </div>
                <canvas id="combinedChart" height="100"></canvas>
            </div>

            <!-- Individual Node 1 -->
            <div class="chart-container">
                <strong style="color: #38bdf8;">NODE 1 (BLUE)</strong>
                <div class="node-info" id="node1-info">---</div>
                <canvas id="node1Chart" height="150"></canvas>
            </div>

            <!-- Individual Node 2 -->
            <div class="chart-container">
                <strong style="color: #f472b6;">NODE 2 (PINK)</strong>
                <div class="node-info" id="node2-info">---</div>
                <canvas id="node2Chart" height="150"></canvas>
            </div>
        </div>
    </div>

    <script>
        const maxPoints = 200;
        const avgWindow = 1200; // Khoảng 1 phút nếu tốc độ 20Hz (điều chỉnh tùy tốc độ node)
        const node1History = [];
        const node2History = [];

        const calculateAvg = (history, newVal) => {
            history.push(newVal);
            if (history.length > avgWindow) history.shift();
            const sum = history.reduce((a, b) => a + b, 0);
            return (sum / history.length).toFixed(1);
        };

        const chartOptions = {
            responsive: true,
            scales: {
                y: { 
                    reverse: true,
                    min: -90, 
                    max: -20, 
                    grid: { color: '#334155' },
                    ticks: { color: '#94a3b8' }
                },
                x: { display: false }
            },
            animation: { duration: 0 },
            plugins: { legend: { display: false } }
        };

        const createChart = (id, datasets) => new Chart(document.getElementById(id), {
            type: 'line',
            data: { labels: Array(maxPoints).fill(''), datasets: datasets },
            options: chartOptions
        });

        const combinedChart = createChart('combinedChart', [
            { borderColor: '#38bdf8', data: Array(maxPoints).fill(null), tension: 0.3, borderWidth: 2, pointRadius: 0 },
            { borderColor: '#f472b6', data: Array(maxPoints).fill(null), tension: 0.3, borderWidth: 2, pointRadius: 0 }
        ]);

        const node1Chart = createChart('node1Chart', [
            { borderColor: '#38bdf8', data: Array(maxPoints).fill(null), tension: 0.3, borderWidth: 2, pointRadius: 0 }
        ]);

        const node2Chart = createChart('node2Chart', [
            { borderColor: '#f472b6', data: Array(maxPoints).fill(null), tension: 0.3, borderWidth: 2, pointRadius: 0 }
        ]);

        const socket = io();
        socket.on('csi_data', (msg) => {
            const rssi = -msg.rssi;
            
            if (msg.node_id === 1) {
                const avg = calculateAvg(node1History, rssi);
                node1Chart.data.datasets[0].data.push(rssi);
                if (node1Chart.data.datasets[0].data.length > maxPoints) node1Chart.data.datasets[0].data.shift();
                node1Chart.update();
                combinedChart.data.datasets[0].data.push(rssi);
                if (combinedChart.data.datasets[0].data.length > maxPoints) combinedChart.data.datasets[0].data.shift();
                document.getElementById('node1-info').innerText = `IP: ${msg.addr} | RSSI: ${rssi} dBm | 1m Avg: ${avg} dBm`;
            } else if (msg.node_id === 2) {
                const avg = calculateAvg(node2History, rssi);
                node2Chart.data.datasets[0].data.push(rssi);
                if (node2Chart.data.datasets[0].data.length > maxPoints) node2Chart.data.datasets[0].data.shift();
                node2Chart.update();
                combinedChart.data.datasets[1].data.push(rssi);
                if (combinedChart.data.datasets[1].data.length > maxPoints) combinedChart.data.datasets[1].data.shift();
                document.getElementById('node2-info').innerText = `IP: ${msg.addr} | RSSI: ${rssi} dBm | 1m Avg: ${avg} dBm`;
            }
            
            combinedChart.update();
            document.getElementById('connection-status').innerText = 'System Online';
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

def udp_listener():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    
    while True:
        data, addr = sock.recvfrom(2048)
        if len(data) >= 18:
            node_id = data[4]
            rssi = struct.unpack('b', bytes([data[16]]))[0]
            socketio.emit('csi_data', {
                'node_id': node_id,
                'rssi': abs(rssi),
                'addr': addr[0]
            })

if __name__ == '__main__':
    threading.Thread(target=udp_listener, daemon=True).start()
    socketio.run(app, host='0.0.0.0', port=WEB_PORT)
