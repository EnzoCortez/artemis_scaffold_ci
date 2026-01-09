let estadoCarga = {
  duplicados: [],
  nuevos: [],
  fuente: null
};

function showTab(id, btn) {
  document.querySelectorAll('.tab-content').forEach(c=>c.classList.remove('active'));
  document.querySelectorAll('nav button').forEach(b=>b.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  btn.classList.add('active');
}

function validarCarga() {
  const fuente = document.getElementById("fuenteSelect").value;
  if (!fuente) {
    showMessage("msgCarga", "Debe seleccionar una fuente.", true);
    return;
  }
  document.getElementById('listaDuplicados').innerHTML = estadoCarga.duplicados.map(i=>`<li>${i}</li>`).join('');
  document.getElementById('listaNuevos').innerHTML = estadoCarga.nuevos.map(i=>`<li>${i}</li>`).join('');
  showMessage('msgCarga', `Validación completada para la fuente: ${fuente}`);
}

function cargarNuevos() { showMessage('msgCarga','Se cargaron IoCs nuevos exitosamente.'); }
function generarTxtIngestados() { alert("TXT con IoCs ingresados generado."); }
function generarTxtNoIngresados() { alert("TXT con IoCs no ingresados generado."); }

function buscarManual() {
  const tbody = document.querySelector('#tablaManual tbody');
  tbody.innerHTML = `<tr><td>1.2.3.4</td><td>Firewall Y</td><td>Bloqueado</td><td><button class="action">Depurar</button></td></tr>`;
}

function generarReporte() {
  const inicio = document.getElementById("fechaInicio").value;
  const fin = document.getElementById("fechaFin").value;
  if (!inicio || !fin) {
    showMessage("msgReporte", "Debe seleccionar ambas fechas.", true);
    return;
  }
  showMessage("msgReporte", `Reporte generado desde ${inicio} hasta ${fin}.`);
}

function showMessage(el, msg, type = 'info') {
  if (!el) {
    console.warn('showMessage: elemento no encontrado');
    return;
  }

  el.textContent = msg;
  el.className = `msg ${type}`;
}


