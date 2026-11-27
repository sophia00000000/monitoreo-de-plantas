# Matera · Fase 2 — arquitectura hexagonal

Sistema de diagnóstico del estado de plantas. Un ESP32 (real, en Wokwi o el simulador en Python)
reporta humedad, luz y temperatura; el backend las evalúa contra la tabla de referencia de la
especie, calcula el **ánimo de la mascota**, guarda todo en SQLite, empuja el estado al front en
tiempo real y le devuelve el ánimo a la pantalla de la matera.

Procesos independientes:

| Proceso | Qué es | Puerto |
|---|---|---|
| Backend | API Flask, responde solo JSON + WebSocket | 5000 |
| Front | HTML/CSS/JS estáticos servidos aparte | 5500 |
| Dispositivo | ESP32 con firmware en `firmware/` (placa real o Wokwi), o `simulador_esp32.py` con el mismo protocolo | — |

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

## Paso a paso (demo completa)

Se usan tres terminales de PowerShell, todas abiertas en la raíz del proyecto y con el entorno
virtual activado (`.\.venv\Scripts\Activate.ps1`).

### Paso 1 — Instalar dependencias (solo la primera vez)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### Paso 2 — Arrancar el backend (terminal 1)

```powershell
$env:MATERA_JWT_SECRETO = "una-clave-larga-y-secreta-para-firmar-jwt"
$env:MATERA_ADMIN_USUARIO = "admin"
$env:MATERA_ADMIN_EMAIL = "admin@matera.co"
$env:MATERA_ADMIN_PASSWORD = "admin12345"
python Main.py
```

Debe aparecer `Running on http://127.0.0.1:5000`. Al primer arranque se crean la base
`datos/matera.db` y la cuenta de administrador `admin` / `admin12345`.

### Paso 3 — Arrancar el front (terminal 2)

```powershell
python -m http.server 5500 --directory frontend
```

Abra `http://127.0.0.1:5500/` en el navegador.

### Paso 4 — Crear una cuenta e iniciar sesión

**Desde el front:** pulse **Iniciar sesion** (botón verde arriba a la derecha, la pestaña
**Iniciar sesion / Registrarse** o el aviso verde de la pantalla inicial). Se abre una pantalla con
dos formularios: *Iniciar sesion* a la izquierda y *Crear cuenta* a la derecha.

- *Crear cuenta*: usuario `ana`, correo `ana@correo.com`, contraseña `clave1234`. La sesión se
  inicia sola al registrarse.
- *Iniciar sesión*: usuario (o correo) y contraseña. Ejemplos:
  - usuaria normal: `ana` / `clave1234`
  - administrador: `admin` / `admin12345` (ve además la pestaña **Administración**)

**Desde PowerShell (opcional, para probar la API sin el front):**

```powershell
$api = "http://127.0.0.1:5000/api/v1"

# Registro
Invoke-RestMethod -Method Post -Uri "$api/auth/registro" -ContentType "application/json" `
  -Body '{"nombre": "ana", "email": "ana@correo.com", "password": "clave1234"}'

# Inicio de sesión: devuelve {"token": "...", "usuario": {...}}
$login = Invoke-RestMethod -Method Post -Uri "$api/auth/login" -ContentType "application/json" `
  -Body '{"usuario": "ana", "password": "clave1234"}'
$cabeceras = @{ Authorization = "Bearer $($login.token)" }

# Usar el JWT: crear y listar plantas
Invoke-RestMethod -Method Post -Uri "$api/plantas" -Headers $cabeceras -ContentType "application/json" `
  -Body '{"apodo": "Mi sansevieria", "especie": "sansevieria"}'
Invoke-RestMethod -Uri "$api/plantas" -Headers $cabeceras
```

El mismo inicio de sesión con `curl` (Git Bash):

```bash
curl -X POST http://127.0.0.1:5000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"usuario": "ana", "password": "clave1234"}'
```

Si la contraseña es incorrecta o el usuario no existe, la respuesta es la misma en ambos casos:
`401 {"error": "CREDENCIALES_INVALIDAS", "mensaje": "Usuario o contrasena incorrectos."}` (RA24).

### Paso 5 — Crear una planta

En **Mis plantas**, formulario *Nueva planta*: apodo `Mi sansevieria`, especie *Lengua de suegra*.
Haga clic en la tarjeta de la planta para abrir su detalle.

### Paso 6 — Encender el simulador (terminal 3)

```powershell
python simulador_esp32.py --mac AA:BB:CC:DD:EE:01 --especie sansevieria --intervalo 5
```

Queda esperando con el mensaje `emparejando  MAC AA:BB:CC:DD:EE:01 lista hasta ...` (tiene 10 minutos).

Para usar la ESP32 real o Wokwi en lugar del simulador, vea la sección
[4. Usar con la ESP32](#4-usar-con-la-esp32-placa-real-o-wokwi).

### Paso 7 — Vincular el dispositivo

En el detalle de la planta, sección **Dispositivo**, escriba `AA:BB:CC:DD:EE:01` y pulse
**Vincular**. El simulador muestra `token recibido` y empieza a enviar lecturas. En el front, el
estado de la planta y el historial se actualizan solos (indicador **en vivo**).

### Paso 8 — Probar el resto de la demo

- **Planta ajena (debe fallar):** cierre sesión, cree otra cuenta (`beto` / `clave1234`) y pida la
  planta de `ana`. Por API:
  ```powershell
  $beto = Invoke-RestMethod -Method Post -Uri "$api/auth/login" -ContentType "application/json" `
    -Body '{"usuario": "beto", "password": "clave1234"}'
  Invoke-RestMethod -Uri "$api/plantas/1" -Headers @{ Authorization = "Bearer $($beto.token)" }
  # -> 404 RECURSO_NO_ENCONTRADO
  ```
- **Compartir:** como `ana`, en el detalle pulse **Generar invitación**. Con la sesión de `beto`,
  pegue el código en *Adoptar planta* (o abra el enlace del QR): `beto` queda como cuidador.
- **Cambiar de CSV a BD:** detenga el backend (Ctrl+C), ejecute
  `$env:MATERA_FUENTE_ESPECIES = "sqlite"` y vuelva a correr `python Main.py`.
- **Desvincular:** en el detalle, **Desvincular dispositivo**. El simulador recibe el rechazo,
  borra su token y termina.

### Paso 9 — Adoptar una planta escaneando el QR con el teléfono

El PC y el teléfono deben estar en la misma red. Las redes universitarias suelen bloquear el tráfico
entre dispositivos, así que lo más seguro es **conectar el PC al hotspot del teléfono**.

1. **IP del PC.** Ejecute `ipconfig` y copie la *Dirección IPv4* del adaptador **Wi-Fi**. En los
   ejemplos se usa `172.20.10.3` (la que asigna el hotspot de un iPhone); reemplácela por la suya.

2. **Firewall** (una sola vez, en PowerShell **como administrador**). Con la red marcada como
   *Pública*, Windows bloquea las conexiones entrantes:
   ```powershell
   New-NetFirewallRule -DisplayName "Matera dev" -Direction Inbound -Protocol TCP -LocalPort 5000,5500 -Action Allow -Profile Any
   ```
   Para quitarla al terminar: `Remove-NetFirewallRule -DisplayName "Matera dev"`.

3. **Backend escuchando en la red** (terminal 1; detenga antes el anterior con Ctrl+C). Además de
   las variables del paso 2:
   ```powershell
   $env:MATERA_HOST = "0.0.0.0"
   $env:MATERA_CORS_ORIGENES = "http://172.20.10.3:5500,http://127.0.0.1:5500"
   python Main.py
   ```
   `MATERA_CORS_ORIGENES` debe incluir la dirección exacta con la que se abre el front; si no, el
   navegador bloquea las llamadas a la API (CORS) y la página carga sin especies ni login.

4. **Front escuchando en la red** (terminal 2; Ctrl+C al anterior):
   ```powershell
   python -m http.server 5500 --bind 0.0.0.0 --directory frontend
   ```

5. **En el PC**, abra `http://172.20.10.3:5500/` (con la IP, **no** con `127.0.0.1`: el QR guarda
   la dirección con la que se abrió la página) y recargue con **Ctrl+F5**. Inicie sesión como
   propietario (`ana`), abra la planta y pulse **Generar invitacion**.

6. **En el teléfono**, escanee el QR con la cámara. Se abre el front con la invitación guardada.
   Inicie sesión con **otra cuenta** (por ejemplo `beto` / `clave1234`, o cree una). El código
   aparece en *Adoptar planta*: pulse **Canjear**. La planta queda en *Mis plantas* del teléfono
   como **CUIDADOR**. Un segundo intento con el mismo QR responde que la invitación ya no está
   disponible (un solo uso, RA20).

Si la IP del PC cambia (por ejemplo, al reconectarse al hotspot), actualice `MATERA_CORS_ORIGENES`,
reinicie el backend y vuelva a abrir la página con la IP nueva.

### Problemas comunes

| Síntoma | Causa probable | Solución |
|---|---|---|
| `ERROR: ya hay un servidor escuchando en 127.0.0.1:5000` | Hay otro backend abierto (en Windows dos procesos pueden compartir el puerto y repartirse las peticiones) | Cierre el otro con Ctrl+C o use `$env:MATERA_PUERTO` |
| Los botones no responden o la lista de especies sale vacía | El backend no está corriendo, o hay dos copias | Revise la terminal 1; deje una sola instancia |
| En el teléfono la página **no carga** | Red o firewall | Compruebe la IP, la regla de firewall y pruebe `http://172.20.10.3:5500/` en el navegador del teléfono |
| En el teléfono la página carga pero **sin especies ni login** | CORS: el origen no está en `MATERA_CORS_ORIGENES` | Agregue `http://<IP>:5500` y reinicie el backend |
| El QR abre `127.0.0.1` en el teléfono | La invitación se generó con el front abierto en `127.0.0.1` | Abra el front en el PC con su IP y genere otra invitación |
| La página abierta con doble clic (`file://`) no funciona | El navegador bloquea las llamadas desde archivos locales | Sírvala con `python -m http.server` (paso 3) |

## 1. Ejecutar el backend

```powershell
$env:MATERA_JWT_SECRETO = "cambie-esto-por-una-clave-larga"
$env:MATERA_ADMIN_USUARIO = "admin"
$env:MATERA_ADMIN_EMAIL = "admin@matera.co"
$env:MATERA_ADMIN_PASSWORD = "admin12345"
python Main.py
```

La base SQLite se crea sola en `datos/matera.db` y el catálogo se siembra desde
`configuracion/especies.csv` la primera vez. Si `datos/matera.db` ya existía con una versión
anterior del esquema, al arrancar se le agrega la columna `diagnostico.animo` (las mediciones viejas
quedan `FELIZ`) y la tabla `regla_animo`, sin perder datos.

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
- muestra la edad de la última lectura ("en vivo · ultima lectura hace X s"). Si pasan más de
  3 intervalos de lectura sin datos, el indicador y el detalle de la planta pasan a **advertencia**:
  "en vivo" solo significa que el WebSocket del navegador está abierto, no que la matera siga
  enviando. El intervalo es 5 s por defecto; si usa otro, defina `window.MATERA_INTERVALO_S`
  antes de cargar `app.js`;
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

## 4. Usar con la ESP32 (placa real o Wokwi)

El firmware está en `firmware/matera_esp32/matera_esp32/` y es un proyecto de **PlatformIO**
(extensión de VS Code). Habla el mismo protocolo WebSocket que el simulador.

### Hardware

| Componente | Wokwi (`diagram.json`, ESP32 DevKit C) | Placa real (ESP32-C3 SuperMini) |
|---|---|---|
| Humedad del suelo (analógico) | potenciómetro → GPIO 34 | sensor capacitivo → GPIO 0 |
| Luz (LDR con divisor de 10 kΩ) | GPIO 35 | GPIO 1 |
| Temperatura DS18B20 (con pull-up 4,7 kΩ) | GPIO 4 | GPIO 4 |
| Pantalla OLED 128×64 I²C | SSD1306, SDA 21 / SCL 22 | SH1106, SDA 7 / SCL 6 |

### Paso 1 — Configurar el firmware

```powershell
cd firmware\matera_esp32\matera_esp32
copy src\config.example.h src\config.h
```

Edite `src/config.h` (está en `.gitignore`: nunca suba su contraseña de Wi-Fi):

| Definición | Qué poner |
|---|---|
| `WIFI_SSID` / `WIFI_PASS` | Red de **2,4 GHz** (el ESP32 no ve redes de 5 GHz). En Wokwi se usa `Wokwi-GUEST`. |
| `BACKEND_HOST` | IP del PC donde corre el backend (`ipconfig` → *Dirección IPv4*). En Wokwi: `host.wokwi.internal`. |
| `BACKEND_PORT` / `BACKEND_SSL` | `5000` / `0`. Use `1` solo si el backend corre con `MATERA_SSL_CERT` (WSS). |
| `URL_FRONT` | Dirección con la que se abre el front desde el teléfono, sin barra final (p. ej. `http://192.168.1.100:5500`). El QR de la pantalla apunta a `URL_FRONT/?mac=<MAC>` y debe medir 53 caracteres o menos. |
| `PIN_*` | Ya vienen para cada placa; cámbielos solo si cableó distinto. |

### Paso 2 — Backend y front accesibles desde la red

La ESP32 es otro equipo de la red: no puede usar `127.0.0.1`. Siga los puntos 1 a 4 del
[Paso 9](#paso-9--adoptar-una-planta-escaneando-el-qr-con-el-teléfono) (IP del PC, regla de
firewall, backend con `MATERA_CORS_ORIGENES` que incluya `http://<IP>:5500`, y front con
`--bind 0.0.0.0`). El PC y la ESP32 deben estar en la misma red; con el hotspot del teléfono suele
funcionar mejor que con la red de la universidad.

### Paso 3 — Compilar y cargar

Desde la carpeta del firmware (o con los botones de PlatformIO en VS Code):

| Entorno | Para qué | Comando |
|---|---|---|
| `simulacion` | Wokwi (ESP32 DevKit, define `SIMULACION`) | `pio run -e simulacion` |
| `real` | ESP32-C3 SuperMini por USB | `pio run -e real -t upload` y luego `pio device monitor` |
| `calibracion` | Programa aparte para medir los valores crudos de los sensores | `pio run -e calibracion -t upload` |

Si `pio` no está en el PATH, use `%USERPROFILE%\.platformio\penv\Scripts\pio.exe`.
`platformio.ini` usa la tabla de particiones `huge_app.csv`: el firmware ocupa ~1,3 MB y no cabe en
la partición por defecto.

**Wokwi:** compile el entorno `simulacion` y abra `diagram.json` con la extensión *Wokwi Simulator*
de VS Code (*Wokwi: Start Simulator*). `wokwi.toml` ya apunta a `firmware.merged.bin`. Mueva el
potenciómetro (humedad), la LDR (luz) y la temperatura del DS18B20 para ver cambiar el ánimo.

**Calibración (placa real):** con el entorno `calibracion`, anote el valor del sensor de suelo en
el aire y dentro de un vaso de agua, y póngalos en `SUELO_AIRE` / `SUELO_AGUA` de `src/main.cpp`.
Ajuste `RL10` con un luxómetro si lo tiene.

### Paso 4 — Vincular la matera

1. Al encender, la pantalla muestra **Conectando Wi-Fi...** y luego **Conectando con el servidor...**.
   El monitor serie (115200 baudios) imprime la MAC: `MAC: AA:BB:CC:DD:EE:FF`.
2. Sin token guardado, la matera se anuncia al backend (ventana de emparejamiento de 10 minutos) y
   muestra un **QR**.
3. Escanee el QR con el teléfono: abre `vincular.html?mac=...`. Inicie sesión, elija o cree la planta
   y confirme. También puede escribir la MAC a mano en el detalle de la planta → **Dispositivo**.
4. El backend entrega el token, la matera lo guarda en su memoria no volátil, se reinicia, se
   autentica y empieza a enviar una lectura cada `INTERVALO_LECTURA_MS`.
5. La pantalla muestra la mascota con H / L / T y su ánimo. En el front, el estado de la planta se
   actualiza solo.

Al **desvincular** desde el front, la matera recibe `{"tipo": "desvinculado"}`, borra su token, se
reinicia y vuelve a mostrar el QR. Si el backend rechaza su token tres veces seguidas (por ejemplo,
porque se borró la base de datos), hace lo mismo.

### Recuperación de conexiones caídas

Una conexión WebSocket puede morir sin cerrarse (el PC cambia de red, el hotspot se apaga, el
backend se reinicia). Para que nadie se quede congelado:

| Dónde | Mecanismo | Efecto |
|---|---|---|
| ESP32 (`conexion.h`) | Watchdog de aplicación: cada lectura debe recibir alguna respuesta (`diagnostico`, `mascota` o `error`). Tras 3 lecturas seguidas sin respuesta, `ws.disconnect()` | Reconecta y se vuelve a autenticar en ~15 s; la pantalla muestra **Conectando con el servidor...** mientras tanto |
| ESP32 (`conexion.h`) | `enableHeartbeat(15000, 3000, 2)`: ping cada 15 s | Detecta el socket muerto aunque no haya lecturas |
| ESP32 (`main.cpp`) | `WiFi.setSleep(false)` y `WiFi.setAutoReconnect(true)` | Menos cortes del radio; se reasocia solo al AP |
| Backend (`app.py`) | `SOCK_SERVER_OPTIONS = {"ping_interval": 25}` | Cierra los sockets sin pong y libera la conexión "operando" de esa MAC |
| Front (`app.js`) | Edad de la última lectura y advertencia tras 3 intervalos sin datos | El usuario ve que los datos están viejos |

### Ánimo de la mascota

El ánimo lo decide el backend (`EvaluadorAnimo`) con los parámetros ya evaluados contra los rangos
**de la especie**, así que la misma lectura puede dejar sedienta a una especie y feliz a otra. Las
reglas viven en la tabla `regla_animo`; si varias coinciden, gana la de menor prioridad, y si
ninguna coincide la planta está `FELIZ`:

| Parámetro | Estado | Ánimo | Prioridad |
|---|---|---|---|
| humedad | BAJO | `SEDIENTA` | 1 |
| temperatura | ALTO | `ACALORADA` | 2 |
| luz | BAJO | `DEPRIMIDA` | 3 |

Tras cada lectura, el backend envía `{"tipo": "mascota", "animo": "SEDIENTA"}` a la conexión
autenticada de esa MAC. Si la matera aún no lo ha recibido (sin conexión, o antes de la primera
lectura), la pantalla usa `animoSimulado()` de `main.cpp`, que tiene umbrales fijos y es **solo un
respaldo**.

Para cambiar una regla basta con editar su fila en `regla_animo`. Para agregar un ánimo nuevo hay que
añadirlo también al enum `Animo` (`matera/dominio/modelo.py`), al `CHECK` de las columnas `animo`
en `esquema.sql`, a `tipos.h` y a `ConexionWS::alMensaje` en `conexion.h`.

### Problemas comunes con la ESP32

| Síntoma | Causa probable | Solución |
|---|---|---|
| Se queda en **Sin Wi-Fi, reiniciando...** | SSID o contraseña mal escritos, o red de 5 GHz | Revise `config.h`; use una red de 2,4 GHz. En la SuperMini puede ayudar `WiFi.setTxPower(WIFI_POWER_8_5dBm)` en `conectarWifi()` |
| Se queda en **Conectando con el servidor...** | `BACKEND_HOST` incorrecto, backend apagado o firewall | Compruebe la IP con `ipconfig`, la regla de firewall y que `python Main.py` siga corriendo |
| El QR abre una página que no carga | `URL_FRONT` apunta a `127.0.0.1` o a una IP vieja | Ponga la IP actual del PC, vuelva a compilar y cargar |
| `The program size ... is greater than maximum allowed` | Partición por defecto | Verifique `board_build.partitions = huge_app.csv` en `platformio.ini` |
| La mascota no cambia aunque el diagnóstico sí | La matera no está autenticada (no hay conexión "operando") | Revise el monitor serie: debe llegar `<- {"tipo":"autenticado"}` y luego `<- {"tipo":"mascota",...}` |
| Lecturas con temperatura `-127` | DS18B20 desconectado o sin resistencia pull-up | Revise el cableado del pin de datos (el backend responde `error` a esas lecturas, pero la matera no se reconecta por eso) |
| El monitor serie repite `[WS] Sin respuesta del backend: reconectando` | El backend no contesta las lecturas (caído, reiniciándose o en otra IP) | Revise la terminal del backend y `BACKEND_HOST` |
| El front dice **en vivo · sin datos nuevos hace X s** | La matera dejó de enviar | Revise su pantalla y el monitor serie; debería reconectarse sola en ~15 s |

## Pruebas

```powershell
python -m unittest discover -s tests -v
```

| Archivo | Qué prueba |
|---|---|
| `tests/test_dominio.py` | Casos de uso con dobles de los puertos de salida (`tests/dobles.py`): lecturas en rango, fuera de rango e inválidas, regla de propiedad, vinculación, invitaciones, especies, cuentas y ánimo de la mascota (`EvaluadorAnimo`, notificación a la matera). Sin servidor, archivos ni BD (RA19). |
| `tests/test_arquitectura.py` | Ningún módulo de `matera/dominio` importa Flask, JWT, bcrypt, SQL, CSV, JSON ni adaptadores (RA4, RA12). |
| `tests/test_api.py` | Integración HTTP + SQLite temporal, con la tabla de referencia en CSV y en BD; `animo` en REST y en la respuesta WS, `ReglasAnimoBD` y migración de una BD con el esquema viejo. |

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

Las lecturas (`POST /dispositivos/<mac>/lecturas`, `GET /plantas/<id>/lecturas`, `ultima_lectura`
del detalle y el WS del front) incluyen `"animo"` en la raíz y dentro de `"diagnostico"`. En el
diagnóstico ad hoc (`POST /diagnosticos`) `animo` es `null`, porque no hay matera a la que mostrarlo.

Protocolo de `/ws/dispositivos` (JSON; `->` dispositivo a backend, `<-` backend a dispositivo):

```text
-> {"tipo": "anuncio", "mac": "AA:BB:CC:DD:EE:FF"}        <- {"tipo": "emparejando", "expira_en": ...}
<- {"tipo": "token", "token": "..."}                      -> {"tipo": "token_recibido"}
-> {"tipo": "autenticar", "mac": "...", "token": "..."}   <- {"tipo": "autenticado"}
-> {"tipo": "lectura", "humedad": 45, "luz": 300, "temperatura": 22, "tomada_en": "ISO-8601"}
                                                          <- {"tipo": "diagnostico", "animo": "FELIZ", ...}
                                                          <- {"tipo": "mascota", "animo": "FELIZ"}
<- {"tipo": "desvinculado"}
<- {"tipo": "error", "error": CODIGO, "mensaje": "..."}
```

Códigos: 400 dato ausente o no numérico · 401 sin identidad o credenciales inválidas ·
403 sin permiso sobre una planta propia/compartida · 404 recurso inexistente o ajeno ·
409 conflicto · 410 invitación no disponible · 422 valor fuera del rango físico ·
429 demasiados intentos · 502 no se pudo entregar el token al dispositivo.

## Estructura

```text
Main.py                         Arranque del servidor (lee HTTPS de variables de entorno)
simulador_esp32.py              Simulador del ESP32 (WS o HTTP)
configuracion/especies.csv|json Tabla de referencia
firmware/matera_esp32/matera_esp32/
  platformio.ini                Entornos simulacion (Wokwi), real (ESP32-C3) y calibracion
  diagram.json, wokwi.toml      Circuito y configuración de Wokwi
  src/main.cpp                  Sensores, fases (Wi-Fi, servidor, QR, operando) y animoSimulado (respaldo)
  src/conexion.h                WebSocket con el backend, token en memoria no volátil, mensaje "mascota"
  src/pantalla.h                OLED: QR, mascota y mensajes
  src/config.example.h          Plantilla de config.h (Wi-Fi, backend, pines)
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
    servicios/animo.py          EvaluadorAnimo: regla del ánimo de la mascota (función pura)
  adaptadores/
    entrada/http/               Controladores REST, JwtVerificador, LimitadorIntentos
    entrada/api_dispositivos.py LecturasController (HTTP) y WsDispositivoAdapter (WS)
    entrada/ws_front.py         WsFrontAdapter (estado en vivo para el navegador)
    salida/tabla_csv.py         AdapterCsv          ┐
    salida/tabla_json.py        AdapterJson         ├ ConsultarRangosPort
    salida/tabla_bd.py          SqliteEspecies      ┘ (+ RepositorioEspeciesPort)
    salida/sqlite_repository.py SqliteUsuarios, SqlitePlantas, SqliteDispositivos, SqliteInvitaciones
    salida/historial_bd.py      RepoLecturas (HistorialLecturasPort), guarda también el ánimo
    salida/reglas_animo_bd.py   ReglasAnimoBD (ReglasAnimoPort, tabla regla_animo)
    salida/auditoria_bd.py      SqliteAuditoria (AuditoriaPort)
    salida/seguridad.py         BcryptHasher, JwtAdapter, TokenOpacoGenerator
    salida/ws_notificador*.py   WsNotificador (estado al front), WsNotificadorDispositivo (token, ánimo, desvinculación)
    salida/esquema.sql          Esquema SQLite (diagrama entidad-relación)
    salida/datos_iniciales.sql  Reglas de ánimo iniciales (idempotente)
    salida/base_datos.py        Conexión SQLite y migración de BD existentes (migrar)
frontend/                       Cliente web estático
tests/                          Pruebas
```
