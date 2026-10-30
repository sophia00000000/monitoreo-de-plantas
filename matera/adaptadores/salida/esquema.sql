-- Esquema SQLite de la matera (fechas ISO-8601 UTC en TEXT, booleanos en INTEGER).
-- Corresponde al diagrama entidad-relacion del documento de arquitectura.

CREATE TABLE IF NOT EXISTS usuario (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT UNIQUE NOT NULL,
    nombre        TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    rol           TEXT NOT NULL DEFAULT 'USUARIO' CHECK (rol IN ('USUARIO', 'ADMIN')),
    activo        INTEGER NOT NULL DEFAULT 1,
    creado_en     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS parametro (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo     TEXT UNIQUE NOT NULL,
    unidad     TEXT NOT NULL,
    min_fisico REAL NOT NULL,
    max_fisico REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS especie (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre            TEXT UNIQUE NOT NULL,
    nombre_cientifico TEXT,
    fuente            TEXT NOT NULL,
    activa            INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS rango_referencia (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    especie_id   INTEGER NOT NULL REFERENCES especie (id),
    parametro_id INTEGER NOT NULL REFERENCES parametro (id),
    minimo       REAL NOT NULL,
    maximo       REAL NOT NULL,
    UNIQUE (especie_id, parametro_id),
    CHECK (minimo < maximo)
);

CREATE TABLE IF NOT EXISTS solicitud_especie (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id       INTEGER NOT NULL REFERENCES usuario (id),
    resuelta_por     INTEGER NULL REFERENCES usuario (id),
    especie_id       INTEGER NULL REFERENCES especie (id),
    nombre_propuesto TEXT NOT NULL,
    justificacion    TEXT,
    estado           TEXT NOT NULL CHECK (estado IN ('PENDIENTE', 'APROBADA', 'RECHAZADA')),
    creada_en        TEXT NOT NULL,
    resuelta_en      TEXT NULL
);

CREATE TABLE IF NOT EXISTS planta (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    especie_id INTEGER NOT NULL REFERENCES especie (id),
    apodo      TEXT NOT NULL,
    creada_en  TEXT NOT NULL,
    activa     INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS vinculo_planta (
    usuario_id INTEGER NOT NULL REFERENCES usuario (id),
    planta_id  INTEGER NOT NULL REFERENCES planta (id),
    tipo       TEXT NOT NULL CHECK (tipo IN ('PROPIETARIO', 'CUIDADOR')),
    creado_en  TEXT NOT NULL,
    PRIMARY KEY (usuario_id, planta_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_vinculo_un_propietario
    ON vinculo_planta (planta_id) WHERE tipo = 'PROPIETARIO';

CREATE TABLE IF NOT EXISTS invitacion (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    planta_id    INTEGER NOT NULL REFERENCES planta (id),
    creada_por   INTEGER NOT NULL REFERENCES usuario (id),
    canjeada_por INTEGER NULL REFERENCES usuario (id),
    token_hash   TEXT UNIQUE NOT NULL,
    estado       TEXT NOT NULL CHECK (estado IN ('PENDIENTE', 'CONSUMIDA', 'EXPIRADA', 'REVOCADA')),
    expira_en    TEXT NOT NULL,
    creada_en    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dispositivo (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    planta_id         INTEGER UNIQUE NULL REFERENCES planta (id),
    mac               TEXT UNIQUE NOT NULL,
    estado            TEXT NOT NULL CHECK (estado IN ('SIN_VINCULAR', 'EMPAREJANDO', 'VINCULADO', 'REVOCADO')),
    token_hash        TEXT NULL,
    ventana_expira_en TEXT NULL,
    registrado_en     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS medicion (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    planta_id      INTEGER NOT NULL REFERENCES planta (id),
    dispositivo_id INTEGER NULL REFERENCES dispositivo (id),
    tomada_en      TEXT NOT NULL,
    origen         TEXT NOT NULL CHECK (origen IN ('HTTP', 'WS'))
);

CREATE INDEX IF NOT EXISTS ix_medicion_planta_fecha ON medicion (planta_id, tomada_en);

CREATE TABLE IF NOT EXISTS medicion_valor (
    medicion_id  INTEGER NOT NULL REFERENCES medicion (id),
    parametro_id INTEGER NOT NULL REFERENCES parametro (id),
    valor        REAL NOT NULL,
    PRIMARY KEY (medicion_id, parametro_id)
);

CREATE TABLE IF NOT EXISTS diagnostico (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    medicion_id   INTEGER UNIQUE NOT NULL REFERENCES medicion (id),
    estado_global TEXT NOT NULL CHECK (estado_global IN ('SALUDABLE', 'EN_RIESGO', 'CRITICO')),
    evaluado_en   TEXT NOT NULL
);

-- minimo y maximo guardan el rango usado al evaluar, para que el historial no cambie
-- si el admin edita la especie despues.
CREATE TABLE IF NOT EXISTS diagnostico_detalle (
    diagnostico_id INTEGER NOT NULL REFERENCES diagnostico (id),
    parametro_id   INTEGER NOT NULL REFERENCES parametro (id),
    estado         TEXT NOT NULL CHECK (estado IN ('BAJO', 'OPTIMO', 'ALTO')),
    recomendacion  TEXT NULL,
    minimo         REAL NULL,
    maximo         REAL NULL,
    PRIMARY KEY (diagnostico_id, parametro_id)
);

CREATE TABLE IF NOT EXISTS auditoria (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id     INTEGER NULL REFERENCES usuario (id),
    dispositivo_id INTEGER NULL REFERENCES dispositivo (id),
    planta_id      INTEGER NULL REFERENCES planta (id),
    evento         TEXT NOT NULL CHECK (evento IN (
        'EMPAREJAMIENTO', 'VINCULACION', 'VINCULACION_REVERTIDA',
        'DESVINCULACION', 'CANJE', 'INTENTO_FALLIDO', 'ACCESO_ADMIN')),
    detalle        TEXT NULL,
    ocurrido_en    TEXT NOT NULL
);
