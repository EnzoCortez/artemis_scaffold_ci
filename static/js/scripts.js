/* static/js/scripts.js
   Artemis - Integración frontend <-> backend (versión completa)
   - Guardar en static/js/scripts.js
   - Requiere IDs en HTML: fileCarga, fuenteSelect, msgCarga, listaDuplicados, listaNuevos,
     fileEstados, nuevoEstado, msgEstados, searchIoc, tablaManual (tbody), msgGestionManual,
     fechaInicio, fechaFin, msgReporte, btn/deleteDepurados (si aplica).
*/

/* ---------------------------
   Helpers: CSRF + fetch wrapper
----------------------------*/
function getCookie(name) {
  const cookie = document.cookie.split(';').find(row => row.trim().startsWith(name + '='));
  return cookie ? decodeURIComponent(cookie.split('=')[1]) : null;
}

async function apiFetch(url, opts = {}) {
  opts.credentials = opts.credentials || 'include';
  opts.headers = opts.headers || {};

  const method = (opts.method || 'GET').toUpperCase();
  if (['POST','PUT','PATCH','DELETE'].includes(method)) {
    const csrftoken = getCookie('csrftoken');
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
----------------------------*/
function showMessage(elOrId, text, kind='ok') {
  // kind: ok / warn / err
  let el = typeof elOrId === 'string' ? document.getElementById(elOrId) : elOrId;
  if (!el) {
    console.warn('showMessage: element not found', elOrId);
    return;
  }
  el.textContent = text;
  el.className = 'message ' + (kind === 'ok' ? 'success' : (kind === 'warn' ? 'warning' : 'err'));
  el.style.display = 'block';
  // hide after a while
  setTimeout(()=>{ try{ el.style.display = 'none'; } catch(e){} }, 8000);
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

/* ---------------------------
  Detección de tipo de IOC (JS)
----------------------------*/
function detectarTipoIoc(value) {
  if (!value) return 'Desconocido';
  const v = value.trim();

  // Hashes
  const md5 = /^[a-f0-9]{32}$/i;
  const sha1 = /^[a-f0-9]{40}$/i;
  const sha256 = /^[a-f0-9]{64}$/i;
  const sha512 = /^[a-f0-9]{128}$/i;

  // IPv4
  const ipv4 = /^(25[0-5]|2[0-4]\d|1?\d{1,2})(\.(25[0-5]|2[0-4]\d|1?\d{1,2})){3}$/;

  // IPv6 (simplificado)
  const ipv6 = /:/;

  const email = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  const url = /^https?:\/\//i;
  const domain = /^[a-z0-9.-]+\.[a-z]{2,}$/i;

  if (md5.test(v) || sha1.test(v) || sha256.test(v) || sha512.test(v)) return 'Hash';
  if (ipv4.test(v)) return 'IP';
  if (ipv6.test(v)) return 'IPV6';
  if (email.test(v)) return 'Correo';
  if (url.test(v)) return 'URL';
  if (domain.test(v)) return 'Dominio';
  return 'Desconocido';
}

/* ---------------------------
  Utilidades para render y parseo
----------------------------*/
function parseListItemText(liText) {
  // Si tiene formato "valor (en FUENTE)" devolvemos value y fuente, si no, solo value.
  if (!liText) return { value: '', fuente: null };
  const m = liText.match(/^(.*?)\s*\(en\s*(.*?)\)\s*$/i);
  if (m) return { value: m[1].trim(), fuente: m[2].trim() };
  return { value: liText.trim(), fuente: null };
}

function renderListIntoUL(ulEl, items, options = {}) {
  // items: array de strings o array de objetos {value, detected_type, fuente, tools}
  if (!ulEl) return;
  ulEl.innerHTML = '';
  if (!Array.isArray(items) || items.length === 0) {
    return;
  }
  items.forEach(it => {
    let value = '';
    let type = '';
    if (typeof it === 'string') {
      value = it;
      type = detectarTipoIoc(value);
    } else if (typeof it === 'object' && it !== null) {
      value = it.value || it.ioc || it.name || '';
      type = it.detected_type || it.ioc_type || detectarTipoIoc(value);
    } else {
      value = String(it);
      type = detectarTipoIoc(value);
    }
    const li = document.createElement('li');
    li.textContent = value;                // mostrar solo el valor
    li.dataset.value = value;             // dato limpio para exportar
    li.dataset.type = type;               // dato del tipo (útil si queremos mostrarlo)
    ulEl.appendChild(li);
  });
}



/* ---------------------------
  Validador de placeholders (para evitar enviar "—")
----------------------------*/
function isPlaceholderValue(s) {
  if (s === null || s === undefined) return true;
  const t = String(s).trim();
  if (!t) return true;
  if (t === '—' || t === '-' || t === '--') return true;
  if (t.length < 2) return true;
  return false;
}

/* ---------------------------
  MÓDULO: CARGA (validación y carga)
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

    // Normalizar la respuesta (acepta strings u objetos)
    const duplicatesRaw = data.duplicates || data.duplicados || [];
    const newRaw = data.new || data.nuevos || [];

    const fuente = fuenteEl.value;

    const duplicates = duplicatesRaw.map(d => {
      if (typeof d === 'string') return { value: d, fuente: fuente };
      if (typeof d === 'object' && d !== null) {
        return {
          value: d.value || d.ioc || d.item || '',
          detected_type: d.ioc_type || d.detected_type || d.type || '',
          tools: d.tools || d.tool || [],
          fuente: d.fuente || fuente
        };
      }
      return { value: String(d), fuente: fuente };
    });

    const newItems = newRaw.map(n => {
      if (typeof n === 'string') return { value: n };
      if (typeof n === 'object' && n !== null) {
        return {
          value: n.value || n.ioc || n.name || '',
          detected_type: n.detected_type || n.type || ''
        };
      }
      return { value: String(n) };
    });

    // Renderizar en ULs
    renderListIntoUL(document.getElementById('listaDuplicados'), duplicates, { showType: true });
    renderListIntoUL(document.getElementById('listaNuevos'), newItems, { showType: true });

    showMessage(msgEl, `Validación completada. Nuevos: ${newItems.length}, Duplicados: ${duplicates.length}`, 'ok');

  } catch (err) {
    showMessage(msgEl, 'Error de conexión al validar: ' + (err.message || err), 'err');
    console.error(err);
  }
}

async function cargarNuevos() {
  const msgEl = document.getElementById('msgCarga');
  const ul = document.getElementById('listaNuevos');
  const fuente = document.getElementById('fuenteSelect') ? document.getElementById('fuenteSelect').value : null;

  if (!ul) return showMessage(msgEl, 'No se encontró la lista de nuevos.', 'err');
  const itemsText = Array.from(ul.querySelectorAll('li')).map(li => li.textContent.trim()).filter(Boolean);
  if (!itemsText.length) return showMessage(msgEl, 'No hay IoCs nuevos para cargar.', 'warn');
  if (!fuente) return showMessage(msgEl, 'Selecciona la fuente del lote antes de cargar.', 'warn');

  const items = itemsText.map(v => ({ value: v, type: detectarTipoIoc(v) }));
  showMessage(msgEl, `Insertando ${items.length} IoCs...`, 'ok');

  try {
    const res = await apiFetch('/api/load-new/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items, fuente })
    });

    // Si no es ok, tratamos de leer texto para debug
    if (!res.ok) {
      let txt;
      try { txt = await res.text(); } catch (e) { txt = `No se pudo leer body: ${e}`; }
      return showMessage(msgEl, `Error al insertar: ${res.status} ${txt}`, 'err');
    }

    // Intentar parsear JSON de forma segura
    let data = null;
    try {
      data = await res.json();
    } catch (e) {
      // respuesta no JSON -> mostrar texto para debug
      const txt = await res.text();
      return showMessage(msgEl, `Respuesta inesperada del servidor (no JSON): ${txt}`, 'err');
    }

    // ahora data está garantizado
    const inserted = Array.isArray(data.inserted) ? data.inserted : (data.inserted ? [data.inserted] : []);
    const existing = Array.isArray(data.existing) ? data.existing : (data.existing ? [data.existing] : []);
    const errors = Array.isArray(data.errors) ? data.errors : (data.errors ? [data.errors] : []);
    const batch = data.batch_id || null;

    showMessage(msgEl, `Insertados: ${inserted.length}. Existían: ${existing.length}. Errores: ${errors.length}`, errors.length ? 'warn' : 'ok');

  
    // Descargar TXT de ingestados por batch (solo si batch existe y hay insertados)
    if (batch && inserted.length) {
      try {
        const r1 = await apiFetch(`/api/export/ingested/?batch=${encodeURIComponent(batch)}`);
        if (r1.ok) {
          const blob = await r1.blob();
          downloadBlob(`iocs_ingestados_${batch}.txt`, blob);
        } else {
          const txt = await r1.text();
          console.warn('No se pudo descargar ingestados por batch:', r1.status, txt);
        }
      } catch (err) {
        console.warn('Error descargando ingestados por batch', err);
      }
    }

    // Descargar TXT de duplicados (si existen)
    if (existing.length) {
      try {
        const r2 = await apiFetch('/api/export/duplicates/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ items: existing })
        });
        if (r2.ok) {
          const blob2 = await r2.blob();
          downloadBlob(`iocs_duplicados_${batch || 'dup'}.txt`, blob2);
        } else {
          const txt = await r2.text();
          console.warn('No se pudo descargar duplicados:', r2.status, txt);
        }
      } catch (err) {
        console.warn('Error descargando duplicados', err);
      }
    }

    // Mostrar algunos errores si existen
    if (errors && errors.length) {
      const firstErrors = errors.slice(0, 10).map(e => `- ${e.value || e}: ${e.error || ''}`).join('\n');
      showMessage(msgEl, `Se produjeron errores (muestra los 10 primeros):\n${firstErrors}`, 'warn');
      msgEl.style.whiteSpace = 'pre-wrap';
    }

    // Limpiar UI: eliminar insertados de la lista de nuevos
    if (inserted.length) {
      Array.from(ul.querySelectorAll('li')).forEach(li => {
        if (inserted.includes(li.textContent.trim())) li.remove();
      });
    }

    // refrescar lista general
    if (typeof refreshIocList === 'function') refreshIocList();

  } catch (err) {
    console.error(err);
    showMessage(msgEl, 'Error de conexión al insertar: ' + (err.message || err), 'err');
  }
}

/* ---------------------------
  DEPURACIÓN: generación de TXT
  - generarTxtIngestados(): POST con items = lista de duplicados mostrados en UI
  - generarTxtNoIngresados(): POST con items = lista de nuevos mostrados en UI
----------------------------*/
async function generarTxtIngestados() {
  // si quieres exportar SOLO los duplicados listados en pantalla
  const lis = Array.from(document.querySelectorAll('#listaDuplicados li')).map(li => li.dataset.value).filter(Boolean);
  if (!lis.length) {
    // en caso de que quieras descargar *todos* los ingestados, usa GET:
    if (!confirm('No hay duplicados listados. ¿Deseas descargar TODOS los IoCs ingestados?')) return;
    // descargar todos con GET
    try {
      const res = await apiFetch('/api/export/ingested/');
      if (!res.ok) { const txt = await res.text(); return alert('Error: ' + res.status + ' ' + txt); }
      const blob = await res.blob();
      downloadBlob('iocs_ingestados.txt', blob);
      return;
    } catch (err) {
      return alert('Error de conexión: ' + err.message);
    }
  }

  // POST con items para exportar solo los listados
  try {
    const res = await apiFetch('/api/export/ingested/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items: lis })
    });
    if (!res.ok) { const txt = await res.text(); return alert('Error: ' + res.status + ' ' + txt); }
    const blob = await res.blob();
    downloadBlob('iocs_ingestados.txt', blob);
  } catch (err) {
    alert('Error de conexión: ' + err.message);
  }
}

async function generarTxtNoIngresados() {
  const lis = Array.from(document.querySelectorAll('#listaNuevos li')).map(li => li.dataset.value).filter(Boolean);
  if (!lis.length) return alert('No hay IoCs nuevos listados para exportar.');

  try {
    const res = await apiFetch('/api/export/not-ingested/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items: lis })
    });
    if (!res.ok) { const txt = await res.text(); return alert('Error: ' + res.status + ' ' + txt); }
    const blob = await res.blob();
    downloadBlob('iocs_no_ingestados.txt', blob);
  } catch (err) {
    alert('Error de conexión: ' + err.message);
  }
}

/* ---------------------------
  GESTIÓN - búsqueda individual y listado
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
    const arr = Array.isArray(data) ? data : (data.results || []);

    arr.forEach(ioc => {
      const id = ioc.id || ioc.pk || '';
      const value = ioc.value || ioc.valor || ioc.name || ioc.ioc || '';
      const status = ioc.status || ioc.estado || '';
      const tipo = detectarTipoIoc(value);

      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${value}</td><td>${tipo}</td><td>${status}</td>
        <td><button type="button" onclick="promptChangeState(${JSON.stringify(id)})">Cambiar</button></td>`;
      tbody.appendChild(tr);
    });

    showMessage(msgEl || 'msgGestionManual', `Resultados: ${arr.length}`, 'ok');
  } catch (err) {
    showMessage(msgEl || 'msgGestionManual', 'Error conexión búsqueda: ' + (err.message || err), 'err');
    console.error(err);
  }
}

function promptChangeState(iocId) {
  const newState = prompt('Ingrese nuevo estado (BLOQUEADO o DEPURADO):');
  if (!newState) return;
  const ns = newState.toUpperCase().trim();
  if (!['BLOQUEADO','DEPURADO'].includes(ns)) return alert('Estado inválido.');
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
    console.error(err);
  }
}

/* ---------------------------
   GESTIÓN - MASIVA (bulk change)
   Endpoint: /iocs/bulk_change_state/ (expects file or JSON lines + new_state)
----------------------------*/
async function cargarTxtEstados() {
  const fileInput = document.getElementById('fileEstados');
  const select = document.getElementById('nuevoEstado') || document.getElementById('estadoNuevo');
  const msgEl = document.getElementById('msgEstados');

  if (!fileInput || !fileInput.files.length) return showMessage(msgEl, 'Selecciona un archivo TXT.', 'warn');
  if (!select || !select.value) return showMessage(msgEl, 'Selecciona un nuevo estado (BLOQUEADO o DEPURADO).', 'warn');

  const newState = select.value.toUpperCase().trim();
  if (!['BLOQUEADO','DEPURADO'].includes(newState)) return showMessage(msgEl, 'Estado inválido. Usa BLOQUEADO o DEPURADO.', 'warn');

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
    console.error(err);
  }
}

// alias para HTML, template llama cargarEstadosDesdeTxt()
async function cargarEstadosDesdeTxt() {
  return cargarTxtEstados();
}

/* ---------------------------
   BORRAR IOC DEPURADOS
----------------------------*/
async function eliminarDepurados() {
  if (!confirm("¿Seguro que quieres eliminar TODOS los IoCs en estado 'DEPURADO'? Esto es irreversible.")) return;
  const msgEl = document.getElementById('msgEstados') || document.getElementById('msgGestionManual') || null;
  showMessage(msgEl, 'Creando auditoría para permitir purga...', 'ok');

  try {
    const label = `Purge_by_UI_${new Date().toISOString()}`;
    const createRes = await apiFetch('/api/audit/create/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ label })
    });
    if (!createRes.ok) {
      const txt = await createRes.text();
      return showMessage(msgEl, `No se pudo crear auditoría: ${createRes.status} ${txt}`, 'err');
    }
    const createData = await createRes.json();
    const audit_id = createData.audit_id;
    showMessage(msgEl, `Auditoría creada (id=${audit_id}). Ejecutando purga...`, 'ok');

    const purgeRes = await apiFetch('/api/purge/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ audit_id: audit_id, dry_run: false })
    });
    if (!purgeRes.ok) {
      const txt = await purgeRes.text();
      return showMessage(msgEl, `Error al purgar: ${purgeRes.status} ${txt}`, 'err');
    }
    const purgeData = await purgeRes.json();
    showMessage(msgEl, `Purgados: ${purgeData.purged_count || purgeData.to_delete || 0}`, 'ok');

    if (typeof refreshIocList === 'function') refreshIocList();
  } catch (err) {
    showMessage(msgEl, 'Error realizando purga: ' + (err.message || err), 'err');
    console.error(err);
  }
}

/* ---------------------------
   Utility: refreshIocList() - puebla tabla en Gestión
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
      const id = ioc.id || ioc.pk || '';
      const value = ioc.value || ioc.valor || ioc.name || ioc.ioc || '';
      const type = (ioc.ioc_type && (ioc.ioc_type.name || ioc.ioc_type)) || detectarTipoIoc(value);
      const status = ioc.status || ioc.estado || '';

      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${value}</td>
        <td>${type}</td>
        <td>${status}</td>
        <td><button onclick="promptChangeState(${JSON.stringify(id)})">Cambiar</button></td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.warn('refreshIocList error', err);
  }
}

/* ---------------------------
   REPORTES (placeholder)
----------------------------*/
async function generarReporte() {
  const from = document.getElementById('fechaInicio').value;
  const to = document.getElementById('fechaFin').value;
  const msgEl = document.getElementById('msgReporte');
  if (!from || !to) return showMessage(msgEl, 'Selecciona fecha inicio y fin', 'warn');

  showMessage(msgEl, 'Funcionalidad de reportes temporalmente deshabilitada en frontend.', 'warn');
}

/* ---------------------------
   Init: refresh on load
----------------------------*/
document.addEventListener('DOMContentLoaded', () => {
  try { refreshIocList(); } catch (e) {}
});

// después de recibir response data del POST /api/load-new/
const batchId = data.batch_id;
const inserted = data.inserted || [];
const existing = data.existing || [];
const errors = data.errors || [];

// descargar ingestados del batch
async function descargarIngestadosBatch(batchId) {
  if (!batchId) return alert('No hay batch_id para descargar ingestados.');
  const url = `/api/export/ingested/?batch=${encodeURIComponent(batchId)}`;
  const res = await fetch(url, { credentials: 'include', headers: { 'X-CSRFToken': getCookie('csrftoken') } });
  if (!res.ok) { alert('Error descargando ingestados: ' + res.status); return; }
  const blob = await res.blob();
  downloadBlob('iocs_ingestados_batch.txt', blob);
}

// descargar duplicados (lista existing) via POST
async function descargarDuplicadosList(existingList) {
  if (!existingList || !existingList.length) return alert('No hay duplicados para descargar.');
  const res = await fetch('/api/export/duplicates/', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
    body: JSON.stringify({ items: existingList })
  });
  if (!res.ok) { alert('Error descargando duplicados: ' + res.status); return; }
  const blob = await res.blob();
  downloadBlob('iocs_duplicados.txt', blob);
}

async function generarReporte() {
  const fechaInicio = document.getElementById("fechaInicio").value;
  const fechaFin = document.getElementById("fechaFin").value;
  const tipo = document.getElementById("tipoReporte").value;

  const url = `/api/reportes/?inicio=${fechaInicio}&fin=${fechaFin}&tipo=${tipo}`;

  try {
    const response = await fetch(url);
    if (!response.ok) throw new Error("Error al generar el reporte");

    const blob = await response.blob();
    const urlBlob = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = urlBlob;
    a.download = `reporte_artemis_${tipo}.txt`;
    document.body.appendChild(a);
    a.click();
    a.remove();

    document.getElementById("msgReporte").textContent = "✅ Reporte generado correctamente.";
  } catch (err) {
    console.error(err);
    document.getElementById("msgReporte").textContent = "❌ Error al generar el reporte.";
  }
}
