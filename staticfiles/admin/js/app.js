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

  const duplicados = ['ioc1.example.com', '192.168.0.10'];
  const nuevos = ['ioc2.example.com', 'hash123456'];

  document.getElementById('listaDuplicados').innerHTML = duplicados.map(i=>`<li>${i}</li>`).join('');
  document.getElementById('listaNuevos').innerHTML = nuevos.map(i=>`<li>${i}</li>`).join('');
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

function showMessage(id,message,isWarning=false) {
  const el = document.getElementById(id);
  el.textContent = message;
  el.className = "message " + (isWarning ? "warning" : "success");
  el.style.display = 'block';
  setTimeout(()=>el.style.display='none',3000);
}

