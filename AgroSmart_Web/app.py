from flask import Flask, request, jsonify, render_template, session, redirect, url_for
import sqlite3
import os
import secrets
from datetime import datetime, timezone

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "agrosmart.db")
app = Flask(__name__)
app.secret_key = os.environ.get("AGROSMART_SECRET_KEY", "troque-esta-chave-antes-de-publicar-" + secrets.token_hex(16))

# IDs e tokens de demonstração. Em produção, use variáveis de ambiente/segredos.
DEVICES = {
    "AGRO-001": {
        "name": "AgroSmart — Unidade 001",
        "token": os.environ.get("AGRO_DEVICE_TOKEN", "troque-token-esp32-001"),
        "crop": "Horta / cultivo geral",
        "location": "Área de demonstração",
    }
}
IRRIGATION_MAX_SECONDS = 10


def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def connect_db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with connect_db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            moisture REAL,
            temperature REAL,
            ph REAL,
            created_at TEXT NOT NULL
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            command TEXT NOT NULL,
            duration_seconds INTEGER NOT NULL DEFAULT 10,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            completed_at TEXT
        )""")
        # Uma leitura de exemplo deixa a tela útil antes de conectar o ESP32.
        count = con.execute("SELECT COUNT(*) FROM readings WHERE device_id = ?", ("AGRO-001",)).fetchone()[0]
        if count == 0:
            con.execute(
                "INSERT INTO readings (device_id, moisture, temperature, ph, created_at) VALUES (?, ?, ?, ?, ?)",
                ("AGRO-001", 42.0, 25.4, 6.5, now_iso())
            )


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/dashboard")
def dashboard():
    if "device_id" not in session:
        return redirect(url_for("index"))
    device = DEVICES.get(session["device_id"])
    if not device:
        session.clear()
        return redirect(url_for("index"))
    return render_template("dashboard.html", device=device, device_id=session["device_id"])


@app.route("/relatorio")
def report_page():
    if "device_id" not in session:
        return redirect(url_for("index"))
    return render_template("report.html", device_id=session["device_id"])


@app.post("/api/login")
def api_login():
    data = request.get_json(silent=True) or {}
    device_id = str(data.get("device_id", "")).strip().upper()
    if device_id not in DEVICES:
        return jsonify(ok=False, message="Número do produto não encontrado. Confira o código no aparelho."), 401
    session["device_id"] = device_id
    return jsonify(ok=True, redirect=url_for("dashboard"), device=DEVICES[device_id]["name"])


@app.post("/api/logout")
def api_logout():
    session.clear()
    return jsonify(ok=True, redirect=url_for("index"))


def require_device_token(data):
    device_id = str(data.get("device_id", "")).strip().upper()
    token = str(data.get("device_token", ""))
    device = DEVICES.get(device_id)
    if not device or not secrets.compare_digest(token, device["token"]):
        return None, device_id
    return device, device_id


@app.post("/api/telemetry")
def receive_telemetry():
    data = request.get_json(silent=True) or {}
    device, device_id = require_device_token(data)
    if not device:
        return jsonify(ok=False, message="Dispositivo/token inválido."), 401
    try:
        moisture = float(data["moisture"])
        temperature = float(data["temperature"])
        ph = float(data["ph"])
    except (KeyError, TypeError, ValueError):
        return jsonify(ok=False, message="Envie moisture, temperature e ph numéricos."), 400
    if not (0 <= moisture <= 100 and -20 <= temperature <= 80 and 0 <= ph <= 14):
        return jsonify(ok=False, message="Leitura fora dos limites aceitos; confira a calibração dos sensores."), 400
    with connect_db() as con:
        con.execute(
            "INSERT INTO readings (device_id, moisture, temperature, ph, created_at) VALUES (?, ?, ?, ?, ?)",
            (device_id, moisture, temperature, ph, now_iso())
        )
    return jsonify(ok=True)


@app.get("/api/telemetry/<device_id>")
def get_telemetry(device_id):
    device_id = device_id.strip().upper()
    if session.get("device_id") != device_id or device_id not in DEVICES:
        return jsonify(ok=False, message="Faça login novamente."), 401
    with connect_db() as con:
        latest = con.execute(
            "SELECT moisture, temperature, ph, created_at FROM readings WHERE device_id = ? ORDER BY id DESC LIMIT 1",
            (device_id,)
        ).fetchone()
        history = con.execute(
            "SELECT moisture, temperature, ph, created_at FROM readings WHERE device_id = ? ORDER BY id DESC LIMIT 12",
            (device_id,)
        ).fetchall()
    return jsonify(ok=True, latest=dict(latest) if latest else None, history=[dict(row) for row in history])


@app.post("/api/irrigation")
def request_irrigation():
    if "device_id" not in session:
        return jsonify(ok=False, message="Faça login para continuar."), 401
    data = request.get_json(silent=True) or {}
    if data.get("confirm") is not True:
        return jsonify(ok=False, message="Confirme o acionamento da irrigação."), 400
    device_id = session["device_id"]
    with connect_db() as con:
        # Não cria comandos repetidos enquanto um comando ainda está pendente.
        pending = con.execute(
            "SELECT id FROM commands WHERE device_id = ? AND status = 'pending' ORDER BY id DESC LIMIT 1",
            (device_id,)
        ).fetchone()
        if pending:
            return jsonify(ok=False, message="Já existe um comando aguardando o ESP32. Aguarde alguns segundos."), 409
        cur = con.execute(
            "INSERT INTO commands (device_id, command, duration_seconds, status, created_at) VALUES (?, 'ON', ?, 'pending', ?)",
            (device_id, IRRIGATION_MAX_SECONDS, now_iso())
        )
        command_id = cur.lastrowid
    return jsonify(ok=True, message="Comando enviado para a fila. O ESP32 precisa estar conectado para executar.", command_id=command_id, max_seconds=IRRIGATION_MAX_SECONDS)


@app.get("/api/device/command")
def device_command():
    data = request.args
    device, device_id = require_device_token(data)
    if not device:
        return jsonify(ok=False, message="Dispositivo/token inválido."), 401
    with connect_db() as con:
        command = con.execute(
            "SELECT id, command, duration_seconds FROM commands WHERE device_id = ? AND status = 'pending' ORDER BY id ASC LIMIT 1",
            (device_id,)
        ).fetchone()
        if not command:
            return jsonify(command="OFF", duration_seconds=0)
        con.execute("UPDATE commands SET status = 'sent' WHERE id = ?", (command["id"],))
    return jsonify(command=command["command"], duration_seconds=min(int(command["duration_seconds"]), IRRIGATION_MAX_SECONDS), command_id=command["id"])


@app.post("/api/device/command/<int:command_id>/complete")
def complete_command(command_id):
    data = request.get_json(silent=True) or {}
    device, device_id = require_device_token(data)
    if not device:
        return jsonify(ok=False), 401
    with connect_db() as con:
        con.execute(
            "UPDATE commands SET status = 'completed', completed_at = ? WHERE id = ? AND device_id = ?",
            (now_iso(), command_id, device_id)
        )
    return jsonify(ok=True)


@app.get("/api/health")
def health():
    return jsonify(ok=True, service="AgroSmart API", time=now_iso())


if __name__ == "__main__":
    init_db()
    # Acessível na rede local para o ESP32. Para produção, use servidor WSGI e HTTPS.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
