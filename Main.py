"""Punto de entrada del backend. La composicion vive en matera/app.py (create_app)."""
import os

from matera.app import create_app

app = create_app()


if __name__ == "__main__":
    certificado = os.environ.get("MATERA_SSL_CERT")
    llave = os.environ.get("MATERA_SSL_KEY")
    ssl_context = (certificado, llave) if certificado and llave else None
    if ssl_context is None:
        print("AVISO: sin MATERA_SSL_CERT/MATERA_SSL_KEY el servidor usa HTTP/WS sin cifrar (solo desarrollo).")
    app.run(
        host=os.environ.get("MATERA_HOST", "127.0.0.1"),
        port=int(os.environ.get("MATERA_PUERTO", "5000")),
        debug=False,
        threaded=True,
        ssl_context=ssl_context,
    )
