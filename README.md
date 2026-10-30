# Matera · Fase 2 — arquitectura hexagonal

Sistema de diagnóstico del estado de plantas. Un ESP32 (aquí, un simulador) reporta humedad, luz y
temperatura; el backend las evalúa contra la tabla de referencia de la especie, las guarda en SQLite
y empuja el estado al front en tiempo real.

Tres procesos independientes:

| Proceso | Qué es | Puerto |
|---|---|---|
| Backend | API Flask, responde solo JSON + WebSocket | 5000 |
| Front | HTML/CSS/JS estáticos servidos aparte | 5500 |
| Simulador | `simulador_esp32.py`, habla el mismo protocolo que el ESP32 | — |

## Requisitos e instalación

Python 3.11 o superior.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Si PowerShell no deja activar el entorno, use `.\.venv\Scripts\python.exe` en lugar de `python`.

## Configuración (variables de entorno)

Los secretos se leen del entorno, nunca del código (RA23).

| Variable | Por defecto | Uso |
|---|---|---|
| `MATERA_JWT_SECRETO` | aleatoria por arranque | Clave HS256 del JWT. Defínala para que las sesiones sobrevivan reinicios. |
| `MATERA_FUENTE_ESPECIES` | `csv` | Tabla de referencia: `csv`, `json` o `sqlite` (RA15). |
| `MATERA_BD` | `datos/matera.db` | Archivo SQLite. |
| `MATERA_ADMIN_USUARIO` / `_EMAIL` / `_PASSWORD` | — | Si no existe ningún admin, se crea con estos datos al arrancar. |
| `MATERA_JWT_MINUTOS` | `60` | Vigencia del JWT. |
| `MATERA_INVITACION_MINUTOS` | `1440` | Vigencia del QR de invitación. |
| `MATERA_CORS_ORIGENES` | `http://127.0.0.1:5500,http://localhost:5500` | Orígenes permitidos (RA7). |
| `MATERA_SSL_CERT` / `MATERA_SSL_KEY` | — | Certificado y llave: activan HTTPS y WSS (RA23). |
| `MATERA_HOST` / `MATERA_PUERTO` | `127.0.0.1` / `5000` | Dirección del servidor. |

## 1. Ejecutar el backend

```powershell
$env:MATERA_JWT_SECRETO = "cambie-esto-por-una-clave-larga"
$env:MATERA_ADMIN_USUARIO = "admin"
$env:MATERA_ADMIN_EMAIL = "admin@matera.co"
$env:MATERA_ADMIN_PASSWORD = "admin12345"
python Main.py
```

La base SQLite se crea sola en `datos/matera.db` y el catálogo se siembra desde
`configuracion/especies.csv` la primera vez.

**Cambio de CSV a BD por configuración (demostración RA15):** detenga el servidor y arránquelo con

```powershell
$env:MATERA_FUENTE_ESPECIES = "sqlite"   # o "csv" / "json"
python Main.py
```

No se toca ningún archivo de código: `create_app()` elige el adaptador de `ConsultarRangosPort`.
La gestión de especies del admin (RF17) escribe en SQLite, así que se ve en el catálogo cuando la
fuente es `sqlite`.

### HTTPS / WSS (RA23)

Con un certificado (por ejemplo autofirmado generado con `openssl` o `mkcert`):

```powershell
$env:MATERA_SSL_CERT = "certs\cert.pem"
$env:MATERA_SSL_KEY  = "certs\key.pem"
python Main.py
```

Luego use `https://127.0.0.1:5000` en el front (`window.MATERA_API`) y `--url https://... --inseguro`
en el simulador si el certificado es autofirmado. Sin certificado, el servidor avisa que corre sin
cifrar (solo desarrollo).

## 2. Ejecutar el front

En otra terminal:

```powershell
python -m http.server 5500 --directory frontend
```

Abrir `http://127.0.0.1:5500/`. El front:

- hace diagnósticos ad hoc sin sesión (RF7);
- registra e inicia sesión (RF8, RF9);
- crea, edita y elimina plantas, y muestra su estado en vivo por WebSocket con consulta periódica
  de respaldo cada 15 s (RF10, RF13, RF19);
- filtra el historial por fechas (RF14);
- vincula y desvincula el dispositivo por MAC (RF11, RF21);
- genera el QR de invitación de un solo uso y lo canjea (RF15);
- envía solicitudes de especie y, para el admin, aprueba solicitudes, gestiona especies y cuentas
  (RF16–RF18).

## 3. Ejecutar el simulador del ESP32

Con el backend corriendo:

```powershell
python simulador_esp32.py --mac AA:BB:CC:DD:EE:01 --especie sansevieria --intervalo 5
```

1. El simulador se conecta a `/ws/dispositivos`, anuncia su MAC y entra en emparejamiento
   (ventana de 10 minutos, RF20 / RA22).
2. En el front, abra una planta y en **Dispositivo** escriba esa MAC. El backend genera el token,
   se lo entrega al simulador una sola vez por el WebSocket y espera su acuse; si no llega, la
   vinculación se revierte.
3. El simulador guarda el token en `.simulador_tokens.json` (ignorado por git), se autentica con
   MAC + token y envía lecturas.

Cada ciclo sortea uno de estos casos (RA18):

| Caso | Probabilidad (por defecto) | Respuesta esperada |
|---|---|---|
| Lectura normal dentro del rango de la especie | resto | `SALUDABLE` |
| Uno o dos parámetros fuera de rango | `--prob-fuera-rango 0.25` | `EN_RIESGO` / `CRITICO` |
| Dato inválido: texto, parámetro ausente, valor imposible, JSON roto | `--prob-invalido 0.15` | error 400 / 422 |
| Token inválido (otra conexión con un token aleatorio) | `--prob-token-invalido 0.10` | `CREDENCIALES_INVALIDAS` |

Otras opciones: `--modo http` (usa `POST /api/v1/dispositivos/<mac>/lecturas`), `--token` (usar un
token ya emitido), `--lecturas N` (detenerse tras N lecturas), `--url`, `--inseguro`.
Si el dispositivo se desvincula, el simulador recibe el rechazo, borra su token local y termina.

## Pruebas

```powershell
python -m unittest discover -s tests -v
```

| Archivo | Qué prueba |
|---|---|
| `tests/test_dominio.py` | Casos de uso con dobles de los puertos de salida (`tests/dobles.py`): lecturas en rango, fuera de rango e inválidas, regla de propiedad, vinculación, invitaciones, especies, cuentas. Sin servidor, archivos ni BD (RA19). |
| `tests/test_arquitectura.py` | Ningún módulo de `matera/dominio` importa Flask, JWT, bcrypt, SQL, CSV, JSON ni adaptadores (RA4, RA12). |
| `tests/test_api.py` | Integración HTTP + SQLite temporal, con la tabla de referencia en CSV y en BD. |

## API

Todas las rutas bajo `/api/v1`. Los errores siempre tienen la forma
`{"error": CODIGO, "mensaje": "...", "detalle": {}}`.

| Método | Ruta | Credencial | RF |
|---|---|---|---|
| GET | `/especies` | ninguna | RF5 |
| POST | `/diagnosticos` | ninguna | RF7 |
| POST | `/auth/registro`, `/auth/login` | ninguna (con límite de intentos) | RF8, RF9 |
| GET, POST | `/plantas` | JWT | RF10, RF13 |
| GET, PATCH, DELETE | `/plantas/<id>` | JWT (propietario o admin para editar/eliminar) | RF10, RF13 |
| DELETE | `/plantas/<id>/vinculo` | JWT (cuidador) | RF10 |
| GET | `/plantas/<id>/lecturas?desde=&hasta=&limite=` | JWT | RF14 |
| POST, DELETE | `/plantas/<id>/dispositivo` `{"mac"}` | JWT (propietario o admin) | RF11, RF21 |
| POST | `/plantas/<id>/invitaciones` | JWT (propietario) | RF15 |
| POST | `/invitaciones/canje` `{"token"}` | JWT | RF15 |
| POST, GET | `/especies/solicitudes` | JWT | RF16 |
| POST | `/especies/solicitudes/<id>/aprobar` · `/rechazar` | JWT admin | RF17 |
| PUT, DELETE | `/especies/<nombre>` | JWT admin | RF17 |
| GET, PATCH | `/admin/usuarios[/<id>]` | JWT admin | RF18 |
| POST | `/dispositivos/<mac>/lecturas` | `Authorization: Bearer <token de dispositivo>` | RF12 |
| WS | `/ws/dispositivos` | MAC + token de dispositivo | RF12, RF20 |
| WS | `/ws/front` | JWT en el primer mensaje | RF19 |

Códigos: 400 dato ausente o no numérico · 401 sin identidad o credenciales inválidas ·
403 sin permiso sobre una planta propia/compartida · 404 recurso inexistente o ajeno ·
409 conflicto · 410 invitación no disponible · 422 valor fuera del rango físico ·
429 demasiados intentos · 502 no se pudo entregar el token al dispositivo.

## Estructura

```text
Main.py                         Arranque del servidor (lee HTTPS de variables de entorno)
simulador_esp32.py              Simulador del ESP32 (WS o HTTP)
configuracion/especies.csv|json Tabla de referencia
matera/
  app.py                        create_app(): único punto de composición (RA14)
  config.py                     Configuración desde variables de entorno
  dominio/                      Sin imports de framework ni infraestructura
    modelo.py                   Especie, Lectura, Diagnostico, Planta, Dispositivo, Invitacion...
    errores.py                  Errores de negocio
    validador.py                Evaluador (DiagnosticarPort), criterios, regla de agregación
    politica_propiedad.py       PoliticaPropiedad: quién puede hacer qué sobre una planta
    puertos/entrada.py          DiagnosticarPort, RegistrarLecturaPort, VincularDispositivoPort...
    puertos/salida.py           ConsultarRangosPort, RepositorioEspeciesPort, HistorialLecturasPort...
    servicios/                  Casos de uso (PlantasService, VincularDispositivoService...)
  adaptadores/
    entrada/http/               Controladores REST, JwtVerificador, LimitadorIntentos
    entrada/api_dispositivos.py LecturasController (HTTP) y WsDispositivoAdapter (WS)
    entrada/ws_front.py         WsFrontAdapter (estado en vivo para el navegador)
    salida/tabla_csv.py         AdapterCsv          ┐
    salida/tabla_json.py        AdapterJson         ├ ConsultarRangosPort
    salida/tabla_bd.py          SqliteEspecies      ┘ (+ RepositorioEspeciesPort)
    salida/sqlite_repository.py SqliteUsuarios, SqlitePlantas, SqliteDispositivos, SqliteInvitaciones
    salida/historial_bd.py      RepoLecturas (HistorialLecturasPort)
    salida/auditoria_bd.py      SqliteAuditoria (AuditoriaPort)
    salida/seguridad.py         BcryptHasher, JwtAdapter, TokenOpacoGenerator
    salida/ws_notificador*.py   WsNotificador (estado al front), WsNotificadorDispositivo (token)
    salida/esquema.sql          Esquema SQLite (diagrama entidad-relación)
frontend/                       Cliente web estático
tests/                          Pruebas
```
