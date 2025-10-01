// Helper para leer cookie CSRF (standard Django)
function getCookie(name) {
  const cookieValue = document.cookie.split('; ').find(row => row.startsWith(name + '='));
  return cookieValue ? decodeURIComponent(cookieValue.split('=')[1]) : null;
}

async function cargarEstadosDesdeTxt() {
  const inputFile = document.getElementById('fileEstados');
  const selectState = document.getElementById('nuevoEstado');
  const msgEl = document.getElementById('msgEstados');

  msgEl.style.display = 'none';
  if (!inputFile.files || inputFile.files.length === 0) {
    msgEl.textContent = 'Por favor, selecciona un archivo .txt.';
    msgEl.className = 'message warning';
    msgEl.style.display = 'block';
    return;
  }
  const file = inputFile.files[0];
  const newState = selectState.value;

  if (!['BLOQUEADO', 'DEPURADO'].includes(newState)) {
    msgEl.textContent = 'Selecciona un estado válido (BLOQUEADO o DEPURADO).';
    msgEl.className = 'message warning';
    msgEl.style.display = 'block';
    return;
  }

  // preparar FormData
  const fd = new FormData();
  fd.append('file', file);
  fd.append('new_state', newState);

  // CSRF
  const csrftoken = getCookie('csrftoken');

  try {
    const resp = await fetch('/iocs/bulk_change_state/', {
      method: 'POST',
      body: fd,
      headers: csrftoken ? {'X-CSRFToken': csrftoken} : {}
    });

    if (!resp.ok) {
      const txt = await resp.text();
      msgEl.textContent = `Error del servidor: ${resp.status} ${txt}`;
      msgEl.className = 'message err';
      msgEl.style.display = 'block';
      return;
    }

    const data = await resp.json();

    // Mostrar resultado amigable
    let out = [];
    out.push(`Actualizados: ${data.updated_count || 0}`);
    if (data.updated && data.updated.length) {
      out.push('Detalles (actualizados/unchanged):');
      data.updated.slice(0,50).forEach(u => {
        if (u.unchanged) out.push(` - ${u.value}: sin cambio (ya ${u.old})`);
        else out.push(` - ${u.value}: ${u.old} -> ${u.new}`);
      });
      if (data.updated.length > 50) out.push(` (mostrando 50 de ${data.updated.length})`);
    }
    if (data.not_found && data.not_found.length) {
      out.push('');
      out.push(`No encontrados (${data.not_found.length}):`);
      data.not_found.slice(0, 50).forEach(v => out.push(` - ${v}`));
      if (data.not_found.length > 50) out.push(` (mostrando 50 de ${data.not_found.length})`);
    }
    if (data.errors && data.errors.length) {
      out.push('');
      out.push(`Errores (${data.errors.length}):`);
      data.errors.slice(0, 20).forEach(e => out.push(` - ${e.value}: ${e.error}`));
    }

    msgEl.textContent = out.join('\n');
    msgEl.className = 'message success';
    msgEl.style.whiteSpace = 'pre-wrap';
    msgEl.style.display = 'block';

    // opcional: refrescar tablas en UI (llama a tu función de listado)
    if (typeof refreshIocList === 'function') refreshIocList();

  } catch (err) {
    console.error(err);
    msgEl.textContent = 'Error de conexión o excepción: ' + err.message;
    msgEl.className = 'message err';
    msgEl.style.display = 'block';
  }
}
