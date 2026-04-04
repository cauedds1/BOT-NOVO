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

const SCRIPT_LABELS = {
  'high_scoring': { label: 'Alto Placar', color: '#f59e0b', icon: '⚡' },
  'defensive': { label: 'Defensivo', color: '#6366f1', icon: '🛡️' },
  'balanced': { label: 'Equilibrado', color: '#22c55e', icon: '⚖️' },
  'home_dominant': { label: 'Mandante Dom.', color: '#818cf8', icon: '🏠' },
  'away_upset': { label: 'Visitante Perigoso', color: '#f87171', icon: '⚠️' },
  'cup_game': { label: 'Jogo de Copa', color: '#8b5cf6', icon: '🏆' },
  'derby': { label: 'Derby/Clássico', color: '#ec4899', icon: '🔥' },
}

function useCountdown(isoDate) {
  const [diff, setDiff] = useState(null)

  useEffect(() => {
    if (!isoDate) return
    const update = () => {
      const now = Date.now()
      const kickoff = new Date(isoDate).getTime()
      const delta = kickoff - now
      setDiff(delta)
    }
    update()
    const t = setInterval(update, 1000)
    return () => clearInterval(t)
  }, [isoDate])

  if (diff === null) return null
  if (diff <= 0) return 'AO VIVO'
  const h = Math.floor(diff / 3600000)
  const m = Math.floor((diff % 3600000) / 60000)
  const s = Math.floor((diff % 60000) / 1000)
  if (h > 23) return null
  return `${h > 0 ? `${h}h ` : ''}${String(m).padStart(2, '0')}m ${String(s).padStart(2, '0')}s`
}

function TeamLogo({ logo, name, size = 44 }) {
  const [err, setErr] = useState(false)
  if (!logo || err) {
    return (
      <div style={{
        width: size, height: size, borderRadius: '50%',
        background: 'rgba(99,102,241,0.2)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: size * 0.4, color: '#818cf8', fontWeight: 700,
      }}>
        {name?.[0] || '?'}
      </div>
    )
  }
  return (
    <img src={logo} alt={name}
      style={{ width: size, height: size, objectFit: 'contain' }}
      onError={() => setErr(true)}
    />
  )
}

function ConfidenceBar({ value, max = 10 }) {
  const pct = Math.min(100, (value / max) * 100)
  let color = '#ef4444'
  if (value >= 7) color = '#22c55e'
  else if (value >= 5.5) color = '#eab308'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1 }}>
      <div className="confidence-bar-track" style={{ flex: 1 }}>
        <div className="confidence-bar-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span style={{ fontSize: 12, fontWeight: 700, color, minWidth: 32, textAlign: 'right' }}>
        {value?.toFixed(1)}
      </span>
    </div>
  )
}

function OddsTrafficLight({ odd, probabilidade }) {
  if (!odd || !probabilidade) return null
  const impliedProb = (1 / odd) * 100
  const edge = probabilidade - impliedProb

  let color, label, bg
  if (edge >= 5) {
    color = '#22c55e'; label = 'Valor'; bg = 'rgba(34,197,94,0.12)'
  } else if (edge >= -3) {
    color = '#eab308'; label = 'Justo'; bg = 'rgba(234,179,8,0.12)'
  } else {
    color = '#f87171'; label = 'Caro'; bg = 'rgba(239,68,68,0.12)'
  }

  return (
    <span style={{
      fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 6,
      background: bg, color, border: `1px solid ${color}33`,
    }}>
      {label} {edge >= 0 ? '+' : ''}{edge.toFixed(1)}%
    </span>
  )
}

function PredictionRow({ palpite, rank }) {
  const conf = palpite.confianca || 0
  let badgeCls = 'badge badge-red'
  if (conf >= 7) badgeCls = 'badge badge-green'
  else if (conf >= 5.5) badgeCls = 'badge badge-yellow'

  return (
    <div style={{
      padding: '12px 0',
      borderBottom: '1px solid rgba(255,255,255,0.04)',
      display: 'flex', flexDirection: 'column', gap: 8,
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, flexWrap: 'wrap' }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 4 }}>
            {rank === 0 && (
              <span style={{
                fontSize: 10, background: 'rgba(99,102,241,0.2)', color: '#818cf8',
                border: '1px solid rgba(99,102,241,0.4)', borderRadius: 4, padding: '1px 6px', fontWeight: 700,
              }}>
                #1
              </span>
            )}
            <span style={{ fontSize: 13, fontWeight: 600, color: '#f1f5f9' }}>{palpite.tipo}</span>
            {palpite.periodo && palpite.periodo !== 'FT' && (
              <span style={{
                fontSize: 10, color: '#64748b', background: 'rgba(255,255,255,0.05)',
                borderRadius: 4, padding: '1px 5px',
              }}>
                {palpite.periodo}
              </span>
            )}
            {palpite.odd && (
              <span style={{ fontSize: 12, color: '#818cf8', fontWeight: 700, marginLeft: 'auto' }}>
                @{typeof palpite.odd === 'number' ? palpite.odd.toFixed(2) : palpite.odd}
              </span>
            )}
            <OddsTrafficLight odd={palpite.odd} probabilidade={palpite.probabilidade} />
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
              <span style={{ fontSize: 11, color: '#475569', minWidth: 60 }}>Prob. Bot</span>
              <ConfidenceBar value={palpite.probabilidade} max={100} />
              <span style={{ fontSize: 11, color: '#64748b', marginLeft: -20 }}>%</span>
            </div>
          )}

          {palpite.confidence_breakdown && Object.keys(palpite.confidence_breakdown).length > 0 && (
            <ConfidenceBreakdown bd={palpite.confidence_breakdown} />
          )}
        </div>
      </div>
    </div>
  )
}

function ConfidenceBreakdown({ bd }) {
  const [open, setOpen] = useState(false)
  const keys = Object.keys(bd).filter(k => k !== 'confianca_final' && k !== 'modificador_historico')
  if (keys.length === 0) return null
  return (
    <div style={{ marginTop: 6 }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          background: 'none', border: 'none', cursor: 'pointer',
          fontSize: 10, color: '#475569', padding: 0,
        }}
      >
        {open ? '▲' : '▼'} Detalhes de confiança
      </button>
      {open && (
        <div style={{
          marginTop: 6, padding: '8px 10px', borderRadius: 8,
          background: 'rgba(99,102,241,0.04)', border: '1px solid rgba(99,102,241,0.1)',
          display: 'flex', flexWrap: 'wrap', gap: '4px 16px',
        }}>
          {keys.map(k => (
            <div key={k} style={{ fontSize: 10, color: '#64748b' }}>
              <span style={{ color: '#475569' }}>{k.replace(/_/g, ' ')}: </span>
              <span style={{ color: '#818cf8', fontWeight: 600 }}>
                {typeof bd[k] === 'number' ? bd[k].toFixed(2) : String(bd[k])}
              </span>
            </div>
          ))}
          {bd.modificador_historico !== undefined && (
            <div style={{ fontSize: 10, color: '#64748b' }}>
              <span style={{ color: '#475569' }}>ajuste histórico: </span>
              <span style={{ color: bd.modificador_historico >= 0 ? '#22c55e' : '#f87171', fontWeight: 600 }}>
                {bd.modificador_historico >= 0 ? '+' : ''}{Number(bd.modificador_historico).toFixed(2)}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function MarketCard({ mercado, minConfianca }) {
  const [open, setOpen] = useState(true)
  const icon = MARKET_ICONS[mercado.mercado] || '📊'
  const palpitesFiltrados = mercado.palpites.filter(p => (p.confianca || 0) >= minConfianca)
  const topConf = palpitesFiltrados[0]?.confianca || 0

  if (palpitesFiltrados.length === 0) return null

  return (
    <div className="card" style={{ marginBottom: 14, overflow: 'hidden' }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: 10,
          padding: '12px 16px', cursor: 'pointer', background: 'transparent', border: 'none',
          borderBottom: open ? '1px solid rgba(255,255,255,0.05)' : 'none',
        }}
      >
        <span style={{ fontSize: 18 }}>{icon}</span>
        <span style={{ fontSize: 14, fontWeight: 700, color: '#e2e8f0' }}>{mercado.mercado}</span>
        <span style={{ fontSize: 11, color: '#475569' }}>
          {palpitesFiltrados.length} palpite{palpitesFiltrados.length !== 1 ? 's' : ''}
        </span>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
          {topConf >= 7 && <span className="badge badge-green" style={{ fontSize: 10 }}>⭐ Top</span>}
          <span style={{ fontSize: 12, color: '#475569' }}>{open ? '▲' : '▼'}</span>
        </div>
      </button>

      {open && (
        <div style={{ padding: '0 16px 4px' }}>
          {palpitesFiltrados.map((p, i) => (
            <PredictionRow key={i} palpite={p} rank={i} />
          ))}
        </div>
      )}
    </div>
  )
}

function FormaRecente({ forma, label }) {
  if (!forma || forma.length === 0) return null

  const getColor = (r) => {
    const upper = String(r).toUpperCase()
    if (upper === 'W' || upper === 'V') return '#22c55e'
    if (upper === 'D' || upper === 'E') return '#eab308'
    return '#f87171'
  }

  const getLabel = (r) => {
    const upper = String(r).toUpperCase()
    if (upper === 'W') return 'V'
    if (upper === 'L') return 'D'
    return upper
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
      <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600 }}>{label}</div>
      <div style={{ display: 'flex', gap: 5 }}>
        {forma.slice(0, 5).map((r, i) => (
          <div key={i} style={{
            width: 28, height: 28, borderRadius: 8,
            background: `${getColor(r)}22`,
            border: `1.5px solid ${getColor(r)}55`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 11, fontWeight: 700, color: getColor(r),
          }}>
            {getLabel(r)}
          </div>
        ))}
      </div>
    </div>
  )
}

function H2HSection({ h2h, timeCasa, timeFora }) {
  if (!h2h || h2h.length === 0) return null

  return (
    <div className="card" style={{ padding: '16px 18px', marginBottom: 14 }}>
      <div style={{ fontSize: 14, fontWeight: 700, color: '#c7d2fe', marginBottom: 14 }}>
        ⚔️ Confrontos Diretos
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {h2h.map((jogo, i) => {
          const dataParts = (jogo.data || jogo.date || '')
          const placarCasa = jogo.gols_casa ?? jogo.home_goals ?? jogo.score_home ?? '?'
          const placarFora = jogo.gols_fora ?? jogo.away_goals ?? jogo.score_away ?? '?'
          const homeName = jogo.time_casa || jogo.home_team || timeCasa
          const awayName = jogo.time_fora || jogo.away_team || timeFora

          return (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '8px 10px', borderRadius: 8,
              background: 'rgba(255,255,255,0.02)',
              border: '1px solid rgba(99,102,241,0.08)',
            }}>
              <span style={{ fontSize: 11, color: '#475569', minWidth: 36 }}>
                {dataParts.slice(0, 4) || '?'}
              </span>
              <span style={{ fontSize: 12, color: '#94a3b8', flex: 1, textAlign: 'right' }}>{homeName}</span>
              <span style={{
                fontSize: 13, fontWeight: 700, color: '#e2e8f0',
                background: 'rgba(99,102,241,0.1)', borderRadius: 6,
                padding: '2px 10px', minWidth: 52, textAlign: 'center',
              }}>
                {placarCasa} – {placarFora}
              </span>
              <span style={{ fontSize: 12, color: '#94a3b8', flex: 1 }}>{awayName}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function StatsComparativas({ stats, timeCasa, timeFora }) {
  if (!stats || Object.keys(stats).length === 0) return null

  const rows = [
    { key: 'media_gols_marcados', label: 'Gols Marcados (méd.)' },
    { key: 'media_gols_sofridos', label: 'Gols Sofridos (méd.)' },
    { key: 'media_cantos', label: 'Escanteios (méd.)' },
    { key: 'media_finalizacoes', label: 'Finalizações (méd.)' },
    { key: 'avg_shots', label: 'Chutes (méd.)' },
    { key: 'posse_media', label: 'Posse de Bola (méd.)' },
    { key: 'avg_possession', label: 'Posse (méd.)' },
  ].filter(r => stats[`${r.key}_casa`] !== undefined || stats[`${r.key}_fora`] !== undefined)

  if (rows.length === 0) return null

  return (
    <div className="card" style={{ padding: '16px 18px', marginBottom: 14 }}>
      <div style={{ fontSize: 14, fontWeight: 700, color: '#c7d2fe', marginBottom: 14 }}>
        📊 Estatísticas Comparativas
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', alignItems: 'center', gap: '8px 12px' }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: '#818cf8', textAlign: 'right', paddingBottom: 4 }}>
          {timeCasa}
        </div>
        <div />
        <div style={{ fontSize: 11, fontWeight: 700, color: '#818cf8', paddingBottom: 4 }}>
          {timeFora}
        </div>

        {rows.map(r => {
          const vCasa = stats[`${r.key}_casa`]
          const vFora = stats[`${r.key}_fora`]
          const casaWins = vCasa !== undefined && vFora !== undefined && vCasa > vFora
          const foraWins = vCasa !== undefined && vFora !== undefined && vFora > vCasa

          return [
            <div key={`c-${r.key}`} style={{
              fontSize: 14, fontWeight: 700, textAlign: 'right',
              color: casaWins ? '#22c55e' : '#e2e8f0',
            }}>
              {vCasa !== undefined ? vCasa : '—'}
            </div>,
            <div key={`l-${r.key}`} style={{
              fontSize: 10, color: '#475569', textAlign: 'center',
              padding: '2px 6px', background: 'rgba(255,255,255,0.03)', borderRadius: 4,
              whiteSpace: 'nowrap',
            }}>
              {r.label}
            </div>,
            <div key={`f-${r.key}`} style={{
              fontSize: 14, fontWeight: 700,
              color: foraWins ? '#22c55e' : '#e2e8f0',
            }}>
              {vFora !== undefined ? vFora : '—'}
            </div>,
          ]
        })}
      </div>
    </div>
  )
}

function ScriptTaticoCard({ script }) {
  if (!script) return null
  const info = SCRIPT_LABELS[script] || { label: script, color: '#818cf8', icon: '📋' }

  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 8,
      padding: '6px 14px', borderRadius: 10,
      background: `${info.color}12`,
      border: `1px solid ${info.color}30`,
    }}>
      <span style={{ fontSize: 16 }}>{info.icon}</span>
      <div>
        <div style={{ fontSize: 10, color: '#64748b', fontWeight: 600 }}>Script Tático</div>
        <div style={{ fontSize: 13, fontWeight: 700, color: info.color }}>{info.label}</div>
      </div>
    </div>
  )
}

function TabelaClassificacao({ classificacao, timeCasa, timeFora }) {
  if (!classificacao || classificacao.length === 0) return null

  const relevantes = classificacao.filter(t =>
    t.team?.name === timeCasa || t.team?.name === timeFora ||
    (t.rank && t.rank <= 5)
  ).slice(0, 8)

  if (relevantes.length === 0) return null

  return (
    <div className="card" style={{ padding: '16px 18px', marginBottom: 14 }}>
      <div style={{ fontSize: 14, fontWeight: 700, color: '#c7d2fe', marginBottom: 14 }}>
        🏆 Classificação da Liga
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr>
              {['Pos', 'Time', 'J', 'V', 'E', 'D', 'Pts'].map(h => (
                <th key={h} style={{
                  padding: '4px 8px', textAlign: h === 'Time' ? 'left' : 'center',
                  color: '#64748b', fontWeight: 600,
                  borderBottom: '1px solid rgba(99,102,241,0.1)',
                }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {relevantes.map((t, i) => {
              const isHighlighted = t.team?.name === timeCasa || t.team?.name === timeFora
              return (
                <tr key={i} style={{
                  background: isHighlighted ? 'rgba(99,102,241,0.08)' : 'transparent',
                }}>
                  <td style={{ padding: '6px 8px', textAlign: 'center', color: '#64748b', fontWeight: 600 }}>
                    {t.rank}
                  </td>
                  <td style={{ padding: '6px 8px', display: 'flex', alignItems: 'center', gap: 6 }}>
                    {t.team?.logo && (
                      <img src={t.team.logo} alt="" style={{ width: 16, height: 16, objectFit: 'contain' }}
                        onError={e => e.target.style.display = 'none'} />
                    )}
                    <span style={{ color: isHighlighted ? '#f1f5f9' : '#94a3b8', fontWeight: isHighlighted ? 700 : 400 }}>
                      {t.team?.name || ''}
                    </span>
                  </td>
                  <td style={{ padding: '6px 8px', textAlign: 'center', color: '#64748b' }}>{t.all?.played ?? '—'}</td>
                  <td style={{ padding: '6px 8px', textAlign: 'center', color: '#22c55e' }}>{t.all?.win ?? '—'}</td>
                  <td style={{ padding: '6px 8px', textAlign: 'center', color: '#eab308' }}>{t.all?.draw ?? '—'}</td>
                  <td style={{ padding: '6px 8px', textAlign: 'center', color: '#f87171' }}>{t.all?.lose ?? '—'}</td>
                  <td style={{ padding: '6px 8px', textAlign: 'center', color: '#f1f5f9', fontWeight: 700 }}>
                    {t.points ?? '—'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function SkeletonCard({ height = 80 }) {
  return (
    <div className="skeleton-card" style={{ height, borderRadius: 12, marginBottom: 14 }} />
  )
}

export default function MatchDetail() {
  const { fixtureId } = useParams()
  const [analise, setAnalise] = useState(null)
  const [loading, setLoading] = useState(true)
  const [processing, setProcessing] = useState(false)
  const [error, setError] = useState(null)
  const [jogoInfo, setJogoInfo] = useState(null)
  const [minConfianca, setMinConfianca] = useState(0)
  const [filtroMercado, setFiltroMercado] = useState('Todos')
  const [activeTab, setActiveTab] = useState('palpites')

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
    } catch {
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

  const countdown = useCountdown(jogoInfo?.data_iso || analise?.data_jogo_iso)
  const isPreMatch = countdown && countdown !== 'AO VIVO'
  const isLast30 = isPreMatch && (() => {
    const ms = new Date(jogoInfo?.data_iso || analise?.data_jogo_iso || 0).getTime() - Date.now()
    return ms > 0 && ms < 30 * 60 * 1000
  })()

  if (loading) {
    return (
      <div style={{ paddingTop: 24 }}>
        <div style={{ height: 18, width: 120, borderRadius: 6, background: 'rgba(99,102,241,0.1)', marginBottom: 24 }} />
        <SkeletonCard height={180} />
        <SkeletonCard height={60} />
        <SkeletonCard />
        <SkeletonCard />
        <SkeletonCard />
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
        <div style={{ display: 'flex', gap: 6, marginTop: 8, flexWrap: 'wrap', justifyContent: 'center' }}>
          {['Estatísticas', 'Odds', 'H2H', 'Analistas', 'Palpites'].map((s, i) => (
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

  const todosMercados = [...(analise.mercados || [])].sort((a, b) => {
    const aMax = Math.max(...(a.palpites || []).map(p => p.confianca || 0))
    const bMax = Math.max(...(b.palpites || []).map(p => p.confianca || 0))
    return bMax - aMax
  })

  const mercadosDisponiveis = ['Todos', ...todosMercados.map(m => m.mercado)]
  const mercadosFiltrados = filtroMercado === 'Todos'
    ? todosMercados
    : todosMercados.filter(m => m.mercado === filtroMercado)

  const topPick = todosMercados[0]?.palpites?.filter(p => (p.confianca || 0) >= minConfianca)[0]
  const topMercado = todosMercados[0]

  const tabs = [
    { id: 'palpites', label: '🎯 Palpites' },
    { id: 'analise', label: '📊 Análise' },
    ...(analise.h2h?.length > 0 ? [{ id: 'h2h', label: '⚔️ H2H' }] : []),
    ...(analise.classificacao?.length > 0 ? [{ id: 'tabela', label: '🏆 Tabela' }] : []),
  ]

  return (
    <div style={{ paddingTop: 24 }}>
      <Link to="/" style={{
        fontSize: 13, color: '#64748b', textDecoration: 'none',
        display: 'inline-flex', alignItems: 'center', gap: 4, marginBottom: 20,
      }}>
        ← Voltar aos jogos
      </Link>

      {/* ── SEÇÃO 1: Hero Card ─────────────────────────────────────────── */}
      <div style={{
        background: 'linear-gradient(135deg, #131729 0%, #1a1d2e 100%)',
        border: '1px solid rgba(99,102,241,0.2)',
        borderRadius: 16, padding: 24, marginBottom: 16,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8, marginBottom: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {jogoInfo?.liga?.logo && (
              <img src={jogoInfo.liga.logo} alt="" style={{ width: 20, height: 20, objectFit: 'contain' }}
                onError={e => e.target.style.display = 'none'} />
            )}
            <span style={{ fontSize: 12, color: '#818cf8', fontWeight: 600 }}>
              {jogoInfo?.liga?.nome || analise.liga}
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            {analise.script_tatico && <ScriptTaticoCard script={analise.script_tatico} />}
            {isLast30 && (
              <span style={{
                fontSize: 11, fontWeight: 700, padding: '4px 10px', borderRadius: 8,
                background: 'rgba(239,68,68,0.15)', color: '#f87171',
                border: '1px solid rgba(239,68,68,0.3)',
                animation: 'pulseDot 1.5s infinite',
              }}>
                🔴 Análise Final
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center justify-center gap-6" style={{ marginBottom: 20 }}>
          <div className="flex flex-col items-center gap-2">
            <TeamLogo logo={jogoInfo?.time_casa?.logo} name={analise.time_casa} />
            <span style={{ fontSize: 14, fontWeight: 700, color: '#f1f5f9', textAlign: 'center', maxWidth: 120 }}>
              {analise.time_casa}
            </span>
            {analise.pos_casa && (
              <span style={{ fontSize: 11, color: '#64748b' }}>#{analise.pos_casa} na tabela</span>
            )}
          </div>

          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 22, fontWeight: 800, color: '#e2e8f0', letterSpacing: '0.1em' }}>VS</div>
            {countdown && (
              <div style={{
                fontSize: countdown === 'AO VIVO' ? 13 : 12,
                color: countdown === 'AO VIVO' ? '#22c55e' : '#818cf8',
                fontWeight: 700, marginTop: 6,
              }}>
                {countdown === 'AO VIVO' ? '🟢 AO VIVO' : `⏱ ${countdown}`}
              </div>
            )}
            {!countdown && jogoInfo?.horario_brt && (
              <div style={{ fontSize: 11, color: '#475569', marginTop: 4 }}>{jogoInfo.horario_brt}</div>
            )}
          </div>

          <div className="flex flex-col items-center gap-2">
            <TeamLogo logo={jogoInfo?.time_fora?.logo} name={analise.time_fora} />
            <span style={{ fontSize: 14, fontWeight: 700, color: '#f1f5f9', textAlign: 'center', maxWidth: 120 }}>
              {analise.time_fora}
            </span>
            {analise.pos_fora && (
              <span style={{ fontSize: 11, color: '#64748b' }}>#{analise.pos_fora} na tabela</span>
            )}
          </div>
        </div>

        {/* Forma recente */}
        {(analise.forma_recente_casa?.length > 0 || analise.forma_recente_fora?.length > 0) && (
          <div style={{ display: 'flex', justifyContent: 'space-around', marginBottom: 20, flexWrap: 'wrap', gap: 12 }}>
            <FormaRecente forma={analise.forma_recente_casa} label="Forma Casa" />
            <div style={{ fontSize: 10, color: '#475569', alignSelf: 'center' }}>ÚLTIMOS 5</div>
            <FormaRecente forma={analise.forma_recente_fora} label="Forma Fora" />
          </div>
        )}

        {/* Stats rápidas */}
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <div style={statBoxStyle}>
            <div style={statLabelStyle}>Palpites</div>
            <div style={statValueStyle}>{analise.total_palpites}</div>
            <div style={statSubStyle}>{analise.mercados?.length || 0} mercados</div>
          </div>
          <div style={statBoxStyle}>
            <div style={statLabelStyle}>Top Confiança</div>
            <div style={{ ...statValueStyle, color: analise.melhor_confianca >= 7 ? '#22c55e' : analise.melhor_confianca >= 5.5 ? '#eab308' : '#f87171' }}>
              {analise.melhor_confianca?.toFixed(1)}/10
            </div>
            <div style={statSubStyle}>score máximo</div>
          </div>
          {topPick && (
            <div style={statBoxStyle}>
              <div style={statLabelStyle}>Top Pick</div>
              <div style={{ ...statValueStyle, fontSize: 14 }}>{topPick.tipo}</div>
              <div style={statSubStyle}>{topMercado?.mercado} · {topPick.confianca?.toFixed(1)}</div>
            </div>
          )}
          {analise.qsc_home !== undefined && analise.qsc_home !== null && (
            <div style={statBoxStyle}>
              <div style={statLabelStyle}>QSC</div>
              <div style={statValueStyle}>{Number(analise.qsc_home).toFixed(1)} × {Number(analise.qsc_away || 0).toFixed(1)}</div>
              <div style={statSubStyle}>qualidade das equipes</div>
            </div>
          )}
        </div>
      </div>

      {/* ── SEÇÃO 2: Tabs de navegação ────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 16, overflowX: 'auto', paddingBottom: 2 }}>
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              padding: '8px 16px', borderRadius: 10, cursor: 'pointer',
              fontSize: 13, fontWeight: 600, whiteSpace: 'nowrap',
              background: activeTab === tab.id ? 'rgba(99,102,241,0.2)' : 'rgba(255,255,255,0.04)',
              color: activeTab === tab.id ? '#818cf8' : '#64748b',
              border: activeTab === tab.id ? '1px solid rgba(99,102,241,0.4)' : '1px solid rgba(255,255,255,0.06)',
              transition: 'all 0.15s ease',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── SEÇÃO 3: Filtros (apenas na tab Palpites) ────────────────── */}
      {activeTab === 'palpites' && (
        <div style={{
          background: 'rgba(255,255,255,0.02)',
          border: '1px solid rgba(99,102,241,0.1)',
          borderRadius: 12, padding: '14px 16px', marginBottom: 16,
        }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'center' }}>
            <div style={{ flex: 1, minWidth: 200 }}>
              <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, marginBottom: 8 }}>
                Confiança mínima: <span style={{ color: '#818cf8' }}>{minConfianca.toFixed(1)}</span>
              </div>
              <input
                type="range" min="0" max="9" step="0.5"
                value={minConfianca}
                onChange={e => setMinConfianca(Number(e.target.value))}
                style={{ width: '100%', accentColor: '#6366f1' }}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: '#475569', marginTop: 2 }}>
                <span>0 (todos)</span><span>5.5 (bom)</span><span>7+ (top)</span><span>9 (elite)</span>
              </div>
            </div>
            <div style={{ minWidth: 160 }}>
              <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, marginBottom: 8 }}>Mercado</div>
              <select
                value={filtroMercado}
                onChange={e => setFiltroMercado(e.target.value)}
                style={{
                  width: '100%', background: 'rgba(255,255,255,0.06)',
                  border: '1px solid rgba(99,102,241,0.2)', borderRadius: 8,
                  color: '#e2e8f0', padding: '6px 10px', fontSize: 13, cursor: 'pointer',
                }}
              >
                {mercadosDisponiveis.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
          </div>
        </div>
      )}

      {/* ── CONTEÚDO POR TAB ─────────────────────────────────────────── */}

      {activeTab === 'palpites' && (
        <>
          {mercadosFiltrados.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px 0', color: '#64748b' }}>
              <div style={{ fontSize: 32, marginBottom: 10 }}>🔍</div>
              <p style={{ fontSize: 14 }}>Nenhum palpite com confiança ≥ {minConfianca.toFixed(1)}</p>
              <button
                onClick={() => { setMinConfianca(0); setFiltroMercado('Todos') }}
                style={{
                  marginTop: 12, fontSize: 12, padding: '6px 16px', borderRadius: 8,
                  background: 'rgba(99,102,241,0.12)', color: '#818cf8',
                  border: '1px solid rgba(99,102,241,0.25)', cursor: 'pointer',
                }}
              >
                Limpar filtros
              </button>
            </div>
          ) : (
            mercadosFiltrados.map((m, i) => (
              <MarketCard key={i} mercado={m} minConfianca={minConfianca} />
            ))
          )}
        </>
      )}

      {activeTab === 'analise' && (
        <>
          <StatsComparativas
            stats={analise.stats_comparativas}
            timeCasa={analise.time_casa}
            timeFora={analise.time_fora}
          />
          {(!analise.stats_comparativas || Object.keys(analise.stats_comparativas).length === 0) && (
            <div style={{
              textAlign: 'center', padding: '40px 24px', color: '#64748b',
              background: 'rgba(99,102,241,0.04)', borderRadius: 12,
              border: '1px dashed rgba(99,102,241,0.15)',
            }}>
              <div style={{ fontSize: 32, marginBottom: 10 }}>📊</div>
              <p style={{ fontSize: 14 }}>Estatísticas comparativas disponíveis após análise completa.</p>
              <p style={{ fontSize: 12, marginTop: 6, color: '#475569' }}>
                Os dados aparecem conforme a API retorna estatísticas da temporada.
              </p>
            </div>
          )}
        </>
      )}

      {activeTab === 'h2h' && (
        <H2HSection
          h2h={analise.h2h}
          timeCasa={analise.time_casa}
          timeFora={analise.time_fora}
        />
      )}

      {activeTab === 'tabela' && (
        <TabelaClassificacao
          classificacao={analise.classificacao}
          timeCasa={analise.time_casa}
          timeFora={analise.time_fora}
        />
      )}
    </div>
  )
}

const statBoxStyle = {
  background: 'rgba(99,102,241,0.06)',
  border: '1px solid rgba(99,102,241,0.12)',
  borderRadius: 10, padding: '12px 16px',
  flex: 1, minWidth: 120,
}
const statLabelStyle = { fontSize: 11, color: '#64748b', fontWeight: 600, marginBottom: 4 }
const statValueStyle = { fontSize: 22, fontWeight: 800, color: '#f1f5f9' }
const statSubStyle = { fontSize: 11, color: '#475569', marginTop: 2 }
