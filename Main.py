"""Punto de entrada del backend. La composicion vive en matera/app.py (create_app)."""
import os
import socket
import sys

from matera.app import create_app


def puerto_ocupado(host: str, puerto: int) -> bool:
    """En Windows dos procesos pueden escuchar el mismo puerto y repartirse las peticiones."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as prueba:
        prueba.settimeout(0.5)
        return prueba.connect_ex((host, puerto)) == 0


app = create_app()


if __name__ == "__main__":
    host = os.environ.get("MATERA_HOST", "127.0.0.1")
    puerto = int(os.environ.get("MATERA_PUERTO", "5000"))
    if puerto_ocupado(host, puerto):
        sys.exit(f"ERROR: ya hay un servidor escuchando en {host}:{puerto}. Cierrelo (Ctrl+C en su terminal) "
                 "o use otro puerto con MATERA_PUERTO.")
    certificado = os.environ.get("MATERA_SSL_CERT")
    llave = os.environ.get("MATERA_SSL_KEY")
    ssl_context = (certificado, llave) if certificado and llave else None
    if ssl_context is None:
        print("AVISO: sin MATERA_SSL_CERT/MATERA_SSL_KEY el servidor usa HTTP/WS sin cifrar (solo desarrollo).")
    app.run(
        host=host,
        port=puerto,
        debug=False,
        threaded=True,
        ssl_context=ssl_context,
    )
