# Sistema de diagnostico de plantas

API REST en Python con Flask para evaluar el estado de una planta a partir de su especie, humedad, iluminacion y temperatura.

El proyecto tiene dos procesos independientes:

- Backend: API Flask, responde exclusivamente JSON.
- Frontend: HTML, CSS y JavaScript estaticos, servido en un origen separado.

## Requisitos

- Python 3.10 o superior
- PowerShell en Windows

## Instalacion

Desde la raiz del proyecto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Si PowerShell no permite activar el entorno virtual, se puede usar directamente su interprete:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Ejecucion del backend

En una terminal, desde la raiz del proyecto:

```powershell
.\.venv\Scripts\python.exe Main.py
```

La API queda disponible en:

```text
http://127.0.0.1:5000
```

El backend no sirve HTML. Sus endpoints responden JSON.

## Ejecucion del frontend

Con el backend ejecutandose, abrir una segunda terminal en la raiz del proyecto y ejecutar:

```powershell
.\.venv\Scripts\python.exe -m http.server 5500 --directory frontend
```

Abrir en el navegador:

```text
http://127.0.0.1:5500/
```

El frontend consume la API mediante `fetch`. CORS esta configurado para permitir `http://127.0.0.1:5500`.

## Pruebas unitarias

Las pruebas ejercitan el dominio sin levantar Flask y sin leer el CSV real. Usan un adaptador en memoria como doble de prueba.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Endpoints

### Listar especies

```http
GET http://127.0.0.1:5000/api/plantas
```

### Evaluar una planta

```http
POST http://127.0.0.1:5000/api/evaluar
Content-Type: application/json
```

Cuerpo de ejemplo:

```json
{
  "especie": "sansevieria",
  "humedad": 40,
  "iluminacion": 300,
  "temperatura": 22
}
```

Unidades:

- `humedad`: porcentaje, de 0 a 100 `%`.
- `iluminacion`: lux, valor mayor o igual a 0.
- `temperatura`: grados Celsius, entre -50 y 60 `C`.

La respuesta clasifica cada parametro como `BAJO`, `OPTIMO` o `ALTO` y calcula el `indice_vitalidad` como `SALUDABLE`, `EN_RIESGO` o `CRITICO`.

## Especies configuradas

La tabla de referencia se encuentra en [configuracion/plantas.csv](configuracion/plantas.csv) e incluye:

- Sansevieria trifasciata
- Aloe vera
- Ficus elastica
- Tradescantia zebrina
- Epipremnum aureum, potos

## Estructura principal

```text
app.py                 Composicion del backend
Main.py                Punto de entrada del servidor Flask
controladores/         Endpoints REST y validacion HTTP
servicios/             Casos de uso de aplicacion
dominio/               Modelos, reglas, normalizacion y puertos
repositorios/          Transformacion de configuracion a entidades
adaptadores/           Implementaciones CSV y JSON
configuracion/         Tabla de rangos de referencia
frontend/              Cliente web estatico
static/                Recursos antiguos del frontend
tests/                 Pruebas unitarias del dominio
```
