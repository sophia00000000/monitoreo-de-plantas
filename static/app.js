const tipo = document.querySelector("#tipo");
const criterios = document.querySelector("#criterios");
const resultado = document.querySelector("#resultado");
let configuracion = {};

async function cargarTipos() {
    const respuesta = await fetch("/api/plantas");
    const datos = await respuesta.json();
    tipo.innerHTML = datos.plantas
        .map((planta) => `<option value="${planta.tipo}">${planta.tipo}</option>`)
        .join("");
    configuracion = Object.fromEntries(datos.plantas.map((planta) => [planta.tipo, planta.criterios]));
    pintarCriterios();
}

function pintarCriterios() {
    criterios.innerHTML = configuracion[tipo.value].map((nombre) => `
        <label>${nombre}
            <input id="${nombre}" type="number" min="0" step="0.1" required>
        </label>`).join("");
}

async function evaluar() {
    resultado.className = "resultado";
    resultado.textContent = "Evaluando...";
    const cuerpo = {
        tipo: tipo.value,
        ...Object.fromEntries(configuracion[tipo.value].map((nombre) => [
            nombre, document.querySelector(`#${nombre}`).value,
        ])),
    };

    const respuesta = await fetch("/api/evaluar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cuerpo),
    });
    const datos = await respuesta.json();
    if (!respuesta.ok) {
        resultado.innerHTML = `<p class="error">${datos.error}</p>`;
        return;
    }

    resultado.innerHTML = `
        <div class="resultado-cabecera">
            <div><span class="etiqueta">${datos.tipo}</span><h2>${datos.planta}</h2></div>
            <strong class="estado ${datos.estado_general === "BUENO" ? "bueno" : "malo"}">${datos.estado_general}</strong>
        </div>
        <div class="criterios">
            ${Object.entries(datos.criterios).map(([nombre, criterio]) => `
                <article class="criterio">
                    <h3>${nombre}</h3>
                    <p>${criterio.valor} <small>(rango ${criterio.minimo} - ${criterio.maximo})</small></p>
                    <span class="estado ${criterio.estado === "BUENO" ? "bueno" : "malo"}">${criterio.estado}</span>
                </article>
            `).join("")}
        </div>`;
}

document.querySelector("#evaluar").addEventListener("click", evaluar);
tipo.addEventListener("change", () => { pintarCriterios(); evaluar(); });
cargarTipos().then(() => {
    document.querySelector("#humedad").value = 75;
    document.querySelector("#iluminacion").value = 800;
    document.querySelector("#temperatura").value = 24;
    return evaluar();
}).catch(() => {
    resultado.className = "resultado";
    resultado.innerHTML = '<p class="error">No se pudo conectar con la API.</p>';
});
