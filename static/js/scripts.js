/* static/js/scripts.js
  Artemis - Integración frontend <-> backend (versión completa)
  - Guardar en static/js/scripts.js
  - Requiere IDs en HTML: fileCarga, fuenteSelect, msgCarga, listaDuplicados, listaNuevos,
    -fileEstados, nuevoEstado, msgEstados, searchIoc, tablaManual (tbody), msgGestionManual,
    fechaInicio, fechaFin, msgReporte, btn/deleteDepurados (si aplica).
*/
window.estadoCarga = {
  duplicados: [],
  nuevos: []
};


// 🔥 ESTADO GLOBAL DE LA CARGA
window.iocsDuplicados = [];
window.iocsNuevos = [];
window.originalFilename = 'iocs';

// Helper global: verifica si el toggle de ofuscación está activo
function isDefangActive() {
  const toggle = document.getElementById('defangToggle');
  return toggle ? toggle.checked : false;
}


/* ---------------------------
  Helpers: CSRF + fetch wrapper
----------------------------*/
function downloadBlob(blob, filename) {
  // Sanitize filename to prevent attribute injection
  // Ensure we have a string
  const name = String(filename || 'download');
  // Allow only safe characters: alphanumeric, dots, underscores, hyphens
  const safeFilename = name.replace(/[^a-zA-Z0-9._-]/g, '_');

  if (window.navigator && window.navigator.msSaveOrOpenBlob) {
    window.navigator.msSaveOrOpenBlob(blob, safeFilename);
    return;
  }

  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.style.display = 'none';
  a.href = url;

  // Use property assignment (safer than setAttribute for XSS context)
  a.download = safeFilename;

  // Safe append
  document.body.appendChild(a);
  a.click();

  // Cleanup
  setTimeout(() => {
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  }, 100);
}

function getCookie(name) {
  const cookie = document.cookie.split(';').find(row => row.trim().startsWith(name + '='));
  return cookie ? decodeURIComponent(cookie.split('=')[1]) : null;
}

window.apiFetch = async function (url, opts = {}) {
  opts.credentials = opts.credentials || 'include';
  opts.headers = opts.headers || {};

  const method = (opts.method || 'GET').toUpperCase();
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
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
function showMessage(elOrId, text, kind = 'ok') {
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
  setTimeout(() => { try { el.style.display = 'none'; } catch (e) { } }, 8000);
}

// Duplicate downloadBlob removed

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

  // URL explícita (http/https)
  if (url.test(v)) return 'URL';

  // URL implícita (dominio + path)
  // Si tiene barra, y lo de antes parece dominio, es URL
  if (v.includes('/') && !v.includes('@')) {
    const parts = v.split('/');
    // Basic check on first part
    if (domain.test(parts[0])) return 'URL';
  }

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
    let tools = [];
    let value = '';
    let type = '';
    if (typeof it === 'string') {
      value = it;
      type = detectarTipoIoc(value);
    } else if (typeof it === 'object' && it !== null) {
      value = it.value || it.ioc || it.name || '';
      type = it.detected_type || it.ioc_type || detectarTipoIoc(value);
      tools = it.tools || [];
    } else {
      value = String(it);
      type = detectarTipoIoc(value);
    }
    const li = document.createElement('li');
    li.style.display = 'flex';
    li.style.justifyContent = 'space-between';
    li.style.alignItems = 'center';
    li.style.marginBottom = '5px';

    let htmlContent = `<span>${value}</span>`;
    if (options.showTools && tools.length > 0) {
      htmlContent += `<span style="font-size: 0.85em; color: #7f8c8d; margin-left: 10px;">(Herramientas: ${tools.join(', ')})</span>`;
    } else if (options.showTools) {
      htmlContent += `<span style="font-size: 0.85em; color: #7f8c8d; margin-left: 10px;">(Sin herramientas)</span>`;
    }

    let actionsHtml = '';
    if (options.showAssignBtn) {
      actionsHtml = `
        <button type="button" class="action secondary" style="padding: 2px 5px; font-size: 0.8em; margin-left: 10px;" 
          onclick="promptAssignTool('${value}')">Asignar a Herramienta</button>
      `;
    }

    li.innerHTML = `<div style="display:flex; align-items:center;">${htmlContent}</div>${actionsHtml}`;
    li.dataset.value = value;             // dato limpio para exportar
    li.dataset.type = type;               // dato del tipo 
    ulEl.appendChild(li);
  });
}


window.toggleColumn = function(toolId, checkbox) {
  const checkboxes = document.querySelectorAll(`.matrix-checkbox[data-tool="${toolId}"]`);
  checkboxes.forEach(cb => {
    if (!cb.disabled) {
      cb.checked = checkbox.checked;
    }
  });
};

window.asignarHerramientasMasivo = async function() {
  const checkboxes = document.querySelectorAll('.matrix-checkbox:checked');
  if (checkboxes.length === 0) {
    return alert('Seleccione al menos un IoC duplicado y herramienta.');
  }

  const assignments = Array.from(checkboxes).map(cb => ({
    value: cb.dataset.ioc,
    tool_id: parseInt(cb.dataset.tool)
  }));


  if (!confirm(`¿Confirmar ${assignments.length} asignaciones seleccionadas?`)) {
    return;
  }

  try {
    const res = await apiFetch('/api/iocs/assign-tool-bulk/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ assignments: assignments })
    });
    
    if (!res.ok) {
      const txt = await res.text();
      return alert('Error en asignación masiva: ' + txt);
    }

    const data = await res.json();
    let msg = data.detail;
    if (data.errors && data.errors.length > 0) {
      msg += '\n\nDetalles de omisión (Incompatibilidades u otros):\n' + data.errors.map(e => `- ${e.value}: ${e.reason}`).join('\n');
    }
    alert(msg);
    
    // Opcional: recargar vista general si se necesita
    if (typeof refreshIocList === 'function') refreshIocList();
    
    // Deseleccionar todo
    document.querySelectorAll('.matrix-checkbox, .col-checkbox').forEach(cb => cb.checked = false);

  } catch (err) {
    alert('Error de conexión: ' + err.message);
  }
};

function renderDuplicatesTable(tbodyId, items, toolsInfo) {
  const tbody = document.getElementById(tbodyId);
  const thead = document.getElementById('listaDuplicadosHead');
  const controls = document.getElementById('matrixControls');
  
  if (!tbody || !thead) return;
  tbody.innerHTML = '';
  thead.innerHTML = '';
  
  if (!Array.isArray(items) || items.length === 0) {
    if (controls) controls.style.display = 'none';
    return;
  }
  
  if (controls) controls.style.display = 'block';

  // 1. Renderizar Cabeceras Dinámicas
  const trHead = document.createElement('tr');
  trHead.innerHTML = `
    <th style="padding: 8px; text-align: left; width: 120px;">IoC</th>
    <th style="padding: 8px; text-align: left; width: 80px;">Tipo</th>
    <th style="padding: 8px; text-align: left; width: 120px;">Htas. Actuales</th>
  `;
  
  (toolsInfo || []).forEach(tool => {
    trHead.innerHTML += `
      <th style="padding: 8px; text-align: center; border-left: 1px solid #ddd;">
        <div style="font-size: 0.9em;">Asignar: ${tool.name}</div>
        <div style="margin-top: 5px; font-weight: normal; font-size: 0.8em;">
          <label style="cursor:pointer;"><input type="checkbox" class="col-checkbox" onchange="toggleColumn(${tool.id}, this)"> Todo</label>
        </div>
      </th>
    `;
  });
  thead.appendChild(trHead);

  // 2. Renderizar Filas de Matriz
  items.forEach(it => {
    let value = '';
    let type = '';
    let toolsCurrent = [];
    
    if (typeof it === 'object' && it !== null) {
      value = it.value || it.ioc || it.name || '';
      type = it.detected_type || it.ioc_type || detectarTipoIoc(value);
      toolsCurrent = it.tools || [];
    } else {
      value = String(it);
      type = detectarTipoIoc(value);
    }

    const tr = document.createElement('tr');
    tr.style.borderBottom = '1px solid #eee';

    const toolsHtml = toolsCurrent.length > 0 
      ? toolsCurrent.join(', ') 
      : '<span style="color:#999">Ninguna</span>';

    let rowHtml = `
      <td style="padding: 8px; font-weight: bold; word-break: break-all;">${value}</td>
      <td style="padding: 8px;">${type}</td>
      <td style="padding: 8px;">${toolsHtml}</td>
    `;

    // Generar celda por cada herramienta
    (toolsInfo || []).forEach(tool => {
      let cellContent = '';
      
      // Si el ioc ya tiene esta herramienta
      if (toolsCurrent.includes(tool.name)) {
        cellContent = `<span style="font-size: 0.8em; color: #7f8c8d; background: #ecf0f1; padding: 2px 5px; border-radius: 4px;" title="Ya está asignado">🔒 Ya tiene</span>`;
      } 
      // Si el tipo de ioc no es compatible con esta herramienta
      else if (!tool.compatible_types.includes(type)) {
        cellContent = `<span style="font-size: 0.8em; color: #e74c3c; background: #fdf5f5; padding: 2px 5px; border-radius: 4px;" title="La herramienta no acepta este tipo">🚫 Incompatible</span>`;
      } 
      // Si es compatible y no lo tiene, dibujamos checkbox
      else {
        cellContent = `<input type="checkbox" class="matrix-checkbox" data-ioc="${value}" data-tool="${tool.id}" style="transform: scale(1.2); cursor: pointer;">`;
      }

      rowHtml += `<td style="padding: 8px; text-align: center; border-left: 1px solid #f1f1f1;">${cellContent}</td>`;
    });

    tr.innerHTML = rowHtml;
    tbody.appendChild(tr);
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
  // guardar estado global



  if (!fileInput || !fileInput.files.length) {
    return showMessage(msgEl, 'Selecciona un archivo TXT.', 'warn');
  }

  if (!fuenteEl || !fuenteEl.value) {
    return showMessage(msgEl, 'Selecciona la fuente del lote.', 'warn');
  }

  let finalFuente = fuenteEl.value;
  if (finalFuente === 'Otro') {
    const customEl = document.getElementById('fuenteOTRO');
    if (!customEl || !customEl.value.trim()) {
      return showMessage(msgEl, 'Por favor, especifique el nombre de la fuente en el campo de texto.', 'warn');
    }
    finalFuente = customEl.value.trim();
  }

  const fd = new FormData();
  fd.append('file', fileInput.files[0]);
  fd.append('fuente', finalFuente); // Usar la fuente procesada

  // Save filename for export
  const fname = fileInput.files[0].name;
  window.originalFilename = fname.substring(0, fname.lastIndexOf('.')) || fname;

  showMessage(msgEl, 'Validando archivo...', 'ok');

  try {
    /* ===============================
       1️⃣ VALIDACIÓN
    =============================== */
    const res = await apiFetch('/api/validate-upload/', {
      method: 'POST',
      body: fd
    });

    if (!res.ok) {
      const txt = await res.text();
      return showMessage(msgEl, `Error validación: ${res.status} ${txt}`, 'err');
    }

    const data = await res.json();

    const duplicatesRaw = data.duplicates || [];
    const newRaw = data.new || [];
    const skippedRaw = data.skipped || [];
    const fuente = finalFuente; // Usar la variable local correcta

    const duplicates = duplicatesRaw.map(d => ({
      value: d.value || d,
      detected_type: d.ioc_type || d.detected_type || '',
      tools: d.tools || [],
      fuente
    }));

    const newItems = newRaw.map(n => ({
      value: n.value || n,
      detected_type: n.detected_type || ''
    }));

    const skippedItems = skippedRaw.map(s => ({
      value: `${s.line || s.value || s} - ${s.reason || 'Inválido'}`,
      detected_type: 'Error/Inválido'
    }));

    window.estadoCarga.duplicados = duplicates.map(d => d.value);
    window.estadoCarga.nuevos = newItems.map(n => n.value);

    /* ===============================
       2️⃣ (ELIMINADO) INGESTA AUTOMÁTICA
       - Ahora se requiere clic manual en "Cargar IoCs nuevos".
    =============================== */
    if (newItems.length === 0) {
      showMessage(msgEl, 'No hay IoCs nuevos (todos duplicados o inválidos).', 'warn');
    } else {
      showMessage(msgEl, `Validación completa. ${newItems.length} nuevos listos para cargar.`, 'ok');
    }

    /* ===============================
       3️⃣ ESTADO GLOBAL (DEPURACIÓN)
    =============================== */
    window.iocsDuplicados = duplicates;
    window.iocsNuevos = newItems;
    window.iocFuente = fuente;

    /* ===============================
       4️⃣ UI
    =============================== */
    renderDuplicatesTable('listaDuplicadosBody', duplicates, data.tools_info || []);
    renderListIntoUL(
      document.getElementById('listaNuevos'),
      newItems,
      { showType: true }
    );

    renderListIntoUL(
      document.getElementById('listaErrores'),
      skippedItems,
      { showType: true }
    );

    showMessage(
      msgEl,
      `Proceso completado. Nuevos: ${newItems.length}, Duplicados: ${duplicates.length}, Rechazados: ${skippedItems.length}`,
      'ok'
    );

  } catch (err) {
    console.error(err);
    showMessage(
      msgEl,
      'Error de conexión: ' + (err.message || err),
      'err'
    );
  }
}



async function cargarNuevos() {
  const msgEl = document.getElementById('msgCarga');
  const ul = document.getElementById('listaNuevos');

  // Logic to get source
  const fuenteSelect = document.getElementById('fuenteSelect');
  let fuente = fuenteSelect ? fuenteSelect.value : null;
  if (fuente === 'Otro') {
    const custom = document.getElementById('fuenteOTRO');
    if (custom) fuente = custom.value.trim();
  }

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
      body: JSON.stringify({ items, fuente, file_name: window.originalFilename || '' })
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
    window.lastBatchId = batch;

    showMessage(msgEl, `Insertados: ${inserted.length}. Existían: ${existing.length}. Errores: ${errors.length}`, errors.length ? 'warn' : 'ok');


    // Descargar TXT de ingestados por batch (solo si batch existe y hay insertados)
    if (batch && inserted.length) {
      try {
        const defangParam = isDefangActive() ? '?defang=true' : '';
        const r1 = await apiFetch(`/api/export/ingested-by-batch/${encodeURIComponent(batch)}/${defangParam}`);
        if (r1.ok) {
          const blob = await r1.blob();
          downloadBlob(blob, `iocs_ingestados_${batch}.zip`);
        } else {
          const txt = await r1.text();
          console.warn('No se pudo descargar ingestados:', r1.status, txt);
        }
      } catch (err) {
        console.warn('Error descargando ingestados', err);
      }
    }

    // Auto-descargar ZIPs de depuración (Duplicados y Nuevos)
    try {
      if (window.iocsDuplicados && window.iocsDuplicados.length > 0) {
        const dupItems = window.iocsDuplicados.map(d => ({
          value: d.value,
          detected_type: d.detected_type || 'Desconocido'
        }));
        await downloadClassifiedZip(dupItems, (window.originalFilename || 'iocs') + '_duplicados');
      }

      if (window.estadoCarga && window.estadoCarga.nuevos && window.estadoCarga.nuevos.length > 0) {
        const nuevosItems = window.estadoCarga.nuevos.map(val => ({
          value: val,
          detected_type: (typeof detectarTipoIoc === 'function') ? detectarTipoIoc(val) : 'Desconocido'
        }));
        await downloadClassifiedZip(nuevosItems, (window.originalFilename || 'iocs') + '_nuevos');
      }
    } catch (autoErr) {
      console.warn("Error en auto-descargas de depuración:", autoErr);
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
  MÓDULO: CARGA INICIAL POR HERRAMIENTA
----------------------------*/
async function validarCargaHerramienta() {
  const fileInput = document.getElementById('fileCargaInit');
  const toolSelect = document.getElementById('herramientaSelectInit');
  const msgEl = document.getElementById('msgCargaInit');

  if (!fileInput || !fileInput.files.length) {
    return showMessage(msgEl, 'Selecciona un archivo TXT.', 'warn');
  }
  if (!toolSelect || !toolSelect.value) {
    return showMessage(msgEl, 'Selecciona una Herramienta de destino.', 'warn');
  }

  const fd = new FormData();
  fd.append('file', fileInput.files[0]);
  fd.append('tool_id', toolSelect.value);

  showMessage(msgEl, 'Validando reglas y cruzando datos con base...', 'ok');

  try {
    const res = await apiFetch('/api/tool-initial-load/validate/', {
      method: 'POST',
      body: fd
    });

    if (!res.ok) {
      const txt = await res.text();
      return showMessage(msgEl, `Error validación: ${res.status} ${txt}`, 'err');
    }

    const data = await res.json();
    
    // Almacenar respuesta en variable global para ejecución posterior
    window.toolInitialLoadData = {
      brand_new: data.brand_new || [],
      new_for_tool: data.new_for_tool || [],
      tool_id: toolSelect.value
    };

    document.getElementById('resultadosCargaInit').style.display = 'block';

    renderListIntoUL(
      document.getElementById('listaBrandNew'),
      data.brand_new,
      { showType: true }
    );
    
    renderListIntoUL(
      document.getElementById('listaNewForTool'),
      data.new_for_tool,
      { showType: true }
    );
    
    renderListIntoUL(
      document.getElementById('listaAlreadyLinked'),
      data.already_linked,
      { showType: true }
    );

    const skippedForUI = (data.skipped || []).map(s => ({
      value: `${s.line || s.value || s} - ${s.reason || 'Inválido'}`,
      detected_type: 'Rechazado'
    }));

    renderListIntoUL(
      document.getElementById('listaErroresInit'),
      skippedForUI,
      { showType: true }
    );

    const readyToLoad = (data.brand_new?.length || 0) + (data.new_for_tool?.length || 0);
    if (readyToLoad === 0) {
      showMessage(msgEl, 'No hay IoCs válidos para reasignar a esta herramienta.', 'warn');
    } else {
      showMessage(msgEl, `Cruce completo. ${readyToLoad} IoCs pendientes de enviar a la herramienta seleccionada.`, 'ok');
    }
  } catch (err) {
    console.error(err);
    showMessage(msgEl, 'Error de conexión: ' + (err.message || err), 'err');
  }
}

async function ejecutarCargaHerramienta() {
  const msgEl = document.getElementById('msgCargaInit');
  const context = window.toolInitialLoadData;
  
  if (!context || (!context.brand_new.length && !context.new_for_tool.length)) {
    return showMessage(msgEl, 'No hay datos listos para enviar. Valide primero la carga.', 'warn');
  }

  showMessage(msgEl, `Insertando/Reasignando IoCs hacia la herramienta seleccionada...`, 'ok');

  try {
    const res = await apiFetch('/api/tool-initial-load/execute/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(context)
    });

    if (!res.ok) {
      const txt = await res.text();
      return showMessage(msgEl, `Error al enlazar herramientas: ${res.status} ${txt}`, 'err');
    }

    const data = await res.json();
    showMessage(msgEl, `${data.detail} Creados: ${data.created_iocs}, Asignados: ${data.linked_to_tool}.`, 'ok');

    // Limpiar caché y listas
    window.toolInitialLoadData = null;
    document.getElementById('listaBrandNew').innerHTML = '';
    document.getElementById('listaNewForTool').innerHTML = '';
    
    if (typeof refreshIocList === 'function') refreshIocList();
  } catch (err) {
    console.error(err);
    showMessage(msgEl, 'Error de conexión al reasignar: ' + (err.message || err), 'err');
  }
}

/* ---------------------------
  DEPURACIÓN: generación de TXT
  - generarTxtIngestados(): POST con items = lista de duplicados mostrados en UI
  - generarTxtNoIngresados(): POST con items = lista de nuevos mostrados en UI
----------------------------*/

function generarTxtDuplicadosDesdeValidacion() {
  if (!window.iocsDuplicados || !window.iocsDuplicados.length) {
    alert('No hay IoCs duplicados para exportar.');
    return;
  }

  // Usar nuevo endpoint backend
  const items = window.iocsDuplicados.map(d => ({
    value: d.value,
    detected_type: d.detected_type || 'Desconocido'
  }));

  downloadClassifiedZip(items, (window.originalFilename || 'iocs') + '_duplicados');
}






async function generarTxtNuevos() {
  const itemsRaw = window.estadoCarga?.nuevos || [];
  if (!itemsRaw.length) {
    alert('No hay IoCs nuevos.');
    return;
  }

  const items = itemsRaw.map(val => ({
    value: val,
    detected_type: detectingTypeHelper(val)
  }));

  downloadClassifiedZip(items, (window.originalFilename || 'iocs') + '_nuevos');
}

async function downloadClassifiedZip(items, title) {
  try {
    const res = await apiFetch('/api/export/classified/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        items: items,
        filename_prefix: title,
        defang: isDefangActive()
      })
    });

    if (!res.ok) {
      const txt = await res.text();
      alert(`Error generando ZIP: ${txt}`);
      return;
    }

    const blob = await res.blob();
    downloadBlob(blob, `${title}_classified.zip`);

  } catch (e) {
    console.error(e);
    alert('Error conectando con el servidor para exportar.');
  }
}

// Helper para reusar logica si hace falta
function detectingTypeHelper(v) {
  return (typeof detectarTipoIoc === 'function') ? detectarTipoIoc(v) : 'Desconocido';
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
    const arr = data.results || (Array.isArray(data) ? data : []);

    arr.forEach(ioc => {
      const id = ioc.id || ioc.pk || '';
      const value = ioc.value || ioc.valor || ioc.name || ioc.ioc || '';
      const status = ioc.status || ioc.estado || '';
      const tipo = detectarTipoIoc(value);

      const tr = document.createElement('tr');

      const tdValue = document.createElement('td');
      tdValue.textContent = value;
      tr.appendChild(tdValue);

      const tdType = document.createElement('td');
      tdType.textContent = tipo;
      tr.appendChild(tdType);

      const tdStatus = document.createElement('td');
      tdStatus.textContent = status;
      tr.appendChild(tdStatus);

      const tdAction = document.createElement('td');
      const btn = document.createElement('button');
      btn.textContent = 'Cambiar';
      btn.onclick = function () { toggleIocState(btn, id, status); }; // Safe closure
      tdAction.appendChild(btn);
      tr.appendChild(tdAction);

      tbody.appendChild(tr);
    });

    showMessage(msgEl || 'msgGestionManual', `Resultados: ${arr.length}`, 'ok');
  } catch (err) {
    showMessage(msgEl || 'msgGestionManual', 'Error conexión búsqueda: ' + (err.message || err), 'err');
    console.error(err);
  }
}

window.toggleIocState = async function(btn, iocId, currentStatus) {
  if (currentStatus === 'NO EXISTE') {
    alert('El indicador no existe en la base de datos y no se puede cambiar su estado.');
    return;
  }
  const nextStatus = currentStatus === 'BLOQUEADO' ? 'DEPURADO' : 'BLOQUEADO';
  
  btn.disabled = true;
  const originalText = btn.textContent;
  btn.textContent = '...';
  
  const msgEl = document.getElementById('msgGestionManual') || null;
  try {
    const res = await apiFetch('/api/change-state/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ioc_id: iocId, new_state: nextStatus })
    });
    if (!res.ok) {
      const txt = await res.text();
      showMessage(msgEl || 'msgGestionManual', `Error cambiando estado: ${res.status} ${txt}`, 'err');
      return;
    }
    const data = await res.json();
    showMessage(msgEl || 'msgGestionManual', data.detail || 'Estado actualizado', 'ok');
    
    // Actualizar visualmente la fila
    const tr = btn.closest('tr');
    if (tr) {
      tr.cells[2].textContent = nextStatus;
      
      // Actualizar data-item del botón Detalles de la misma fila
      const detBtn = tr.querySelector('button[onclick^="mostrarDetalles"]');
      if (detBtn) {
        const itemData = JSON.parse(detBtn.getAttribute('data-item'));
        itemData.status = nextStatus;
        detBtn.setAttribute('data-item', JSON.stringify(itemData));
      }
    }
    
    // Actualizar el onclick del botón Cambiar
    if (btn.onclick) {
      btn.onclick = function() { toggleIocState(btn, iocId, nextStatus); };
    } else {
      btn.setAttribute('onclick', `toggleIocState(this, ${JSON.stringify(iocId).replace(/"/g, '&quot;')}, '${nextStatus}')`);
    }
  } catch (err) {
    showMessage(msgEl || 'msgGestionManual', 'Error de conexión: ' + (err.message || err), 'err');
    console.error(err);
  } finally {
    btn.disabled = false;
    btn.textContent = originalText;
  }
};

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
      `Encontrados: ${(data.updated && data.updated.length) || 0}`,
      `No encontrados: ${(data.not_found && data.not_found.length) || 0}`,
      `Errores: ${(data.errors && data.errors.length) || 0}`
    ];
    if (data.not_found && data.not_found.length) {
      out.push('No encontrados (ejemplo):');
      data.not_found.slice(0, 50).forEach(v => out.push(` - ${v}`));
    }
    if (data.errors && data.errors.length) {
      out.push('Errores (ejemplo):');
      data.errors.slice(0, 20).forEach(e => out.push(` - ${e.value}: ${e.error}`));
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
  if (!confirm("¿Seguro que quieres eliminar TODOS los IoCs en estado 'DEPURADO'?\n\nSe descargará un reporte TXT con el detalle.\nEsta acción es irreversible y NO guardará historial en base de datos.")) return;

  const msgEl = document.getElementById('msgEstados') || document.getElementById('msgGestionManual') || null;
  showMessage(msgEl, 'Procesando eliminación y generando reporte...', 'ok');

  try {
    // Llamada directa a purge (sin crear audit previo)
    const res = await apiFetch('/api/purge/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dry_run: false })
    });

    if (!res.ok) {
      const txt = await res.text();
      return showMessage(msgEl, `Error al purgar: ${res.status} ${txt}`, 'err');
    }

    // El backend ahora devuelve un ARCHIVO (Blob), no JSON
    const blob = await res.blob();

    // Obtener nombre del header o usar default
    let filename = `reporte_eliminacion_${new Date().toISOString().slice(0, 10)}.txt`;
    const disposition = res.headers.get('Content-Disposition');
    if (disposition && disposition.indexOf('filename="') !== -1) {
      filename = disposition.split('filename="')[1].split('"')[0];
    }

    // Descargar archivo
    downloadBlob(blob, filename);

    showMessage(msgEl, `Eliminados correctamente. Reporte descargado: ${filename}`, 'ok');

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
    const arr = data.results || (Array.isArray(data) ? data : []);
    tbody.innerHTML = '';

    arr.forEach(ioc => {
      const id = ioc.id || ioc.pk || '';
      const value = ioc.value || ioc.valor || ioc.name || ioc.ioc || '';
      const type = (ioc.ioc_type && (ioc.ioc_type.name || ioc.ioc_type)) || detectarTipoIoc(value);
      const status = ioc.status || ioc.estado || '';

      const tr = document.createElement('tr');

      const tdValue = document.createElement('td');
      tdValue.textContent = value;
      tr.appendChild(tdValue);

      const tdType = document.createElement('td');
      tdType.textContent = type;
      tr.appendChild(tdType);

      const tdStatus = document.createElement('td');
      tdStatus.textContent = status;
      tr.appendChild(tdStatus);

      const tdAction = document.createElement('td');
      const btn = document.createElement('button');
      btn.textContent = 'Cambiar';
      btn.onclick = function () { toggleIocState(btn, id, status); };
      tdAction.appendChild(btn);
      tr.appendChild(tdAction);

      tbody.appendChild(tr);
    });
  } catch (err) {
    console.warn('refreshIocList error', err);
  }
}

async function generarReporte() {
  const inicio = document.getElementById('fechaInicio').value;
  const fin = document.getElementById('fechaFin').value;
  const tipo = document.getElementById('tipoReporte').value || 'resumen';

  const fuente = document.getElementById('fuenteSelectReport') ? document.getElementById('fuenteSelectReport').value.trim() : '';

  // Nuevos params
  const fuenteCustom = document.getElementById('fuenteCustomReport') ? document.getElementById('fuenteCustomReport').value.trim() : '';
  const iocType = document.getElementById('filtroIocTypeReport') ? document.getElementById('filtroIocTypeReport').value.trim() : '';

  const msgEl = document.getElementById('msgReporte');
  if (!inicio || !fin) {
    return showMessage(msgEl, 'Selecciona fecha inicio y fin', 'warn');
  }

  showMessage(msgEl, 'Generando reporte...', 'ok');

  // construir query string
  const params = new URLSearchParams({ inicio, fin, tipo });
  if (fuente) params.set('fuente', fuente);
  if (fuenteCustom) params.set('fuente_custom', fuenteCustom);
  if (iocType) params.set('ioc_type', iocType);

  try {
    const res = await apiFetch(`/api/reportes/?${params.toString()}`, { method: 'GET' });
    if (!res.ok) {
      const txt = await res.text();
      showMessage(msgEl, `Error al generar el reporte: ${res.status} ${txt}`, 'err');
      return;
    }

    // leer blob y descargar
    const blob = await res.blob();
    // nombre de archivo sugerido
    const filename = `reporte_artemis_${tipo}_${inicio.replace(/-/g, '')}_${fin.replace(/-/g, '')}.txt`;
    downloadBlob(blob, filename);
    showMessage(msgEl, 'Reporte generado y descargado.', 'ok');
  } catch (err) {
    console.error('Error generando reporte', err);
    showMessage(msgEl, 'Error generando reporte: ' + (err.message || err), 'err');
  }
}

// Duplicate downloadBlob removed

async function apiFetch(url, options = {}) {
  const opts = {
    credentials: 'include', // 🔒 sesiones Django
    ...options
  };

  const res = await fetch(url, opts);

  if (res.status === 401 || res.status === 403) {
    console.warn('Sesión expirada o no autenticado');
    window.location.href = '/login/';
    throw new Error('No autenticado');
  }

  return res;
}


function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
  return null;
}




// Initialize listeners
document.addEventListener('DOMContentLoaded', function () {
  const fSelect = document.getElementById('fuenteSelect');
  const fOtro = document.getElementById('fuenteOTRO');
  if (fSelect && fOtro) {
    fSelect.addEventListener('change', function () {
      if (this.value === 'Otro') {
        fOtro.style.display = 'block';
        fOtro.focus();
      } else {
        fOtro.style.display = 'none';
        fOtro.value = ''; // clear if hidden
        fOtro.value = ''; // clear if hidden
      }
    });

    // Report Source Custom
    const rSelect = document.getElementById('fuenteSelectReport');
    const rOtro = document.getElementById('fuenteCustomReport');
    if (rSelect && rOtro) {
      rSelect.addEventListener('change', function () {
        if (this.value === 'Otro') {
          rOtro.style.display = 'inline-block'; // or block
          rOtro.focus();
        } else {
          rOtro.style.display = 'none';
          rOtro.value = '';
        }
      });
    }
  }
});
