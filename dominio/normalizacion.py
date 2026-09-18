def normalizar_especie(especie: str) -> str:
    """Devuelve la clave canonica usada para guardar y buscar especies."""
    return " ".join(especie.strip().lower().split())
