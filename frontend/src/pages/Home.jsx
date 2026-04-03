import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

function ConfidencePill({ value }) {
  let cls = 'badge badge-red'
  if (value >= 7) cls = 'badge badge-green'
  else if (value >= 5.5) cls = 'badge badge-yellow'
  return <span className={cls}>{value?.toFixed(1)}/10</span>
}

function TeamLogo({ logo, name, size = 28 }) {
  const [err, setErr] = useState(false)
  if (!logo || err) {
    return (
      <div
        style={{
          width: size, height: size, borderRadius: '50%',
          background: 'rgba(99,102,241,0.2)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: size * 0.45, color: '#818cf8', fontWeight: 700,
        }}
      >
        {name?.[0] || '?'}
      </div>
    )
  }
  return (
    <img
      src={logo} alt={name}
      style={{ width: size, height: size, objectFit: 'contain', borderRadius: 4 }}
      onError={() => setErr(true)}
    />
  )
}

function MatchCard({ jogo }) {
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState(jogo.tem_analise ? 'ready' : 'none')

  const handleAnalyze = async (e) => {
    e.preventDefault()
    e.stopPropagation()
    if (loading || status === 'processing') return
    setLoading(true)
    setStatus('processing')
    try {
      const r = await fetch(`/api/analisar/${jogo.fixture_id}`, { method: 'POST' })
      const d = await r.json()
      if (d.status === 'ready') setStatus('ready')
      else setStatus('processing')
    } catch {
      setStatus('none')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (status !== 'processing') return
    const poll = setInterval(async () => {
      try {
        const r = await fetch(`/api/status/${jogo.fixture_id}`)
        const d = await r.json()
        if (d.status === 'ready') { setStatus('ready'); clearInterval(poll) }
        if (d.status === 'error') { setStatus('none'); clearInterval(poll) }
      } catch { clearInterval(poll) }
    }, 3000)
    return () => clearInterval(poll)
  }, [status, jogo.fixture_id])

  const isProcessing = status === 'processing'
  const isReady = status === 'ready'

  return (
    <Link
      to={isReady ? `/jogo/${jogo.fixture_id}` : '#'}
      onClick={isReady ? undefined : handleAnalyze}
      style={{ textDecoration: 'none', display: 'block' }}
    >
      <div
        className="card"
        style={{ padding: '14px 16px', marginBottom: 8, cursor: 'pointer', position: 'relative' }}
      >
        <div className="flex items-center gap-3">
          <span style={{ fontSize: 12, color: '#64748b', fontWeight: 600, minWidth: 38 }}>
            {jogo.horario_brt}
          </span>

          <div className="flex items-center gap-2 flex-1 min-w-0">
            <TeamLogo logo={jogo.time_casa?.logo} name={jogo.time_casa?.nome} />
            <span style={{ fontSize: 13, fontWeight: 600, color: '#e2e8f0', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 110 }}>
              {jogo.time_casa?.nome}
            </span>
            <span style={{ fontSize: 11, color: '#475569', margin: '0 2px' }}>vs</span>
            <span style={{ fontSize: 13, fontWeight: 600, color: '#e2e8f0', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 110 }}>
              {jogo.time_fora?.nome}
            </span>
            <TeamLogo logo={jogo.time_fora?.logo} name={jogo.time_fora?.nome} />
          </div>

          <div className="ml-auto flex-shrink-0">
            {isReady && (
              <span className="badge badge-green" style={{ fontSize: 11 }}>
                ✓ Analisado
              </span>
            )}
            {isProcessing && (
              <span className="badge badge-blue" style={{ fontSize: 11, gap: 5 }}>
                <div className="spinner" style={{ width: 12, height: 12, borderWidth: 2 }} />
                Analisando...
              </span>
            )}
            {!isReady && !isProcessing && (
              <button
                onClick={handleAnalyze}
                style={{
                  fontSize: 11, fontWeight: 600, padding: '3px 10px',
                  background: 'rgba(99,102,241,0.15)',
                  color: '#818cf8',
                  border: '1px solid rgba(99,102,241,0.3)',
                  borderRadius: 8, cursor: 'pointer',
                }}
              >
                Analisar →
              </button>
            )}
          </div>
        </div>
      </div>
    </Link>
  )
}

function LeagueSection({ liga, jogos }) {
  const [open, setOpen] = useState(true)

  return (
    <div style={{ marginBottom: 24 }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: 10,
          background: 'rgba(99,102,241,0.06)', border: '1px solid rgba(99,102,241,0.12)',
          borderRadius: 10, padding: '9px 14px', cursor: 'pointer', marginBottom: 8,
        }}
      >
        {liga.logo && (
          <img src={liga.logo} alt="" style={{ width: 20, height: 20, objectFit: 'contain' }} onError={e => e.target.style.display = 'none'} />
        )}
        <span style={{ fontSize: 13, fontWeight: 700, color: '#c7d2fe' }}>
          {liga.nome}
        </span>
        <span style={{ fontSize: 11, color: '#475569', marginLeft: 4 }}>
          {liga.pais}
        </span>
        <span style={{ marginLeft: 'auto', fontSize: 11, color: '#475569' }}>
          {jogos.length} jogo{jogos.length !== 1 ? 's' : ''} {open ? '▲' : '▼'}
        </span>
      </button>

      {open && jogos.map(j => (
        <MatchCard key={j.fixture_id} jogo={j} />
      ))}
    </div>
  )
}

export default function Home() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchJogos = async () => {
    setLoading(true)
    setError(null)
    try {
      const r = await fetch('/api/jogos/hoje')
      if (!r.ok) throw new Error('Erro ao buscar jogos')
      const d = await r.json()
      setData(d)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchJogos() }, [])

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center" style={{ minHeight: 300, gap: 16, paddingTop: 60 }}>
        <div className="spinner" style={{ width: 44, height: 44 }} />
        <p style={{ color: '#64748b', fontSize: 14 }}>Carregando jogos de hoje...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center" style={{ minHeight: 300, gap: 12, paddingTop: 60 }}>
        <div style={{ fontSize: 40 }}>⚠️</div>
        <p style={{ color: '#f87171', fontSize: 14 }}>Erro ao conectar com a API</p>
        <p style={{ color: '#64748b', fontSize: 12 }}>{error}</p>
        <button
          onClick={fetchJogos}
          style={{
            marginTop: 8, padding: '8px 20px', borderRadius: 8,
            background: 'rgba(99,102,241,0.15)', color: '#818cf8',
            border: '1px solid rgba(99,102,241,0.3)', cursor: 'pointer', fontSize: 13,
          }}
        >
          Tentar novamente
        </button>
      </div>
    )
  }

  const ligas = data?.ligas || []
  const total = data?.total || 0

  return (
    <div style={{ paddingTop: 28 }}>
      <div className="flex items-center justify-between" style={{ marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: '#f1f5f9', letterSpacing: '-0.02em' }}>
            Jogos de Hoje
          </h1>
          <p style={{ fontSize: 13, color: '#64748b', marginTop: 3 }}>
            {total} partida{total !== 1 ? 's' : ''} em {ligas.length} liga{ligas.length !== 1 ? 's' : ''}
          </p>
        </div>
        <button
          onClick={fetchJogos}
          style={{
            fontSize: 12, padding: '6px 14px', borderRadius: 8,
            background: 'rgba(99,102,241,0.1)', color: '#818cf8',
            border: '1px solid rgba(99,102,241,0.2)', cursor: 'pointer',
          }}
        >
          ↻ Atualizar
        </button>
      </div>

      {ligas.length === 0 ? (
        <div style={{
          textAlign: 'center', padding: '60px 0', color: '#64748b',
          background: 'rgba(99,102,241,0.04)', border: '1px dashed rgba(99,102,241,0.15)',
          borderRadius: 12,
        }}>
          <div style={{ fontSize: 48, marginBottom: 12 }}>📭</div>
          <p style={{ fontSize: 15, fontWeight: 600, color: '#94a3b8' }}>Sem jogos disponíveis</p>
          <p style={{ fontSize: 13, marginTop: 6 }}>Nenhuma partida encontrada nas ligas monitoradas.</p>
        </div>
      ) : (
        ligas.map((grupo) => (
          <LeagueSection
            key={grupo.liga.id}
            liga={grupo.liga}
            jogos={grupo.jogos}
          />
        ))
      )}
    </div>
  )
}
