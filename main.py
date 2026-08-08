from flask import Flask, request, jsonify
import sqlite3
from datetime import datetime


def geodesic(point1, point2):
    class Distance:
        def __init__(self, km):
            self.km = km
    lat1, lon1 = point1
    lat2, lon2 = point2
    from math import radians, cos, sin, asin, sqrt
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = 6371
    return Distance(c * r)


app = Flask(__name__)


# --- Inicializar BD ---
def init_db():
    conn = sqlite3.connect("ecolife.db")
    cur = conn.cursor()
    # Usuarios
    cur.execute("""CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT,
        correo TEXT UNIQUE,
        contrasena TEXT,
        puntos INTEGER DEFAULT 0
    )""")
    # Emisiones
    cur.execute("""CREATE TABLE IF NOT EXISTS emisiones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        km REAL,
        vehiculo TEXT,
        co2 REAL,
        fecha TEXT
    )""")
    # Acciones
    cur.execute("""CREATE TABLE IF NOT EXISTS acciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        tipo TEXT,
        puntos INTEGER,
        fecha TEXT
    )""")
    conn.commit()
    conn.close()


init_db()


# --- Registro de usuario ---
@app.route("/registro", methods=["POST"])
def registro():
    data = request.json
    nombre = data["nombre"]
    correo = data["correo"]
    contrasena = data["contrasena"]
    conn = sqlite3.connect("ecolife.db")
    cur = conn.cursor()
    try:
        query = (
            "INSERT INTO usuarios (nombre, correo, contrasena) "
            "VALUES (?,?,?)"
        )
        cur.execute(query, (nombre, correo, contrasena))
        conn.commit()
        return jsonify({"mensaje": "Usuario registrado"})
    except sqlite3.IntegrityError:
        return jsonify({"error": "Correo ya existe"}), 400
    finally:
        conn.close()


# --- Login ---
@app.route("/login", methods=["POST"])
def login():
    data = request.json
    correo, contrasena = data["correo"], data["contrasena"]
    conn = sqlite3.connect("ecolife.db")
    cur = conn.cursor()
    query = (
        "SELECT id FROM usuarios WHERE correo=? AND contrasena=?"
    )
    cur.execute(query, (correo, contrasena))
    usuario = cur.fetchone()
    conn.close()
    if usuario:
        return jsonify({"mensaje": "Login exitoso", "usuario_id": usuario[0]})
        return jsonify({"error": "Credenciales inválidas"}), 401


# --- Fórmula CO₂ ---
FACTORES = {
    "auto": 0.21,
    "moto": 0.12,
    "bus": 0.05,
    "bicicleta": 0.0,
}


@app.route("/co2", methods=["POST"])
def calcular_co2():
    data = request.json
    km = data.get("km", 0)
    vehiculo = data.get("vehiculo", "auto")
    usuario_id = data.get("usuario_id")

    co2 = km * FACTORES.get(vehiculo, 0.2)
    fecha = datetime.now().strftime("%Y-%m-%d")

    conn = sqlite3.connect("ecolife.db")
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO emisiones "
        "(usuario_id, km, vehiculo, co2, fecha) "
        "VALUES (?,?,?,?,?)",
        (usuario_id, km, vehiculo, co2, fecha),
    )
    conn.commit()
    conn.close()

    return jsonify({"co2_emitido": co2, "mensaje": "Emisión registrada"})


# --- Registrar acción ecológica ---
@app.route("/accion", methods=["POST"])
def registrar_accion():
    data = request.json
    usuario_id = data.get("usuario_id")
    tipo = data.get("tipo")
    puntos = data.get("puntos", 10)
    fecha = datetime.now().strftime("%Y-%m-%d")

    conn = sqlite3.connect("ecolife.db")
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO acciones "
        "(usuario_id, tipo, puntos, fecha) "
        "VALUES (?,?,?,?)",
        (usuario_id, tipo, puntos, fecha)
    )
    conn.commit()
    conn.close()

    return jsonify({"mensaje": "Acción registrada", "puntos": puntos})


# --- Perfil ecológico ---
@app.route("/perfil/<int:usuario_id>", methods=["GET"])
def perfil(usuario_id):
    conn = sqlite3.connect("ecolife.db")
    cur = conn.cursor()
    cur.execute(
        "SELECT SUM(co2) FROM emisiones "
        "WHERE usuario_id=?",
        (usuario_id,)
    )
    co2_total = cur.fetchone()[0] or 0
    cur.execute(
        "SELECT SUM(puntos) FROM acciones "
        "WHERE usuario_id=?",
        (usuario_id,)
    )
    puntos = cur.fetchone()[0] or 0
    conn.close()
    return jsonify({
        "usuario_id": usuario_id,
        "co2_total": co2_total,
        "puntos": puntos,
    })


# --- Geolocalización de puntos de acopio ---
@app.route("/acopio", methods=["POST"])
def puntos_acopio():
    data = request.json
    ubicacion_usuario = tuple(data.get("ubicacion"))  # [lat, lon]
    centros = [
        (
            "Centro Reciclaje Rimac",
            (-12.027, -77.042),
        ),
        (
            "Punto Verde San Juan",
            (-12.158, -76.971),
        ),
    ]
    cercanos = []
    for nombre, coords in centros:
        distancia = geodesic(ubicacion_usuario, coords).km
        if distancia <= 10:  # dentro de 10 km
            cercanos.append({
                "nombre": nombre,
                "distancia_km": round(distancia, 2),
            })
    return jsonify({"centros_cercanos": cercanos})


app.run(debug=True)
