const especie = document.querySelector("#especie");
const criterios = document.querySelector("#criterios");
const resultado = document.querySelector("#resultado");
let configuracion = {};

async function cargarTipos() {
    const respuesta = await fetch("/api/plantas");
    const datos = await respuesta.json();
    especie.innerHTML = datos.plantas
        .map((planta) => `<option value="${planta.especie}">${planta.especie}</option>`)
        .join("");
    configuracion = Object.fromEntries(datos.plantas.map((planta) => [planta.especie, planta.criterios]));
    pintarCriterios();
}

function pintarCriterios() {
    criterios.innerHTML = configuracion[especie.value].map((criterio) => {
        const nombre = criterio.nombre;
        return `<label>${nombre} (${criterio.unidad})
            <input id="${nombre}" type="number" min="0" step="0.1" required>
        </label>`;
    }).join("");
}

async function evaluar() {
    resultado.className = "resultado";
    resultado.textContent = "Evaluando...";
    const cuerpo = {
        especie: especie.value,
        ...Object.fromEntries(configuracion[especie.value].map((criterio) => {
            const nombre = criterio.nombre;
            return [nombre, document.querySelector(`#${nombre}`).value];
        })),
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
            <div><span class="etiqueta">${datos.especie}</span><h2>${datos.planta}</h2></div>
            <strong class="estado ${datos.indice_vitalidad === "SALUDABLE" ? "bueno" : "malo"}">${datos.indice_vitalidad}</strong>
        </div>
        <div class="criterios">
            ${Object.entries(datos.criterios).map(([nombre, criterio]) => `
                <article class="criterio">
                    <h3>${nombre}</h3>
                    <p>${criterio.valor} ${criterio.unidad} <small>(rango ${criterio.minimo} - ${criterio.maximo} ${criterio.unidad})</small></p>
                    <span class="estado ${criterio.estado === "OPTIMO" ? "bueno" : "malo"}">${criterio.estado}</span>
                </article>
            `).join("")}
        </div>`;
    resultado.innerHTML += `<div class="recomendaciones"><h3>Recomendaciones</h3>${datos.recomendaciones.length
        ? `<ul>${datos.recomendaciones.map((recomendacion) => `<li>${recomendacion}</li>`).join("")}</ul>`
        : "<p>No hay parametros fuera de rango.</p>"}</div>`;
}

document.querySelector("#evaluar").addEventListener("click", evaluar);
especie.addEventListener("change", () => { pintarCriterios(); evaluar(); });
cargarTipos().then(() => {
    document.querySelector("#humedad").value = 75;
    document.querySelector("#iluminacion").value = 800;
    document.querySelector("#temperatura").value = 24;
    return evaluar();
}).catch(() => {
    resultado.className = "resultado";
    resultado.innerHTML = '<p class="error">No se pudo conectar con la API.</p>';
});
