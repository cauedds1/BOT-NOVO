import { useState, useEffect, useRef, useCallback } from 'react'
import { Link } from 'react-router-dom'

const AUTO_REFRESH_SECS = 600

function TeamLogo({ logo, name, size = 28 }) {
  const [err, setErr] = useState(false)
  if (!logo || err) {
    return (
      <div
        style={{
          width: size, height: size, borderRadius: '50%',
          background: 'rgba(99,102,241,0.2)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: size * 0.45, color: '#818cf8', fontWeight: 700, flexShrink: 0,
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

  const topPick = jogo.best_palpites?.[0]

  return (
    <Link
      to={isReady ? `/jogo/${jogo.fixture_id}` : '#'}
      onClick={isReady ? undefined : handleAnalyze}
      style={{ textDecoration: 'none', display: 'block' }}
    >
      <div
        className="card"
        style={{ padding: compact ? '12px 14px' : '14px 16px', marginBottom: 8, cursor: 'pointer' }}
      >
        <div className="flex items-center gap-3">
          <span style={{ fontSize: 12, color: '#64748b', fontWeight: 600, minWidth: 38, flexShrink: 0 }}>
            {jogo.horario_brt}
          </span>

          <div className="flex items-center gap-2 flex-1 min-w-0">
            <TeamLogo logo={jogo.time_casa?.logo} name={jogo.time_casa?.nome} size={compact ? 22 : 28} />
            <span style={{
              fontSize: compact ? 12 : 13, fontWeight: 600, color: '#e2e8f0',
              whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 100,
            }}>
              {jogo.time_casa?.nome}
            </span>
            <span style={{ fontSize: 11, color: '#475569', margin: '0 2px', flexShrink: 0 }}>vs</span>
            <span style={{
              fontSize: compact ? 12 : 13, fontWeight: 600, color: '#e2e8f0',
              whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 100,
            }}>
              {jogo.time_fora?.nome}
            </span>
            <TeamLogo logo={jogo.time_fora?.logo} name={jogo.time_fora?.nome} size={compact ? 22 : 28} />
          </div>

          <div className="ml-auto flex-shrink-0 flex items-center gap-6">
            {isReady && topPick && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 5, flexShrink: 0 }}>
                <span style={{ fontSize: 10, color: '#64748b' }}>{topPick.mercado}:</span>
                <span style={{ fontSize: 11, fontWeight: 700, color: topPick.confianca >= 7 ? '#22c55e' : '#eab308', maxWidth: 100, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {topPick.tipo}
                </span>
                {topPick.odd && <span style={{ fontSize: 10, color: '#818cf8' }}>@{Number(topPick.odd).toFixed(2)}</span>}
              </div>
            )}
            {isReady && (
              <span className="badge badge-green" style={{ fontSize: 11 }}>✓ Analisado</span>
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
                  background: 'rgba(99,102,241,0.15)', color: '#818cf8',
                  border: '1px solid rgba(99,102,241,0.3)', borderRadius: 8, cursor: 'pointer',
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
          padding: '16px 18px', marginBottom: 10, cursor: 'pointer',
          border: '1px solid rgba(99,102,241,0.25)',
          background: 'linear-gradient(135deg, rgba(99,102,241,0.08) 0%, rgba(15,23,42,0.8) 100%)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}>
              {jogo.liga.logo && (
                <img
                  src={jogo.liga.logo} alt=""
                  style={{ width: 16, height: 16, objectFit: 'contain' }}
                  onError={e => e.target.style.display = 'none'}
                />
              )}
              <span style={{ fontSize: 11, color: '#818cf8', fontWeight: 600 }}>
                {jogo.liga.nome}
              </span>
              <span style={{ fontSize: 10, color: '#475569' }}>·</span>
              <span style={{ fontSize: 11, color: '#64748b' }}>{jogo.horario_brt}</span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <TeamLogo logo={jogo.time_casa?.logo} name={jogo.time_casa?.nome} size={32} />
                <span style={{ fontSize: 14, fontWeight: 700, color: '#f1f5f9' }}>
                  {jogo.time_casa?.nome}
                </span>
              </div>
              <span style={{ fontSize: 12, color: '#475569', fontWeight: 700 }}>vs</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 14, fontWeight: 700, color: '#f1f5f9' }}>
                  {jogo.time_fora?.nome}
                </span>
                <TeamLogo logo={jogo.time_fora?.logo} name={jogo.time_fora?.nome} size={32} />
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 8, flexShrink: 0 }}>
            <div style={{
              fontSize: 10, fontWeight: 700, color: '#f59e0b',
              background: 'rgba(245,158,11,0.12)', border: '1px solid rgba(245,158,11,0.25)',
              borderRadius: 6, padding: '2px 7px',
            }}>
              ⭐ {score.toFixed(0)}
            </div>
            {isReady && (
              <span className="badge badge-green" style={{ fontSize: 11 }}>✓ Analisado</span>
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
                  fontSize: 11, fontWeight: 600, padding: '4px 12px',
                  background: 'rgba(99,102,241,0.2)', color: '#818cf8',
                  border: '1px solid rgba(99,102,241,0.35)', borderRadius: 8, cursor: 'pointer',
                }}
              >
                Analisar →
              </button>
            )}
          </div>
        </div>

        {/* best_palpites preview quando já analisado */}
        {isReady && jogo.best_palpites?.length > 0 && (
          <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid rgba(99,102,241,0.12)', display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {jogo.best_palpites.slice(0, 3).map((p, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 5,
                background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.15)',
                borderRadius: 8, padding: '4px 9px',
              }}>
                <span style={{ fontSize: 10, color: '#64748b' }}>{p.mercado}:</span>
                <span style={{ fontSize: 11, fontWeight: 700, color: p.confianca >= 7 ? '#22c55e' : '#eab308' }}>{p.tipo}</span>
                {p.odd && <span style={{ fontSize: 10, color: '#818cf8' }}>@{Number(p.odd).toFixed(2)}</span>}
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
    <div style={{ marginBottom: 6 }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: 8,
          background: 'rgba(99,102,241,0.05)', border: '1px solid rgba(99,102,241,0.1)',
          borderRadius: 8, padding: '8px 12px', cursor: 'pointer', marginBottom: open ? 6 : 0,
        }}
      >
        {liga.logo && (
          <img src={liga.logo} alt="" style={{ width: 18, height: 18, objectFit: 'contain' }} onError={e => e.target.style.display = 'none'} />
        )}
        <span style={{ fontSize: 12, fontWeight: 700, color: '#c7d2fe' }}>{liga.nome}</span>
        <span style={{ marginLeft: 'auto', fontSize: 11, color: '#475569' }}>
          {jogos.length} jogo{jogos.length !== 1 ? 's' : ''} {open ? '▲' : '▼'}
        </span>
      </button>
      {open && jogos.map(j => (
        <MatchCard key={j.fixture_id} jogo={j} compact />
      ))}
    </div>
  )
}

function CountrySection({ pais, ligas }) {
  const [open, setOpen] = useState(true)
  const totalJogos = ligas.reduce((acc, l) => acc + l.jogos.length, 0)
  const bandeira = ligas[0]?.liga?.bandeira || ''

  return (
    <div style={{ marginBottom: 16 }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: 10,
          background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.15)',
          borderRadius: 10, padding: '10px 14px', cursor: 'pointer', marginBottom: open ? 10 : 0,
        }}
      >
        {bandeira && (
          <img src={bandeira} alt="" style={{ width: 20, height: 14, objectFit: 'cover', borderRadius: 2 }} onError={e => e.target.style.display = 'none'} />
        )}
        <span style={{ fontSize: 13, fontWeight: 700, color: '#e2e8f0' }}>{pais}</span>
        <span style={{ fontSize: 11, color: '#475569', marginLeft: 4 }}>
          {ligas.length} liga{ligas.length !== 1 ? 's' : ''} · {totalJogos} jogo{totalJogos !== 1 ? 's' : ''}
        </span>
        <span style={{ marginLeft: 'auto', fontSize: 12, color: '#475569' }}>{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div style={{ paddingLeft: 8 }}>
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
    <span style={{ fontSize: 11, color: '#475569' }}>
      Atualiza em {mins}:{String(secs).padStart(2, '0')}
    </span>
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

export default function Home() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [countdown, setCountdown] = useState(AUTO_REFRESH_SECS)
  const [search, setSearch] = useState('')
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
          onClick={handleRefresh}
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

  const principais = data?.principais || []
  const porPais = data?.por_pais || []
  const total = data?.total || 0
  const totalPaises = porPais.length
  const isDemo = data?.is_demo || false

  const q = search.trim()

  const filteredPrincipais = q
    ? principais.filter(j => matchesSearch(j, q))
    : principais

  const filteredPorPais = q
    ? porPais
        .map(p => ({
          ...p,
          ligas: p.ligas
            .map(l => ({ ...l, jogos: l.jogos.filter(j => matchesSearch(j, q)) }))
            .filter(l => l.jogos.length > 0),
        }))
        .filter(p => p.ligas.length > 0)
    : porPais

  const totalFiltrados = q
    ? filteredPorPais.reduce((acc, p) => acc + p.ligas.reduce((a, l) => a + l.jogos.length, 0), 0)
    : total

  return (
    <div style={{ paddingTop: 24 }}>
      {isDemo && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10,
          background: 'rgba(234,179,8,0.1)', border: '1px solid rgba(234,179,8,0.35)',
          borderRadius: 10, padding: '10px 16px', marginBottom: 20,
        }}>
          <span style={{ fontSize: 18 }}>🧪</span>
          <div>
            <p style={{ fontSize: 13, fontWeight: 600, color: '#fbbf24', margin: 0 }}>
              Modo Demonstração
            </p>
            <p style={{ fontSize: 12, color: '#92400e', margin: 0, marginTop: 2 }}>
              A API não retornou jogos reais (plano gratuito bloqueado para a temporada atual).
              Os dados abaixo são ficticios para demonstrar a interface.
            </p>
          </div>
        </div>
      )}

      {/* ── Cabeçalho ─────────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: '#f1f5f9', letterSpacing: '-0.02em' }}>
            Jogos de Hoje
          </h1>
          <p style={{ fontSize: 13, color: '#64748b', marginTop: 3 }}>
            {q
              ? `${totalFiltrados} resultado${totalFiltrados !== 1 ? 's' : ''} para "${q}"`
              : `${total} partida${total !== 1 ? 's' : ''} em ${totalPaises} pa${totalPaises !== 1 ? 'íses' : 'ís'}`
            }
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <AutoRefreshTimer secondsLeft={countdown} />
          <button
            onClick={handleRefresh}
            style={{
              fontSize: 12, padding: '6px 14px', borderRadius: 8,
              background: 'rgba(99,102,241,0.1)', color: '#818cf8',
              border: '1px solid rgba(99,102,241,0.2)', cursor: 'pointer',
            }}
          >
            ↻ Atualizar
          </button>
        </div>
      </div>

      {/* ── Campo de busca ────────────────────────────────────── */}
      <div style={{ position: 'relative', marginBottom: 28 }}>
        <span style={{
          position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)',
          fontSize: 15, color: '#475569', pointerEvents: 'none',
        }}>
          🔍
        </span>
        <input
          type="text"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Buscar por time, competição ou país..."
          style={{
            width: '100%', padding: '10px 40px 10px 40px',
            background: 'rgba(15,23,42,0.8)', border: '1px solid rgba(99,102,241,0.2)',
            borderRadius: 10, color: '#e2e8f0', fontSize: 14, outline: 'none',
            transition: 'border-color 0.2s',
          }}
          onFocus={e => e.target.style.borderColor = 'rgba(99,102,241,0.55)'}
          onBlur={e => e.target.style.borderColor = 'rgba(99,102,241,0.2)'}
        />
        {search && (
          <button
            onClick={() => setSearch('')}
            style={{
              position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)',
              background: 'none', border: 'none', color: '#475569', cursor: 'pointer',
              fontSize: 16, lineHeight: 1, padding: 2,
            }}
          >
            ✕
          </button>
        )}
      </div>

      {total === 0 ? (
        <div style={{
          textAlign: 'center', padding: '60px 0', color: '#64748b',
          background: 'rgba(99,102,241,0.04)', border: '1px dashed rgba(99,102,241,0.15)',
          borderRadius: 12,
        }}>
          <div style={{ fontSize: 48, marginBottom: 12 }}>📭</div>
          <p style={{ fontSize: 15, fontWeight: 600, color: '#94a3b8' }}>Sem jogos disponíveis</p>
          <p style={{ fontSize: 13, marginTop: 6 }}>Nenhuma partida encontrada nas ligas monitoradas.</p>
        </div>
      ) : q && totalFiltrados === 0 ? (
        <div style={{
          textAlign: 'center', padding: '48px 0', color: '#64748b',
          background: 'rgba(99,102,241,0.04)', border: '1px dashed rgba(99,102,241,0.15)',
          borderRadius: 12,
        }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>🔍</div>
          <p style={{ fontSize: 15, fontWeight: 600, color: '#94a3b8' }}>Nenhum resultado</p>
          <p style={{ fontSize: 13, marginTop: 6 }}>
            Não há jogos com "<span style={{ color: '#818cf8' }}>{q}</span>" hoje.
          </p>
          <button
            onClick={() => setSearch('')}
            style={{
              marginTop: 16, padding: '7px 20px', borderRadius: 8, cursor: 'pointer',
              background: 'rgba(99,102,241,0.15)', color: '#818cf8',
              border: '1px solid rgba(99,102,241,0.3)', fontSize: 13,
            }}
          >
            Limpar busca
          </button>
        </div>
      ) : (
        <>
          {filteredPrincipais.length > 0 && (
            <section style={{ marginBottom: 36 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
                <span style={{ fontSize: 16, fontWeight: 700, color: '#f1f5f9' }}>⭐ Principais Jogos</span>
                <span style={{
                  fontSize: 11, color: '#f59e0b',
                  background: 'rgba(245,158,11,0.12)', border: '1px solid rgba(245,158,11,0.2)',
                  borderRadius: 20, padding: '2px 8px',
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
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
                <span style={{ fontSize: 16, fontWeight: 700, color: '#f1f5f9' }}>🌍 Todos os Jogos</span>
                <span style={{ fontSize: 11, color: '#64748b' }}>
                  por país e liga
                </span>
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
