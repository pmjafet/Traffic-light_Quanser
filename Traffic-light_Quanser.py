import os
import json
import time
import threading
import requests
from flask import Flask, jsonify, request, render_template_string

app = Flask(__name__)

# --- CONFIGURACIÓN PERSISTENTE ---
CONFIG_FILE = "semaforos_independientes.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {"lights": {}}

def save_config():
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)

config = load_config()

# --- LÓGICA DE CONTROL INDEPENDIENTE ---

def send_to_hardware(ip, color):
    """Envía la orden física a una IP específica."""
    try:
        url = f"http://{ip}:5000/immediate/{color}"
        requests.get(url, timeout=0.5)
    except:
        pass # Silenciar errores de conexión en el motor

def traffic_engine():
    """Motor principal que gestiona los tiempos de cada semáforo por separado."""
    while True:
        for ip, data in list(config["lights"].items()):
            if data["mode"] == "sequence":
                # Si el tiempo se agotó, pasar al siguiente color
                if time.time() >= data.get("next_change", 0):
                    # Definir el orden: Green -> Yellow -> Red
                    order = ["green", "yellow", "red"]
                    current_idx = order.index(data["active_color"]) if data["active_color"] in order else 2
                    next_idx = (current_idx + 1) % len(order)
                    next_color = order[next_idx]
                    
                    # Actualizar estado
                    data["active_color"] = next_color
                    # Obtener tiempo del nuevo color (convertir a float)
                    duration = float(data["times"].get(next_color, 5))
                    data["next_change"] = time.time() + duration
                    
                    # Enviar al hardware
                    threading.Thread(target=send_to_hardware, args=(ip, next_color), daemon=True).start()
        
        time.sleep(0.1) # Precisión de 100ms

# Iniciar motor
threading.Thread(target=traffic_engine, daemon=True).start()

# --- RUTAS DE LA API ---

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/status')
def get_status():
    return jsonify(config)

@app.route('/add_light', methods=['POST'])
def add_light():
    ip = request.json.get("ip", "").strip()
    if ip and ip not in config["lights"]:
        config["lights"][ip] = {
            "active_color": "off",
            "mode": "manual",
            "times": {"red": 5, "yellow": 2, "green": 5},
            "next_change": 0
        }
        save_config()
    return jsonify(config)

@app.route('/remove_light', methods=['POST'])
def remove_light():
    ip = request.json.get("ip")
    if ip in config["lights"]:
        del config["lights"][ip]
        save_config()
    return jsonify(config)

@app.route('/manual_control', methods=['POST'])
def manual_control():
    data = request.json
    ip, color = data.get("ip"), data.get("color")
    if ip in config["lights"]:
        config["lights"][ip]["mode"] = "manual"
        config["lights"][ip]["active_color"] = color
        send_to_hardware(ip, color)
        save_config()
    return jsonify(config)

@app.route('/start_indiv_sequence', methods=['POST'])
def start_indiv_sequence():
    data = request.json
    ip = data.get("ip")
    if ip in config["lights"]:
        config["lights"][ip]["times"] = {
            "red": float(data.get("red", 5)),
            "yellow": float(data.get("yellow", 2)),
            "green": float(data.get("green", 5))
        }
        config["lights"][ip]["mode"] = "sequence"
        config["lights"][ip]["active_color"] = "green" # Empezar siempre en verde
        config["lights"][ip]["next_change"] = time.time() + config["lights"][ip]["times"]["green"]
        send_to_hardware(ip, "green")
        save_config()
    return jsonify(config)

@app.route('/global_action', methods=['POST'])
def global_action():
    action = request.json.get("action")
    for ip, data in config["lights"].items():
        if action == "off":
            data["mode"] = "manual"
            data["active_color"] = "off"
            send_to_hardware(ip, "off")
        elif action == "sync_sequence":
            # Iniciar todos en verde con los tiempos actuales de cada uno
            data["mode"] = "sequence"
            data["active_color"] = "green"
            data["next_change"] = time.time() + data["times"]["green"]
            send_to_hardware(ip, "green")
    save_config()
    return jsonify(config)

# --- INTERFAZ DINÁMICA V2 (PREMIUM DARK) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Semaforo Master - Pro Control</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
        :root { 
            --bg: #050505; 
            --card: #121212; 
            --accent: #2196F3; 
            --red: #ff3d3d; 
            --yellow: #ffc107; 
            --green: #00e676; 
            --glass: rgba(255, 255, 255, 0.03);
        }
        
        body { 
            font-family: 'Inter', sans-serif; 
            background: var(--bg); 
            color: #e0e0e0; 
            margin: 0; 
            padding: 20px; 
            letter-spacing: -0.02em;
        }

        .container { max-width: 1400px; margin: auto; }

        /* Header Estilo Dashboard */
        .top-bar { 
            display: flex; justify-content: space-between; align-items: center; 
            background: var(--glass); backdrop-filter: blur(10px);
            padding: 20px 30px; border-radius: 20px; margin-bottom: 30px; 
            border: 1px solid rgba(255,255,255,0.05);
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        }

        .main-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr)); gap: 25px; }

        /* Tarjeta Estilizada */
        .light-card { 
            background: var(--card); border-radius: 24px; padding: 25px; 
            border: 1px solid #222; position: relative; overflow: hidden;
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        }
        .light-card:hover { transform: translateY(-5px); border-color: #333; box-shadow: 0 15px 40px rgba(0,0,0,0.6); }

        .ip-header { 
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 20px; border-bottom: 1px solid #222; padding-bottom: 15px;
        }
        .ip-address { font-family: 'JetBrains Mono', monospace; font-weight: 600; color: var(--accent); }

        /* Semáforo Visual Realista */
        .lamp { 
            background: linear-gradient(145deg, #111, #000); 
            width: 60px; padding: 15px; border-radius: 30px; 
            display: flex; flex-direction: column; gap: 15px; 
            border: 3px solid #1a1a1a; box-shadow: inset 0 5px 15px rgba(0,0,0,0.8);
        }
        .circle { 
            width: 60px; height: 60px; border-radius: 50%; opacity: 0.1; 
            transition: 0.4s; filter: grayscale(0.5) blur(1px); 
        }
        
        /* Brillos Intensos */
        .red.active { background: var(--red); opacity: 1; filter: grayscale(0); box-shadow: 0 0 40px rgba(255, 61, 61, 0.4); }
        .yellow.active { background: var(--yellow); opacity: 1; filter: grayscale(0); box-shadow: 0 0 40px rgba(255, 193, 7, 0.4); }
        .green.active { background: var(--green); opacity: 1; filter: grayscale(0); box-shadow: 0 0 40px rgba(0, 230, 118, 0.4); }

        /* Controles */
        .controls { flex: 1; padding-left: 10px; }
        .section-title { font-size: 0.7rem; text-transform: uppercase; color: #555; margin-bottom: 10px; font-weight: 700; letter-spacing: 0.1em; }
        
        .btn-group { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 20px; }
        
        .btn { 
            border: none; padding: 10px; border-radius: 12px; cursor: pointer; 
            font-weight: 700; font-size: 0.8em; transition: 0.3s;
            background: #1a1a1a; color: #666;
        }
        .btn:hover { filter: brightness(1.2); transform: scale(1.05); }
        .btn-active-red { background: var(--red) !important; color: white !important; }
        .btn-active-green { background: var(--green) !important; color: white !important; }

        .time-box { background: #1a1a1a; border-radius: 12px; padding: 10px; margin-bottom: 15px; border: 1px solid #252525; }
        .time-inputs { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
        input[type="number"] { 
            background: #000; border: 1px solid #333; color: var(--green); 
            padding: 8px; border-radius: 8px; width: 100%; text-align: center; font-family: monospace;
        }

        /* Contador */
        .countdown { 
            font-family: monospace; font-size: 1.5rem; font-weight: bold; 
            color: #444; text-align: right; margin-top: -10px; margin-bottom: 10px;
        }
        .countdown.running { color: var(--accent); text-shadow: 0 0 10px var(--accent); }

        .mode-badge { 
            font-size: 0.6rem; font-weight: 800; padding: 4px 10px; 
            border-radius: 20px; background: #333; color: #aaa;
        }
        .badge-sequence { background: rgba(33, 150, 243, 0.2); color: var(--accent); border: 1px solid var(--accent); }
    </style>
</head>
<body>

<div class="container">
    <div class="top-bar">
        <div>
            <h1 style="margin:0; font-size: 1.4rem;">🚦 Traffic <span style="color:var(--accent)">Master</span></h1>
            <small style="color:#555">Sistemas de Control Independiente</small>
        </div>
        <div style="display: flex; gap: 15px; align-items: center;">
            <input type="text" id="newIp" placeholder="192.168.1.XX" style="background: #000; border: 1px solid #333; color:#fff; padding: 12px; border-radius: 12px; width: 180px;">
            <button class="btn" style="background: var(--accent); color:white; padding: 12px 25px;" onclick="addLight()">Añadir Nodo</button>
            <div style="width: 1px; background: #333; height: 40px; margin: 0 5px;"></div>
            <button class="btn" onclick="globalAction('sync_sequence')">Sincronizar</button>
            <button class="btn" style="background: #200; color: var(--red);" onclick="globalAction('off')">Apagar Todo</button>
        </div>
    </div>

    <div class="main-grid" id="mainGrid"></div>
</div>

<script>
    async function updateUI() {
        try {
            const res = await fetch('/status');
            const data = await res.json();
            const grid = document.getElementById('mainGrid');

            Object.entries(data.lights).forEach(([ip, light]) => {
                let card = document.querySelector(`.light-card[data-ip="${ip}"]`);
                
                if (!card) {
                    card = document.createElement('div');
                    card.className = 'light-card';
                    card.dataset.ip = ip;
                    card.innerHTML = `
                        <div class="ip-header">
                            <div style="display:flex; flex-direction:column">
                                <span class="ip-address">${ip}</span>
                                <span class="mode-badge" id="mode-${ip}">${light.mode}</span>
                            </div>
                            <button class="btn" style="background:none; color:#444" onclick="removeLight('${ip}')">✕</button>
                        </div>
                        <div id="count-${ip}" class="countdown">--</div>
                        <div class="card-content" style="display:flex; gap:20px">
                            <div class="lamp">
                                <div id="red-${ip}" class="circle red"></div>
                                <div id="yellow-${ip}" class="circle yellow"></div>
                                <div id="green-${ip}" class="circle green"></div>
                            </div>
                            <div class="controls">
                                <div class="section-title">Control Manual</div>
                                <div class="btn-group">
                                    <button class="btn" onclick="manualControl('${ip}', 'red')">R</button>
                                    <button class="btn" onclick="manualControl('${ip}', 'yellow')">A</button>
                                    <button class="btn" onclick="manualControl('${ip}', 'green')">V</button>
                                    <button class="btn" onclick="manualControl('${ip}', 'off')">✕</button>
                                </div>
                                <div class="section-title">Configuración de Ciclo</div>
                                <div class="time-box">
                                    <div class="time-inputs">
                                        <div><small>Rojo</small><input type="number" id="tr-${ip}" value="${light.times.red}"></div>
                                        <div><small>Ambar</small><input type="number" id="ty-${ip}" value="${light.times.yellow}"></div>
                                        <div><small>Verde</small><input type="number" id="tg-${ip}" value="${light.times.green}"></div>
                                    </div>
                                </div>
                                <button class="btn" style="background: var(--accent); color:white; width: 100%; box-shadow: 0 4px 15px rgba(33, 150, 243, 0.3);" onclick="startIndivSeq('${ip}')">Aplicar y Correr Ciclo</button>
                            </div>
                        </div>
                    `;
                    grid.appendChild(card);
                }

                // Actualizar Modo
                const badge = document.getElementById(`mode-${ip}`);
                badge.innerText = light.mode.toUpperCase();
                badge.className = light.mode === 'sequence' ? 'mode-badge badge-sequence' : 'mode-badge';

                // Actualizar Luces
                ['red', 'yellow', 'green'].forEach(c => {
                    document.getElementById(`${c}-${ip}`).classList.toggle('active', light.active_color === c);
                });

                // Lógica de Countdown
                const countEl = document.getElementById(`count-${ip}`);
                if(light.mode === 'sequence' && light.next_change > 0) {
                    const remaining = Math.max(0, Math.ceil(light.next_change - Date.now()/1000));
                    countEl.innerText = remaining + "s";
                    countEl.classList.add('running');
                } else {
                    countEl.innerText = "--";
                    countEl.classList.remove('running');
                }

                // Inputs (solo si no hay foco)
                const inputs = { 'tr': light.times.red, 'ty': light.times.yellow, 'tg': light.times.green };
                Object.entries(inputs).forEach(([prefix, val]) => {
                    const el = document.getElementById(`${prefix}-${ip}`);
                    if (document.activeElement !== el) el.value = val;
                });
            });

            // Limpiar si se borró
            Array.from(grid.querySelectorAll('.light-card')).forEach(card => {
                if (!data.lights[card.dataset.ip]) card.remove();
            });

        } catch(e) {}
    }

    // (Las funciones addLight, removeLight, etc. se mantienen igual que en tu código anterior)
    async function addLight() {
        const ip = document.getElementById('newIp').value;
        if(!ip) return;
        await fetch('/add_light', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ip}) });
        document.getElementById('newIp').value = "";
        updateUI();
    }
    async function removeLight(ip) {
        if(!confirm("¿Eliminar " + ip + "?")) return;
        await fetch('/remove_light', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ip}) });
        updateUI();
    }
    async function manualControl(ip, color) {
        await fetch('/manual_control', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ip, color}) });
        updateUI();
    }
    async function startIndivSeq(ip) {
        const payload = {
            ip: ip,
            red: document.getElementById('tr-'+ip).value,
            yellow: document.getElementById('ty-'+ip).value,
            green: document.getElementById('tg-'+ip).value
        };
        await fetch('/start_indiv_sequence', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload) });
        updateUI();
    }
    async function globalAction(action) {
        await fetch('/global_action', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({action}) });
        updateUI();
    }

    setInterval(updateUI, 1000);
    updateUI();
</script>
</body>
</html>
"""
if __name__ == '__main__':
    # j'ai utilisé le port 5001 pour eviter les problemes
    app.run(host='0.0.0.0', port=5001, debug=False)