import { useState, useEffect, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'

const MARKET_ICONS = {
  'Gols': '⚽',
  'Resultado': '🏁',
  'BTTS': '🎲',
  'Cantos': '🚩',
  'Cartões': '🟨',
  'Finalizações': '🎯',
  'Handicaps': '⚖️',
  'Dupla Chance': '🔀',
  'Gols Ambos Tempos': '⏱️',
  'Placar Exato': '🔢',
  'Handicap Europeu': '🏷️',
  'Primeiro a Marcar': '🥇',
}

function ConfidenceBar({ value, max = 10 }) {
  const pct = Math.min(100, (value / max) * 100)
  let color = '#ef4444'
  if (value >= 7) color = '#22c55e'
  else if (value >= 5.5) color = '#eab308'

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1 }}>
      <div className="confidence-bar-track" style={{ flex: 1 }}>
        <div
          className="confidence-bar-fill"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <span style={{ fontSize: 12, fontWeight: 700, color, minWidth: 32, textAlign: 'right' }}>
        {value?.toFixed(1)}
      </span>
    </div>
  )
}

function PredictionRow({ palpite, rank }) {
  const conf = palpite.confianca || 0
  let badgeCls = 'badge badge-red'
  if (conf >= 7) badgeCls = 'badge badge-green'
  else if (conf >= 5.5) badgeCls = 'badge badge-yellow'

  return (
    <div
      style={{
        padding: '12px 0',
        borderBottom: '1px solid rgba(255,255,255,0.04)',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, flexWrap: 'wrap' }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 4 }}>
            {rank === 0 && (
              <span style={{ fontSize: 10, background: 'rgba(99,102,241,0.2)', color: '#818cf8', border: '1px solid rgba(99,102,241,0.4)', borderRadius: 4, padding: '1px 6px', fontWeight: 700 }}>
                #1
              </span>
            )}
            <span style={{ fontSize: 13, fontWeight: 600, color: '#f1f5f9' }}>
              {palpite.tipo}
            </span>
            {palpite.periodo && palpite.periodo !== 'FT' && (
              <span style={{ fontSize: 10, color: '#64748b', background: 'rgba(255,255,255,0.05)', borderRadius: 4, padding: '1px 5px' }}>
                {palpite.periodo}
              </span>
            )}
            {palpite.odd && (
              <span style={{ fontSize: 12, color: '#818cf8', fontWeight: 700, marginLeft: 'auto' }}>
                @{typeof palpite.odd === 'number' ? palpite.odd.toFixed(2) : palpite.odd}
              </span>
            )}
          </div>

          {palpite.justificativa && (
            <p style={{ fontSize: 12, color: '#64748b', lineHeight: 1.5, marginBottom: 6 }}>
              {palpite.justificativa}
            </p>
          )}

          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 11, color: '#475569', minWidth: 60 }}>Confiança</span>
            <ConfidenceBar value={conf} />
          </div>

          {palpite.probabilidade > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 4 }}>
              <span style={{ fontSize: 11, color: '#475569', minWidth: 60 }}>Prob.</span>
              <ConfidenceBar value={palpite.probabilidade} max={100} />
              <span style={{ fontSize: 11, color: '#64748b', marginLeft: -20 }}>%</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function MarketCard({ mercado }) {
  const [open, setOpen] = useState(true)
  const icon = MARKET_ICONS[mercado.mercado] || '📊'
  const topConf = mercado.palpites[0]?.confianca || 0

  return (
    <div
      className="card"
      style={{ marginBottom: 14, overflow: 'hidden' }}
    >
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: 10,
          padding: '12px 16px', cursor: 'pointer', background: 'transparent', border: 'none',
          borderBottom: open ? '1px solid rgba(255,255,255,0.05)' : 'none',
        }}
      >
        <span style={{ fontSize: 18 }}>{icon}</span>
        <span style={{ fontSize: 14, fontWeight: 700, color: '#e2e8f0' }}>
          {mercado.mercado}
        </span>
        <span style={{ fontSize: 11, color: '#475569' }}>
          {mercado.palpites.length} palpite{mercado.palpites.length !== 1 ? 's' : ''}
        </span>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
          {topConf >= 7 && <span className="badge badge-green" style={{ fontSize: 10 }}>⭐ Top</span>}
          <span style={{ fontSize: 12, color: '#475569' }}>{open ? '▲' : '▼'}</span>
        </div>
      </button>

      {open && (
        <div style={{ padding: '0 16px 4px' }}>
          {mercado.palpites.map((p, i) => (
            <PredictionRow key={i} palpite={p} rank={i} />
          ))}
        </div>
      )}
    </div>
  )
}

function StatBox({ label, value, sub }) {
  return (
    <div
      style={{
        background: 'rgba(99,102,241,0.06)',
        border: '1px solid rgba(99,102,241,0.12)',
        borderRadius: 10,
        padding: '12px 16px',
        flex: 1,
        minWidth: 120,
      }}
    >
      <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 800, color: '#f1f5f9' }}>{value}</div>
      {sub && <div style={{ fontSize: 11, color: '#475569', marginTop: 2 }}>{sub}</div>}
    </div>
  )
}

function TeamLogo({ logo, name, size = 44 }) {
  const [err, setErr] = useState(false)
  if (!logo || err) {
    return (
      <div
        style={{
          width: size, height: size, borderRadius: '50%',
          background: 'rgba(99,102,241,0.2)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: size * 0.4, color: '#818cf8', fontWeight: 700,
        }}
      >
        {name?.[0] || '?'}
      </div>
    )
  }
  return (
    <img
      src={logo} alt={name}
      style={{ width: size, height: size, objectFit: 'contain' }}
      onError={() => setErr(true)}
    />
  )
}

export default function MatchDetail() {
  const { fixtureId } = useParams()
  const [analise, setAnalise] = useState(null)
  const [loading, setLoading] = useState(true)
  const [processing, setProcessing] = useState(false)
  const [error, setError] = useState(null)
  const [jogoInfo, setJogoInfo] = useState(null)

  const checkStatus = useCallback(async () => {
    try {
      const r = await fetch(`/api/analise/${fixtureId}`)
      if (r.ok) {
        const d = await r.json()
        if (d.status === 'ready') {
          setAnalise(d)
          setProcessing(false)
          setLoading(false)
          return true
        }
        if (d.status === 'processing') {
          setProcessing(true)
          setLoading(false)
          return false
        }
      } else if (r.status === 404) {
        setLoading(false)
        return false
      }
    } catch {
      setLoading(false)
    }
    return false
  }, [fixtureId])

  const triggerAnalise = useCallback(async () => {
    setProcessing(true)
    try {
      const r = await fetch(`/api/analisar/${fixtureId}`, { method: 'POST' })
      const d = await r.json()
      if (d.status === 'ready') {
        await checkStatus()
      }
    } catch (e) {
      setError('Erro ao iniciar análise')
      setProcessing(false)
    }
  }, [fixtureId, checkStatus])

  useEffect(() => {
    const run = async () => {
      const found = await checkStatus()
      if (!found && !processing) {
        await triggerAnalise()
      }
    }
    run()
  }, [fixtureId])

  useEffect(() => {
    if (!processing) return
    const poll = setInterval(async () => {
      const done = await checkStatus()
      if (done) clearInterval(poll)
    }, 3000)
    return () => clearInterval(poll)
  }, [processing, checkStatus])

  useEffect(() => {
    const loadJogoInfo = async () => {
      try {
        const r = await fetch('/api/jogos/hoje')
        if (!r.ok) return
        const d = await r.json()
        const grupos = d.por_pais
          ? d.por_pais.flatMap(p => p.ligas || [])
          : (d.ligas || [])
        for (const grupo of grupos) {
          for (const j of grupo.jogos || []) {
            if (j.fixture_id === parseInt(fixtureId)) {
              setJogoInfo(j)
              return
            }
          }
        }
      } catch {}
    }
    loadJogoInfo()
  }, [fixtureId])

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center" style={{ minHeight: 400, gap: 16, paddingTop: 80 }}>
        <div className="spinner" style={{ width: 48, height: 48 }} />
        <p style={{ color: '#64748b', fontSize: 14 }}>Carregando análise...</p>
      </div>
    )
  }

  if (processing) {
    return (
      <div className="flex flex-col items-center justify-center" style={{ minHeight: 400, gap: 16, paddingTop: 80, textAlign: 'center' }}>
        <div className="spinner" style={{ width: 48, height: 48 }} />
        <p style={{ color: '#c7d2fe', fontSize: 16, fontWeight: 600 }}>Analisando o jogo...</p>
        <p style={{ color: '#64748b', fontSize: 13, maxWidth: 360 }}>
          O sistema está processando estatísticas, odds e dados táticos.
          Isso pode levar até 60 segundos.
        </p>
        <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
          {['Estatísticas', 'Odds', 'Analistas', 'Palpites'].map((s, i) => (
            <span key={i} style={{
              fontSize: 11, padding: '3px 8px',
              background: 'rgba(99,102,241,0.1)', color: '#818cf8',
              border: '1px solid rgba(99,102,241,0.2)', borderRadius: 6,
            }}>
              {s}
            </span>
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div style={{ textAlign: 'center', paddingTop: 80 }}>
        <p style={{ color: '#f87171', fontSize: 14 }}>{error}</p>
        <Link to="/" style={{ color: '#818cf8', fontSize: 13, marginTop: 12, display: 'block' }}>
          ← Voltar aos jogos
        </Link>
      </div>
    )
  }

  if (!analise) {
    return (
      <div style={{ textAlign: 'center', paddingTop: 80 }}>
        <p style={{ color: '#64748b', fontSize: 14 }}>Análise não encontrada.</p>
        <Link to="/" style={{ color: '#818cf8', fontSize: 13, marginTop: 12, display: 'block' }}>← Voltar</Link>
      </div>
    )
  }

  const topMercados = [...(analise.mercados || [])].sort((a, b) => {
    const aMax = Math.max(...(a.palpites || []).map(p => p.confianca || 0))
    const bMax = Math.max(...(b.palpites || []).map(p => p.confianca || 0))
    return bMax - aMax
  })

  const topPick = topMercados[0]?.palpites[0]

  return (
    <div style={{ paddingTop: 24 }}>
      <Link to="/" style={{ fontSize: 13, color: '#64748b', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 4, marginBottom: 20 }}>
        ← Voltar aos jogos
      </Link>

      {/* Hero card */}
      <div
        style={{
          background: 'linear-gradient(135deg, #131729 0%, #1a1d2e 100%)',
          border: '1px solid rgba(99,102,241,0.2)',
          borderRadius: 16,
          padding: 24,
          marginBottom: 20,
        }}
      >
        <div style={{ fontSize: 12, color: '#818cf8', fontWeight: 600, marginBottom: 12 }}>
          {jogoInfo?.liga?.nome || analise.liga}
        </div>

        <div className="flex items-center justify-center gap-6" style={{ marginBottom: 20 }}>
          <div className="flex flex-col items-center gap-2">
            <TeamLogo logo={jogoInfo?.time_casa?.logo} name={analise.time_casa} />
            <span style={{ fontSize: 14, fontWeight: 700, color: '#f1f5f9', textAlign: 'center', maxWidth: 120 }}>
              {analise.time_casa}
            </span>
          </div>

          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 22, fontWeight: 800, color: '#e2e8f0', letterSpacing: '0.1em' }}>
              vs
            </div>
            <div style={{ fontSize: 11, color: '#475569', marginTop: 4 }}>
              {jogoInfo?.horario_brt}
            </div>
          </div>

          <div className="flex flex-col items-center gap-2">
            <TeamLogo logo={jogoInfo?.time_fora?.logo} name={analise.time_fora} />
            <span style={{ fontSize: 14, fontWeight: 700, color: '#f1f5f9', textAlign: 'center', maxWidth: 120 }}>
              {analise.time_fora}
            </span>
          </div>
        </div>

        {/* Stats row */}
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <StatBox
            label="Total de Palpites"
            value={analise.total_palpites}
            sub={`em ${analise.mercados?.length || 0} mercados`}
          />
          <StatBox
            label="Melhor Confiança"
            value={`${analise.melhor_confianca?.toFixed(1)}/10`}
            sub="score máximo"
          />
          {topPick && (
            <StatBox
              label="Top Pick"
              value={topPick.tipo}
              sub={`${topMercados[0]?.mercado} — conf. ${topPick.confianca?.toFixed(1)}`}
            />
          )}
        </div>
      </div>

      {/* Mercados */}
      <h2 style={{ fontSize: 16, fontWeight: 700, color: '#c7d2fe', marginBottom: 14, letterSpacing: '-0.01em' }}>
        Análise por Mercado
      </h2>

      {topMercados.map((m, i) => (
        <MarketCard key={i} mercado={m} />
      ))}
    </div>
  )
}
