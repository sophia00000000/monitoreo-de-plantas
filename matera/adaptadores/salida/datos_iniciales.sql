-- Datos iniciales idempotentes. Se ejecuta despues de registrar los parametros (necesita sus id).

-- Animo de la mascota (antes estaba fijo en animoSimulado() del firmware, sin tener en cuenta la especie).
INSERT OR IGNORE INTO regla_animo (parametro_id, estado, animo, prioridad)
    SELECT id, 'BAJO', 'SEDIENTA', 1 FROM parametro WHERE codigo = 'humedad';
INSERT OR IGNORE INTO regla_animo (parametro_id, estado, animo, prioridad)
    SELECT id, 'ALTO', 'ACALORADA', 2 FROM parametro WHERE codigo = 'temperatura';
INSERT OR IGNORE INTO regla_animo (parametro_id, estado, animo, prioridad)
    SELECT id, 'BAJO', 'DEPRIMIDA', 3 FROM parametro WHERE codigo = 'luz';
