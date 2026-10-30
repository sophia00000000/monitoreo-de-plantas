// Cliente web de la matera: consume la API JSON con fetch y recibe el estado en vivo por WebSocket.
// La API vive en el mismo equipo que sirve el front, en el puerto 5000. Usar location.hostname
// permite abrir el front desde otro dispositivo de la red (p. ej. el telefono que escanea el QR).
const API_BASE = window.MATERA_API || `${location.protocol}//${location.hostname}:5000`;
const API = `${API_BASE}/api/v1`;
const WS_URL = API_BASE.replace(/^http/, "ws") + "/ws/front";
const CONSULTA_PERIODICA_MS = 15000;
const PARAMETROS = [
    { codigo: "humedad", nombre: "Humedad", unidad: "%" },
    { codigo: "luz", nombre: "Luz", unidad: "lux" },
    { codigo: "temperatura", nombre: "Temperatura", unidad: "C" },
];

const estado = {
    sesion: leerSesion(),
    especies: [],
    plantas: [],
    plantaAbierta: null,
    socket: null,
    temporizador: null,
};

// ------------------------------------------------------------------ utilidades

const $ = (selector) => document.querySelector(selector);

function esc(valor) {
    return String(valor ?? "").replace(/[&<>"']/g, (c) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[c]);
}

function leerSesion() {
    try { return JSON.parse(sessionStorage.getItem("matera_sesion")); } catch { return null; }
}

function guardarSesion(sesion) {
    estado.sesion = sesion;
    try {
        if (sesion) sessionStorage.setItem("matera_sesion", JSON.stringify(sesion));
        else sessionStorage.removeItem("matera_sesion");
    } catch { /* almacenamiento no disponible */ }
}

function avisar(mensaje, tipo = "ok") {
    const aviso = $("#aviso");
    aviso.textContent = mensaje;
    aviso.className = `aviso ${tipo}`;
    clearTimeout(avisar.t);
    avisar.t = setTimeout(() => aviso.classList.add("oculto"), 5000);
}

function fecha(iso) {
    return iso ? new Date(iso).toLocaleString() : "-";
}

function claseEstado(valor) {
    return { SALUDABLE: "bueno", OPTIMO: "bueno", EN_RIESGO: "medio", CRITICO: "malo", BAJO: "malo", ALTO: "malo" }[valor] || "";
}

function datosFormulario(form) {
    return Object.fromEntries(new FormData(form).entries());
}

async function api(ruta, { metodo = "GET", cuerpo, autenticado = true } = {}) {
    const cabeceras = {};
    if (cuerpo !== undefined) cabeceras["Content-Type"] = "application/json";
    if (autenticado && estado.sesion) cabeceras.Authorization = `Bearer ${estado.sesion.token}`;
    const respuesta = await fetch(`${API}${ruta}`, {
        method: metodo,
        headers: cabeceras,
        body: cuerpo !== undefined ? JSON.stringify(cuerpo) : undefined,
    });
    const datos = respuesta.status === 204 ? null : await respuesta.json().catch(() => null);
    if (!respuesta.ok) {
        if (respuesta.status === 401 && autenticado && estado.sesion) {
            cerrarSesion();
            throw new Error("Tu sesion expiro. Vuelve a iniciar sesion.");
        }
        throw new Error(datos?.mensaje || `Error ${respuesta.status}`);
    }
    return datos;
}

async function accion(fn) {
    try { await fn(); } catch (error) { avisar(error.message, "error"); }
}

// ------------------------------------------------------------------ navegacion y sesion

function mostrarVista(nombre) {
    if ((nombre === "plantas" || nombre === "solicitudes" || nombre === "admin") && !estado.sesion) nombre = "acceso";
    document.querySelectorAll(".vista").forEach((v) => v.classList.add("oculto"));
    $(`#vista-${nombre}`).classList.remove("oculto");
    document.querySelectorAll("#pestanas button").forEach((b) => b.classList.toggle("activa", b.dataset.vista === nombre));
    if (nombre === "plantas") cargarPlantas();
    if (nombre === "solicitudes") cargarMisSolicitudes();
    if (nombre === "admin") cargarAdmin();
}

function pintarSesion() {
    const usuario = estado.sesion?.usuario;
    document.body.classList.toggle("con-sesion", Boolean(usuario));
    document.body.classList.toggle("es-admin", usuario?.rol === "ADMIN");
    $("#sesion").innerHTML = usuario
        ? `<span>${esc(usuario.nombre)} <small>${esc(usuario.rol)}</small></span><button id="salir" class="secundario">Salir</button>`
        : `<button id="entrar">Iniciar sesion</button>`;
    $("#salir")?.addEventListener("click", cerrarSesion);
    $("#entrar")?.addEventListener("click", () => mostrarVista("acceso"));
}

function iniciarSesion(sesion) {
    guardarSesion(sesion);
    pintarSesion();
    conectarTiempoReal();
    clearInterval(estado.temporizador);
    estado.temporizador = setInterval(() => estado.sesion && cargarPlantas(false), CONSULTA_PERIODICA_MS);
    mostrarVista("plantas");
    canjearPendiente();
}

function cerrarSesion() {
    guardarSesion(null);
    clearInterval(estado.temporizador);
    estado.socket?.close();
    estado.socket = null;
    estado.plantas = [];
    estado.plantaAbierta = null;
    pintarSesion();
    mostrarVista("diagnostico");
}

// ------------------------------------------------------------------ catalogo y diagnostico ad hoc

async function cargarEspecies() {
    const datos = await api("/especies", { autenticado: false });
    estado.especies = datos.especies;
    const opciones = estado.especies.map((e) =>
        `<option value="${esc(e.nombre)}">${esc(e.nombre_cientifico || e.nombre)}</option>`).join("");
    document.querySelectorAll(".select-especies").forEach((s) => { s.innerHTML = opciones; });
    $("#catalogo").innerHTML = estado.especies.map((e) => `
        <article class="ficha">
            <strong>${esc(e.nombre_cientifico || e.nombre)}</strong><small>${esc(e.nombre)}</small>
            <ul>${e.rangos.map((r) => `<li>${esc(r.parametro)}: ${r.minimo} - ${r.maximo} ${esc(r.unidad)}</li>`).join("")}</ul>
        </article>`).join("");
}

function htmlDiagnostico(d, titulo = "") {
    return `
        <div class="resultado">
            <div class="resultado-cabecera">
                <div><span class="etiqueta">${esc(d.especie)}</span>${titulo ? `<h3>${esc(titulo)}</h3>` : ""}</div>
                <strong class="estado ${claseEstado(d.estado_global)}">${esc(d.estado_global)}</strong>
            </div>
            <div class="criterios">${d.parametros.map((p) => `
                <article class="criterio">
                    <h4>${esc(p.parametro)}</h4>
                    <p>${p.valor} ${esc(p.unidad)}</p>
                    <small>rango ${p.minimo} - ${p.maximo} ${esc(p.unidad)}</small>
                    <span class="estado ${claseEstado(p.estado)}">${esc(p.estado)}</span>
                </article>`).join("")}
            </div>
            ${d.recomendaciones.length ? `<ul class="recomendaciones">${d.recomendaciones.map((r) => `<li>${esc(r)}</li>`).join("")}</ul>` : ""}
        </div>`;
}

$("#form-diagnostico").addEventListener("submit", (evento) => {
    evento.preventDefault();
    accion(async () => {
        const datos = datosFormulario(evento.target);
        const diagnostico = await api("/diagnosticos", { metodo: "POST", cuerpo: datos, autenticado: false });
        $("#resultado-diagnostico").innerHTML = htmlDiagnostico(diagnostico);
    });
});

// ------------------------------------------------------------------ acceso

$("#form-login").addEventListener("submit", (evento) => {
    evento.preventDefault();
    accion(async () => {
        const sesion = await api("/auth/login", { metodo: "POST", cuerpo: datosFormulario(evento.target), autenticado: false });
        evento.target.reset();
        iniciarSesion(sesion);
        avisar(`Hola, ${sesion.usuario.nombre}`);
    });
});

$("#form-registro").addEventListener("submit", (evento) => {
    evento.preventDefault();
    accion(async () => {
        const datos = datosFormulario(evento.target);
        await api("/auth/registro", { metodo: "POST", cuerpo: datos, autenticado: false });
        const sesion = await api("/auth/login", {
            metodo: "POST", cuerpo: { usuario: datos.nombre, password: datos.password }, autenticado: false,
        });
        evento.target.reset();
        iniciarSesion(sesion);
        avisar("Cuenta creada.");
    });
});

// ------------------------------------------------------------------ plantas

async function cargarPlantas(conAvisos = true) {
    try {
        const datos = await api("/plantas");
        estado.plantas = datos.plantas;
        pintarPlantas();
        suscribirPlantas();
        if (estado.plantaAbierta && !estado.plantas.some((p) => p.id === estado.plantaAbierta.id)) {
            estado.plantaAbierta = null;
            $("#detalle-planta").innerHTML = "";
        }
    } catch (error) {
        if (conAvisos) avisar(error.message, "error");
    }
}

function pintarPlantas() {
    const lista = $("#lista-plantas");
    if (!estado.plantas.length) {
        lista.innerHTML = `<p class="ayuda">Aun no tienes plantas. Crea una o canjea una invitacion.</p>`;
        return;
    }
    lista.innerHTML = estado.plantas.map((p) => {
        const valores = p.ultima_lectura?.valores || {};
        return `
        <button class="tarjeta ${estado.plantaAbierta?.id === p.id ? "seleccionada" : ""}" data-planta="${p.id}">
            <span class="etiqueta">${esc(p.especie)} · ${esc(p.vinculo || "ADMIN")}</span>
            <strong>${esc(p.apodo)}</strong>
            <span class="estado ${claseEstado(p.estado_actual)}">${esc(p.estado_actual || "SIN LECTURAS")}</span>
            <small>${PARAMETROS.map((x) => valores[x.codigo] !== undefined ? `${valores[x.codigo]} ${x.unidad}` : "").filter(Boolean).join(" · ") || "Sin dispositivo reportando"}</small>
            <small>${p.ultima_lectura ? `Actualizado ${fecha(p.ultima_lectura.tomada_en)}` : ""}</small>
        </button>`;
    }).join("");
    lista.querySelectorAll("[data-planta]").forEach((b) =>
        b.addEventListener("click", () => abrirPlanta(Number(b.dataset.planta))));
}

$("#form-planta").addEventListener("submit", (evento) => {
    evento.preventDefault();
    accion(async () => {
        const planta = await api("/plantas", { metodo: "POST", cuerpo: datosFormulario(evento.target) });
        evento.target.reset();
        avisar(`Planta "${planta.apodo}" creada.`);
        await cargarPlantas();
        abrirPlanta(planta.id);
    });
});

$("#form-canje").addEventListener("submit", (evento) => {
    evento.preventDefault();
    accion(async () => {
        const planta = await api("/invitaciones/canje", { metodo: "POST", cuerpo: datosFormulario(evento.target) });
        evento.target.reset();
        avisar(`Ahora cuidas "${planta.apodo}".`);
        await cargarPlantas();
        abrirPlanta(planta.id);
    });
});

async function abrirPlanta(id) {
    await accion(async () => {
        const planta = await api(`/plantas/${id}`);
        estado.plantaAbierta = planta;
        pintarPlantas();
        pintarDetalle();
        await cargarHistorial();
    });
}

function pintarDetalle() {
    const p = estado.plantaAbierta;
    const esPropietario = p.vinculo === "PROPIETARIO";
    const puedeGestionar = esPropietario || estado.sesion.usuario.rol === "ADMIN";
    const opcionesEspecie = estado.especies.map((e) =>
        `<option value="${esc(e.nombre)}" ${e.nombre === p.especie ? "selected" : ""}>${esc(e.nombre_cientifico || e.nombre)}</option>`).join("");

    $("#detalle-planta").innerHTML = `
    <section class="panel detalle">
        <div class="titulo-fila">
            <div><span class="etiqueta">${esc(p.especie)} · ${esc(p.vinculo || "acceso de administrador")}</span><h2>${esc(p.apodo)}</h2></div>
            <button id="cerrar-detalle" class="secundario">Cerrar</button>
        </div>

        <h3>Estado actual</h3>
        <div id="estado-planta">${p.ultima_lectura
            ? htmlDiagnostico(p.ultima_lectura.diagnostico, `Lectura del ${fecha(p.ultima_lectura.tomada_en)}`)
            : `<p class="ayuda">Todavia no hay lecturas. Vincula un dispositivo para empezar.</p>`}</div>

        <div class="dos-columnas">
            <div>
                <h3>Dispositivo</h3>
                ${p.dispositivo
                    ? `<p>MAC <code>${esc(p.dispositivo.mac)}</code> <span class="estado bueno">${esc(p.dispositivo.estado)}</span></p>
                       ${puedeGestionar ? `<button id="desvincular-dispositivo" class="peligro">Desvincular dispositivo</button>` : ""}`
                    : puedeGestionar
                        ? `<form id="form-vincular" class="pila">
                              <p class="ayuda">Enciende el dispositivo (o el simulador) para que entre en emparejamiento y escribe su MAC.</p>
                              <label>MAC <input name="mac" placeholder="AA:BB:CC:DD:EE:01" required></label>
                              <button type="submit">Vincular</button>
                           </form>`
                        : `<p class="ayuda">Sin dispositivo vinculado.</p>`}
            </div>
            <div>
                ${esPropietario ? `
                <h3>Compartir</h3>
                <p class="ayuda">Genera un codigo QR de un solo uso para que otra persona cuide esta planta.</p>
                <button id="generar-invitacion">Generar invitacion</button>
                <div id="invitacion"></div>` : ""}
            </div>
        </div>

        ${puedeGestionar ? `
        <h3>Editar</h3>
        <form id="form-editar" class="fila-form">
            <label>Apodo <input name="apodo" value="${esc(p.apodo)}" maxlength="60" required></label>
            <label>Especie <select name="especie">${opcionesEspecie}</select></label>
            <button type="submit">Guardar</button>
            <button type="button" id="eliminar-planta" class="peligro">Eliminar planta</button>
        </form>` : ""}
        ${p.vinculo === "CUIDADOR" ? `<button id="dejar-de-cuidar" class="peligro">Dejar de cuidar esta planta</button>` : ""}

        <h3>Historial</h3>
        <form id="form-historial" class="fila-form">
            <label>Desde <input name="desde" type="datetime-local"></label>
            <label>Hasta <input name="hasta" type="datetime-local"></label>
            <button type="submit">Filtrar</button>
        </form>
        <div id="historial"></div>
    </section>`;

    $("#cerrar-detalle").addEventListener("click", () => {
        estado.plantaAbierta = null;
        $("#detalle-planta").innerHTML = "";
        pintarPlantas();
    });
    $("#form-vincular")?.addEventListener("submit", (evento) => {
        evento.preventDefault();
        accion(async () => {
            avisar("Vinculando... esperando confirmacion del dispositivo.");
            await api(`/plantas/${p.id}/dispositivo`, { metodo: "POST", cuerpo: datosFormulario(evento.target) });
            avisar("Dispositivo vinculado.");
            await recargarPlantaAbierta();
        });
    });
    $("#desvincular-dispositivo")?.addEventListener("click", () => accion(async () => {
        if (!confirm("Se revocara el token del dispositivo. Continuar?")) return;
        await api(`/plantas/${p.id}/dispositivo`, { metodo: "DELETE" });
        avisar("Dispositivo desvinculado.");
        await recargarPlantaAbierta();
    }));
    $("#generar-invitacion")?.addEventListener("click", () => accion(generarInvitacion));
    $("#form-editar")?.addEventListener("submit", (evento) => {
        evento.preventDefault();
        accion(async () => {
            await api(`/plantas/${p.id}`, { metodo: "PATCH", cuerpo: datosFormulario(evento.target) });
            avisar("Cambios guardados.");
            await recargarPlantaAbierta();
        });
    });
    $("#eliminar-planta")?.addEventListener("click", () => accion(async () => {
        if (!confirm(`Eliminar "${p.apodo}"? Tambien se revoca su dispositivo.`)) return;
        await api(`/plantas/${p.id}`, { metodo: "DELETE" });
        estado.plantaAbierta = null;
        $("#detalle-planta").innerHTML = "";
        avisar("Planta eliminada.");
        await cargarPlantas();
    }));
    $("#dejar-de-cuidar")?.addEventListener("click", () => accion(async () => {
        await api(`/plantas/${p.id}/vinculo`, { metodo: "DELETE" });
        estado.plantaAbierta = null;
        $("#detalle-planta").innerHTML = "";
        avisar("Ya no cuidas esta planta.");
        await cargarPlantas();
    }));
    $("#form-historial").addEventListener("submit", (evento) => {
        evento.preventDefault();
        accion(cargarHistorial);
    });
}

async function recargarPlantaAbierta() {
    await cargarPlantas();
    if (estado.plantaAbierta) await abrirPlanta(estado.plantaAbierta.id);
}

async function generarInvitacion() {
    const p = estado.plantaAbierta;
    const invitacion = await api(`/plantas/${p.id}/invitaciones`, { metodo: "POST" });
    const enlace = `${location.origin}${location.pathname}?invitacion=${encodeURIComponent(invitacion.token)}`;
    const caja = $("#invitacion");
    caja.innerHTML = `
        <div id="qr" class="qr"></div>
        <p class="ayuda">Un solo uso. Expira ${fecha(invitacion.expira_en)}.</p>
        <label>Codigo <input readonly value="${esc(invitacion.token)}"></label>`;
    if (window.QRCode) {
        new QRCode($("#qr"), { text: enlace, width: 180, height: 180 });  // dibujar el QR es trabajo del front
    } else {
        $("#qr").innerHTML = `<p class="ayuda">No se pudo cargar la libreria de QR; comparte el codigo.</p>`;
    }
}

async function cargarHistorial() {
    const p = estado.plantaAbierta;
    const form = $("#form-historial");
    const parametros = new URLSearchParams({ limite: "100" });
    for (const campo of ["desde", "hasta"]) {
        const valor = form?.elements[campo].value;
        if (valor) parametros.set(campo, new Date(valor).toISOString());
    }
    const datos = await api(`/plantas/${p.id}/lecturas?${parametros}`);
    pintarHistorial(datos.lecturas);
}

function pintarHistorial(lecturas) {
    $("#historial").innerHTML = lecturas.length ? `
        <div class="tabla-scroll"><table>
            <thead><tr><th>Fecha</th>${PARAMETROS.map((x) => `<th>${x.nombre} (${x.unidad})</th>`).join("")}<th>Estado</th><th>Origen</th></tr></thead>
            <tbody>${lecturas.map((l) => `
                <tr>
                    <td>${fecha(l.tomada_en)}</td>
                    ${PARAMETROS.map((x) => {
                        const evaluado = l.diagnostico.parametros.find((d) => d.parametro === x.codigo);
                        return `<td class="${claseEstado(evaluado?.estado)}-texto">${l.valores[x.codigo] ?? "-"}</td>`;
                    }).join("")}
                    <td><span class="estado ${claseEstado(l.diagnostico.estado_global)}">${esc(l.diagnostico.estado_global)}</span></td>
                    <td>${esc(l.origen)}</td>
                </tr>`).join("")}
            </tbody>
        </table></div>` : `<p class="ayuda">No hay lecturas en ese rango.</p>`;
}

// ------------------------------------------------------------------ tiempo real (RF19)

function conectarTiempoReal() {
    if (!estado.sesion || estado.socket) return;
    const indicador = $("#estado-tiempo-real");
    let socket;
    try { socket = new WebSocket(WS_URL); } catch { return; }
    estado.socket = socket;
    socket.addEventListener("open", () => {
        socket.send(JSON.stringify({ tipo: "autenticar", token: estado.sesion.token }));  // nunca en la URL
    });
    socket.addEventListener("message", (evento) => {
        const mensaje = JSON.parse(evento.data);
        if (mensaje.tipo === "autenticado") {
            indicador.textContent = "en vivo";
            indicador.className = "chip vivo";
            socket.suscritas = new Set();
            suscribirPlantas();
        } else if (mensaje.tipo === "estado") {
            recibirEstado(mensaje.planta_id, mensaje.medicion);
        }
    });
    socket.addEventListener("close", () => {
        indicador.textContent = "sin conexion en vivo (consulta cada 15 s)";
        indicador.className = "chip";
        if (estado.socket === socket) estado.socket = null;
        if (estado.sesion) setTimeout(conectarTiempoReal, 5000);
    });
}

function suscribirPlantas() {
    const socket = estado.socket;
    if (!socket || socket.readyState !== WebSocket.OPEN || !socket.suscritas) return;
    for (const planta of estado.plantas) {
        if (!socket.suscritas.has(planta.id)) {
            socket.send(JSON.stringify({ tipo: "suscribir", planta_id: planta.id }));
            socket.suscritas.add(planta.id);
        }
    }
}

function recibirEstado(plantaId, medicion) {
    const planta = estado.plantas.find((p) => p.id === plantaId);
    if (planta) {
        planta.ultima_lectura = medicion;
        planta.estado_actual = medicion.diagnostico.estado_global;
        pintarPlantas();
    }
    if (estado.plantaAbierta?.id === plantaId) {
        estado.plantaAbierta.ultima_lectura = medicion;
        $("#estado-planta").innerHTML = htmlDiagnostico(medicion.diagnostico, `Lectura del ${fecha(medicion.tomada_en)}`);
        const form = $("#form-historial");
        if (form && !form.elements.desde.value && !form.elements.hasta.value) accion(cargarHistorial);
    }
}

// ------------------------------------------------------------------ solicitudes de especie (RF16)

$("#form-solicitud").addEventListener("submit", (evento) => {
    evento.preventDefault();
    accion(async () => {
        await api("/especies/solicitudes", { metodo: "POST", cuerpo: datosFormulario(evento.target) });
        evento.target.reset();
        avisar("Solicitud enviada.");
        await cargarMisSolicitudes();
    });
});

async function cargarMisSolicitudes() {
    await accion(async () => {
        const { solicitudes } = await api("/especies/solicitudes");
        $("#mis-solicitudes").innerHTML = solicitudes.length ? `<ul class="lista">${solicitudes.map((s) => `
            <li><strong>${esc(s.nombre_propuesto)}</strong> <span class="estado ${s.estado === "APROBADA" ? "bueno" : s.estado === "RECHAZADA" ? "malo" : "medio"}">${esc(s.estado)}</span>
            <small>${fecha(s.creada_en)}</small></li>`).join("")}</ul>` : `<p class="ayuda">No has enviado solicitudes.</p>`;
    });
}

// ------------------------------------------------------------------ administracion (RF17, RF18)

async function cargarAdmin() {
    await accion(async () => {
        const [{ solicitudes }, { usuarios }] = await Promise.all([
            api("/especies/solicitudes?estado=PENDIENTE"),
            api("/admin/usuarios"),
        ]);
        await cargarEspecies();
        pintarAdminSolicitudes(solicitudes);
        pintarAdminEspecies();
        pintarAdminUsuarios(usuarios);
    });
}

function camposRangos() {
    return PARAMETROS.map((x) => `
        <label>${x.nombre} min <input name="${x.codigo}_minimo" type="number" step="0.1" required></label>
        <label>${x.nombre} max <input name="${x.codigo}_maximo" type="number" step="0.1" required></label>`).join("");
}

function especieDesdeFormulario(form) {
    const datos = datosFormulario(form);
    return {
        nombre: datos.nombre,
        nombre_cientifico: datos.nombre_cientifico,
        fuente: datos.fuente || "admin",
        rangos: Object.fromEntries(PARAMETROS.map((x) => [x.codigo, {
            minimo: Number(datos[`${x.codigo}_minimo`]), maximo: Number(datos[`${x.codigo}_maximo`]),
        }])),
    };
}

function pintarAdminSolicitudes(solicitudes) {
    $("#admin-solicitudes").innerHTML = solicitudes.length ? solicitudes.map((s) => `
        <form class="panel aprobar" data-solicitud="${s.id}">
            <p><strong>${esc(s.nombre_propuesto)}</strong> <small>${esc(s.justificacion)}</small></p>
            <div class="campos">
                <label>Clave <input name="nombre" value="${esc(s.nombre_propuesto)}" required></label>
                <label>Nombre cientifico <input name="nombre_cientifico"></label>
                <label>Fuente <input name="fuente"></label>
                ${camposRangos()}
            </div>
            <button type="submit">Aprobar</button>
            <button type="button" class="peligro" data-rechazar="${s.id}">Rechazar</button>
        </form>`).join("") : `<p class="ayuda">No hay solicitudes pendientes.</p>`;
    document.querySelectorAll("[data-solicitud]").forEach((form) => form.addEventListener("submit", (evento) => {
        evento.preventDefault();
        accion(async () => {
            await api(`/especies/solicitudes/${form.dataset.solicitud}/aprobar`, { metodo: "POST", cuerpo: especieDesdeFormulario(form) });
            avisar("Especie aprobada y agregada al catalogo.");
            await cargarAdmin();
        });
    }));
    document.querySelectorAll("[data-rechazar]").forEach((b) => b.addEventListener("click", () => accion(async () => {
        await api(`/especies/solicitudes/${b.dataset.rechazar}/rechazar`, { metodo: "POST" });
        avisar("Solicitud rechazada.");
        await cargarAdmin();
    })));
}

function pintarAdminEspecies() {
    $("#admin-especies").innerHTML = `
        <div class="tabla-scroll"><table>
            <thead><tr><th>Especie</th>${PARAMETROS.map((x) => `<th>${x.nombre}</th>`).join("")}<th></th></tr></thead>
            <tbody>${estado.especies.map((e) => `
                <tr><td>${esc(e.nombre_cientifico || e.nombre)}<small>${esc(e.nombre)}</small></td>
                ${PARAMETROS.map((x) => {
                    const r = e.rangos.find((y) => y.parametro === x.codigo);
                    return `<td>${r ? `${r.minimo} - ${r.maximo}` : "-"}</td>`;
                }).join("")}
                <td><button class="peligro" data-desactivar="${esc(e.nombre)}">Desactivar</button></td></tr>`).join("")}
            </tbody>
        </table></div>
        <form id="form-especie" class="panel">
            <h3>Agregar o editar especie</h3>
            <div class="campos">
                <label>Clave <input name="nombre" required></label>
                <label>Nombre cientifico <input name="nombre_cientifico"></label>
                <label>Fuente <input name="fuente"></label>
                ${camposRangos()}
            </div>
            <button type="submit">Guardar especie</button>
        </form>
        <p class="ayuda">La gestion de especies escribe en la base de datos. El catalogo la refleja cuando el backend usa MATERA_FUENTE_ESPECIES=sqlite.</p>`;
    document.querySelectorAll("[data-desactivar]").forEach((b) => b.addEventListener("click", () => accion(async () => {
        if (!confirm(`Desactivar ${b.dataset.desactivar}?`)) return;
        await api(`/especies/${encodeURIComponent(b.dataset.desactivar)}`, { metodo: "DELETE" });
        avisar("Especie desactivada.");
        await cargarAdmin();
    })));
    $("#form-especie").addEventListener("submit", (evento) => {
        evento.preventDefault();
        accion(async () => {
            const especie = especieDesdeFormulario(evento.target);
            await api(`/especies/${encodeURIComponent(especie.nombre)}`, { metodo: "PUT", cuerpo: especie });
            avisar("Especie guardada.");
            await cargarAdmin();
        });
    });
}

function pintarAdminUsuarios(usuarios) {
    const propio = estado.sesion.usuario.id;
    $("#admin-usuarios").innerHTML = `
        <div class="tabla-scroll"><table>
            <thead><tr><th>Usuario</th><th>Correo</th><th>Rol</th><th>Activa</th><th></th></tr></thead>
            <tbody>${usuarios.map((u) => `
                <tr>
                    <td>${esc(u.nombre)}</td><td>${esc(u.email)}</td>
                    <td>${esc(u.rol)}</td>
                    <td><span class="estado ${u.activo ? "bueno" : "malo"}">${u.activo ? "SI" : "NO"}</span></td>
                    <td>${u.id === propio ? "<small>tu cuenta</small>" : `
                        <button class="secundario" data-usuario="${u.id}" data-cambio='${JSON.stringify({ activo: !u.activo })}'>${u.activo ? "Desactivar" : "Activar"}</button>
                        <button class="secundario" data-usuario="${u.id}" data-cambio='${JSON.stringify({ rol: u.rol === "ADMIN" ? "USUARIO" : "ADMIN" })}'>${u.rol === "ADMIN" ? "Quitar admin" : "Hacer admin"}</button>`}
                    </td>
                </tr>`).join("")}
            </tbody>
        </table></div>`;
    document.querySelectorAll("[data-usuario]").forEach((b) => b.addEventListener("click", () => accion(async () => {
        await api(`/admin/usuarios/${b.dataset.usuario}`, { metodo: "PATCH", cuerpo: JSON.parse(b.dataset.cambio) });
        avisar("Cuenta actualizada.");
        await cargarAdmin();
    })));
}

// ------------------------------------------------------------------ invitacion por enlace del QR

function capturarInvitacionDeUrl() {
    const parametros = new URLSearchParams(location.search);
    const token = parametros.get("invitacion");
    if (!token) return;
    try { sessionStorage.setItem("matera_invitacion", token); } catch { /* sin almacenamiento */ }
    history.replaceState(null, "", location.pathname);
}

function canjearPendiente() {
    let token = null;
    try { token = sessionStorage.getItem("matera_invitacion"); sessionStorage.removeItem("matera_invitacion"); } catch { /* */ }
    if (token) {
        $("#form-canje").elements.token.value = token;
        avisar("Tienes una invitacion pendiente: pulsa Canjear para adoptar la planta.");
    }
}

// ------------------------------------------------------------------ arranque

document.querySelectorAll("#pestanas button").forEach((b) =>
    b.addEventListener("click", () => mostrarVista(b.dataset.vista)));
document.querySelectorAll("[data-ir]").forEach((b) =>
    b.addEventListener("click", () => mostrarVista(b.dataset.ir)));

capturarInvitacionDeUrl();
pintarSesion();
cargarEspecies().catch(() => avisar("No se pudo conectar con la API.", "error"));
if (estado.sesion) {
    iniciarSesion(estado.sesion);
} else if (sessionStorage.getItem("matera_invitacion")) {
    mostrarVista("acceso");
    avisar("Inicia sesion para aceptar la invitacion.");
}
