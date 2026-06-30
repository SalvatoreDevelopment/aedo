import { useEffect, useState } from 'react'
import { api } from './api'

const OUTCOME = {
  success: { label: 'successo', cls: 'ok' },
  success_cost: { label: 'riesci, ma…', cls: 'warn' },
  failure: { label: 'fallimento', cls: 'bad' },
}
const OBJ_ICON = { open: '○', completed: '✓', failed: '✕' }

export default function App() {
  const [campaigns, setCampaigns] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.campaigns()
      .then((cs) => {
        setCampaigns(cs)
        if (cs.length) setSelectedId(cs[0].id)
        else setData(null)
      })
      .catch(() => setError('api'))
  }, [])

  useEffect(() => {
    if (!selectedId) return
    setData(null)
    Promise.all([
      api.campaign(selectedId), api.inventory(selectedId),
      api.relationships(selectedId), api.objectives(selectedId),
      api.events(selectedId),
    ])
      .then(([detail, inventory, relationships, objectives, events]) =>
        setData({ detail, inventory, relationships, objectives, events }))
      .catch(() => setError('api'))
  }, [selectedId])

  if (error === 'api') {
    return (
      <div className="wrap">
        <div className="empty">
          <h1>🎭 Aedo</h1>
          <p>API non raggiungibile. Avvia il server con:</p>
          <pre>python -m aedo.api</pre>
        </div>
      </div>
    )
  }

  return (
    <div className="wrap">
      <header className="topbar">
        <div className="brand">🎭 <span>Aedo</span></div>
        {campaigns.length > 0 && (
          <select value={selectedId ?? ''} onChange={(e) => setSelectedId(Number(e.target.value))}>
            {campaigns.map((c) => (
              <option key={c.id} value={c.id}>{c.name} — {c.genre}</option>
            ))}
          </select>
        )}
      </header>

      {campaigns.length === 0 && (
        <div className="empty"><p>Nessuna campagna ancora. Creane una su Discord con <code>/nuova-campagna</code>.</p></div>
      )}

      {data && (
        <main className="grid">
          <Scene detail={data.detail} />
          <Sheet player={data.detail.player} attributes={data.detail.attributes} />
          <Inventory items={data.inventory} />
          <Relationships rels={data.relationships} playerName={data.detail.player?.name} />
          <Objectives objs={data.objectives} />
          <Diary events={data.events} />
        </main>
      )}
    </div>
  )
}

function Card({ title, icon, wide, children }) {
  return (
    <section className={`card${wide ? ' wide' : ''}`}>
      <h2>{icon} {title}</h2>
      {children}
    </section>
  )
}

function Scene({ detail }) {
  return (
    <Card title={detail.name} icon="🎭" wide>
      <div className="muted small">{detail.genre} · {detail.mode} · {detail.crunch_level}</div>
      {detail.summary && <p className="voice">{detail.summary}</p>}
    </Card>
  )
}

function Sheet({ player, attributes }) {
  if (!player) return <Card title="Personaggio" icon="📋"><p className="muted">Nessun personaggio.</p></Card>
  return (
    <Card title={player.name} icon="📋">
      {player.description && <p className="muted small">{player.description}</p>}
      <div className="label">Attributi</div>
      <div className="rows">
        {attributes.map((a) => (
          <div className="row" key={a.name}>
            <span>{a.name}</span><span className="val">{player.attributes[a.name] ?? 0}</span>
          </div>
        ))}
      </div>
      <div className="label">Risorse</div>
      <div className="pills">
        {Object.entries(player.resources).map(([k, v]) => (
          <span className="pill" key={k}>{k} {v}</span>
        ))}
      </div>
      {player.conditions.length > 0 && (
        <>
          <div className="label">Condizioni</div>
          <div className="pills">{player.conditions.map((c) => <span className="pill bad" key={c}>{c}</span>)}</div>
        </>
      )}
    </Card>
  )
}

function Inventory({ items }) {
  return (
    <Card title="Inventario" icon="🎒">
      {items.length === 0 ? <p className="muted">Tasche vuote.</p> : (
        <div className="rows">
          {items.map((it) => (
            <div className="row" key={it.id}>
              <span>{it.name}</span>
              <span className="muted small">{it.quantity !== 1 ? `×${it.quantity}` : (it.description || '')}</span>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

function Relationships({ rels, playerName }) {
  return (
    <Card title="Relazioni" icon="❤">
      {rels.length === 0 ? <p className="muted">Ancora nessun legame.</p> : (
        <div className="rows">
          {rels.map((r) => {
            const other = r.from_name === playerName ? r.to_name : r.from_name
            const pct = Math.round((r.affinity + 100) / 2)
            const cls = r.affinity >= 0 ? 'ok' : 'bad'
            return (
              <div className="rel" key={r.id}>
                <div className="row">
                  <span>{other}</span>
                  <span className="muted small">{r.kind} {r.affinity >= 0 ? '+' : ''}{r.affinity}</span>
                </div>
                <div className="bar"><div className={`fill ${cls}`} style={{ width: `${pct}%` }} /></div>
              </div>
            )
          })}
        </div>
      )}
    </Card>
  )
}

function Objectives({ objs }) {
  return (
    <Card title="Obiettivi" icon="🎯">
      {objs.length === 0 ? <p className="muted">Nessun obiettivo.</p> : (
        <div className="rows">
          {objs.map((o) => (
            <div className="row" key={o.id}>
              <span className={o.status === 'completed' ? 'done' : ''}>{OBJ_ICON[o.status]} {o.title}</span>
              <span className={`tag ${o.status}`}>{o.status}</span>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

function Diary({ events }) {
  return (
    <Card title="Diario" icon="📖" wide>
      {events.length === 0 ? <p className="muted">La storia non è ancora iniziata.</p> : (
        <div className="diary">
          {events.map((e) => {
            const o = OUTCOME[e.outcome]
            return (
              <div className="entry" key={e.id}>
                <div className="entry-head">
                  <strong>{e.actor}</strong>
                  {e.action_text && e.action_text !== '(apertura)' && <span className="muted small">{e.action_text}</span>}
                  {o && <span className={`tag ${o.cls}`}>{o.label}</span>}
                </div>
                <p className="voice">{e.narration}</p>
              </div>
            )
          })}
        </div>
      )}
    </Card>
  )
}
