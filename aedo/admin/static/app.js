// Il Banco del Master — logica dell'interfaccia (vanilla JS, nessun build).
// Due metà: il Quadro di Comando (servizi) e il Controllo dello Stato (scrittura DB).

const $ = (sel, root = document) => root.querySelector(sel);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

async function jf(url, { method = 'GET', body } = {}) {
  const res = await fetch(url, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
  return data;
}

let toastTimer = null;
function toast(msg, isErr = false) {
  const t = $('#toast');
  t.textContent = msg;
  t.className = 'toast' + (isErr ? ' err' : '');
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, 3000);
}

// ============================================================
//  QUADRO DI COMANDO
// ============================================================
const STATE_LABEL = {
  running: 'in funzione', stopped: 'spento',
  errored: 'errore', unavailable: 'non disponibile',
};
const openConsoles = new Set();
let lastServicesJson = '';
let servicesList = [];

async function loadServices() {
  let list;
  try {
    list = await jf('/admin/api/command/services');
  } catch {
    return;
  }
  servicesList = list;
  const json = JSON.stringify(list);
  if (json !== lastServicesJson) {
    lastServicesJson = json;
    renderServices(list);
  }
  refreshConsoles();
}

function renderServices(list) {
  const apiOn = list.some((s) => s.key === 'api' && s.state === 'running');
  $('#services').innerHTML = list.map((s) => {
    const on = s.state === 'running';
    const disabled = s.state === 'unavailable';
    const open = (on && s.url)
      ? `<button class="btn-console" data-action="open" title="Apri nel browser">apri ↗</button>` : '';
    const hint = s.unavailable_hint
      ? `<div class="unavailable-hint">${esc(s.unavailable_hint)}</div>` : '';
    // La web giocatore ha bisogno anche dell'API accesa (fa da proxy verso :8000).
    const depHint = (s.key === 'web' && on && !apiOn)
      ? `<div class="dep-hint">⚠ Accendi anche l'API giocatore, o la dashboard mostrerà un errore.</div>` : '';
    const consoleOpen = openConsoles.has(s.key);
    return `
      <div class="service" data-key="${esc(s.key)}">
        <div class="service-head">
          <span class="led ${esc(s.state)}"></span>
          <span class="service-name">${esc(s.label)}</span>
          <span class="service-state">${esc(STATE_LABEL[s.state] || s.state)}</span>
        </div>
        <div class="service-desc">${esc(s.description)}</div>
        <div class="service-actions">
          <button class="lever ${on ? 'on' : ''}" data-action="toggle"
                  data-running="${on}" ${disabled ? 'disabled' : ''}
                  title="${on ? 'Spegni' : 'Accendi'}"><span class="knob"></span></button>
          ${open}
          <button class="btn-console" data-action="console">${consoleOpen ? 'nascondi log' : 'log'}</button>
          <button class="btn-console" data-action="expand" title="Apri i log in grande">⤢</button>
        </div>
        ${hint}${depHint}
        <div class="console" data-role="console" ${consoleOpen ? '' : 'hidden'}></div>
      </div>`;
  }).join('');
}

$('#services').addEventListener('click', async (e) => {
  const btn = e.target.closest('button');
  if (!btn) return;
  const key = btn.closest('.service').dataset.key;
  if (btn.dataset.action === 'toggle') {
    const running = btn.dataset.running === 'true';
    btn.disabled = true;
    try {
      const r = await jf(`/admin/api/command/services/${key}/${running ? 'stop' : 'start'}`, { method: 'POST' });
      toast(`${key}: ${r.message}`);
    } catch (err) {
      toast(`${key}: ${err.message}`, true);
    }
    lastServicesJson = '';
    await loadServices();
  } else if (btn.dataset.action === 'console') {
    if (openConsoles.has(key)) openConsoles.delete(key);
    else openConsoles.add(key);
    lastServicesJson = '';
    await loadServices();
  } else if (btn.dataset.action === 'open') {
    try {
      await jf(`/admin/api/command/services/${key}/open`, { method: 'POST' });
      toast('Apro nel browser…');
    } catch (err) {
      toast(err.message, true);
    }
  } else if (btn.dataset.action === 'expand') {
    openLogModal(key);
  }
});

// --- Finestra grande dei log ---
let logModalKey = null;
let logModalTimer = null;

function openLogModal(key) {
  const svc = servicesList.find((s) => s.key === key);
  logModalKey = key;
  $('#log-modal-title').textContent = 'Log — ' + (svc ? svc.label : key);
  $('#log-modal-body').textContent = '';
  $('#log-modal').hidden = false;
  refreshModalLogs();
  clearInterval(logModalTimer);
  logModalTimer = setInterval(refreshModalLogs, 1200);
}

async function refreshModalLogs() {
  if (!logModalKey) return;
  try {
    const { lines } = await jf(`/admin/api/command/services/${logModalKey}/logs?limit=500`);
    const box = $('#log-modal-body');
    const follow = $('#log-autoscroll').checked;
    box.textContent = (lines || []).join('\n');
    if (follow) box.scrollTop = box.scrollHeight;
  } catch { /* servizio non disponibile */ }
}

function closeLogModal() {
  logModalKey = null;
  clearInterval(logModalTimer);
  $('#log-modal').hidden = true;
}

$('#log-close').addEventListener('click', closeLogModal);
$('#log-modal').addEventListener('click', (e) => { if (e.target.id === 'log-modal') closeLogModal(); });
$('#log-copy').addEventListener('click', () => {
  const text = $('#log-modal-body').textContent;
  if (navigator.clipboard) navigator.clipboard.writeText(text).then(() => toast('Log copiati.'));
});
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && logModalKey) closeLogModal(); });

async function refreshConsoles() {
  for (const key of openConsoles) {
    try {
      const { lines } = await jf(`/admin/api/command/services/${key}/logs?limit=200`);
      const box = document.querySelector(`.service[data-key="${key}"] .console`);
      if (box) {
        const atBottom = box.scrollTop + box.clientHeight >= box.scrollHeight - 10;
        box.textContent = (lines || []).join('\n');
        if (atBottom) box.scrollTop = box.scrollHeight;
      }
    } catch { /* servizio sparito: ignora */ }
  }
}

// ============================================================
//  CONTROLLO DELLO STATO
// ============================================================
let campaignId = null;
let state = null;

async function loadCampaigns() {
  let camps = [];
  try {
    camps = await jf('/admin/api/campaigns');
  } catch {
    toast('API dati non raggiungibile.', true);
    return;
  }
  const sel = $('#campaign-select');
  if (!camps.length) {
    sel.innerHTML = '<option>nessuna campagna</option>';
    $('#state-empty').textContent = 'Nessuna campagna. Creane una su Discord con /nuova-campagna.';
    return;
  }
  sel.innerHTML = camps.map((c) =>
    `<option value="${c.id}">${esc(c.name)} — ${esc(c.genre)}</option>`).join('');
  sel.onchange = () => selectCampaign(Number(sel.value));
  selectCampaign(camps[0].id);
}

async function selectCampaign(id) {
  campaignId = id;
  try {
    state = await jf(`/admin/api/campaigns/${id}/state`);
    renderState();
  } catch (err) {
    toast(err.message, true);
  }
}

function applyState(newState) {
  state = newState;
  renderState();
}

// Wrapper: esegue una scrittura, aggiorna lo stato dalla risposta, avvisa.
async function write(url, method, body, okMsg) {
  try {
    const updated = await jf(url, { method, body });
    applyState(updated);
    if (okMsg) toast(okMsg);
  } catch (err) {
    toast(err.message, true);
  }
}
const base = () => `/admin/api/campaigns/${campaignId}`;

function renderState() {
  if (!state) return;
  $('#state-empty').hidden = true;
  $('#state-panels').hidden = false;
  renderCharacters();
  renderInventory();
  renderRelationships();
  renderObjectives();
  renderNpcForm();
}

// ---- Personaggi: attributi, risorse, condizioni ----
function renderCharacters() {
  const attrs = state.attributes.map((a) => a.name);
  $('#characters-body').innerHTML = state.characters.map((ch) => {
    const attrChips = attrs.map((name) => `
      <span class="chip">${esc(name)}
        <button class="step" data-act="attr" data-id="${ch.id}" data-name="${esc(name)}" data-d="-1">−</button>
        <span class="val">${ch.attributes[name] ?? 0}</span>
        <button class="step" data-act="attr" data-id="${ch.id}" data-name="${esc(name)}" data-d="1">+</button>
      </span>`).join('');
    const resChips = Object.entries(ch.resources).map(([k, v]) => `
      <span class="chip">${esc(k)}
        <button class="step" data-act="res-adj" data-id="${ch.id}" data-name="${esc(k)}" data-d="-1">−</button>
        <span class="val">${v}</span>
        <button class="step" data-act="res-adj" data-id="${ch.id}" data-name="${esc(k)}" data-d="1">+</button>
        <button class="chip-x" data-act="res-del" data-id="${ch.id}" data-name="${esc(k)}" title="Rimuovi risorsa">×</button>
      </span>`).join('') || '<span class="muted">nessuna</span>';
    const condChips = (ch.conditions || []).map((c) => `
      <span class="chip">${esc(c)}
        <button class="chip-x" data-act="cond-del" data-id="${ch.id}" data-name="${esc(c)}">×</button>
      </span>`).join('') || '<span class="muted">nessuna</span>';
    const del = ch.is_player ? '' :
      `<button class="btn-ghost btn-danger" data-act="npc-del" data-id="${ch.id}" style="margin-left:auto">elimina</button>`;
    return `
      <div class="entity">
        <div class="entity-head">
          <span class="entity-name">${esc(ch.name)}</span>
          <span class="badge ${ch.is_player ? 'pg' : 'npc'}">${ch.is_player ? 'giocante' : 'NPC'}</span>
          ${del}
        </div>
        <div class="mini-label">Attributi</div><div class="kv">${attrChips}</div>
        <div class="mini-label">Risorse</div><div class="kv">${resChips}</div>
        <div class="mini-form">
          <input class="small" placeholder="nome" data-f="res-name-${ch.id}" />
          <input class="small" type="number" value="0" data-f="res-val-${ch.id}" />
          <button class="btn-ghost" data-act="res-set" data-id="${ch.id}">imposta risorsa</button>
        </div>
        <div class="mini-label">Condizioni</div><div class="kv">${condChips}</div>
        <div class="mini-form">
          <input placeholder="nuova condizione" data-f="cond-${ch.id}" />
          <button class="btn-ghost" data-act="cond-add" data-id="${ch.id}">aggiungi</button>
        </div>
      </div>`;
  }).join('');
}

$('#characters-body').addEventListener('click', (e) => {
  const b = e.target.closest('button'); if (!b) return;
  const id = b.dataset.id, name = b.dataset.name, act = b.dataset.act;
  const cbase = `${base()}/characters/${id}`;
  if (act === 'attr') {
    const cur = state.characters.find((c) => String(c.id) === id).attributes[name] ?? 0;
    write(cbase, 'PATCH', { attributes: { [name]: cur + Number(b.dataset.d) } });
  } else if (act === 'res-adj') {
    write(`${cbase}/resources/adjust`, 'POST', { name, delta: Number(b.dataset.d) });
  } else if (act === 'res-del') {
    write(`${cbase}/resources/remove`, 'POST', { condition: name });
  } else if (act === 'res-set') {
    const rn = $(`[data-f="res-name-${id}"]`).value.trim();
    const rv = Number($(`[data-f="res-val-${id}"]`).value);
    if (!rn) return toast('Indica il nome della risorsa.', true);
    write(`${cbase}/resources/set`, 'POST', { name: rn, value: rv }, 'Risorsa impostata.');
  } else if (act === 'cond-add') {
    const c = $(`[data-f="cond-${id}"]`).value.trim();
    if (!c) return;
    write(`${cbase}/conditions/add`, 'POST', { condition: c }, 'Condizione aggiunta.');
  } else if (act === 'cond-del') {
    write(`${cbase}/conditions/remove`, 'POST', { condition: name });
  } else if (act === 'npc-del') {
    if (confirm('Eliminare questo NPC?')) write(cbase, 'DELETE', null, 'NPC eliminato.');
  }
});

// ---- Inventario ----
function renderInventory() {
  const owner = (id) => state.characters.find((c) => c.id === id);
  const rows = state.items.map((it) => {
    const o = owner(it.owner_id);
    return `
      <div class="entity rel-line">
        <span class="entity-name">${esc(it.name)}</span>
        <span class="chip">qty
          <button class="step" data-act="qty" data-id="${it.id}" data-q="${it.quantity - 1}">−</button>
          <span class="val">${it.quantity}</span>
          <button class="step" data-act="qty" data-id="${it.id}" data-q="${it.quantity + 1}">+</button>
        </span>
        <span class="muted">${o ? esc(o.name) : 'nel mondo'}</span>
        <button class="btn-ghost btn-danger" data-act="item-del" data-id="${it.id}" style="margin-left:auto">togli</button>
      </div>`;
  }).join('') || '<p class="muted">Nessun oggetto.</p>';
  const ownerOpts = state.characters.map((c) =>
    `<option value="${c.id}">${esc(c.name)}</option>`).join('');
  $('#inventory-body').innerHTML = `${rows}
    <div class="mini-label">Dai un oggetto</div>
    <div class="mini-form">
      <select data-f="item-owner">${ownerOpts}</select>
      <input placeholder="oggetto" data-f="item-name" />
      <input class="small" type="number" value="1" min="1" data-f="item-qty" />
      <button class="btn-wax" data-act="item-give">Dai</button>
    </div>`;
}

$('#inventory-body').addEventListener('click', (e) => {
  const b = e.target.closest('button'); if (!b) return;
  const act = b.dataset.act;
  if (act === 'qty') {
    write(`${base()}/items/${b.dataset.id}`, 'PATCH', { quantity: Number(b.dataset.q) });
  } else if (act === 'item-del') {
    write(`${base()}/items/${b.dataset.id}`, 'DELETE', null, 'Oggetto tolto.');
  } else if (act === 'item-give') {
    const owner_id = Number($('[data-f="item-owner"]').value);
    const name = $('[data-f="item-name"]').value.trim();
    const quantity = Math.max(1, Number($('[data-f="item-qty"]').value) || 1);
    if (!name) return toast('Indica il nome dell\'oggetto.', true);
    write(`${base()}/items`, 'POST', { owner_id, name, quantity }, 'Oggetto consegnato.');
  }
});

// ---- Relazioni ----
function renderRelationships() {
  const name = (id) => (state.characters.find((c) => c.id === id) || {}).name || '?';
  const rows = state.relationships.map((r) => {
    const pct = Math.round((r.affinity + 100) / 2);
    const cls = r.affinity >= 0 ? 'pos' : 'neg';
    return `
      <div class="entity">
        <div class="rel-line">
          <span class="entity-name">${esc(name(r.from_id))} → ${esc(name(r.to_id))}</span>
          <input value="${esc(r.kind)}" data-f="rel-kind-${r.id}" style="width:120px"
                 data-act="rel-kind" data-id="${r.id}" />
          <button class="btn-ghost btn-danger" data-act="rel-del" data-id="${r.id}" style="margin-left:auto">elimina</button>
        </div>
        <div class="rel-line">
          <button class="step" data-act="rel-aff" data-id="${r.id}" data-d="-5">−5</button>
          <div class="aff-bar"><div class="aff-fill ${cls}" style="width:${pct}%"></div></div>
          <span class="val" style="min-width:34px;text-align:right">${r.affinity > 0 ? '+' : ''}${r.affinity}</span>
          <button class="step" data-act="rel-aff" data-id="${r.id}" data-d="5">+5</button>
        </div>
      </div>`;
  }).join('') || '<p class="muted">Nessun legame.</p>';
  const opts = state.characters.map((c) => `<option value="${c.id}">${esc(c.name)}</option>`).join('');
  $('#relationships-body').innerHTML = `${rows}
    <div class="mini-label">Nuovo legame</div>
    <div class="mini-form">
      <select data-f="rel-from">${opts}</select>
      <span>→</span>
      <select data-f="rel-to">${opts}</select>
      <input placeholder="tipo" value="conoscente" data-f="rel-newkind" style="width:110px" />
      <input class="small" type="number" value="0" data-f="rel-newaff" />
      <button class="btn-wax" data-act="rel-create">Crea</button>
    </div>`;
}

$('#relationships-body').addEventListener('click', (e) => {
  const b = e.target.closest('button'); if (!b) return;
  const act = b.dataset.act, id = b.dataset.id;
  if (act === 'rel-aff') {
    write(`${base()}/relationships/${id}`, 'PATCH', { affinity_delta: Number(b.dataset.d) });
  } else if (act === 'rel-del') {
    write(`${base()}/relationships/${id}`, 'DELETE', null, 'Legame eliminato.');
  } else if (act === 'rel-create') {
    const from_id = Number($('[data-f="rel-from"]').value);
    const to_id = Number($('[data-f="rel-to"]').value);
    const kind = $('[data-f="rel-newkind"]').value.trim() || 'conoscente';
    const affinity = Number($('[data-f="rel-newaff"]').value) || 0;
    if (from_id === to_id) return toast('Scegli due personaggi diversi.', true);
    write(`${base()}/relationships`, 'POST', { from_id, to_id, kind, affinity }, 'Legame creato.');
  }
});
$('#relationships-body').addEventListener('change', (e) => {
  const inp = e.target.closest('[data-act="rel-kind"]');
  if (!inp) return;
  write(`${base()}/relationships/${inp.dataset.id}`, 'PATCH', { kind: inp.value.trim() });
});

// ---- Obiettivi ----
function renderObjectives() {
  const statuses = [['open', 'apri'], ['completed', 'completa'], ['failed', 'fallisci']];
  const rows = state.objectives.map((o) => {
    const btns = statuses.map(([s, lbl]) =>
      `<button class="btn-ghost ${o.status === s ? 'active' : ''}" data-act="obj-status"
               data-id="${o.id}" data-s="${s}">${lbl}</button>`).join('');
    return `
      <div class="entity">
        <div class="rel-line">
          <span class="entity-name ${o.status === 'completed' ? 'done' : ''}">${esc(o.title)}</span>
          <button class="btn-ghost btn-danger" data-act="obj-del" data-id="${o.id}" style="margin-left:auto">elimina</button>
        </div>
        <div class="obj-status">${btns}</div>
      </div>`;
  }).join('') || '<p class="muted">Nessun obiettivo.</p>';
  $('#objectives-body').innerHTML = `${rows}
    <div class="mini-label">Nuovo obiettivo</div>
    <div class="mini-form">
      <input placeholder="titolo della quest" data-f="obj-title" style="flex:1" />
      <button class="btn-wax" data-act="obj-create">Crea</button>
    </div>`;
}

$('#objectives-body').addEventListener('click', (e) => {
  const b = e.target.closest('button'); if (!b) return;
  const act = b.dataset.act, id = b.dataset.id;
  if (act === 'obj-status') {
    write(`${base()}/objectives/${id}/status`, 'POST', { status: b.dataset.s });
  } else if (act === 'obj-del') {
    write(`${base()}/objectives/${id}`, 'DELETE', null, 'Obiettivo eliminato.');
  } else if (act === 'obj-create') {
    const title = $('[data-f="obj-title"]').value.trim();
    if (!title) return toast('Indica il titolo.', true);
    write(`${base()}/objectives`, 'POST', { title }, 'Obiettivo creato.');
  }
});

// ---- Nuovo NPC ----
function renderNpcForm() {
  $('#npc-body').innerHTML = `
    <div class="mini-form">
      <input placeholder="nome" data-f="npc-name" />
      <input placeholder="descrizione (opzionale)" data-f="npc-desc" style="flex:1" />
      <button class="btn-wax" data-act="npc-create">Crea NPC</button>
    </div>`;
}

$('#npc-body').addEventListener('click', (e) => {
  const b = e.target.closest('button'); if (!b || b.dataset.act !== 'npc-create') return;
  const name = $('[data-f="npc-name"]').value.trim();
  const description = $('[data-f="npc-desc"]').value.trim();
  if (!name) return toast('Indica il nome dell\'NPC.', true);
  write(`${base()}/npcs`, 'POST', { name, description }, 'NPC creato.');
});

// ============================================================
//  AVVIO
// ============================================================
loadServices();
loadCampaigns();
setInterval(loadServices, 2500);
