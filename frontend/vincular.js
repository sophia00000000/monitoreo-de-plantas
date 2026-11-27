
// ---------------------------------------------------------
// CONFIGURACION
// ---------------------------------------------------------

const API_BASE = window.MATERA_API ||
    `${location.protocol}//${location.hostname}:5000`;

const API = `${API_BASE}/api/v1`;

// MAC recibida desde el QR del ESP32.
const mac = new URLSearchParams(location.search).get("mac");

// Sesion existente, si la hay.
let sesion = leerSesion();

// Si ya se creo una planta pero fallo la vinculacion,
// conservamos su ID para poder reintentar.
let plantaPendiente = null;


// ---------------------------------------------------------
// ELEMENTOS
// ---------------------------------------------------------

const $ = (selector) => document.querySelector(selector);

const seccionAcceso = $("#seccion-acceso");
const seccionPlanta = $("#seccion-planta");
const seccionResultado = $("#seccion-resultado");


// ---------------------------------------------------------
// SESION
// ---------------------------------------------------------

function leerSesion() {
    try {
        return JSON.parse(sessionStorage.getItem("matera_sesion"));
    } catch {
        return null;
    }
}

function guardarSesion(datos) {
    sesion = datos;

    try {
        sessionStorage.setItem(
            "matera_sesion",
            JSON.stringify(datos)
        );
    } catch {
        // El almacenamiento puede no estar disponible.
    }
}


// ---------------------------------------------------------
// MENSAJES
// ---------------------------------------------------------

function mostrarMensaje(mensaje, tipo = "ok") {
    const elemento = $("#mensaje");

    elemento.textContent = mensaje;
    elemento.className = `aviso ${tipo}`;
}

function ocultarMensaje() {
    $("#mensaje").classList.add("oculto");
}


// ---------------------------------------------------------
// API
// ---------------------------------------------------------

async function api(ruta, opciones = {}) {
    const {
        metodo = "GET",
        cuerpo,
        autenticado = true
    } = opciones;

    const cabeceras = {};

    if (cuerpo !== undefined) {
        cabeceras["Content-Type"] = "application/json";
    }

    if (autenticado && sesion) {
        cabeceras.Authorization = `Bearer ${sesion.token}`;
    }

    const respuesta = await fetch(`${API}${ruta}`, {
        method: metodo,
        headers: cabeceras,
        body: cuerpo !== undefined
            ? JSON.stringify(cuerpo)
            : undefined
    });

    const datos = respuesta.status === 204
        ? null
        : await respuesta.json().catch(() => null);

    if (!respuesta.ok) {
        throw new Error(
            datos?.mensaje || `Error ${respuesta.status}`
        );
    }

    return datos;
}


// ---------------------------------------------------------
// COMPROBAR MAC
// ---------------------------------------------------------

function comprobarMac() {
    if (!mac) {
        $("#estado-mac").textContent =
            "No se recibió la MAC del dispositivo.";

        $("#seccion-acceso").classList.add("oculto");
        $("#seccion-planta").classList.add("oculto");

        return false;
    }

    const formatoMac = /^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$/;

    if (!formatoMac.test(mac)) {
        $("#estado-mac").textContent =
            "La dirección MAC recibida no es válida.";

        return false;
    }

    $("#estado-mac").textContent =
        "Dispositivo detectado correctamente.";

    $("#mac-dispositivo").textContent = `MAC: ${mac}`;

    return true;
}


// ---------------------------------------------------------
// CATALOGO DE ESPECIES
// ---------------------------------------------------------

async function cargarEspecies() {
    const datos = await api("/especies", {
        autenticado: false
    });

    const selector = $("#especie");

    selector.innerHTML = `
        <option value="">Selecciona una especie</option>
    `;

    datos.especies.forEach((especie) => {
        const opcion = document.createElement("option");

        opcion.value = especie.nombre;
        opcion.textContent =
            especie.nombre_cientifico || especie.nombre;

        selector.appendChild(opcion);
    });
}


// ---------------------------------------------------------
// MOSTRAR SECCIONES
// ---------------------------------------------------------

function mostrarAcceso() {
    seccionAcceso.classList.remove("oculto");
    seccionPlanta.classList.add("oculto");
    seccionResultado.classList.add("oculto");
}

async function mostrarRegistroPlanta() {
    seccionAcceso.classList.add("oculto");
    seccionPlanta.classList.remove("oculto");
    seccionResultado.classList.add("oculto");

    await cargarEspecies();
}


// ---------------------------------------------------------
// INICIAR SESION
// ---------------------------------------------------------

$("#form-login").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    ocultarMensaje();

    try {
        const datos = Object.fromEntries(
            new FormData(evento.target).entries()
        );

        const resultado = await api("/auth/login", {
            metodo: "POST",
            cuerpo: datos,
            autenticado: false
        });

        guardarSesion(resultado);

        evento.target.reset();

        await mostrarRegistroPlanta();

    } catch (error) {
        mostrarMensaje(error.message, "error");
    }
});


// ---------------------------------------------------------
// REGISTRAR CUENTA
// ---------------------------------------------------------

$("#form-registro").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    ocultarMensaje();

    try {
        const datos = Object.fromEntries(
            new FormData(evento.target).entries()
        );

        await api("/auth/registro", {
            metodo: "POST",
            cuerpo: datos,
            autenticado: false
        });

        // Iniciar sesion automaticamente despues del registro.
        const resultado = await api("/auth/login", {
            metodo: "POST",
            cuerpo: {
                usuario: datos.nombre,
                password: datos.password
            },
            autenticado: false
        });

        guardarSesion(resultado);

        evento.target.reset();

        await mostrarRegistroPlanta();

    } catch (error) {
        mostrarMensaje(error.message, "error");
    }
});


// ---------------------------------------------------------
// CREAR PLANTA Y VINCULAR DISPOSITIVO
// ---------------------------------------------------------

$("#form-planta").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    ocultarMensaje();

    const boton = $("#btn-vincular");

    boton.disabled = true;
    boton.textContent = "Procesando...";

    try {
        // PASO 1: Crear la planta, si todavía no existe.
        if (!plantaPendiente) {
            const datos = Object.fromEntries(
                new FormData(evento.target).entries()
            );

            const planta = await api("/plantas", {
                metodo: "POST",
                cuerpo: datos
            });

            plantaPendiente = planta.id;
        }

        // PASO 2: Vincular la MAC a la planta creada.
        await api(`/plantas/${plantaPendiente}/dispositivo`, {
            metodo: "POST",
            cuerpo: {
                mac: mac
            }
        });

        // PASO 3: Mostrar confirmacion.
        seccionPlanta.classList.add("oculto");
        seccionAcceso.classList.add("oculto");
        seccionResultado.classList.remove("oculto");

        $("#resultado-texto").textContent =
            "La planta se creó y el dispositivo fue vinculado correctamente. " +
            "El ESP32 recibirá su token mediante WebSocket.";

        plantaPendiente = null;

    } catch (error) {
        mostrarMensaje(error.message, "error");

    } finally {
        boton.disabled = false;
        boton.textContent = "Crear planta y vincular dispositivo";
    }
});


// ---------------------------------------------------------
// INICIO
// ---------------------------------------------------------

async function iniciar() {
    if (!comprobarMac()) {
        return;
    }

    try {
        if (sesion?.token) {
            // Comprobar que el token sigue siendo válido.
            await api("/plantas");

            await mostrarRegistroPlanta();

        } else {
            mostrarAcceso();
        }

    } catch (error) {
        // Si la sesion expiro, solicitar un nuevo inicio de sesion.
        sesion = null;

        try {
            sessionStorage.removeItem("matera_sesion");
        } catch {
            // Sin almacenamiento.
        }

        mostrarAcceso();
        mostrarMensaje(
            "Tu sesión expiró. Inicia sesión nuevamente.",
            "error"
        );
    }
}

iniciar();
