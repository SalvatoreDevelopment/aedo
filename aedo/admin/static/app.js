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
let lastCampaignsJson = '';

// Ricaricata all'avvio e ogni pochi secondi: così una campagna creata su Discord
// mentre il Banco è aperto compare da sola, senza riavviare. Preserva la
// campagna che stai guardando (non ti resetta i pannelli sotto le mani).
async function loadCampaigns() {
  let camps = [];
  try {
    camps = await jf('/admin/api/campaigns');
  } catch {
    if (!lastCampaignsJson) toast('Dati non raggiungibili.', true);
    return;
  }
  const json = JSON.stringify(camps);
  if (json === lastCampaignsJson) return;  // niente di nuovo: non toccare la UI
  lastCampaignsJson = json;

  const sel = $('#campaign-select');
  if (!camps.length) {
    sel.innerHTML = '<option>nessuna campagna</option>';
    $('#state-empty').textContent = 'Nessuna campagna. Creane una su Discord con /nuova-campagna.';
    $('#state-empty').hidden = false;
    $('#state-panels').hidden = true;
    campaignId = null;
    return;
  }
  const prev = campaignId;
  sel.innerHTML = camps.map((c) =>
    `<option value="${c.id}">${esc(c.name)} — ${esc(c.genre)}</option>`).join('');
  sel.onchange = () => selectCampaign(Number(sel.value));

  // Mantieni la selezione corrente se esiste ancora; altrimenti prendi la prima.
  const stillThere = camps.some((c) => c.id === prev);
  const target = stillThere ? prev : camps[0].id;
  sel.value = String(target);
  if (target !== prev) selectCampaign(target);  // carica lo stato solo se cambia
}

$('#delete-campaign').addEventListener('click', async () => {
  if (!campaignId) return;
  const name = (state && state.name) || 'questa campagna';
  const ok = confirm(
    `Eliminare DEFINITIVAMENTE «${name}» e tutto il suo contenuto ` +
    `(personaggio, NPC, diario, ricordi, relazioni, obiettivi)?\n\n` +
    `Anche il canale Discord verrà cancellato (col bot acceso).\n` +
    `L'azione è irreversibile.`
  );
  if (!ok) return;
  try {
    const r = await jf(`/admin/api/campaigns/${campaignId}`, { method: 'DELETE' });
    toast(r.channel_queued
      ? 'Campagna eliminata. Il canale Discord sparirà a breve (serve il bot acceso).'
      : 'Campagna eliminata.');
    campaignId = null;
    state = null;
    lastCampaignsJson = '';   // forza il ricaricamento della lista
    await loadCampaigns();
  } catch (err) {
    toast(err.message, true);
  }
});

async function selectCampaign(id) {
  campaignId = id;
  try {
    state = await jf(`/admin/api/campaigns/${id}/state`);
    renderState();
    loadRegia();
    loadBlueprint();
    renderTools();
    loadStats();
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

// ---- Regia narrativa ----
let regia = null;
let regiaTimer = null;
const CMD_KIND = { inject_event: 'Evento diretto', narrate_event: 'Evento narrato da Aedo', override_last: 'Correzione esito' };
const CMD_STATUS = { pending: '⏳ in coda', done: '✓ postato', error: '✕ errore' };
const OUTCOME_LABEL = { success: 'successo', success_cost: 'riesci, ma…', failure: 'fallimento' };

async function loadRegia() {
  if (!campaignId) return;
  try {
    regia = await jf(`/admin/api/campaigns/${campaignId}/regia`);
    renderRegia();
  } catch { /* la campagna potrebbe non esistere più */ }
}

async function writeRegia(url, method, body, okMsg) {
  try {
    regia = await jf(url, { method, body });
    renderRegia();
    if (okMsg) toast(okMsg);
  } catch (err) {
    toast(err.message, true);
  }
}

function renderRegia() {
  if (!regia) return;
  const r = regia;
  const noChannel = !r.has_channel
    ? `<div class="dep-hint">⚠ Questa campagna non ha un canale Discord: gli eventi non hanno dove essere postati (le note funzionano comunque).</div>`
    : '';

  // Override dell'ultima prova
  let override;
  if (r.last_event) {
    const cur = r.last_event.outcome ? (OUTCOME_LABEL[r.last_event.outcome] || r.last_event.outcome) : '—';
    override = `
      <div class="mini-label">Correggi l'ultima prova (Aedo ri-narra)</div>
      <div class="muted small">«${esc(r.last_event.action_text)}» — ora: <b>${esc(cur)}</b></div>
      <div class="mini-form">
        <button class="btn-ghost" data-act="override" data-o="success">successo</button>
        <button class="btn-ghost" data-act="override" data-o="success_cost">riesci, ma…</button>
        <button class="btn-ghost" data-act="override" data-o="failure">fallimento</button>
      </div>`;
  } else {
    override = `<div class="mini-label">Correggi l'ultima prova</div><div class="muted small">Nessuna prova recente da correggere.</div>`;
  }

  // Coda comandi
  const cmds = r.commands.length
    ? r.commands.map((c) => `
        <div class="cmd-row">
          <span class="cmd-status ${esc(c.status)}">${CMD_STATUS[c.status] || c.status}</span>
          <span class="cmd-kind">${CMD_KIND[c.kind] || c.kind}</span>
          <span class="muted small cmd-payload">${esc((c.payload || '').slice(0, 70))}</span>
          ${c.error ? `<span class="cmd-err">${esc(c.error)}</span>` : ''}
        </div>`).join('')
    : '<div class="muted small">Ancora nessun ordine di regia.</div>';

  // Note segrete
  const notes = r.notes.length
    ? r.notes.map((n) => `
        <div class="cmd-row">
          <span class="small">${esc(n.text)}</span>
          <button class="chip-x" data-act="note-del" data-id="${n.id}" style="margin-left:auto" title="Elimina nota">×</button>
        </div>`).join('')
    : '<div class="muted small">Nessuna nota.</div>';

  $('#regia-body').innerHTML = `
    ${noChannel}
    <div class="regia-grid">
      <div>
        <div class="mini-label">Inietta un evento nel canale</div>
        <textarea data-f="regia-text" rows="3" placeholder="Es. Le luci si spengono di colpo e un tuono scuote le finestre…" style="width:100%"></textarea>
        <div class="mini-form">
          <button class="btn-wax" data-act="event-narrated">Fai narrare ad Aedo</button>
          <button class="btn-ghost" data-act="event-direct">Posta testuale</button>
        </div>
        ${override}
      </div>
      <div>
        <div class="mini-label">Note segrete del master</div>
        <div class="cmd-list">${notes}</div>
        <div class="mini-form">
          <input data-f="regia-note" placeholder="appunto privato…" style="flex:1" />
          <button class="btn-ghost" data-act="note-add">aggiungi</button>
        </div>
      </div>
    </div>
    <div class="mini-label">Ordini recenti <button class="btn-ghost" data-act="regia-refresh" style="float:right">aggiorna</button></div>
    <div class="cmd-list">${cmds}</div>`;

  // Se ci sono ordini in coda, ricontrolla fra poco (il bot li esegue in ~4s).
  clearTimeout(regiaTimer);
  if (r.commands.some((c) => c.status === 'pending')) {
    regiaTimer = setTimeout(loadRegia, 4000);
  }
}

$('#regia-body').addEventListener('click', (e) => {
  const b = e.target.closest('button'); if (!b) return;
  const act = b.dataset.act;
  const rbase = `/admin/api/campaigns/${campaignId}`;
  if (act === 'event-narrated' || act === 'event-direct') {
    const text = $('[data-f="regia-text"]').value.trim();
    if (!text) return toast('Scrivi l\'evento da mettere in scena.', true);
    const mode = act === 'event-direct' ? 'direct' : 'narrated';
    writeRegia(`${rbase}/regia/event`, 'POST', { mode, text }, 'Evento messo in coda per il canale.');
  } else if (act === 'override') {
    writeRegia(`${rbase}/regia/override`, 'POST', { outcome: b.dataset.o }, 'Correzione in coda: Aedo ri-narrerà.');
  } else if (act === 'note-add') {
    const text = $('[data-f="regia-note"]').value.trim();
    if (!text) return;
    writeRegia(`${rbase}/notes`, 'POST', { text }, 'Nota salvata.');
  } else if (act === 'note-del') {
    writeRegia(`${rbase}/notes/${b.dataset.id}`, 'DELETE', null, 'Nota eliminata.');
  } else if (act === 'regia-refresh') {
    loadRegia();
  }
});

// ---- Editor regole e genere (Blueprint) ----
let blueprint = null;
const CRUNCH_LABEL = {
  narrative: 'Narrativo — meccaniche nascoste',
  balanced: 'Bilanciato — qualche numero',
  tactical: 'Tattico — numeri e tiri in vista',
};

async function loadBlueprint() {
  if (!campaignId) return;
  try {
    blueprint = await jf(`/admin/api/campaigns/${campaignId}/blueprint`);
    renderBlueprint();
  } catch { /* campagna assente */ }
}

async function writeBlueprint(patch, okMsg) {
  try {
    blueprint = await jf(`/admin/api/campaigns/${campaignId}/blueprint`, { method: 'PATCH', body: patch });
    renderBlueprint();
    if (okMsg) toast(okMsg);
  } catch (err) {
    toast(err.message, true);
  }
}

function readAttributes() {
  return [...document.querySelectorAll('#blueprint-body .attr-row')].map((row) => ({
    name: row.querySelector('[data-k="aname"]').value.trim(),
    description: row.querySelector('[data-k="adesc"]').value.trim(),
  })).filter((a) => a.name);
}

function readResources() {
  const out = {};
  document.querySelectorAll('#blueprint-body .res-row').forEach((row) => {
    const name = row.querySelector('[data-k="rname"]').value.trim();
    const val = Number(row.querySelector('[data-k="rval"]').value) || 0;
    if (name) out[name] = Math.max(0, val);
  });
  return out;
}

function renderBlueprint() {
  if (!blueprint) return;
  const bp = blueprint;
  const crunchOpts = bp.crunch_options.map((c) =>
    `<option value="${c}" ${c === bp.crunch_level ? 'selected' : ''}>${esc(CRUNCH_LABEL[c] || c)}</option>`).join('');
  const attrs = bp.attributes.map((a, i) => `
    <div class="attr-row">
      <input data-k="aname" value="${esc(a.name)}" placeholder="attributo" data-bp="attributes" />
      <input data-k="adesc" value="${esc(a.description || '')}" placeholder="a cosa serve" data-bp="attributes" style="flex:1" />
      <button class="chip-x" data-act="attr-del" data-i="${i}" title="Rimuovi">×</button>
    </div>`).join('') || '<div class="muted small">Nessun attributo.</div>';
  const resources = Object.entries(bp.default_resources).map(([k, v]) => `
    <div class="res-row">
      <input data-k="rname" value="${esc(k)}" placeholder="risorsa" data-bp="default_resources" style="flex:1" />
      <input data-k="rval" type="number" value="${v}" class="small" data-bp="default_resources" />
      <button class="chip-x" data-act="res-del" data-k="${esc(k)}" title="Rimuovi">×</button>
    </div>`).join('') || '<div class="muted small">Nessuna risorsa.</div>';
  const conflicts = bp.conflict_types.map((c, i) => `
    <span class="chip">${esc(c)}
      <button class="chip-x" data-act="conf-del" data-i="${i}">×</button>
    </span>`).join('') || '<span class="muted small">Nessuno.</span>';

  $('#blueprint-body').innerHTML = `
    <div class="bp-grid">
      <label class="bp-field"><span>Nome del ruleset</span>
        <input data-bp="name" value="${esc(bp.name)}" /></label>
      <label class="bp-field"><span>Genere e ambientazione</span>
        <input data-bp="genre" value="${esc(bp.genre)}" /></label>
      <label class="bp-field"><span>Tono / voce</span>
        <input data-bp="tone" value="${esc(bp.tone)}" /></label>
      <label class="bp-field"><span>Meccaniche visibili</span>
        <select data-bp="crunch_level">${crunchOpts}</select></label>
      <label class="bp-field"><span>Dado base (es. 2d6, 1d20)</span>
        <input data-bp="dice_formula" value="${esc(bp.dice_formula)}" /></label>
      <label class="bp-field"><span>Fascia "riesci, ma…"</span>
        <input data-bp="success_band" type="number" min="0" value="${bp.success_band}" /></label>
    </div>
    <label class="bp-field"><span>Come recita Aedo (persona del narratore)</span>
      <textarea data-bp="narrator_persona" rows="2">${esc(bp.narrator_persona)}</textarea></label>
    <label class="bp-field"><span>Regole speciali (in italiano, le legge Aedo)</span>
      <textarea data-bp="special_rules" rows="2">${esc(bp.special_rules)}</textarea></label>

    <div class="mini-label">Attributi</div>
    <div class="bp-list">${attrs}</div>
    <div class="mini-form">
      <input data-f="new-attr-name" placeholder="nuovo attributo" />
      <input data-f="new-attr-desc" placeholder="descrizione" style="flex:1" />
      <button class="btn-ghost" data-act="attr-add">aggiungi</button>
    </div>

    <div class="mini-label">Risorse di partenza dei personaggi</div>
    <div class="bp-list">${resources}</div>
    <div class="mini-form">
      <input data-f="new-res-name" placeholder="risorsa (es. vita)" />
      <input data-f="new-res-val" type="number" value="5" class="small" />
      <button class="btn-ghost" data-act="res-add">aggiungi</button>
    </div>

    <div class="mini-label">Tipi di conflitto</div>
    <div class="kv">${conflicts}</div>
    <div class="mini-form">
      <input data-f="new-conf" placeholder="es. inseguimento" />
      <button class="btn-ghost" data-act="conf-add">aggiungi</button>
    </div>

    <div class="mini-label">Modello AI (narratore)</div>
    <div class="muted small">In uso: <code>${esc(bp.ai_model)}</code> — si cambia nel file <code>.env</code> (AEDO_MODEL) e vale al riavvio del bot.</div>`;
}

// Salvataggio dei campi scalari al blur/change.
$('#blueprint-body').addEventListener('change', (e) => {
  const f = e.target.closest('[data-bp]');
  if (!f) return;
  const field = f.dataset.bp;
  if (field === 'attributes') {
    writeBlueprint({ attributes: readAttributes() });
  } else if (field === 'default_resources') {
    writeBlueprint({ default_resources: readResources() });
  } else if (field === 'success_band') {
    writeBlueprint({ success_band: Number(f.value) || 0 });
  } else {
    writeBlueprint({ [field]: f.value });
  }
});

$('#blueprint-body').addEventListener('click', (e) => {
  const b = e.target.closest('button'); if (!b) return;
  const act = b.dataset.act;
  if (act === 'attr-add') {
    const name = $('[data-f="new-attr-name"]').value.trim();
    if (!name) return toast('Indica il nome dell\'attributo.', true);
    const desc = $('[data-f="new-attr-desc"]').value.trim();
    writeBlueprint({ attributes: [...blueprint.attributes, { name, description: desc }] }, 'Attributo aggiunto.');
  } else if (act === 'attr-del') {
    const next = blueprint.attributes.filter((_, i) => i !== Number(b.dataset.i));
    writeBlueprint({ attributes: next });
  } else if (act === 'res-add') {
    const name = $('[data-f="new-res-name"]').value.trim();
    if (!name) return toast('Indica il nome della risorsa.', true);
    const val = Math.max(0, Number($('[data-f="new-res-val"]').value) || 0);
    writeBlueprint({ default_resources: { ...blueprint.default_resources, [name]: val } }, 'Risorsa aggiunta.');
  } else if (act === 'res-del') {
    const next = { ...blueprint.default_resources };
    delete next[b.dataset.k];
    writeBlueprint({ default_resources: next });
  } else if (act === 'conf-add') {
    const c = $('[data-f="new-conf"]').value.trim();
    if (!c) return;
    writeBlueprint({ conflict_types: [...blueprint.conflict_types, c] }, 'Aggiunto.');
  } else if (act === 'conf-del') {
    const next = blueprint.conflict_types.filter((_, i) => i !== Number(b.dataset.i));
    writeBlueprint({ conflict_types: next });
  }
});

// ---- Strumenti: oracolo + generatori ----
const ORACLE_CLASS = { yes: 'ok', yes_but: 'warn', no_but: 'warn', no: 'bad' };

function renderTools() {
  $('#tools-body').innerHTML = `
    <div class="mini-label">Oracolo — fai una domanda sì/no</div>
    <div class="mini-form">
      <input data-f="oracle-q" placeholder="Es. Il barista sa qualcosa?" style="flex:1" />
      <select data-f="oracle-like">
        <option value="unlikely">improbabile</option>
        <option value="even" selected>50 e 50</option>
        <option value="likely">probabile</option>
      </select>
      <button class="btn-wax" data-act="oracle">Chiedi</button>
    </div>
    <div id="oracle-answer"></div>

    <div class="mini-label">Generatori (dal genere della campagna)</div>
    <div class="mini-form">
      <button class="btn-ghost" data-act="gen" data-kind="names">Nomi</button>
      <button class="btn-ghost" data-act="gen" data-kind="npc">Un NPC</button>
      <button class="btn-ghost" data-act="gen" data-kind="hook">Gancio di trama</button>
    </div>
    <div id="gen-result"></div>`;
}

$('#tools-body').addEventListener('click', async (e) => {
  const b = e.target.closest('button'); if (!b) return;
  const act = b.dataset.act;
  if (act === 'oracle') {
    const question = $('[data-f="oracle-q"]').value.trim();
    if (!question) return toast('Fai una domanda.', true);
    const likelihood = $('[data-f="oracle-like"]').value;
    try {
      const a = await jf('/admin/api/tools/oracle', { method: 'POST', body: { question, likelihood } });
      $('#oracle-answer').innerHTML =
        `<div class="oracle-answer ${ORACLE_CLASS[a.grade]}">${esc(a.answer)}</div>`;
    } catch (err) { toast(err.message, true); }
  } else if (act === 'gen') {
    try {
      const g = await jf(`/admin/api/campaigns/${campaignId}/tools/generate`,
        { method: 'POST', body: { kind: b.dataset.kind } });
      const list = g.items.map((it) => `<div class="gen-item">${esc(it)}</div>`).join('');
      const createBtn = g.npc
        ? `<button class="btn-ghost" data-act="gen-npc-create" data-name="${esc(g.npc.name)}">aggiungi «${esc(g.npc.name)}» alla campagna</button>`
        : '';
      $('#gen-result').innerHTML = `<div class="gen-list">${list}</div>${createBtn}`;
    } catch (err) { toast(err.message, true); }
  } else if (act === 'gen-npc-create') {
    try {
      state = await jf(`/admin/api/campaigns/${campaignId}/npcs`, { method: 'POST', body: { name: b.dataset.name } });
      renderState();
      loadStats();
      toast('NPC aggiunto alla campagna.');
    } catch (err) { toast(err.message, true); }
  }
});

// ---- Statistiche ----
async function loadStats() {
  if (!campaignId) return;
  try {
    const s = await jf(`/admin/api/campaigns/${campaignId}/stats`);
    renderStats(s);
  } catch { /* campagna assente */ }
}

function renderStats(s) {
  const o = s.outcomes || {};
  const obj = s.objectives || {};
  const rels = s.relationships.map((r) => {
    const pct = Math.round((r.affinity + 100) / 2);
    const cls = r.affinity >= 0 ? 'pos' : 'neg';
    return `
      <div class="rel-line">
        <span class="small" style="min-width:100px">${esc(r.name)}</span>
        <div class="aff-bar"><div class="aff-fill ${cls}" style="width:${pct}%"></div></div>
        <span class="small" style="min-width:34px;text-align:right">${r.affinity > 0 ? '+' : ''}${r.affinity}</span>
      </div>`;
  }).join('') || '<span class="muted small">Nessun legame.</span>';

  $('#stats-body').innerHTML = `
    <div class="stat-grid">
      <div class="stat"><b>${s.turns}</b><span>turni giocati</span></div>
      <div class="stat"><b>${s.npc_count}</b><span>NPC</span></div>
      <div class="stat"><b>${s.memory_count}</b><span>ricordi</span></div>
      <div class="stat"><b>${s.events_total}</b><span>eventi totali</span></div>
    </div>
    <div class="mini-label">Esiti delle prove</div>
    <div class="kv">
      <span class="chip"><span class="dot ok"></span> successi <span class="val">${o.success || 0}</span></span>
      <span class="chip"><span class="dot warn"></span> riesci, ma <span class="val">${o.success_cost || 0}</span></span>
      <span class="chip"><span class="dot bad"></span> fallimenti <span class="val">${o.failure || 0}</span></span>
    </div>
    <div class="mini-label">Obiettivi</div>
    <div class="kv">
      <span class="chip">aperti <span class="val">${obj.open || 0}</span></span>
      <span class="chip">completati <span class="val">${obj.completed || 0}</span></span>
      <span class="chip">falliti <span class="val">${obj.failed || 0}</span></span>
    </div>
    <div class="mini-label">Affinità con gli NPC <button class="btn-ghost" data-act="stats-refresh" style="float:right">aggiorna</button></div>
    <div class="rows">${rels}</div>`;
}

$('#stats-body').addEventListener('click', (e) => {
  if (e.target.closest('[data-act="stats-refresh"]')) loadStats();
});

// ============================================================
//  AVVIO
// ============================================================
loadServices();
loadCampaigns();
setInterval(loadServices, 2500);
setInterval(loadCampaigns, 8000);  // fa comparire da sé le campagne appena create
