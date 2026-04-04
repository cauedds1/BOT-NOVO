import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import MatchDrawer from '../components/MatchDrawer'

const AUTO_REFRESH_SECS = 600

const MERCADOS_DISPONIVEIS = ['Gols', 'Resultado', 'BTTS', 'Cantos', 'Cartões', 'Handicaps', 'Dupla Chance', 'Placar Exato']

const MERCADO_EMOJI = {
  'Gols': '⚽', 'Resultado': '🏁', 'BTTS': '🎲', 'Cantos': '🚩',
  'Cartões': '🟨', 'Finalizações': '🎯', 'Handicaps': '⚖️', 'Dupla Chance': '🔀',
  'Gols Ambos Tempos': '⏱️', 'Placar Exato': '🔢', 'Handicap Europeu': '🏷️', 'Primeiro a Marcar': '🥇',
}

function useCountdown(dataIso) {
  const [label, setLabel] = useState('')
  const [minsLeft, setMinsLeft] = useState(null)
  useEffect(() => {
    if (!dataIso) return
    const update = () => {
      const now = new Date(); const target = new Date(dataIso)
      if (isNaN(target.getTime())) { setLabel(''); setMinsLeft(null); return }
      const diffMins = Math.floor((target - now) / 60000)
      setMinsLeft(diffMins)
      if (diffMins < -90) setLabel('encerrado')
      else if (diffMins < 0) setLabel('ao vivo')
      else if (diffMins === 0) setLabel('agora')
      else if (diffMins < 60) setLabel(`em ${diffMins}min`)
      else { const h = Math.floor(diffMins / 60); const m = diffMins % 60; setLabel(m > 0 ? `em ${h}h${m}` : `em ${h}h`) }
    }
    update(); const iv = setInterval(update, 30000); return () => clearInterval(iv)
  }, [dataIso])
  return { label, minsLeft }
}

function TeamLogo({ logo, name, size = 28 }) {
  const [err, setErr] = useState(false)
  if (!logo || err) return (
    <div style={{
      width: size, height: size, borderRadius: '50%',
      background: 'var(--accent-dim)', border: '1px solid var(--accent-border)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: size * 0.4, color: 'var(--accent-light)', fontWeight: 700, flexShrink: 0,
    }}>
      {name?.[0] || '?'}
    </div>
  )
  return <img src={logo} alt={name} style={{ width: size, height: size, objectFit: 'contain', flexShrink: 0 }} onError={() => setErr(true)} />
}

function FormDots({ forma }) {
  if (!forma || forma.length === 0) return null
  return (
    <div style={{ display: 'flex', gap: 3, alignItems: 'center' }}>
      {forma.slice(0, 5).map((r, i) => {
        const u = String(r).toUpperCase()
        const cls = (u === 'W' || u === 'V') ? 'form-dot form-dot-w' : (u === 'D' || u === 'E') ? 'form-dot form-dot-d' : 'form-dot form-dot-l'
        return <div key={i} className={cls} />
      })}
    </div>
  )
}

function ProbBar({ palpites }) {
  let home = 33, draw = 33, away = 34
  if (palpites?.length > 0) {
    const resPalpite = palpites.find(p => p.mercado === 'Resultado')
    if (resPalpite?.prob_casa != null) {
      home = Number(resPalpite.prob_casa) || 33
      draw = Number(resPalpite.prob_empate) || 33
      away = Number(resPalpite.prob_fora) || 34
    }
  }
  const total = home + draw + away
  const hPct = total > 0 ? (home / total * 100).toFixed(1) : 33.3
  const dPct = total > 0 ? (draw / total * 100).toFixed(1) : 33.3
  const aPct = total > 0 ? (away / total * 100).toFixed(1) : 33.4

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 80 }}>
      <div className="prob-bar">
        <div className="prob-bar-home" style={{ width: `${hPct}%` }} />
        <div className="prob-bar-draw" style={{ width: `${dPct}%` }} />
        <div className="prob-bar-away" style={{ width: `${aPct}%` }} />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 8, color: 'var(--text-faint)', fontVariantNumeric: 'tabular-nums' }}>
        <span style={{ color: 'var(--accent-light)' }}>{hPct}%</span>
        <span style={{ color: 'var(--amber-light)' }}>{dPct}%</span>
        <span style={{ color: 'var(--green-light)' }}>{aPct}%</span>
      </div>
    </div>
  )
}

function MatchRow({ jogo, onOpen, featured = false }) {
  const [status, setStatus] = useState(jogo.tem_analise ? 'ready' : 'none')
  const [loading, setLoading] = useState(false)
  const { label: countdown, minsLeft } = useCountdown(jogo.data_iso)
  useEffect(() => { setStatus(jogo.tem_analise ? 'ready' : 'none') }, [jogo.tem_analise])

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

  const handleAnalyze = async (e) => {
    e.preventDefault(); e.stopPropagation()
    if (loading || status === 'processing') return
    setLoading(true); setStatus('processing')
    try {
      const r = await fetch(`/api/analisar/${jogo.fixture_id}`, { method: 'POST' })
      const d = await r.json()
      setStatus(d.status === 'ready' ? 'ready' : 'processing')
    } catch { setStatus('none') } finally { setLoading(false) }
  }

  const isReady = status === 'ready'
  const isProcessing = status === 'processing'
  const isLiveSoon = minsLeft !== null && minsLeft >= 0 && minsLeft <= 30
  const topPick = jogo.best_palpites?.[0]
  const forma = jogo.forma_casa || jogo.forma || []
  const formaFora = jogo.forma_fora || []

  if (isProcessing) return (
    <div className="skeleton-card" style={{ padding: '11px 14px', marginBottom: 4 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{ minWidth: 42, flexShrink: 0 }}>
          <div style={{ height: 12, borderRadius: 4, background: 'var(--surface-2)', marginBottom: 4, width: 36 }} />
          <div style={{ height: 8, borderRadius: 3, background: 'var(--surface)', width: 28 }} />
        </div>
        <div style={{ flex: 1 }} />
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'var(--text-faint)' }}>
          <div className="spinner" style={{ width: 12, height: 12, borderWidth: 1.5 }} />
          Analisando...
        </div>
      </div>
    </div>
  )

  return (
    <div
      className={`match-row${isReady ? ' analyzed' : ''}${isLiveSoon ? ' live-soon' : ''}`}
      style={{ padding: '11px 14px', marginBottom: 4, cursor: 'pointer' }}
      onClick={() => onOpen(jogo.fixture_id, jogo)}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 40, flexShrink: 0 }}>
          <span style={{ fontSize: 12, color: 'var(--text-secondary)', fontWeight: 700, lineHeight: 1, letterSpacing: '-0.01em' }}>
            {jogo.horario_brt}
          </span>
          {countdown && (
            <span style={{ fontSize: 9, color: isLiveSoon ? 'var(--red)' : 'var(--text-faint)', marginTop: 3, whiteSpace: 'nowrap', fontWeight: 600 }}>
              {countdown}
            </span>
          )}
          {isReady && (
            jogo.fixture_metadata?.lineup_confirmado
              ? <span style={{ fontSize: 8, color: 'var(--green)', marginTop: 2, fontWeight: 600 }}>✅</span>
              : null
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flex: 1, minWidth: 0, overflow: 'hidden' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5, flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <TeamLogo logo={jogo.time_casa?.logo} name={jogo.time_casa?.nome} size={22} />
              <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 110 }}>
                {jogo.time_casa?.nome}
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <TeamLogo logo={jogo.time_fora?.logo} name={jogo.time_fora?.nome} size={22} />
              <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 110 }}>
                {jogo.time_fora?.nome}
              </span>
            </div>
          </div>
        </div>

        {(forma.length > 0 || formaFora.length > 0) && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5, flexShrink: 0 }}>
            {forma.length > 0 && <FormDots forma={forma} />}
            {formaFora.length > 0 && <FormDots forma={formaFora} />}
          </div>
        )}

        {isReady && jogo.best_palpites?.length > 0 && (
          <div style={{ flexShrink: 0 }}>
            <ProbBar palpites={jogo.best_palpites} />
          </div>
        )}

        <div style={{ display: 'flex', alignItems: 'center', gap: 5, flexShrink: 0 }}>
          {isLiveSoon && isReady && <span className="chip chip-red" style={{ fontSize: 9 }}>🔴</span>}
          {featured && !isLiveSoon && <span className="chip chip-amber" style={{ fontSize: 9 }}>⭐</span>}
          {isReady && topPick && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 3,
              background: 'var(--accent-dim)', border: '1px solid var(--accent-border)',
              borderRadius: 'var(--radius-sm)', padding: '3px 7px', maxWidth: 100,
            }}>
              <span style={{ fontSize: 10 }}>{MERCADO_EMOJI[topPick.mercado] || '📊'}</span>
              <span style={{
                fontSize: 10, fontWeight: 700,
                color: (topPick.confianca || 0) >= 7 ? 'var(--green-light)' : 'var(--amber-light)',
                whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 60,
              }}>{topPick.tipo}</span>
              {topPick.probabilidade != null && (
                <span style={{ fontSize: 9, color: 'var(--text-faint)' }}>{Number(topPick.probabilidade).toFixed(0)}%</span>
              )}
            </div>
          )}
          {isReady && <span className="badge badge-green" style={{ fontSize: 9, padding: '1px 6px' }}>✓</span>}
          {!isReady && !isProcessing && (
            <button onClick={handleAnalyze} className="pill" style={{ fontSize: 11, padding: '3px 9px', color: 'var(--accent-light)', background: 'var(--accent-dim)', borderColor: 'var(--accent-border)' }}>
              Analisar →
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

function LeagueSection({ liga, jogos, onOpen }) {
  const [open, setOpen] = useState(true)
  return (
    <div style={{ marginBottom: 2 }}>
      <button className="league-header" onClick={() => setOpen(o => !o)} style={{ marginBottom: open ? 2 : 0 }}>
        {liga.logo && <img src={liga.logo} alt="" style={{ width: 16, height: 16, objectFit: 'contain', flexShrink: 0 }} onError={e => e.target.style.display='none'} />}
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)' }}>{liga.nome}</span>
        <span style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--text-faint)', fontWeight: 500 }}>
          {jogos.length} {open ? '▴' : '▾'}
        </span>
      </button>
      {open && (
        <div style={{ paddingLeft: 2 }}>
          {jogos.map(j => <MatchRow key={j.fixture_id} jogo={j} onOpen={onOpen} compact />)}
        </div>
      )}
    </div>
  )
}

function CountrySection({ pais, ligas, onOpen }) {
  const [open, setOpen] = useState(true)
  const totalJogos = ligas.reduce((acc, l) => acc + l.jogos.length, 0)
  const bandeira = ligas[0]?.liga?.bandeira || ''
  return (
    <div style={{ marginBottom: 8 }}>
      <button className="country-header" onClick={() => setOpen(o => !o)} style={{ marginBottom: open ? 6 : 0 }}>
        {bandeira && <img src={bandeira} alt="" style={{ width: 18, height: 13, objectFit: 'cover', borderRadius: 2, flexShrink: 0 }} onError={e => e.target.style.display='none'} />}
        <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.01em' }}>{pais}</span>
        <span style={{ fontSize: 11, color: 'var(--text-faint)', fontWeight: 500 }}>
          {ligas.length} liga{ligas.length !== 1 ? 's' : ''} · {totalJogos} jogo{totalJogos !== 1 ? 's' : ''}
        </span>
        <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-faint)' }}>{open ? '▴' : '▾'}</span>
      </button>
      {open && (
        <div style={{ paddingLeft: 6 }}>
          {ligas.map(g => <LeagueSection key={g.liga.id} liga={g.liga} jogos={g.jogos} onOpen={onOpen} />)}
        </div>
      )}
    </div>
  )
}

function AutoRefreshTimer({ secondsLeft }) {
  const mins = Math.floor(secondsLeft / 60); const secs = secondsLeft % 60
  return <span style={{ fontSize: 11, color: 'var(--text-faint)', fontVariantNumeric: 'tabular-nums' }}>
    {mins}:{String(secs).padStart(2, '0')}
  </span>
}

function FilterPanel({ filters, onChange, ligas }) {
  const [open, setOpen] = useState(false)
  const hasActive = filters.confiancaMin > 60 || filters.mercados.length > 0 || filters.ligaIds.length > 0 || filters.sort !== 'horario' || filters.apenasAnalisados

  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
        <button onClick={() => setOpen(o => !o)} className={`pill${hasActive ? ' pill-active' : ''}`} style={{ gap: 6 }}>
          <span style={{ fontSize: 12 }}>⚙️</span>
          <span>Filtros</span>
          {hasActive && (
            <span style={{
              fontSize: 9, background: 'var(--accent)', color: '#fff',
              borderRadius: '50%', width: 14, height: 14,
              display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800,
            }}>!</span>
          )}
          <span style={{ fontSize: 10 }}>{open ? '▴' : '▾'}</span>
        </button>
        {[{ v: 'horario', l: 'Horário' }, { v: 'confianca', l: 'Confiança' }, { v: 'score', l: 'Relevância' }].map(({ v, l }) => (
          <button key={v} onClick={() => onChange({ ...filters, sort: v })} className={`pill${filters.sort === v ? ' pill-active' : ''}`} style={{ fontSize: 11, padding: '4px 10px' }}>
            {l}
          </button>
        ))}
        <button onClick={() => onChange({ ...filters, apenasAnalisados: !filters.apenasAnalisados })}
          className={`pill${filters.apenasAnalisados ? ' pill-active' : ''}`}
          style={{ fontSize: 11, padding: '4px 10px' }}>
          ✓ Analisados
        </button>
        {hasActive && (
          <button onClick={() => onChange({ confiancaMin: 60, mercados: [], ligaIds: [], sort: 'horario', apenasAnalisados: false })}
            style={{ fontSize: 11, padding: '4px 10px', color: 'var(--red)', background: 'var(--red-dim)', border: '1px solid var(--red-border)', borderRadius: 'var(--radius-sm)', cursor: 'pointer' }}>
            ✕ Limpar
          </button>
        )}
      </div>

      {open && (
        <div className="panel" style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              Confiança mínima <span style={{ color: 'var(--accent-light)', textTransform: 'none', letterSpacing: 0, fontWeight: 800 }}>{filters.confiancaMin}%</span>
            </div>
            <input type="range" min="60" max="95" step="5" value={filters.confiancaMin} onChange={e => onChange({ ...filters, confiancaMin: Number(e.target.value) })} style={{ width: '100%', accentColor: 'var(--accent)' }} />
          </div>

          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Mercados</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
              {MERCADOS_DISPONIVEIS.map(m => {
                const on = filters.mercados.includes(m)
                return (
                  <button key={m} onClick={() => onChange({ ...filters, mercados: on ? filters.mercados.filter(x => x !== m) : [...filters.mercados, m] })}
                    className={`pill${on ? ' pill-active' : ''}`} style={{ fontSize: 11, padding: '4px 10px' }}>
                    {m}
                  </button>
                )
              })}
            </div>
          </div>

          {ligas.length > 0 && (
            <div>
              <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Ligas</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                {ligas.slice(0, 16).map(l => {
                  const on = filters.ligaIds.includes(l.id)
                  return (
                    <button key={l.id} onClick={() => onChange({ ...filters, ligaIds: on ? filters.ligaIds.filter(x => x !== l.id) : [...filters.ligaIds, l.id] })}
                      className={`pill${on ? ' pill-active' : ''}`} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, padding: '4px 8px' }}>
                      {l.logo && <img src={l.logo} alt="" style={{ width: 13, height: 13, objectFit: 'contain' }} onError={e => e.target.style.display='none'} />}
                      {l.nome}
                    </button>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function matchesSearch(jogo, q) {
  const lq = q.toLowerCase().trim()
  if (!lq) return true
  return jogo.time_casa?.nome?.toLowerCase().includes(lq) || jogo.time_fora?.nome?.toLowerCase().includes(lq) || jogo.liga?.nome?.toLowerCase().includes(lq) || jogo.liga?.pais?.toLowerCase().includes(lq)
}

function matchesFilters(jogo, filters) {
  if (filters.apenasAnalisados && !jogo.tem_analise) return false
  if (filters.ligaIds.length > 0 && !filters.ligaIds.includes(jogo.liga?.id)) return false
  const isActive = filters.confiancaMin > 60 || filters.mercados.length > 0
  if (isActive) {
    if (!jogo.tem_analise || !jogo.best_palpites?.length) return false
    if (filters.mercados.length > 0 && !filters.mercados.some(m => (jogo.best_palpites || []).some(p => p.mercado === m))) return false
    if (filters.confiancaMin > 60 && !(jogo.best_palpites || []).some(p => ((p.confianca || 0) / 10 * 100) >= filters.confiancaMin)) return false
  }
  return true
}

function sortJogos(jogos, sort) {
  if (sort === 'confianca') return [...jogos].sort((a, b) => Math.max(0, ...(b.best_palpites || []).map(p => p.confianca || 0)) - Math.max(0, ...(a.best_palpites || []).map(p => p.confianca || 0)))
  if (sort === 'score') return [...jogos].sort((a, b) => (b.score_destaque || 0) - (a.score_destaque || 0))
  return [...jogos].sort((a, b) => (a.horario_brt || '').localeCompare(b.horario_brt || ''))
}

export default function Home() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [countdown, setCountdown] = useState(AUTO_REFRESH_SECS)
  const [search, setSearch] = useState('')
  const [filters, setFilters] = useState({ confiancaMin: 60, mercados: [], ligaIds: [], sort: 'horario', apenasAnalisados: false })
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [drawerFixtureId, setDrawerFixtureId] = useState(null)
  const [drawerJogo, setDrawerJogo] = useState(null)
  const timerRef = useRef(null); const countRef = useRef(AUTO_REFRESH_SECS)

  const fetchJogos = useCallback(async () => {
    setLoading(true); setError(null)
    try { const r = await fetch('/api/jogos/hoje'); if (!r.ok) throw new Error('Erro'); const d = await r.json(); setData(d) }
    catch (e) { setError(e.message) } finally { setLoading(false) }
  }, [])

  const handleRefresh = useCallback(() => {
    countRef.current = AUTO_REFRESH_SECS; setCountdown(AUTO_REFRESH_SECS); fetchJogos()
  }, [fetchJogos])

  useEffect(() => { fetchJogos() }, [fetchJogos])

  useEffect(() => {
    timerRef.current = setInterval(() => {
      countRef.current -= 1; setCountdown(countRef.current)
      if (countRef.current <= 0) { countRef.current = AUTO_REFRESH_SECS; setCountdown(AUTO_REFRESH_SECS); fetchJogos() }
    }, 1000)
    return () => clearInterval(timerRef.current)
  }, [fetchJogos])

  const openDrawer = useCallback((fixtureId, jogo) => {
    setDrawerFixtureId(fixtureId)
    setDrawerJogo(jogo)
    setDrawerOpen(true)
  }, [])

  const closeDrawer = useCallback(() => {
    setDrawerOpen(false)
  }, [])

  const allJogos = useMemo(() => {
    if (!data?.por_pais) return []
    return data.por_pais.flatMap(p => p.ligas.flatMap(l => l.jogos))
  }, [data])

  const allLigas = useMemo(() => {
    if (!data?.por_pais) return []
    const seen = new Set(); const out = []
    data.por_pais.forEach(p => p.ligas.forEach(l => { if (!seen.has(l.liga.id)) { seen.add(l.liga.id); out.push(l.liga) } }))
    return out
  }, [data])

  const filteredPrincipais = useMemo(() => {
    if (!data?.principais) return []
    const q = search.trim()
    return sortJogos(data.principais.filter(j => matchesSearch(j, q) && matchesFilters(j, filters)), filters.sort).slice(0, 8)
  }, [data, search, filters])

  const filteredPorPais = useMemo(() => {
    if (!data?.por_pais) return []
    const q = search.trim()
    return data.por_pais.map(p => ({
      ...p,
      ligas: p.ligas.map(l => ({ ...l, jogos: sortJogos(l.jogos.filter(j => matchesSearch(j, q) && matchesFilters(j, filters)), filters.sort) })).filter(l => l.jogos.length > 0),
    })).filter(p => p.ligas.length > 0)
  }, [data, search, filters])

  const filteredJogos = useMemo(() => {
    const q = search.trim()
    return sortJogos(allJogos.filter(j => matchesSearch(j, q) && matchesFilters(j, filters)), filters.sort)
  }, [allJogos, search, filters])

  if (loading) return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 320, gap: 14, paddingTop: 60 }}>
      <div className="spinner" style={{ width: 40, height: 40 }} />
      <p style={{ color: 'var(--text-muted)', fontSize: 14 }}>Carregando jogos de hoje...</p>
    </div>
  )

  if (error) return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 320, gap: 12, paddingTop: 60 }}>
      <div style={{ fontSize: 36 }}>⚠️</div>
      <p style={{ color: 'var(--red)', fontSize: 14 }}>Erro ao conectar com a API</p>
      <p style={{ color: 'var(--text-muted)', fontSize: 12 }}>{error}</p>
      <button onClick={handleRefresh} className="pill pill-active" style={{ marginTop: 8, padding: '8px 20px', fontSize: 13 }}>Tentar novamente</button>
    </div>
  )

  const total = data?.total || 0
  const totalPaises = data?.por_pais?.length || 0
  const totalAnalisados = allJogos.filter(j => j.tem_analise).length
  const totalFiltrados = filteredJogos.length

  const clearAll = () => { setSearch(''); setFilters({ confiancaMin: 60, mercados: [], ligaIds: [], sort: 'horario', apenasAnalisados: false }) }

  return (
    <div style={{ paddingTop: 24 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px,1fr))', gap: 10, marginBottom: 20 }}>
        {[
          { label: 'Jogos Hoje', value: total, sub: `${totalPaises} países` },
          { label: 'Analisados', value: totalAnalisados, sub: `${total > 0 ? ((totalAnalisados/total)*100).toFixed(0) : 0}% do total`, color: totalAnalisados > 0 ? 'var(--green-light)' : undefined },
          { label: 'Em Exibição', value: totalFiltrados, sub: filters.sort === 'horario' ? 'ord. horário' : filters.sort === 'confianca' ? 'ord. confiança' : 'ord. relevância' },
        ].map(({ label, value, sub, color }) => (
          <div key={label} className="stat-box" style={{ padding: '10px 14px' }}>
            <div className="stat-label">{label}</div>
            <div className="stat-value" style={{ fontSize: 20, ...(color ? { color } : {}) }}>{value}</div>
            <div className="stat-sub">{sub}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <div style={{ position: 'relative', flex: 1 }}>
          <span style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', fontSize: 14, color: 'var(--text-faint)', pointerEvents: 'none' }}>🔍</span>
          <input type="text" value={search} onChange={e => setSearch(e.target.value)}
            className="token-input" placeholder="Buscar por time, liga ou país..."
            style={{ paddingLeft: 36 }}
          />
          {search && (
            <button onClick={() => setSearch('')} style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', color: 'var(--text-faint)', cursor: 'pointer', fontSize: 15, lineHeight: 1, padding: 2 }}>✕</button>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
          <AutoRefreshTimer secondsLeft={countdown} />
          <button onClick={handleRefresh} className="pill" style={{ fontSize: 11, padding: '5px 10px' }}>↻</button>
        </div>
      </div>

      <FilterPanel filters={filters} onChange={setFilters} ligas={allLigas} />

      {total === 0 ? (
        <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--text-muted)', background: 'var(--surface)', border: '1px dashed var(--border)', borderRadius: 'var(--radius)' }}>
          <div style={{ fontSize: 44, marginBottom: 12 }}>📭</div>
          <p style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-secondary)' }}>Sem jogos disponíveis</p>
          <p style={{ fontSize: 13, marginTop: 6 }}>Nenhuma partida encontrada nas ligas monitoradas.</p>
        </div>
      ) : totalFiltrados === 0 ? (
        <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--text-muted)', background: 'var(--surface)', border: '1px dashed var(--border)', borderRadius: 'var(--radius)' }}>
          <div style={{ fontSize: 36, marginBottom: 12 }}>🔍</div>
          <p style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-secondary)' }}>Nenhum resultado</p>
          <p style={{ fontSize: 13, marginTop: 6 }}>Ajuste os filtros ou a busca para ver mais jogos.</p>
          <button onClick={clearAll} className="pill pill-active" style={{ marginTop: 16, padding: '7px 20px', fontSize: 13 }}>Limpar tudo</button>
        </div>
      ) : (
        <>
          {filteredPrincipais.length > 0 && (
            <section style={{ marginBottom: 24 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 10 }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.01em' }}>⭐ Principais Jogos</span>
                <span className="chip chip-amber">Top {filteredPrincipais.length}</span>
              </div>
              {filteredPrincipais.map(j => <MatchRow key={j.fixture_id} jogo={j} onOpen={openDrawer} featured />)}
            </section>
          )}

          {filteredPorPais.length > 0 && (
            <section>
              <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 10 }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.01em' }}>🌍 Todos os Jogos</span>
                <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>por país e liga</span>
              </div>
              {filteredPorPais.map(({ pais, ligas }) => <CountrySection key={pais} pais={pais} ligas={ligas} onOpen={openDrawer} />)}
            </section>
          )}
        </>
      )}

      {drawerOpen && drawerFixtureId && (
        <MatchDrawer fixtureId={drawerFixtureId} jogo={drawerJogo} onClose={closeDrawer} />
      )}
    </div>
  )
}
