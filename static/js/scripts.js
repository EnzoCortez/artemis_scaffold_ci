/* static/js/scripts.js
  Versión final para Artemis - integra frontend con backend Django
*/

/* ---------------------------
  Helpers: CSRF + fetch wrapper
----------------------------*/
function getCookie(name) {
  const cookie = document.cookie.split('; ').find(row => row.trim().startsWith(name + '='));
  return cookie ? decodeURIComponent(cookie.split('=')[1]) : null;
}

async function apiFetch(url, opts = {}) {
  // Ensure session cookie is sent
  opts.credentials = opts.credentials || 'include';

  const method = (opts.method || 'GET').toUpperCase();
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
    const csrftoken = getCookie('csrftoken');
    opts.headers = opts.headers || {};
    if (csrftoken && !opts.headers['X-CSRFToken']) {
      opts.headers['X-CSRFToken'] = csrftoken;
    }
  }

  try {
    const res = await fetch(url, opts);
    return res;
  } catch (err) {
    console.error('Network/API error for', url, err);
    throw err;
  }
}

/* ---------------------------
  UI helpers
---------------------------*/
function showMessage(elOrId, text, kind = 'ok') {
  //k ind: ok / warn / err
  let el = (typeof elOrId === 'string') ? document.getElementById(elOrId) : elOrId;
  if (!el) {
    console.warn('showMessage: element not found', elOrId);
    return;
  }
  el.textContent = text;
  el.className = 'message ' + (kind === 'ok' ? 'success' : (kind === 'warn' ? 'warning' : 'err'));
  el.style.display = 'block';
  // hide after a while
  setTimeout(() => { try { el.style.display = 'none'; } catch (e) {} }, 8000);
}

function downloadBlob(filename, blob) {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

function detectIocType(value) {
  if (!value) return 'Dominio';
  if (value.includes('@')) return 'Correo';
  const ipPattern = /^(\d{1,3}\.){3}\d{1,3}$/;
  if (ipPattern.test(value)) return 'IP';
  if (value.startsWith('http://') || value.startsWith('https://')) return 'URL';
  return 'Dominio';
}

function extractField(obj, keys) {
  for (const k of keys) if (obj && obj[k] !== undefined && obj[k] !== null) return obj[k];
  return '';
}

/* ---------------------------
   MÓDULO: CARGA (validación y carga)
   Endpoints:
     POST /api/validate-upload/    -> { duplicates: [...], new: [...] }
     POST /api/load-new/           -> expects JSON { items: [ {value,type}, ... ] } -> { inserted: [...], errors: [...] }
----------------------------*/
async function validarCarga() {
  const fileInput = document.getElementById('fileCarga');
  const fuenteEl = document.getElementById('fuenteSelect');
  const msgEl = document.getElementById('msgCarga');

  if (!fileInput || !fileInput.files.length) return showMessage(msgEl, 'Selecciona un archivo TXT.', 'warn');
  if (!fuenteEl || !fuenteEl.value) return showMessage(msgEl, 'Selecciona la fuente del lote.', 'warn');

  const fd = new FormData();
  fd.append('file', fileInput.files[0]);
  fd.append('fuente', fuenteEl.value);

  showMessage(msgEl, 'Validando archivo...', 'ok');
  try {
    const res = await apiFetch('/api/validate-upload/', { method: 'POST', body: fd });
    if (!res.ok) {
      const txt = await res.text();
      return showMessage(msgEl, `Error validación: ${res.status} ${txt}`, 'err');
    }
    const data = await res.json();

    // aceptar tanto claves en inglés como en español
    const duplicates = data.duplicates || data.duplicados || [];
    const news = data.new || data.nuevos || [];

    const listaDuplicados = document.getElementById('listaDuplicados');
    const listaNuevos = document.getElementById('listaNuevos');
    listaDuplicados.innerHTML = duplicates.length ? duplicates.map(d => `<li>${d}</li>`).join('') : '<li><em>—</em></li>';
    listaNuevos.innerHTML = news.length ? news.map(n => `<li>${n}</li>`).join('') : '<li><em>—</em></li>';

    showMessage(msgEl, `Validación completada. Nuevos: ${news.length}, Duplicados: ${duplicates.length}`, 'ok');
  } catch (err) {
    showMessage(msgEl, 'Error de conexión al validar: ' + (err.message || err), 'err');
  }
}

async function cargarNuevos() {
  const ul = document.getElementById('listaNuevos');
  const msgEl = document.getElementById('msgCarga');
  if (!ul) return showMessage(msgEl, 'No se encontró la lista de nuevos.', 'err');

  const items = Array.from(ul.querySelectorAll('li')).map(li => li.textContent.trim()).filter(Boolean);
  if (!items.length) return showMessage(msgEl, 'No hay IoCs nuevos para cargar.', 'warn');

  const payload = items.map(v => ({ value: v, type: detectIocType(v) }));

  showMessage(msgEl, `Insertando ${payload.length} IoCs...`, 'ok');
  try {
    const res = await apiFetch('/api/load-new/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items: payload })
    });
    if (!res.ok) {
      const txt = await res.text();
      return showMessage(msgEl, `Error al insertar: ${res.status} ${txt}`, 'err');
    }
    const data = await res.json();
    const inserted = data.inserted || [];
    const errors = data.errors || [];

    showMessage(msgEl, `Insertados: ${inserted.length}. Errores: ${errors.length}`, errors.length ? 'warn' : 'ok');

    // eliminar los insertados de la listaNuevos
    if (inserted.length) {
      Array.from(ul.querySelectorAll('li')).forEach(li => {
        if (inserted.includes(li.textContent.trim())) li.remove();
      });
    }

    if (typeof refreshIocList === 'function') refreshIocList();

  } catch (err) {
    showMessage(msgEl, 'Error de conexión al insertar: ' + (err.message || err), 'err');
  }
}

/* ---------------------------
   MÓDULO: DEPURACIÓN (descargas)
   GET /api/export/ingested/  (returns blob)
   POST /api/export/not-ingested/ (expects { items: [...] }) -> returns blob
----------------------------*/
async function generarTxtIngestados() {
  try {
    const res = await apiFetch('/api/export/ingested/');
    if (!res.ok) {
      const txt = await res.text();
      return alert('Error al descargar ingestados: ' + res.status + ' ' + txt);
    }
    const blob = await res.blob();
    downloadBlob('iocs_ingestados.txt', blob);
  } catch (err) {
    alert('Error de conexión: ' + (err.message || err));
  }
}

async function generarTxtNoIngresados() {
  // si hay listaNuevos en UI la usamos, sino pedimos confirmación para generar vacío
  const items = Array.from(document.querySelectorAll('#listaNuevos li')).map(li => li.textContent.trim()).filter(Boolean);
  if (!items.length) {
    if (!confirm('No hay elementos listados como "Nuevos". Deseas generar archivo con lista vacía (será vacía)?')) return;
  }

  try {
    const res = await apiFetch('/api/export/not-ingested/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items })
    });
    if (!res.ok) {
      const txt = await res.text();
      return alert('Error al generar no-ingresados: ' + res.status + ' ' + txt);
    }
    const blob = await res.blob();
    downloadBlob('iocs_no_ingestados.txt', blob);
  } catch (err) {
    alert('Error de conexión: ' + (err.message || err));
  }
}

/* ---------------------------
   MÓDULO: GESTIÓN - búsqueda individual y listado
   GET /api/iocs/?search=...
   Endpoint devuelve array de IocEntry (serializer)
----------------------------*/
async function buscarManual() {
  const q = document.getElementById('searchIoc').value.trim();
  const tbody = document.querySelector('#tablaManual tbody');
  const msgEl = document.getElementById('msgGestionManual') || null;
  if (!tbody) return showMessage(msgEl || 'msgGestionManual', 'Tabla manual no encontrada', 'err');
  tbody.innerHTML = '';

  try {
    const url = '/api/iocs/' + (q ? `?search=${encodeURIComponent(q)}` : '');
    const res = await apiFetch(url);
    if (!res.ok) {
      const txt = await res.text();
      return showMessage(msgEl || 'msgGestionManual', `Error buscando: ${res.status} ${txt}`, 'err');
    }
    const data = await res.json();
    // espera: array de objetos
    const arr = Array.isArray(data) ? data : (data.results || []);
    arr.forEach(ioc => {
      const id = extractField(ioc, ['id', 'pk']);
      const value = extractField(ioc, ['value', 'ioc', 'name']);
      const type = (ioc.ioc_type && (ioc.ioc_type.name || ioc.ioc_type)) || extractField(ioc, ['ioc_type', 'type']);
      const status = extractField(ioc, ['status', 'estado']) || '';

      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${value}</td><td>${type}</td><td>${status}</td>
        <td><button type="button" onclick="promptChangeState(${JSON.stringify(id)})">Cambiar</button></td>`;
      tbody.appendChild(tr);
    });

    showMessage(msgEl || 'msgGestionManual', `Resultados: ${arr.length}`, 'ok');

  } catch (err) {
    showMessage(msgEl || 'msgGestionManual', 'Error conexión búsqueda: ' + (err.message || err), 'err');
  }
}

function promptChangeState(iocId) {
  const newState = prompt('Ingrese nuevo estado (BLOQUEADO o DEPURADO):');
  if (!newState) return;
  const ns = newState.toUpperCase().trim();
  if (!['BLOQUEADO', 'DEPURADO'].includes(ns)) return alert('Estado inválido.');
  cambiarEstadoManual(iocId, ns);
}

async function cambiarEstadoManual(iocId, newState) {
  const msgEl = document.getElementById('msgGestionManual') || null;
  try {
    const res = await apiFetch('/api/change-state/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ioc_id: iocId, new_state: newState })
    });
    if (!res.ok) {
      const txt = await res.text();
      return showMessage(msgEl || 'msgGestionManual', `Error cambiando estado: ${res.status} ${txt}`, 'err');
    }
    const data = await res.json();
    showMessage(msgEl || 'msgGestionManual', data.detail || 'Estado actualizado', 'ok');
    buscarManual();
  } catch (err) {
    showMessage(msgEl || 'msgGestionManual', 'Error de conexión: ' + (err.message || err), 'err');
  }
}

/* ---------------------------
   MÓDULO: GESTIÓN - MASIVA (bulk)
   POST /iocs/bulk_change_state/  (form-data: file + new_state) 
   HTML calls cargarEstadosDesdeTxt() so we provide that name
----------------------------*/
async function cargarTxtEstados() {
  // internal implementation (kept for compatibility)
  const fileInput = document.getElementById('fileEstados');
  const select = document.getElementById('nuevoEstado');
  const msgEl = document.getElementById('msgEstados');

  if (!fileInput || !fileInput.files.length) return showMessage(msgEl, 'Selecciona un archivo TXT.', 'warn');
  if (!select || !select.value) return showMessage(msgEl, 'Selecciona un nuevo estado (BLOQUEADO o DEPURADO).', 'warn');

  const newState = select.value.toUpperCase().trim();
  if (!['BLOQUEADO', 'DEPURADO'].includes(newState)) return showMessage(msgEl, 'Estado inválido. Usa BLOQUEADO o DEPURADO.', 'warn');

  const fd = new FormData();
  fd.append('file', fileInput.files[0]);
  fd.append('new_state', newState);

  showMessage(msgEl, 'Enviando archivo para actualización masiva...', 'ok');

  try {
    const res = await apiFetch('/iocs/bulk_change_state/', { method: 'POST', body: fd });
    if (!res.ok) {
      const txt = await res.text();
      return showMessage(msgEl, `Error servidor: ${res.status} ${txt}`, 'err');
    }
    const data = await res.json();
    const out = [
      `Actualizados: ${data.updated_count || 0}`,
      `Encontrados: ${ (data.updated && data.updated.length) || 0 }`,
      `No encontrados: ${ (data.not_found && data.not_found.length) || 0 }`,
      `Errores: ${ (data.errors && data.errors.length) || 0 }`
    ];
    if (data.not_found && data.not_found.length) {
      out.push('No encontrados (ejemplo):');
      data.not_found.slice(0, 50).forEach(v => out.push(` - ${v}`));
    }
    if (data.errors && data.errors.length) {
      out.push('Errores (ejemplo):');
      data.errors.slice(0,20).forEach(e => out.push(` - ${e.value}: ${e.error}`));
    }
    showMessage(msgEl, out.join('\n'), 'ok');
    msgEl.style.whiteSpace = 'pre-wrap';
    if (typeof refreshIocList === 'function') refreshIocList();
  } catch (err) {
    showMessage(msgEl, 'Excepción al enviar archivo: ' + (err.message || err), 'err');
  }
}

// alias to match HTML onclick if needed
async function cargarEstadosDesdeTxt() {
  return cargarTxtEstados();
}

/* ---------------------------
   MÓDULO: REPORTES (audit create)
   POST /api/audit/create/  -> { audit_id, detail }
----------------------------*/
async function generarReporte() {
  const from = document.getElementById('fechaInicio').value;
  const to = document.getElementById('fechaFin').value;
  const msgEl = document.getElementById('msgReporte');

  if (!from || !to) return showMessage(msgEl, 'Selecciona fecha inicio y fin', 'warn');

  try {
    const res = await apiFetch(`/api/reporte/?fecha_inicio=${from}&fecha_fin=${to}`);
    if (!res.ok) {
      const txt = await res.text();
      return showMessage(msgEl, `Error reporte: ${res.status} ${txt}`, 'err');
    }
    const blob = await res.blob();
    downloadBlob(`reporte_${from}_${to}.txt`, blob);
    showMessage(msgEl, 'Reporte generado y descargado', 'ok');
  } catch (err) {
    showMessage(msgEl, 'Error conexión reporte: ' + (err.message || err), 'err');
  }
}


/* ---------------------------
   Utility: refreshIocList() - list all iocs and populate tablaManual
----------------------------*/
async function refreshIocList() {
  const tbody = document.querySelector('#tablaManual tbody');
  if (!tbody) return;
  try {
    const res = await apiFetch('/api/iocs/');
    if (!res.ok) return;
    const data = await res.json();
    const arr = Array.isArray(data) ? data : (data.results || []);
    tbody.innerHTML = '';
    arr.forEach(ioc => {
      const id = extractField(ioc, ['id','pk']);
      const value = extractField(ioc, ['value','ioc','name']);
      const type = (ioc.ioc_type && (ioc.ioc_type.name || ioc.ioc_type)) || '';
      const status = extractField(ioc, ['status','estado']) || '';
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${value}</td><td>${type}</td><td>${status}</td>
        <td><button onclick="promptChangeState(${JSON.stringify(id)})">Cambiar</button></td>`;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.warn('refreshIocList error', err);
  }
}

/* ---------------------------
  Init
----------------------------*/
document.addEventListener('DOMContentLoaded', () => {
  // initial refresh (safe if unauthenticated - view may return empty)
  try { refreshIocList(); } catch (e) {}
});
