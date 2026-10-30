"""Simulador del ESP32 de la matera (R3, RA18).

Habla el mismo protocolo que un dispositivo real:
  1. Si no tiene token, se conecta a /ws/dispositivos, anuncia su MAC y espera a que el usuario
     lo vincule desde el front (ventana de 10 minutos). Recibe el token una sola vez y lo guarda.
  2. Se autentica con MAC + token y envia lecturas cada --intervalo segundos, por WS o por HTTP.
  3. Mezcla lecturas normales con valores fuera de rango, datos invalidos y tokens invalidos.

Ejemplos:
  python simulador_esp32.py --mac AA:BB:CC:DD:EE:01 --especie sansevieria
  python simulador_esp32.py --mac AA:BB:CC:DD:EE:01 --modo http --intervalo 2
  python simulador_esp32.py --url https://127.0.0.1:5000 --inseguro   (certificado autofirmado)
"""
import argparse
import json
import random
import secrets
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import simple_websocket

ARCHIVO_TOKENS = Path(__file__).with_name(".simulador_tokens.json")
RANGOS_POR_DEFECTO = {"humedad": (40, 60), "luz": (300, 800), "temperatura": (18, 26)}
LIMITES_FISICOS = {"humedad": (0, 100), "luz": (0, 200_000), "temperatura": (-50, 60)}


# ---------------------------------------------------------------- utilidades

def log(etiqueta: str, mensaje: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {etiqueta:<14} {mensaje}", flush=True)


def ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def contexto_ssl(inseguro: bool):
    if not inseguro:
        return None
    contexto = ssl.create_default_context()
    contexto.check_hostname = False
    contexto.verify_mode = ssl.CERT_NONE
    return contexto


def url_ws(base: str) -> str:
    return base.replace("https://", "wss://").replace("http://", "ws://") + "/ws/dispositivos"


def cerrar(ws) -> None:
    try:
        ws.close()
    except Exception:
        pass  # el servidor ya cerro la conexion


def cargar_token(mac: str) -> str | None:
    if ARCHIVO_TOKENS.exists():
        return json.loads(ARCHIVO_TOKENS.read_text(encoding="utf-8")).get(mac)
    return None


def guardar_token(mac: str, token: str | None) -> None:
    datos = json.loads(ARCHIVO_TOKENS.read_text(encoding="utf-8")) if ARCHIVO_TOKENS.exists() else {}
    if token is None:
        datos.pop(mac, None)
    else:
        datos[mac] = token
    ARCHIVO_TOKENS.write_text(json.dumps(datos, indent=2), encoding="utf-8")


def rangos_de_especie(base: str, especie: str | None, ssl_ctx) -> dict[str, tuple[float, float]]:
    """Consulta el catalogo publico para generar valores realistas para la especie."""
    if not especie:
        return RANGOS_POR_DEFECTO
    try:
        with urllib.request.urlopen(f"{base}/api/v1/especies", context=ssl_ctx, timeout=5) as r:
            especies = json.load(r)["especies"]
    except (urllib.error.URLError, OSError, ValueError):
        log("aviso", "no se pudo leer el catalogo; se usan rangos genericos")
        return RANGOS_POR_DEFECTO
    for e in especies:
        if e["nombre"] == especie:
            return {r["parametro"]: (r["minimo"], r["maximo"]) for r in e["rangos"]}
    log("aviso", f"especie '{especie}' no encontrada; se usan rangos genericos")
    return RANGOS_POR_DEFECTO


# ---------------------------------------------------------------- generacion de lecturas

def lectura_normal(rangos) -> dict:
    return {p: round(random.uniform(mn, mx), 1) for p, (mn, mx) in rangos.items()}


def lectura_fuera_de_rango(rangos) -> dict:
    lectura = lectura_normal(rangos)
    for parametro in random.sample(list(rangos), k=random.choice([1, 2])):
        mn, mx = rangos[parametro]
        fmin, fmax = LIMITES_FISICOS[parametro]
        if random.random() < 0.5 and mn > fmin:
            lectura[parametro] = round(random.uniform(fmin, mn - 0.1), 1)
        else:
            lectura[parametro] = round(random.uniform(mx + 0.1, min(fmax, mx * 1.5 + 5)), 1)
    return lectura


def lectura_invalida(rangos) -> tuple[str, dict | str]:
    lectura = lectura_normal(rangos)
    caso = random.choice(["no_numerico", "ausente", "imposible", "json_roto"])
    if caso == "no_numerico":
        lectura["luz"] = "mucha"
    elif caso == "ausente":
        lectura.pop("temperatura")
    elif caso == "imposible":
        lectura["humedad"] = 150
    else:
        return caso, '{"tipo": "lectura", "humedad": 4'
    return caso, lectura


# ---------------------------------------------------------------- emparejamiento por WS

def emparejar(base: str, mac: str, ssl_ctx) -> str:
    ws = simple_websocket.Client.connect(url_ws(base), ssl_context=ssl_ctx)
    try:
        ws.send(json.dumps({"tipo": "anuncio", "mac": mac}))
        respuesta = json.loads(ws.receive(timeout=10))
        if respuesta.get("tipo") != "emparejando":
            raise SystemExit(f"No se pudo entrar en emparejamiento: {respuesta.get('mensaje')}")
        log("emparejando", f"MAC {mac} lista hasta {respuesta['expira_en']}")
        log("emparejando", "Vincule esta MAC a una planta desde el front (Mis plantas > Dispositivo).")
        while True:
            crudo = ws.receive(timeout=600)
            if crudo is None:
                raise SystemExit("La ventana de emparejamiento vencio sin vinculacion.")
            mensaje = json.loads(crudo)
            if mensaje.get("tipo") == "token":
                ws.send(json.dumps({"tipo": "token_recibido"}))
                log("vinculado", "token recibido (se guarda localmente; nunca se imprime)")
                return mensaje["token"]
    finally:
        cerrar(ws)


# ---------------------------------------------------------------- envio de lecturas

class CanalWs:
    def __init__(self, base, mac, token, ssl_ctx):
        self.base, self.mac, self.token, self.ssl_ctx = base, mac, token, ssl_ctx
        self.ws = None

    def conectar(self):
        self.ws = simple_websocket.Client.connect(url_ws(self.base), ssl_context=self.ssl_ctx)
        self.ws.send(json.dumps({"tipo": "autenticar", "mac": self.mac, "token": self.token}))
        respuesta = json.loads(self.ws.receive(timeout=10))
        if respuesta.get("tipo") != "autenticado":
            raise PermissionError(respuesta.get("mensaje", "credenciales rechazadas"))

    def enviar(self, carga) -> dict:
        if self.ws is None:
            self.conectar()
        if isinstance(carga, dict):
            carga = json.dumps({"tipo": "lectura", "tomada_en": ahora_iso(), **carga})
        try:
            self.ws.send(carga)
            respuesta = json.loads(self.ws.receive(timeout=10))
        except (simple_websocket.ConnectionClosed, OSError, TypeError):
            self.ws = None
            raise ConnectionError("conexion WS cerrada")
        if respuesta.get("error") == "CREDENCIALES_INVALIDAS":
            raise PermissionError(respuesta.get("mensaje"))
        return respuesta

    def cerrar(self) -> None:
        if self.ws is not None:
            cerrar(self.ws)
            self.ws = None

    def probar_token_invalido(self) -> dict:
        ws = simple_websocket.Client.connect(url_ws(self.base), ssl_context=self.ssl_ctx)
        try:
            ws.send(json.dumps({"tipo": "autenticar", "mac": self.mac, "token": secrets.token_urlsafe(32)}))
            return json.loads(ws.receive(timeout=10))
        finally:
            cerrar(ws)


class CanalHttp:
    def __init__(self, base, mac, token, ssl_ctx):
        self.base, self.mac, self.token, self.ssl_ctx = base, mac, token, ssl_ctx

    def enviar(self, carga, token=None) -> dict:
        cuerpo = carga if isinstance(carga, str) else json.dumps({"tomada_en": ahora_iso(), **carga})
        peticion = urllib.request.Request(
            f"{self.base}/api/v1/dispositivos/{self.mac}/lecturas",
            data=cuerpo.encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token or self.token}"},
        )
        try:
            with urllib.request.urlopen(peticion, context=self.ssl_ctx, timeout=10) as r:
                datos = json.load(r)
                return {"tipo": "diagnostico", **datos["diagnostico"]}
        except urllib.error.HTTPError as error:
            datos = json.loads(error.read() or b"{}")
            if error.code == 401 and token is None:
                raise PermissionError(datos.get("mensaje", "credenciales rechazadas"))
            return {"tipo": "error", "status": error.code, **datos}

    def cerrar(self) -> None:
        pass

    def probar_token_invalido(self) -> dict:
        return self.enviar(lectura_normal(RANGOS_POR_DEFECTO), token=secrets.token_urlsafe(32))


def describir(respuesta: dict) -> str:
    if respuesta.get("tipo") == "diagnostico":
        fuera = [f"{p['parametro']}={p['valor']} {p['estado']}" for p in respuesta["parametros"] if p["estado"] != "OPTIMO"]
        return respuesta["estado_global"] + (f" ({', '.join(fuera)})" if fuera else "")
    status = f"{respuesta['status']} " if "status" in respuesta else ""
    return f"rechazada: {status}{respuesta.get('error')} - {respuesta.get('mensaje')}"


# ---------------------------------------------------------------- programa principal

def main() -> None:
    parser = argparse.ArgumentParser(description="Simulador del ESP32 de la matera")
    parser.add_argument("--url", default="http://127.0.0.1:5000", help="URL base del backend")
    parser.add_argument("--mac", default="AA:BB:CC:DD:EE:01")
    parser.add_argument("--especie", default=None, help="genera valores realistas para esta especie")
    parser.add_argument("--intervalo", type=float, default=5.0, help="segundos entre lecturas")
    parser.add_argument("--modo", choices=["ws", "http"], default="ws", help="canal para las lecturas")
    parser.add_argument("--token", default=None, help="token ya emitido (omite el emparejamiento)")
    parser.add_argument("--lecturas", type=int, default=0, help="cantidad de lecturas (0 = sin fin)")
    parser.add_argument("--prob-fuera-rango", type=float, default=0.25)
    parser.add_argument("--prob-invalido", type=float, default=0.15)
    parser.add_argument("--prob-token-invalido", type=float, default=0.10)
    parser.add_argument("--inseguro", action="store_true", help="acepta certificados autofirmados (WSS/HTTPS)")
    args = parser.parse_args()

    base = args.url.rstrip("/")
    mac = args.mac.upper()
    ssl_ctx = contexto_ssl(args.inseguro)
    if base.startswith("http://"):
        log("aviso", "conexion sin cifrar; en produccion use https:// (RA23)")

    token = args.token or cargar_token(mac)
    if token is None:
        token = emparejar(base, mac, ssl_ctx)
        guardar_token(mac, token)

    rangos = rangos_de_especie(base, args.especie, ssl_ctx)
    canal = CanalWs(base, mac, token, ssl_ctx) if args.modo == "ws" else CanalHttp(base, mac, token, ssl_ctx)
    log("inicio", f"modo={args.modo} intervalo={args.intervalo}s rangos={rangos}")

    try:
        enviar_lecturas(args, canal, rangos, mac)
    finally:
        canal.cerrar()


def enviar_lecturas(args, canal, rangos, mac) -> None:
    enviadas = 0
    while args.lecturas == 0 or enviadas < args.lecturas:
        enviadas += 1
        sorteo = random.random()
        try:
            if sorteo < args.prob_token_invalido:
                log("token invalido", describir(canal.probar_token_invalido()))
            elif sorteo < args.prob_token_invalido + args.prob_invalido:
                caso, carga = lectura_invalida(rangos)
                if caso == "json_roto" and args.modo == "http":
                    carga = '{"humedad": 4'
                log(f"invalida:{caso}", describir(canal.enviar(carga)))
            elif sorteo < args.prob_token_invalido + args.prob_invalido + args.prob_fuera_rango:
                log("fuera de rango", describir(canal.enviar(lectura_fuera_de_rango(rangos))))
            else:
                log("normal", describir(canal.enviar(lectura_normal(rangos))))
        except PermissionError as error:
            log("rechazado", f"{str(error).rstrip('.')}. El dispositivo fue desvinculado; se borra el token local.")
            guardar_token(mac, None)
            raise SystemExit(1)
        except (ConnectionError, OSError, urllib.error.URLError) as error:
            log("sin conexion", f"{error}; se reintenta en el siguiente ciclo")
        time.sleep(args.intervalo)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nSimulador detenido.")
