import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { Link } from 'react-router-dom'

const AUTO_REFRESH_SECS = 600

const MERCADOS_DISPONIVEIS = ['Gols', 'Resultado', 'BTTS', 'Cantos', 'Cartões', 'Handicaps', 'Dupla Chance', 'Placar Exato']

const MERCADO_EMOJI = {
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

function useCountdown(dataIso) {
  const [label, setLabel] = useState('')
  const [minsLeft, setMinsLeft] = useState(null)

  useEffect(() => {
    if (!dataIso) return
    const update = () => {
      const now = new Date()
      const target = new Date(dataIso)
      if (isNaN(target.getTime())) { setLabel(''); setMinsLeft(null); return }
      const diffMs = target - now
      const diffMins = Math.floor(diffMs / 60000)
      setMinsLeft(diffMins)
      if (diffMins < -90) {
        setLabel('encerrado')
      } else if (diffMins < 0) {
        setLabel('ao vivo')
      } else if (diffMins === 0) {
        setLabel('agora')
      } else if (diffMins < 60) {
        setLabel(`em ${diffMins}min`)
      } else {
        const hrs = Math.floor(diffMins / 60)
        const mins = diffMins % 60
        setLabel(mins > 0 ? `em ${hrs}h${mins}` : `em ${hrs}h`)
      }
    }
    update()
    const iv = setInterval(update, 30000)
    return () => clearInterval(iv)
  }, [dataIso])

  return { label, minsLeft }
}

function TeamLogo({ logo, name, size = 28 }) {
  const [err, setErr] = useState(false)
  if (!logo || err) {
    return (
      <div
        style={{
          width: size, height: size, borderRadius: '50%',
          background: 'rgba(99,102,241,0.15)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: size * 0.42, color: '#818cf8', fontWeight: 700, flexShrink: 0,
        }}
      >
        {name?.[0] || '?'}
      </div>
    )
  }
  return (
    <img
      src={logo} alt={name}
      style={{ width: size, height: size, objectFit: 'contain', borderRadius: 4, flexShrink: 0 }}
      onError={() => setErr(true)}
    />
  )
}

function MatchCard({ jogo, compact = false }) {
  const [status, setStatus] = useState(jogo.tem_analise ? 'ready' : 'none')
  const [loading, setLoading] = useState(false)
  const { label: countdown, minsLeft } = useCountdown(jogo.data_iso)

  useEffect(() => {
    setStatus(jogo.tem_analise ? 'ready' : 'none')
  }, [jogo.tem_analise])

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
  const isLast30 = minsLeft !== null && minsLeft >= 0 && minsLeft <= 30
  const topPicks = jogo.best_palpites?.slice(0, 2) || []

  if (isProcessing) {
    return (
      <div className="card skeleton-card" style={{ padding: compact ? '10px 12px' : '11px 14px', marginBottom: 4 }}>
        <div className="flex items-center gap-3">
          <div style={{ width: 44, flexShrink: 0 }}>
            <div style={{ height: 13, borderRadius: 4, background: 'rgba(255,255,255,0.06)', marginBottom: 4 }} />
            <div style={{ height: 9, borderRadius: 3, background: 'rgba(255,255,255,0.04)', width: 32 }} />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1 }}>
            <div style={{ width: 22, height: 22, borderRadius: '50%', background: 'rgba(255,255,255,0.06)', flexShrink: 0 }} />
            <div style={{ height: 12, borderRadius: 4, background: 'rgba(255,255,255,0.07)', flex: 1, maxWidth: 90 }} />
            <div style={{ height: 10, width: 18, borderRadius: 3, background: 'rgba(255,255,255,0.04)' }} />
            <div style={{ height: 12, borderRadius: 4, background: 'rgba(255,255,255,0.07)', flex: 1, maxWidth: 90 }} />
            <div style={{ width: 22, height: 22, borderRadius: '50%', background: 'rgba(255,255,255,0.06)', flexShrink: 0 }} />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 10, color: '#4b5563' }}>
              <div className="spinner" style={{ width: 10, height: 10, borderWidth: 1.5, flexShrink: 0 }} />
              Analisando...
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <Link
      to={isReady ? `/jogo/${jogo.fixture_id}` : '#'}
      onClick={isReady ? undefined : handleAnalyze}
      style={{ textDecoration: 'none', display: 'block' }}
    >
      <div
        className="card"
        style={{
          padding: compact ? '10px 12px' : '11px 14px',
          marginBottom: 4,
          cursor: 'pointer',
          borderColor: isLast30 ? 'rgba(239,68,68,0.22)' : undefined,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 42, flexShrink: 0 }}>
            <span style={{ fontSize: 12, color: '#94a3b8', fontWeight: 700, letterSpacing: '-0.01em', lineHeight: 1 }}>
              {jogo.horario_brt}
            </span>
            {countdown && (
              <span style={{ fontSize: 9, color: isLast30 ? '#f87171' : '#4b5563', marginTop: 3, whiteSpace: 'nowrap', fontWeight: 500 }}>
                {countdown}
              </span>
            )}
            {isReady && (
              jogo.fixture_metadata?.lineup_confirmado
                ? <span style={{ fontSize: 8, color: '#22c55e', marginTop: 2, fontWeight: 600 }}>✅ Lineup</span>
                : <span style={{ fontSize: 8, color: '#f59e0b', marginTop: 2, fontWeight: 600 }}>⏳ Lineup</span>
            )}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 7, flex: 1, minWidth: 0, overflow: 'hidden' }}>
            <TeamLogo logo={jogo.time_casa?.logo} name={jogo.time_casa?.nome} size={compact ? 21 : 24} />
            <span style={{
              fontSize: compact ? 11 : 12, fontWeight: 600, color: '#e2e8f0',
              whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 88,
            }}>
              {jogo.time_casa?.nome}
            </span>
            <span style={{ fontSize: 10, color: '#4b5563', margin: '0 1px', flexShrink: 0, fontWeight: 600 }}>vs</span>
            <span style={{
              fontSize: compact ? 11 : 12, fontWeight: 600, color: '#e2e8f0',
              whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 88,
            }}>
              {jogo.time_fora?.nome}
            </span>
            <TeamLogo logo={jogo.time_fora?.logo} name={jogo.time_fora?.nome} size={compact ? 21 : 24} />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 5, flexShrink: 0 }}>
            {isLast30 && isReady && (
              <span style={{
                fontSize: 9, fontWeight: 700, padding: '2px 6px', borderRadius: 5,
                background: 'rgba(239,68,68,0.1)', color: '#f87171',
                border: '1px solid rgba(239,68,68,0.2)', whiteSpace: 'nowrap',
              }}>
                🔴 Final
              </span>
            )}
            {isReady && topPicks.length > 0 && (
              <div style={{ display: 'flex', gap: 3, flexShrink: 0 }}>
                {topPicks.map((p, i) => (
                  <div key={i} style={{
                    display: 'flex', alignItems: 'center', gap: 3,
                    background: 'rgba(99,102,241,0.07)',
                    border: '1px solid rgba(99,102,241,0.15)',
                    borderRadius: 6, padding: '2px 6px',
                  }}>
                    <span style={{ fontSize: 10 }}>{MERCADO_EMOJI[p.mercado] || '📊'}</span>
                    <span style={{
                      fontSize: 10, fontWeight: 700,
                      color: p.confianca >= 7 ? '#4ade80' : '#fbbf24',
                      whiteSpace: 'nowrap', maxWidth: 66, overflow: 'hidden', textOverflow: 'ellipsis',
                    }}>
                      {p.tipo}
                    </span>
                    {p.probabilidade != null && (
                      <span style={{ fontSize: 9, color: '#818cf8' }}>{Number(p.probabilidade).toFixed(0)}%</span>
                    )}
                  </div>
                ))}
              </div>
            )}
            {isReady && (
              <span className="badge badge-green" style={{ fontSize: 10 }}>✓</span>
            )}
            {isProcessing && (
              <span className="badge badge-blue" style={{ fontSize: 10, gap: 4 }}>
                <div className="spinner" style={{ width: 9, height: 9, borderWidth: 1.5 }} />
                ...
              </span>
            )}
            {!isReady && !isProcessing && (
              <button
                onClick={handleAnalyze}
                style={{
                  fontSize: 11, fontWeight: 600, padding: '3px 9px',
                  background: 'rgba(99,102,241,0.1)', color: '#818cf8',
                  border: '1px solid rgba(99,102,241,0.22)', borderRadius: 7, cursor: 'pointer',
                  whiteSpace: 'nowrap', transition: 'all 0.15s',
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

function FeaturedMatchCard({ jogo }) {
  const [status, setStatus] = useState(jogo.tem_analise ? 'ready' : 'none')
  const [loading, setLoading] = useState(false)
  const { label: countdown, minsLeft } = useCountdown(jogo.data_iso)

  useEffect(() => {
    setStatus(jogo.tem_analise ? 'ready' : 'none')
  }, [jogo.tem_analise])

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
  const isLast30 = minsLeft !== null && minsLeft >= 0 && minsLeft <= 30
  const score = jogo.score_destaque || 0

  return (
    <Link
      to={isReady ? `/jogo/${jogo.fixture_id}` : '#'}
      onClick={isReady ? undefined : handleAnalyze}
      style={{ textDecoration: 'none', display: 'block' }}
    >
      <div
        className="card"
        style={{
          padding: '15px 18px', marginBottom: 8, cursor: 'pointer',
          borderColor: isLast30 ? 'rgba(239,68,68,0.28)' : 'rgba(99,102,241,0.2)',
          background: isLast30
            ? 'rgba(239,68,68,0.04)'
            : 'rgba(99,102,241,0.04)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10, flexWrap: 'wrap' }}>
              {jogo.liga.logo && (
                <img
                  src={jogo.liga.logo} alt=""
                  style={{ width: 15, height: 15, objectFit: 'contain' }}
                  onError={e => e.target.style.display = 'none'}
                />
              )}
              <span style={{ fontSize: 11, color: '#818cf8', fontWeight: 600 }}>
                {jogo.liga.nome}
              </span>
              <span style={{ fontSize: 10, color: '#4b5563' }}>·</span>
              <span style={{ fontSize: 11, color: '#94a3b8', fontWeight: 700 }}>{jogo.horario_brt}</span>
              {countdown && (
                <span style={{ fontSize: 10, color: isLast30 ? '#f87171' : '#64748b' }}>
                  ({countdown})
                </span>
              )}
              {isLast30 && (
                <span style={{
                  fontSize: 10, fontWeight: 700, padding: '1px 6px', borderRadius: 5,
                  background: 'rgba(239,68,68,0.1)', color: '#f87171',
                  border: '1px solid rgba(239,68,68,0.2)',
                }}>
                  🔴 Análise Final
                </span>
              )}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <TeamLogo logo={jogo.time_casa?.logo} name={jogo.time_casa?.nome} size={30} />
                <span style={{ fontSize: 15, fontWeight: 700, color: '#f1f5f9', letterSpacing: '-0.02em' }}>
                  {jogo.time_casa?.nome}
                </span>
              </div>
              <span style={{ fontSize: 11, color: '#4b5563', fontWeight: 700, padding: '0 4px' }}>vs</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 15, fontWeight: 700, color: '#f1f5f9', letterSpacing: '-0.02em' }}>
                  {jogo.time_fora?.nome}
                </span>
                <TeamLogo logo={jogo.time_fora?.logo} name={jogo.time_fora?.nome} size={30} />
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 7, flexShrink: 0 }}>
            <div style={{
              fontSize: 10, fontWeight: 700, color: '#fbbf24',
              background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.2)',
              borderRadius: 6, padding: '2px 7px',
            }}>
              ⭐ {score.toFixed(0)}
            </div>
            {isReady && (
              <span className="badge badge-green" style={{ fontSize: 11 }}>✓ Analisado</span>
            )}
            {isProcessing && (
              <span className="badge badge-blue" style={{ fontSize: 11, gap: 5 }}>
                <div className="spinner" style={{ width: 11, height: 11, borderWidth: 2 }} />
                Analisando...
              </span>
            )}
            {!isReady && !isProcessing && (
              <button
                onClick={handleAnalyze}
                style={{
                  fontSize: 11, fontWeight: 600, padding: '4px 11px',
                  background: 'rgba(99,102,241,0.12)', color: '#818cf8',
                  border: '1px solid rgba(99,102,241,0.28)', borderRadius: 7, cursor: 'pointer',
                  transition: 'all 0.15s',
                }}
              >
                Analisar →
              </button>
            )}
          </div>
        </div>

        {isReady && jogo.best_palpites?.length > 0 && (
          <div style={{
            marginTop: 10, paddingTop: 10,
            borderTop: '1px solid rgba(255,255,255,0.06)',
            display: 'flex', gap: 6, flexWrap: 'wrap',
          }}>
            {jogo.best_palpites.slice(0, 3).map((p, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 5,
                background: 'rgba(99,102,241,0.07)',
                border: '1px solid rgba(99,102,241,0.13)',
                borderRadius: 7, padding: '4px 9px',
              }}>
                <span style={{ fontSize: 12 }}>{MERCADO_EMOJI[p.mercado] || '📊'}</span>
                <span style={{ fontSize: 11, fontWeight: 700, color: p.confianca >= 7 ? '#4ade80' : '#fbbf24' }}>
                  {p.tipo}
                </span>
                {p.probabilidade != null && (
                  <span style={{ fontSize: 10, color: '#818cf8', fontWeight: 600 }}>{Number(p.probabilidade).toFixed(0)}%</span>
                )}
                {p.odd && <span style={{ fontSize: 10, color: '#64748b' }}>@{Number(p.odd).toFixed(2)}</span>}
              </div>
            ))}
          </div>
        )}
      </div>
    </Link>
  )
}

function LeagueSection({ liga, jogos }) {
  const [open, setOpen] = useState(true)

  return (
    <div style={{ marginBottom: 4 }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: 8,
          background: 'transparent',
          border: 'none',
          borderRadius: 7, padding: '7px 10px', cursor: 'pointer', marginBottom: open ? 4 : 0,
        }}
      >
        {liga.logo && (
          <img src={liga.logo} alt="" style={{ width: 16, height: 16, objectFit: 'contain' }} onError={e => e.target.style.display = 'none'} />
        )}
        <span style={{ fontSize: 12, fontWeight: 600, color: '#94a3b8' }}>{liga.nome}</span>
        <span style={{ marginLeft: 'auto', fontSize: 10, color: '#4b5563', fontWeight: 500 }}>
          {jogos.length} jogo{jogos.length !== 1 ? 's' : ''} {open ? '▴' : '▾'}
        </span>
      </button>
      {open && (
        <div style={{ paddingLeft: 2 }}>
          {jogos.map(j => (
            <MatchCard key={j.fixture_id} jogo={j} compact />
          ))}
        </div>
      )}
    </div>
  )
}

function CountrySection({ pais, ligas }) {
  const [open, setOpen] = useState(true)
  const totalJogos = ligas.reduce((acc, l) => acc + l.jogos.length, 0)
  const bandeira = ligas[0]?.liga?.bandeira || ''

  return (
    <div style={{ marginBottom: 10 }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: 9,
          background: 'rgba(255,255,255,0.025)',
          border: '1px solid rgba(255,255,255,0.07)',
          borderRadius: 9, padding: '9px 12px', cursor: 'pointer', marginBottom: open ? 8 : 0,
          transition: 'background 0.15s',
        }}
      >
        {bandeira && (
          <img src={bandeira} alt="" style={{ width: 18, height: 13, objectFit: 'cover', borderRadius: 2 }} onError={e => e.target.style.display = 'none'} />
        )}
        <span style={{ fontSize: 13, fontWeight: 700, color: '#e2e8f0', letterSpacing: '-0.01em' }}>{pais}</span>
        <span style={{ fontSize: 11, color: '#4b5563', marginLeft: 4, fontWeight: 500 }}>
          {ligas.length} liga{ligas.length !== 1 ? 's' : ''} · {totalJogos} jogo{totalJogos !== 1 ? 's' : ''}
        </span>
        <span style={{ marginLeft: 'auto', fontSize: 11, color: '#4b5563' }}>{open ? '▴' : '▾'}</span>
      </button>

      {open && (
        <div style={{ paddingLeft: 6 }}>
          {ligas.map((grupo) => (
            <LeagueSection key={grupo.liga.id} liga={grupo.liga} jogos={grupo.jogos} />
          ))}
        </div>
      )}
    </div>
  )
}

function AutoRefreshTimer({ secondsLeft }) {
  const mins = Math.floor(secondsLeft / 60)
  const secs = secondsLeft % 60
  return (
    <span style={{ fontSize: 11, color: '#4b5563', fontVariantNumeric: 'tabular-nums' }}>
      Atualiza em {mins}:{String(secs).padStart(2, '0')}
    </span>
  )
}

function FilterPanel({ filters, onChange, ligas }) {
  const [open, setOpen] = useState(false)
  const hasActive = filters.confiancaMin > 60 || filters.mercados.length > 0 ||
    filters.ligaIds.length > 0 || filters.sort !== 'horario' || filters.apenasAnalisados

  return (
    <div style={{ marginBottom: 18 }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          display: 'flex', alignItems: 'center', gap: 7, padding: '7px 13px',
          background: hasActive ? 'rgba(99,102,241,0.14)' : 'rgba(255,255,255,0.04)',
          border: `1px solid ${hasActive ? 'rgba(99,102,241,0.4)' : 'rgba(255,255,255,0.08)'}`,
          borderRadius: 8, cursor: 'pointer', fontSize: 12,
          color: hasActive ? '#818cf8' : '#64748b', fontWeight: 600,
          transition: 'all 0.15s',
        }}
      >
        <span>⚙️ Filtros</span>
        {hasActive && (
          <span style={{
            fontSize: 9, background: '#6366f1', color: '#fff',
            borderRadius: '50%', width: 14, height: 14,
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800,
          }}>!</span>
        )}
        <span style={{ fontSize: 10, marginLeft: 1 }}>{open ? '▴' : '▾'}</span>
      </button>

      {open && (
        <div style={{
          marginTop: 8, padding: '16px 18px',
          background: 'rgba(255,255,255,0.025)', border: '1px solid rgba(255,255,255,0.07)',
          borderRadius: 10, display: 'flex', flexDirection: 'column', gap: 16,
        }}>
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: '#64748b', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              Confiança mínima
              <span style={{ color: '#818cf8', marginLeft: 6, textTransform: 'none', letterSpacing: 0, fontWeight: 800 }}>
                {filters.confiancaMin}%
              </span>
            </div>
            <input
              type="range" min="60" max="95" step="5"
              value={filters.confiancaMin}
              onChange={e => onChange({ ...filters, confiancaMin: Number(e.target.value) })}
              style={{ width: '100%', accentColor: '#6366f1' }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#4b5563', marginTop: 3 }}>
              <span>60%</span><span>70%</span><span>80%</span><span>95%</span>
            </div>
          </div>

          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: '#64748b', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Mercados</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
              {MERCADOS_DISPONIVEIS.map(m => {
                const on = filters.mercados.includes(m)
                return (
                  <button key={m} onClick={() => onChange({
                    ...filters,
                    mercados: on ? filters.mercados.filter(x => x !== m) : [...filters.mercados, m],
                  })} style={{
                    fontSize: 11, fontWeight: 600, padding: '4px 10px', borderRadius: 7, cursor: 'pointer',
                    background: on ? 'rgba(99,102,241,0.15)' : 'rgba(255,255,255,0.04)',
                    color: on ? '#818cf8' : '#4b5563',
                    border: `1px solid ${on ? 'rgba(99,102,241,0.35)' : 'rgba(255,255,255,0.07)'}`,
                    transition: 'all 0.12s',
                  }}>
                    {m}
                  </button>
                )
              })}
            </div>
          </div>

          {ligas.length > 0 && (
            <div>
              <div style={{ fontSize: 11, fontWeight: 700, color: '#64748b', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Ligas</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                {ligas.slice(0, 16).map(l => {
                  const on = filters.ligaIds.includes(l.id)
                  return (
                    <button key={l.id} onClick={() => onChange({
                      ...filters,
                      ligaIds: on ? filters.ligaIds.filter(x => x !== l.id) : [...filters.ligaIds, l.id],
                    })} style={{
                      display: 'flex', alignItems: 'center', gap: 4,
                      fontSize: 11, fontWeight: 600, padding: '4px 8px', borderRadius: 7, cursor: 'pointer',
                      background: on ? 'rgba(99,102,241,0.15)' : 'rgba(255,255,255,0.04)',
                      color: on ? '#818cf8' : '#64748b',
                      border: `1px solid ${on ? 'rgba(99,102,241,0.35)' : 'rgba(255,255,255,0.07)'}`,
                    }}>
                      {l.logo && <img src={l.logo} alt="" style={{ width: 13, height: 13, objectFit: 'contain' }} onError={e => e.target.style.display = 'none'} />}
                      {l.nome}
                    </button>
                  )
                })}
              </div>
            </div>
          )}

          <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Ordenar:</div>
            {[
              { v: 'horario', l: '⏰ Horário' },
              { v: 'confianca', l: '📊 Confiança' },
              { v: 'score', l: '⭐ Relevância' },
            ].map(({ v, l }) => (
              <button key={v} onClick={() => onChange({ ...filters, sort: v })} style={{
                fontSize: 11, fontWeight: 600, padding: '4px 10px', borderRadius: 7, cursor: 'pointer',
                background: filters.sort === v ? 'rgba(99,102,241,0.15)' : 'rgba(255,255,255,0.04)',
                color: filters.sort === v ? '#818cf8' : '#4b5563',
                border: `1px solid ${filters.sort === v ? 'rgba(99,102,241,0.35)' : 'rgba(255,255,255,0.07)'}`,
                transition: 'all 0.12s',
              }}>
                {l}
              </button>
            ))}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <button onClick={() => onChange({ ...filters, apenasAnalisados: !filters.apenasAnalisados })} style={{
              width: 34, height: 18, borderRadius: 10, border: 'none', cursor: 'pointer', padding: 0,
              background: filters.apenasAnalisados ? '#6366f1' : 'rgba(255,255,255,0.1)',
              position: 'relative', transition: 'background 0.2s', flexShrink: 0,
            }}>
              <div style={{
                width: 14, height: 14, borderRadius: '50%', background: '#fff',
                position: 'absolute', top: 2,
                left: filters.apenasAnalisados ? 18 : 2,
                transition: 'left 0.2s',
              }} />
            </button>
            <span style={{ fontSize: 12, color: '#64748b' }}>Apenas jogos já analisados</span>
          </div>

          {hasActive && (
            <button onClick={() => onChange({ confiancaMin: 60, mercados: [], ligaIds: [], sort: 'horario', apenasAnalisados: false })} style={{
              alignSelf: 'flex-start', fontSize: 11, padding: '4px 12px', borderRadius: 7,
              background: 'rgba(239,68,68,0.07)', color: '#f87171',
              border: '1px solid rgba(239,68,68,0.18)', cursor: 'pointer', fontWeight: 600,
            }}>
              ✕ Limpar filtros
            </button>
          )}
        </div>
      )}
    </div>
  )
}

function matchesSearch(jogo, q) {
  const lq = q.toLowerCase().trim()
  if (!lq) return true
  return (
    jogo.time_casa?.nome?.toLowerCase().includes(lq) ||
    jogo.time_fora?.nome?.toLowerCase().includes(lq) ||
    jogo.liga?.nome?.toLowerCase().includes(lq) ||
    jogo.liga?.pais?.toLowerCase().includes(lq)
  )
}

function matchesFilters(jogo, filters) {
  if (filters.apenasAnalisados && !jogo.tem_analise) return false
  if (filters.ligaIds.length > 0 && !filters.ligaIds.includes(jogo.liga?.id)) return false

  const isActiveFilter = filters.confiancaMin > 60 || filters.mercados.length > 0

  if (isActiveFilter) {
    if (!jogo.tem_analise || !jogo.best_palpites?.length) return false

    if (filters.mercados.length > 0) {
      const hasMercado = filters.mercados.some(m =>
        (jogo.best_palpites || []).some(p => p.mercado === m)
      )
      if (!hasMercado) return false
    }

    if (filters.confiancaMin > 60) {
      const picks = (jogo.best_palpites || [])
      const qualifyingPick = picks.some(p => {
        const conf = p.confianca || 0
        return (conf / 10 * 100) >= filters.confiancaMin
      })
      if (!qualifyingPick) return false
    }
  }

  return true
}

function sortJogos(jogos, sort) {
  if (sort === 'confianca') {
    return [...jogos].sort((a, b) => {
      const aConf = Math.max(0, ...(a.best_palpites || []).map(p => p.confianca || 0))
      const bConf = Math.max(0, ...(b.best_palpites || []).map(p => p.confianca || 0))
      return bConf - aConf
    })
  }
  if (sort === 'score') {
    return [...jogos].sort((a, b) => (b.score_destaque || 0) - (a.score_destaque || 0))
  }
  return [...jogos].sort((a, b) => (a.horario_brt || '').localeCompare(b.horario_brt || ''))
}

export default function Home() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [countdown, setCountdown] = useState(AUTO_REFRESH_SECS)
  const [search, setSearch] = useState('')
  const [filters, setFilters] = useState({
    confiancaMin: 60,
    mercados: [],
    ligaIds: [],
    sort: 'horario',
    apenasAnalisados: false,
  })
  const timerRef = useRef(null)
  const countRef = useRef(AUTO_REFRESH_SECS)

  const fetchJogos = useCallback(async () => {
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
  }, [])

  const resetTimer = useCallback(() => {
    countRef.current = AUTO_REFRESH_SECS
    setCountdown(AUTO_REFRESH_SECS)
  }, [])

  const handleRefresh = useCallback(() => {
    resetTimer()
    fetchJogos()
  }, [fetchJogos, resetTimer])

  useEffect(() => {
    fetchJogos()
  }, [fetchJogos])

  useEffect(() => {
    timerRef.current = setInterval(() => {
      countRef.current -= 1
      setCountdown(countRef.current)
      if (countRef.current <= 0) {
        countRef.current = AUTO_REFRESH_SECS
        setCountdown(AUTO_REFRESH_SECS)
        fetchJogos()
      }
    }, 1000)
    return () => clearInterval(timerRef.current)
  }, [fetchJogos])

  const allJogos = useMemo(() => {
    if (!data?.por_pais) return []
    return data.por_pais.flatMap(p => p.ligas.flatMap(l => l.jogos))
  }, [data])

  const allLigas = useMemo(() => {
    if (!data?.por_pais) return []
    const seen = new Set()
    const out = []
    data.por_pais.forEach(p => p.ligas.forEach(l => {
      if (!seen.has(l.liga.id)) { seen.add(l.liga.id); out.push(l.liga) }
    }))
    return out
  }, [data])

  const filteredJogos = useMemo(() => {
    const q = search.trim()
    return sortJogos(
      allJogos.filter(j => matchesSearch(j, q) && matchesFilters(j, filters)),
      filters.sort
    )
  }, [allJogos, search, filters])

  const filteredPrincipais = useMemo(() => {
    if (!data?.principais) return []
    const q = search.trim()
    return sortJogos(
      data.principais.filter(j => matchesSearch(j, q) && matchesFilters(j, filters)),
      filters.sort
    ).slice(0, 8)
  }, [data, search, filters])

  const filteredPorPais = useMemo(() => {
    if (!data?.por_pais) return []
    const q = search.trim()
    return data.por_pais
      .map(p => ({
        ...p,
        ligas: p.ligas
          .map(l => ({
            ...l,
            jogos: sortJogos(
              l.jogos.filter(j => matchesSearch(j, q) && matchesFilters(j, filters)),
              filters.sort
            ),
          }))
          .filter(l => l.jogos.length > 0),
      }))
      .filter(p => p.ligas.length > 0)
  }, [data, search, filters])

  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 320, gap: 14, paddingTop: 60 }}>
        <div className="spinner" style={{ width: 40, height: 40 }} />
        <p style={{ color: '#64748b', fontSize: 14 }}>Carregando jogos de hoje...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 320, gap: 12, paddingTop: 60 }}>
        <div style={{ fontSize: 36 }}>⚠️</div>
        <p style={{ color: '#f87171', fontSize: 14 }}>Erro ao conectar com a API</p>
        <p style={{ color: '#64748b', fontSize: 12 }}>{error}</p>
        <button
          onClick={handleRefresh}
          style={{
            marginTop: 8, padding: '8px 20px', borderRadius: 8,
            background: 'rgba(99,102,241,0.12)', color: '#818cf8',
            border: '1px solid rgba(99,102,241,0.25)', cursor: 'pointer', fontSize: 13,
          }}
        >
          Tentar novamente
        </button>
      </div>
    )
  }

  const total = data?.total || 0
  const totalPaises = data?.por_pais?.length || 0
  const isDemo = data?.is_demo || false
  const totalFiltrados = filteredJogos.length

  return (
    <div style={{ paddingTop: 28 }}>
      {isDemo && (
        <div style={{
          display: 'flex', alignItems: 'flex-start', gap: 10,
          background: 'rgba(245,158,11,0.06)', border: '1px solid rgba(245,158,11,0.22)',
          borderRadius: 10, padding: '11px 15px', marginBottom: 20,
        }}>
          <span style={{ fontSize: 16, flexShrink: 0, marginTop: 1 }}>🧪</span>
          <div>
            <p style={{ fontSize: 13, fontWeight: 700, color: '#fbbf24', margin: 0, letterSpacing: '-0.01em' }}>
              Modo Demonstração
            </p>
            <p style={{ fontSize: 12, color: '#92400e', margin: '3px 0 0', lineHeight: 1.4 }}>
              A API não retornou jogos reais. Os dados abaixo são fictícios para demonstrar a interface.
            </p>
          </div>
        </div>
      )}

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: '#f1f5f9', letterSpacing: '-0.03em', lineHeight: 1 }}>
            Jogos de Hoje
          </h1>
          <p style={{ fontSize: 12, color: '#64748b', marginTop: 4 }}>
            {totalFiltrados !== total
              ? `${totalFiltrados} de ${total} partida${total !== 1 ? 's' : ''} (filtrado)`
              : `${total} partida${total !== 1 ? 's' : ''} em ${totalPaises} pa${totalPaises !== 1 ? 'íses' : 'ís'}`
            }
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <AutoRefreshTimer secondsLeft={countdown} />
          <button
            onClick={handleRefresh}
            style={{
              fontSize: 12, padding: '6px 12px', borderRadius: 7,
              background: 'rgba(99,102,241,0.08)', color: '#818cf8',
              border: '1px solid rgba(99,102,241,0.18)', cursor: 'pointer', fontWeight: 500,
              transition: 'all 0.15s',
            }}
          >
            ↻ Atualizar
          </button>
        </div>
      </div>

      <div style={{ position: 'relative', marginBottom: 12 }}>
        <span style={{
          position: 'absolute', left: 13, top: '50%', transform: 'translateY(-50%)',
          fontSize: 14, color: '#4b5563', pointerEvents: 'none',
        }}>
          🔍
        </span>
        <input
          type="text"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Buscar por time, competição ou país..."
          style={{
            width: '100%', padding: '10px 38px 10px 38px',
            background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: 9, color: '#e2e8f0', fontSize: 13, outline: 'none',
            transition: 'border-color 0.18s',
          }}
          onFocus={e => e.target.style.borderColor = 'rgba(99,102,241,0.4)'}
          onBlur={e => e.target.style.borderColor = 'rgba(255,255,255,0.08)'}
        />
        {search && (
          <button
            onClick={() => setSearch('')}
            style={{
              position: 'absolute', right: 11, top: '50%', transform: 'translateY(-50%)',
              background: 'none', border: 'none', color: '#4b5563', cursor: 'pointer',
              fontSize: 15, lineHeight: 1, padding: 2,
            }}
          >
            ✕
          </button>
        )}
      </div>

      <FilterPanel filters={filters} onChange={setFilters} ligas={allLigas} />

      {total === 0 ? (
        <div style={{
          textAlign: 'center', padding: '60px 0', color: '#64748b',
          background: 'rgba(255,255,255,0.02)', border: '1px dashed rgba(255,255,255,0.08)',
          borderRadius: 12,
        }}>
          <div style={{ fontSize: 44, marginBottom: 12 }}>📭</div>
          <p style={{ fontSize: 15, fontWeight: 600, color: '#94a3b8' }}>Sem jogos disponíveis</p>
          <p style={{ fontSize: 13, marginTop: 6 }}>Nenhuma partida encontrada nas ligas monitoradas.</p>
        </div>
      ) : totalFiltrados === 0 ? (
        <div style={{
          textAlign: 'center', padding: '48px 0', color: '#64748b',
          background: 'rgba(255,255,255,0.02)', border: '1px dashed rgba(255,255,255,0.08)',
          borderRadius: 12,
        }}>
          <div style={{ fontSize: 36, marginBottom: 12 }}>🔍</div>
          <p style={{ fontSize: 15, fontWeight: 600, color: '#94a3b8' }}>Nenhum resultado</p>
          <p style={{ fontSize: 13, marginTop: 6 }}>
            Ajuste os filtros ou a busca para ver mais jogos.
          </p>
          <button
            onClick={() => { setSearch(''); setFilters({ confiancaMin: 60, mercados: [], ligaIds: [], sort: 'horario', apenasAnalisados: false }) }}
            style={{
              marginTop: 16, padding: '7px 20px', borderRadius: 8, cursor: 'pointer',
              background: 'rgba(99,102,241,0.12)', color: '#818cf8',
              border: '1px solid rgba(99,102,241,0.25)', fontSize: 13,
            }}
          >
            Limpar tudo
          </button>
        </div>
      ) : (
        <>
          {filteredPrincipais.length > 0 && (
            <section style={{ marginBottom: 32 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 12 }}>
                <span style={{ fontSize: 14, fontWeight: 700, color: '#f1f5f9', letterSpacing: '-0.01em' }}>⭐ Principais Jogos</span>
                <span style={{
                  fontSize: 10, color: '#fbbf24',
                  background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.18)',
                  borderRadius: 20, padding: '2px 8px', fontWeight: 600,
                }}>
                  Top {filteredPrincipais.length}
                </span>
              </div>
              {filteredPrincipais.map(j => (
                <FeaturedMatchCard key={j.fixture_id} jogo={j} />
              ))}
            </section>
          )}

          {filteredPorPais.length > 0 && (
            <section>
              <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 12 }}>
                <span style={{ fontSize: 14, fontWeight: 700, color: '#f1f5f9', letterSpacing: '-0.01em' }}>🌍 Todos os Jogos</span>
                <span style={{ fontSize: 11, color: '#64748b' }}>por país e liga</span>
              </div>
              {filteredPorPais.map(({ pais, ligas }) => (
                <CountrySection key={pais} pais={pais} ligas={ligas} />
              ))}
            </section>
          )}
        </>
      )}
    </div>
  )
}
