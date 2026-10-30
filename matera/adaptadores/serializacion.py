"""Traduccion de objetos del dominio a diccionarios JSON (DTO de salida), compartida por HTTP y WS."""
from datetime import datetime

from matera.dominio.modelo import (
    PARAMETROS,
    Diagnostico,
    Dispositivo,
    Especie,
    Medicion,
    Planta,
    PlantaDetalle,
    SolicitudEspecie,
    Usuario,
)


def fecha(valor: datetime | None) -> str | None:
    return valor.isoformat() if valor else None


def especie_a_json(especie: Especie) -> dict:
    return {
        "nombre": especie.nombre,
        "nombre_cientifico": especie.nombre_cientifico,
        "fuente": especie.fuente,
        "activa": especie.activa,
        "rangos": [
            {
                "parametro": codigo,
                "unidad": PARAMETROS[codigo].unidad if codigo in PARAMETROS else "",
                "minimo": rango.minimo,
                "maximo": rango.maximo,
            }
            for codigo, rango in especie.rangos.items()
        ],
    }


def diagnostico_a_json(diagnostico: Diagnostico) -> dict:
    return {
        "especie": diagnostico.especie,
        "estado_global": diagnostico.estado_global.value,
        "parametros": [
            {
                "parametro": p.parametro,
                "valor": p.valor,
                "unidad": p.unidad,
                "minimo": p.minimo,
                "maximo": p.maximo,
                "estado": p.estado.value,
                "recomendacion": p.recomendacion,
            }
            for p in diagnostico.parametros
        ],
        "recomendaciones": diagnostico.recomendaciones,
    }


def medicion_a_json(medicion: Medicion) -> dict:
    return {
        "id": medicion.id,
        "planta_id": medicion.planta_id,
        "dispositivo_id": medicion.dispositivo_id,
        "tomada_en": fecha(medicion.tomada_en),
        "origen": medicion.origen.value,
        "valores": dict(medicion.lectura.valores),
        "diagnostico": diagnostico_a_json(medicion.diagnostico),
    }


def planta_a_json(planta: Planta) -> dict:
    return {
        "id": planta.id,
        "apodo": planta.apodo,
        "especie": planta.especie,
        "creada_en": fecha(planta.creada_en),
    }


def dispositivo_a_json(dispositivo: Dispositivo | None) -> dict | None:
    if dispositivo is None:
        return None
    return {"id": dispositivo.id, "mac": dispositivo.mac, "estado": dispositivo.estado.value}


def planta_detalle_a_json(detalle: PlantaDetalle) -> dict:
    ultima = detalle.ultima_medicion
    return {
        **planta_a_json(detalle.planta),
        "vinculo": detalle.vinculo.value if detalle.vinculo else None,
        "dispositivo": dispositivo_a_json(detalle.dispositivo),
        "estado_actual": ultima.diagnostico.estado_global.value if ultima else None,
        "ultima_lectura": medicion_a_json(ultima) if ultima else None,
    }


def usuario_a_json(usuario: Usuario) -> dict:
    return {
        "id": usuario.id,
        "nombre": usuario.nombre,
        "email": usuario.email,
        "rol": usuario.rol.value,
        "activo": usuario.activo,
        "creado_en": fecha(usuario.creado_en),
    }


def solicitud_a_json(solicitud: SolicitudEspecie) -> dict:
    return {
        "id": solicitud.id,
        "usuario_id": solicitud.usuario_id,
        "nombre_propuesto": solicitud.nombre_propuesto,
        "justificacion": solicitud.justificacion,
        "estado": solicitud.estado.value,
        "creada_en": fecha(solicitud.creada_en),
        "resuelta_en": fecha(solicitud.resuelta_en),
    }
