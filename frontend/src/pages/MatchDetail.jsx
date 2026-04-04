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
      setDiff(kickoff - now)
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
        fontSize: size * 0.4, color: '#818cf8', fontWeight: 700, flexShrink: 0,
      }}>
        {name?.[0] || '?'}
      </div>
    )
  }
  return <img src={logo} alt={name} style={{ width: size, height: size, objectFit: 'contain', flexShrink: 0 }} onError={() => setErr(true)} />
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
  if (edge >= 5) { color = '#22c55e'; label = 'Valor'; bg = 'rgba(34,197,94,0.12)' }
  else if (edge >= -3) { color = '#eab308'; label = 'Justo'; bg = 'rgba(234,179,8,0.12)' }
  else { color = '#f87171'; label = 'Caro'; bg = 'rgba(239,68,68,0.12)' }
  return (
    <span style={{
      fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 6,
      background: bg, color, border: `1px solid ${color}33`,
    }}>
      {label} {edge >= 0 ? '+' : ''}{edge.toFixed(1)}%
    </span>
  )
}

function ConfidenceBreakdown({ bd }) {
  const [open, setOpen] = useState(false)
  const keys = Object.keys(bd).filter(k => k !== 'confianca_final' && k !== 'modificador_historico')
  if (keys.length === 0) return null
  return (
    <div style={{ marginTop: 6 }}>
      <button onClick={() => setOpen(o => !o)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 10, color: '#475569', padding: 0 }}>
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
              <span style={{ color: '#818cf8', fontWeight: 600 }}>{typeof bd[k] === 'number' ? bd[k].toFixed(2) : String(bd[k])}</span>
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

function PredictionRow({ palpite, rank }) {
  const conf = palpite.confianca || 0
  return (
    <div style={{ padding: '12px 0', borderBottom: '1px solid rgba(255,255,255,0.04)', display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, flexWrap: 'wrap' }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 4 }}>
            {rank === 0 && (
              <span style={{ fontSize: 10, background: 'rgba(99,102,241,0.2)', color: '#818cf8', border: '1px solid rgba(99,102,241,0.4)', borderRadius: 4, padding: '1px 6px', fontWeight: 700 }}>
                #1
              </span>
            )}
            <span style={{ fontSize: 13, fontWeight: 600, color: '#f1f5f9' }}>{palpite.tipo}</span>
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
            <OddsTrafficLight odd={palpite.odd} probabilidade={palpite.probabilidade} />
          </div>
          {palpite.justificativa && (
            <p style={{ fontSize: 12, color: '#64748b', lineHeight: 1.5, marginBottom: 6 }}>{palpite.justificativa}</p>
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

function MarketCard({ mercado, minConfianca }) {
  const [open, setOpen] = useState(true)
  const icon = MARKET_ICONS[mercado.mercado] || '📊'
  const palpitesFiltrados = (mercado.palpites || []).filter(p => (p.confianca || 0) >= minConfianca)
  const topConf = palpitesFiltrados[0]?.confianca || 0
  if (palpitesFiltrados.length === 0) return null
  return (
    <div className="card" style={{ marginBottom: 14, overflow: 'hidden' }}>
      <button onClick={() => setOpen(o => !o)} style={{
        width: '100%', display: 'flex', alignItems: 'center', gap: 10,
        padding: '12px 16px', cursor: 'pointer', background: 'transparent', border: 'none',
        borderBottom: open ? '1px solid rgba(255,255,255,0.05)' : 'none',
      }}>
        <span style={{ fontSize: 18 }}>{icon}</span>
        <span style={{ fontSize: 14, fontWeight: 700, color: '#e2e8f0' }}>{mercado.mercado}</span>
        <span style={{ fontSize: 11, color: '#475569' }}>{palpitesFiltrados.length} palpite{palpitesFiltrados.length !== 1 ? 's' : ''}</span>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
          {topConf >= 7 && <span className="badge badge-green" style={{ fontSize: 10 }}>⭐ Top</span>}
          <span style={{ fontSize: 12, color: '#475569' }}>{open ? '▲' : '▼'}</span>
        </div>
      </button>
      {open && (
        <div style={{ padding: '0 16px 4px' }}>
          {palpitesFiltrados.map((p, i) => <PredictionRow key={i} palpite={p} rank={i} />)}
        </div>
      )}
    </div>
  )
}

function FormaRecente({ forma, label }) {
  if (!forma || forma.length === 0) return null
  const getColor = (r) => {
    const u = String(r).toUpperCase()
    if (u === 'W' || u === 'V') return '#22c55e'
    if (u === 'D' || u === 'E') return '#eab308'
    return '#f87171'
  }
  const getLabel = (r) => {
    const u = String(r).toUpperCase()
    if (u === 'W') return 'V'
    if (u === 'L') return 'D'
    return u
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
      <div style={{ fontSize: 10, color: '#64748b', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</div>
      <div style={{ display: 'flex', gap: 4 }}>
        {forma.slice(0, 5).map((r, i) => (
          <div key={i} style={{
            width: 26, height: 26, borderRadius: 7,
            background: `${getColor(r)}18`, border: `1.5px solid ${getColor(r)}44`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 10, fontWeight: 700, color: getColor(r),
          }}>
            {getLabel(r)}
          </div>
        ))}
      </div>
    </div>
  )
}

function H2HSection({ h2h, h2hSummary, timeCasa, timeFora }) {
  if (!h2h || h2h.length === 0) return (
    <div style={{ textAlign: 'center', padding: '40px 0', color: '#64748b' }}>
      <div style={{ fontSize: 32, marginBottom: 10 }}>⚔️</div>
      <p style={{ fontSize: 14 }}>Sem dados de confrontos diretos armazenados.</p>
    </div>
  )
  return (
    <div>
      {h2hSummary && h2hSummary.total_jogos > 0 && (
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 14 }}>
          <div style={statBoxStyle}>
            <div style={statLabelStyle}>Gols/Jogo (H2H)</div>
            <div style={{ ...statValueStyle, fontSize: 20 }}>{h2hSummary.media_gols}</div>
            <div style={statSubStyle}>{h2hSummary.total_jogos} confrontos</div>
          </div>
          <div style={statBoxStyle}>
            <div style={statLabelStyle}>BTTS nos H2H</div>
            <div style={{ ...statValueStyle, fontSize: 20 }}>{h2hSummary.btts_freq}%</div>
            <div style={statSubStyle}>ambos marcaram</div>
          </div>
        </div>
      )}
      <div className="card" style={{ padding: '16px 18px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {h2h.map((jogo, i) => {
            const data = (jogo.data || jogo.date || '').slice(0, 4)
            const gc = jogo.gols_casa ?? jogo.home_goals ?? jogo.score_home ?? '?'
            const gf = jogo.gols_fora ?? jogo.away_goals ?? jogo.score_away ?? '?'
            const home = jogo.time_casa || jogo.home_team || timeCasa
            const away = jogo.time_fora || jogo.away_team || timeFora
            return (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '8px 10px', borderRadius: 8,
                background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(99,102,241,0.08)',
              }}>
                <span style={{ fontSize: 11, color: '#475569', minWidth: 32 }}>{data}</span>
                <span style={{ fontSize: 12, color: '#94a3b8', flex: 1, textAlign: 'right', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{home}</span>
                <span style={{
                  fontSize: 13, fontWeight: 700, color: '#e2e8f0',
                  background: 'rgba(99,102,241,0.1)', borderRadius: 6,
                  padding: '2px 10px', minWidth: 52, textAlign: 'center', flexShrink: 0,
                }}>{gc} – {gf}</span>
                <span style={{ fontSize: 12, color: '#94a3b8', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{away}</span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

function StatsComparativas({ stats, timeCasa, timeFora }) {
  if (!stats || Object.keys(stats).length === 0) return (
    <div style={{ textAlign: 'center', padding: '40px 24px', color: '#64748b', background: 'rgba(99,102,241,0.04)', borderRadius: 12, border: '1px dashed rgba(99,102,241,0.15)' }}>
      <div style={{ fontSize: 32, marginBottom: 10 }}>📊</div>
      <p style={{ fontSize: 14 }}>Estatísticas comparativas disponíveis após análise completa.</p>
      <p style={{ fontSize: 12, marginTop: 6, color: '#475569' }}>Os dados aparecem conforme a API retorna estatísticas da temporada.</p>
    </div>
  )
  const rows = [
    { key: 'media_gols_marcados', label: 'Gols Marcados (méd.)' },
    { key: 'media_gols_sofridos', label: 'Gols Sofridos (méd.)' },
    { key: 'btts_percent', label: 'BTTS % (recente)' },
    { key: 'over25_percent', label: 'Over 2.5 % (recente)' },
    { key: 'media_cantos', label: 'Escanteios (méd.)' },
    { key: 'media_finalizacoes', label: 'Finalizações (méd.)' },
    { key: 'avg_shots', label: 'Chutes (méd.)' },
    { key: 'posse_media', label: 'Posse de Bola (%)' },
    { key: 'avg_possession', label: 'Posse (%)' },
  ].filter(r => stats[`${r.key}_casa`] !== undefined || stats[`${r.key}_fora`] !== undefined)

  if (rows.length === 0) return (
    <div style={{ textAlign: 'center', padding: '40px 24px', color: '#64748b', background: 'rgba(99,102,241,0.04)', borderRadius: 12, border: '1px dashed rgba(99,102,241,0.15)' }}>
      <p style={{ fontSize: 14 }}>Sem métricas comparativas disponíveis para este jogo.</p>
    </div>
  )

  return (
    <div className="card" style={{ padding: '16px 18px' }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', alignItems: 'center', gap: '8px 12px' }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: '#818cf8', textAlign: 'right', paddingBottom: 4 }}>{timeCasa}</div>
        <div />
        <div style={{ fontSize: 11, fontWeight: 700, color: '#818cf8', paddingBottom: 4 }}>{timeFora}</div>
        {rows.map(r => {
          const vC = stats[`${r.key}_casa`]
          const vF = stats[`${r.key}_fora`]
          const cW = vC !== undefined && vF !== undefined && vC > vF
          const fW = vC !== undefined && vF !== undefined && vF > vC
          return [
            <div key={`c-${r.key}`} style={{ fontSize: 15, fontWeight: 700, textAlign: 'right', color: cW ? '#22c55e' : '#e2e8f0' }}>
              {vC !== undefined ? vC : '—'}
            </div>,
            <div key={`l-${r.key}`} style={{ fontSize: 10, color: '#475569', textAlign: 'center', padding: '2px 6px', background: 'rgba(255,255,255,0.03)', borderRadius: 4, whiteSpace: 'nowrap' }}>
              {r.label}
            </div>,
            <div key={`f-${r.key}`} style={{ fontSize: 15, fontWeight: 700, color: fW ? '#22c55e' : '#e2e8f0' }}>
              {vF !== undefined ? vF : '—'}
            </div>,
          ]
        })}
      </div>
    </div>
  )
}

function PlayerMarketRow({ record }) {
  const conf = record.confianca || 0
  let confColor = '#ef4444'
  if (conf >= 7) confColor = '#22c55e'
  else if (conf >= 5) confColor = '#eab308'

  const mediaHistorico = record.media_historico != null ? record.media_historico : null
  const mediaCasa = record.media_casa != null ? record.media_casa : null
  const mediaFora = record.media_fora != null ? record.media_fora : null
  const isHome = record.eh_mandante

  return (
    <div style={{ padding: '10px 0', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <span style={{ fontSize: 12, fontWeight: 700, color: '#e2e8f0', flex: 1 }}>{record.jogador}</span>
        {record.odd && (
          <span style={{ fontSize: 11, color: '#818cf8', fontWeight: 700 }}>@{Number(record.odd).toFixed(2)}</span>
        )}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 10, color: '#64748b', background: 'rgba(255,255,255,0.04)', borderRadius: 4, padding: '1px 6px' }}>
          {record.mercado}
        </span>
        <span style={{ fontSize: 10, fontWeight: 700, color: confColor, background: `${confColor}14`, borderRadius: 4, padding: '1px 6px', border: `1px solid ${confColor}25` }}>
          {conf.toFixed(1)}/10
        </span>
        {record.amostra_pequena && (
          <span style={{ fontSize: 10, color: '#f59e0b', background: 'rgba(245,158,11,0.1)', borderRadius: 4, padding: '1px 6px', border: '1px solid rgba(245,158,11,0.2)' }}>
            ⚠️ amostra n={record.n_jogos}&lt;6
          </span>
        )}
      </div>
      <div style={{ display: 'flex', gap: 14, fontSize: 11, color: '#64748b', flexWrap: 'wrap' }}>
        {mediaHistorico !== null && (
          <span>📈 Média geral: <strong style={{ color: '#94a3b8' }}>{(mediaHistorico * 100).toFixed(1)}%</strong></span>
        )}
        {isHome && mediaCasa !== null && (
          <span>🏠 Casa: <strong style={{ color: '#818cf8' }}>{(mediaCasa * 100).toFixed(1)}%</strong></span>
        )}
        {!isHome && mediaFora !== null && (
          <span>✈️ Fora: <strong style={{ color: '#34d399' }}>{(mediaFora * 100).toFixed(1)}%</strong></span>
        )}
        <span>📊 Prob: <strong style={{ color: '#94a3b8' }}>{record.probabilidade.toFixed(1)}%</strong></span>
        {record.n_jogos > 0 && <span>🎮 {record.n_jogos} jogos</span>}
      </div>
      {record.ultimos_5?.length > 0 && (
        <div style={{ display: 'flex', gap: 4, marginTop: 6, alignItems: 'center' }}>
          <span style={{ fontSize: 10, color: '#475569' }}>Últimos {record.ultimos_5.length}:</span>
          {record.ultimos_5.map((v, i) => (
            <span key={i} style={{
              fontSize: 10, fontWeight: 700,
              color: v > 0 ? '#22c55e' : '#475569',
              background: v > 0 ? 'rgba(34,197,94,0.1)' : 'rgba(255,255,255,0.04)',
              borderRadius: 4, padding: '1px 5px',
            }}>
              {v}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

function JogadoresSection({ fixtureId, timeCasa, timeFora }) {
  const [dados, setDados] = useState(null)
  const [loading, setLoading] = useState(true)
  const [aba, setAba] = useState('escalacao')

  useEffect(() => {
    fetch(`/api/jogadores/${fixtureId}`)
      .then(r => r.json())
      .then(d => { setDados(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [fixtureId])

  if (loading) return (
    <div style={{ textAlign: 'center', padding: '24px 0', color: '#64748b' }}>
      <div className="spinner" style={{ width: 28, height: 28, margin: '0 auto 8px' }} />
      <p style={{ fontSize: 13 }}>Carregando dados de jogadores...</p>
    </div>
  )

  const mercadosMandante = dados?.mercados_mandante || []
  const mercadosVisitante = dados?.mercados_visitante || []
  const mandantesStats = dados?.mandantes || []
  const visitantesStats = dados?.visitantes || []
  const lineupConfirmado = dados?.lineup_confirmado ?? false

  const semMercados = mercadosMandante.length === 0 && mercadosVisitante.length === 0
  const semLineup = mandantesStats.length === 0 && visitantesStats.length === 0

  if (semMercados && semLineup) return (
    <div style={{ textAlign: 'center', padding: '40px 0', color: '#64748b' }}>
      <div style={{ fontSize: 32, marginBottom: 10 }}>👥</div>
      <p style={{ fontSize: 14 }}>Sem dados de jogadores para este jogo.</p>
      <p style={{ fontSize: 12, marginTop: 6, color: '#475569' }}>Os perfis e mercados de jogadores aparecem após análise com estatísticas individuais da API.</p>
    </div>
  )

  return (
    <div>
      {/* Sub-tabs: Escalação / Mercados de Jogadores */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 14 }}>
        {[
          { id: 'escalacao', label: '👕 Escalação' },
          { id: 'mercados', label: '📊 Mercados de Jogadores' },
        ].map(t => (
          <button key={t.id} onClick={() => setAba(t.id)} style={{
            padding: '6px 12px', borderRadius: 8, cursor: 'pointer', fontSize: 12, fontWeight: 600,
            background: aba === t.id ? 'rgba(99,102,241,0.2)' : 'rgba(255,255,255,0.04)',
            color: aba === t.id ? '#818cf8' : '#64748b',
            border: `1px solid ${aba === t.id ? 'rgba(99,102,241,0.4)' : 'rgba(255,255,255,0.06)'}`,
          }}>
            {t.label}
          </button>
        ))}
      </div>

      {aba === 'escalacao' && (
        <EscalacaoSection mandantes={mandantesStats} visitantes={visitantesStats} timeCasa={timeCasa} timeFora={timeFora} lineupConfirmado={lineupConfirmado} />
      )}

      {aba === 'mercados' && (
        semMercados ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: '#64748b', background: 'rgba(99,102,241,0.04)', borderRadius: 12, border: '1px dashed rgba(99,102,241,0.15)' }}>
            <div style={{ fontSize: 32, marginBottom: 10 }}>📊</div>
            <p style={{ fontSize: 14 }}>Mercados de jogadores não disponíveis.</p>
            <p style={{ fontSize: 12, marginTop: 6, color: '#475569' }}>Os mercados individuais aparecem quando a API retorna estatísticas de desempenho dos jogadores.</p>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
            <div className="card" style={{ padding: '14px 16px' }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: '#818cf8', marginBottom: 10 }}>🏠 {timeCasa}</div>
              {mercadosMandante.map((r, i) => <PlayerMarketRow key={i} record={r} />)}
            </div>
            <div className="card" style={{ padding: '14px 16px' }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: '#818cf8', marginBottom: 10 }}>✈️ {timeFora}</div>
              {mercadosVisitante.map((r, i) => <PlayerMarketRow key={i} record={r} />)}
            </div>
          </div>
        )
      )}
    </div>
  )
}

function EscalacaoSection({ mandantes, visitantes, timeCasa, timeFora, lineupConfirmado = false }) {
  const titularesCasa = mandantes.filter(j => j.foi_titular)
  const reservasCasa = mandantes.filter(j => !j.foi_titular)
  const titularesFora = visitantes.filter(j => j.foi_titular)
  const reservasFora = visitantes.filter(j => !j.foi_titular)

  if (titularesCasa.length === 0 && titularesFora.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '40px 0', color: '#64748b', background: 'rgba(99,102,241,0.04)', borderRadius: 12, border: '1px dashed rgba(99,102,241,0.15)' }}>
        <div style={{ fontSize: 32, marginBottom: 10 }}>🟩</div>
        <p style={{ fontSize: 14 }}>Escalação não confirmada para este jogo.</p>
        <p style={{ fontSize: 12, marginTop: 6, color: '#475569' }}>
          O lineup é divulgado normalmente 1 hora antes do jogo. Os dados aparecem quando a API retorna a escalação confirmada.
        </p>
      </div>
    )
  }

  const statusBanner = lineupConfirmado ? (
    <div style={{ padding: '6px 12px', background: 'rgba(34,197,94,0.08)', border: '1px solid rgba(34,197,94,0.2)', borderRadius: 8, marginBottom: 10, fontSize: 11, color: '#22c55e', fontWeight: 600 }}>
      ✅ Escalação confirmada
    </div>
  ) : (
    <div style={{ padding: '6px 12px', background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.2)', borderRadius: 8, marginBottom: 10, fontSize: 11, color: '#f59e0b', fontWeight: 600 }}>
      ⏳ Provável escalação — aguardando confirmação oficial (~1h antes do jogo). Jogadores lesionados 🏥 e suspensos 🚫 marcados quando disponíveis.
    </div>
  )

  const splitLines = (players) => {
    if (players.length === 0) return []
    if (players.length <= 4) return [players]
    const n = players.length
    if (n <= 8) {
      const mid = Math.ceil(n / 2)
      return [players.slice(0, 1), players.slice(1, mid), players.slice(mid)]
    }
    return [players.slice(0, 1), players.slice(1, 5), players.slice(5, 9), players.slice(9)]
  }

  const FieldPlayer = ({ j, color = '#818cf8' }) => (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3 }}>
      <div style={{
        width: 36, height: 36, borderRadius: '50%', border: `2px solid ${color}`,
        background: `${color}18`, display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 10, fontWeight: 800, color,
        position: 'relative',
      }}>
        {j.nome ? j.nome.split(' ').pop()?.slice(0, 3).toUpperCase() : `J${j.jogador_id}`}
        {j.cartao_amarelo && <span style={{ position: 'absolute', top: -4, right: -4, fontSize: 8 }}>🟨</span>}
        {j.cartao_vermelho && <span style={{ position: 'absolute', top: -4, right: -4, fontSize: 8 }}>🟥</span>}
        {j.gols > 0 && <span style={{ position: 'absolute', bottom: -4, left: -4, fontSize: 8 }}>⚽</span>}
      </div>
      <span style={{ fontSize: 9, color: '#94a3b8', textAlign: 'center', maxWidth: 52, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {j.nome?.split(' ').pop() || `#${j.jogador_id}`}
      </span>
    </div>
  )

  const FormationField = ({ players, teamName, isCasa }) => {
    const lines = splitLines(players)
    const color = isCasa ? '#818cf8' : '#34d399'
    return (
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 12, fontWeight: 700, color, marginBottom: 6, textAlign: 'center' }}>
          {isCasa ? '🏠' : '✈️'} {teamName}
        </div>
        <div style={{
          background: 'linear-gradient(180deg, rgba(34,197,94,0.05) 0%, rgba(34,197,94,0.02) 100%)',
          border: '1px solid rgba(34,197,94,0.12)',
          borderRadius: 12, padding: '12px 8px',
          display: 'flex', flexDirection: isCasa ? 'column' : 'column-reverse', gap: 14,
          minHeight: 280,
        }}>
          {lines.map((line, li) => (
            <div key={li} style={{ display: 'flex', justifyContent: 'space-evenly', alignItems: 'center' }}>
              {line.map((j, i) => <FieldPlayer key={i} j={j} color={color} />)}
            </div>
          ))}
          {players.length === 0 && (
            <div style={{ textAlign: 'center', padding: '20px 0', color: '#64748b', fontSize: 12 }}>Sem dados</div>
          )}
        </div>
      </div>
    )
  }

  const BenchRow = ({ j, color }) => (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 6, padding: '4px 8px',
      borderRadius: 6, background: 'rgba(255,255,255,0.02)',
    }}>
      <div style={{ width: 20, height: 20, borderRadius: '50%', border: `1px dashed ${color}50`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 8, color: '#475569' }}>S</div>
      <span style={{ fontSize: 10, color: '#64748b', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {j.nome?.split(' ').pop() || `#${j.jogador_id}`}
      </span>
      {j.minutos > 0 && <span style={{ fontSize: 9, color: '#475569' }}>{j.minutos}'</span>}
    </div>
  )

  return (
    <div>
      {statusBanner}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 10, color: '#475569', fontWeight: 600 }}>Legenda:</span>
        <span style={{ fontSize: 10, color: '#475569' }}>⚽ Gol</span>
        <span style={{ fontSize: 10, color: '#475569' }}>🟨 Amarelo</span>
        <span style={{ fontSize: 10, color: '#475569' }}>🟥 Vermelho</span>
        <span style={{ fontSize: 10, color: '#475569' }}>🏥 Lesionado (quando disponível)</span>
        <span style={{ fontSize: 10, color: '#475569' }}>🚫 Suspenso (quando disponível)</span>
      </div>
      <div style={{ display: 'flex', gap: 10, marginBottom: 14 }}>
        <FormationField players={titularesCasa} teamName={timeCasa} isCasa={true} />
        <div style={{ width: 1, background: 'rgba(255,255,255,0.06)', flexShrink: 0 }} />
        <FormationField players={titularesFora} teamName={timeFora} isCasa={false} />
      </div>
      {(reservasCasa.length > 0 || reservasFora.length > 0) && (
        <div className="card" style={{ padding: '10px 14px' }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: '#64748b', marginBottom: 8 }}>Banco de Reservas</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4 }}>
            <div>{reservasCasa.map((j, i) => <BenchRow key={i} j={j} color="#818cf8" />)}</div>
            <div>{reservasFora.map((j, i) => <BenchRow key={i} j={j} color="#34d399" />)}</div>
          </div>
        </div>
      )}
    </div>
  )
}

function ArbitroSection({ arbitro, metadata }) {
  const nomeArbitro = arbitro || metadata?.arbitro || ''

  if (!nomeArbitro) return (
    <div style={{ textAlign: 'center', padding: '40px 0', color: '#64748b', background: 'rgba(99,102,241,0.04)', borderRadius: 12, border: '1px dashed rgba(99,102,241,0.15)' }}>
      <div style={{ fontSize: 32, marginBottom: 10 }}>🟨</div>
      <p style={{ fontSize: 14 }}>Árbitro não informado para este jogo.</p>
      <p style={{ fontSize: 12, marginTop: 6, color: '#475569' }}>O perfil do árbitro aparece quando a API retorna o nome do juiz.</p>
    </div>
  )

  const cartoesPorJogo = metadata?.arbitro_cartoes_por_jogo ?? null
  const penalusPorJogo = metadata?.arbitro_penaltis_por_jogo ?? null
  const estiloArbitro = metadata?.arbitro_estilo ?? null
  const estiloMap = { rigoroso: '#f87171', moderado: '#eab308', permissivo: '#22c55e' }
  const estiloCor = estiloArbitro ? (estiloMap[estiloArbitro] ?? '#818cf8') : null

  const hasRealStats = cartoesPorJogo !== null || penalusPorJogo !== null || estiloArbitro !== null

  return (
    <div>
      <div className="card" style={{ padding: '20px 22px', marginBottom: hasRealStats ? 14 : 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: hasRealStats ? 16 : 0 }}>
          <div style={{ width: 52, height: 52, borderRadius: 14, background: 'rgba(99,102,241,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 24, flexShrink: 0 }}>
            🟨
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 16, fontWeight: 700, color: '#f1f5f9' }}>{nomeArbitro}</div>
            <div style={{ fontSize: 12, color: '#64748b', marginTop: 2 }}>Árbitro Principal</div>
          </div>
          {estiloArbitro && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '6px 12px', borderRadius: 10,
              background: `${estiloCor}12`, border: `1px solid ${estiloCor}30`,
            }}>
              <div>
                <div style={{ fontSize: 10, color: '#64748b' }}>Estilo</div>
                <div style={{ fontSize: 13, fontWeight: 700, color: estiloCor, textTransform: 'capitalize' }}>{estiloArbitro}</div>
              </div>
            </div>
          )}
        </div>

        {hasRealStats && (
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 16 }}>
            {cartoesPorJogo !== null && (
              <div style={statBoxStyle}>
                <div style={statLabelStyle}>Cartões / Jogo</div>
                <div style={{ ...statValueStyle, fontSize: 22, color: cartoesPorJogo >= 4 ? '#f87171' : cartoesPorJogo >= 3 ? '#eab308' : '#22c55e' }}>
                  {Number(cartoesPorJogo).toFixed(1)}
                </div>
                <div style={statSubStyle}>média real</div>
              </div>
            )}
            {penalusPorJogo !== null && (
              <div style={statBoxStyle}>
                <div style={statLabelStyle}>Penaltis / Jogo</div>
                <div style={{ ...statValueStyle, fontSize: 22, color: penalusPorJogo >= 0.15 ? '#f87171' : '#94a3b8' }}>
                  {Number(penalusPorJogo).toFixed(2)}
                </div>
                <div style={statSubStyle}>frequência real</div>
              </div>
            )}
          </div>
        )}

        {!hasRealStats && (
          <div style={{ marginTop: 14, padding: '10px 14px', background: 'rgba(99,102,241,0.04)', border: '1px dashed rgba(99,102,241,0.15)', borderRadius: 8 }}>
            <p style={{ fontSize: 12, color: '#64748b', margin: 0 }}>
              Histórico detalhado do árbitro não disponível no plano atual da API. Apenas o nome foi fornecido pela fonte de dados.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

function TabelaClassificacao({ classificacao, timeCasa, timeFora }) {
  if (!classificacao || classificacao.length === 0) return (
    <div style={{ textAlign: 'center', padding: '40px 0', color: '#64748b' }}>
      <p style={{ fontSize: 14 }}>Sem dados de classificação disponíveis.</p>
    </div>
  )
  const relevantes = classificacao.filter(t =>
    t.team?.name === timeCasa || t.team?.name === timeFora || (t.rank && t.rank <= 5)
  ).slice(0, 10)
  if (relevantes.length === 0) return null
  return (
    <div className="card" style={{ padding: '16px 18px' }}>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr>
              {['#', 'Time', 'J', 'V', 'E', 'D', 'Pts'].map(h => (
                <th key={h} style={{ padding: '4px 8px', textAlign: h === 'Time' ? 'left' : 'center', color: '#64748b', fontWeight: 600, borderBottom: '1px solid rgba(99,102,241,0.1)' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {relevantes.map((t, i) => {
              const hl = t.team?.name === timeCasa || t.team?.name === timeFora
              return (
                <tr key={i} style={{ background: hl ? 'rgba(99,102,241,0.08)' : 'transparent' }}>
                  <td style={{ padding: '6px 8px', textAlign: 'center', color: '#64748b', fontWeight: 600 }}>{t.rank}</td>
                  <td style={{ padding: '6px 8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      {t.team?.logo && <img src={t.team.logo} alt="" style={{ width: 16, height: 16, objectFit: 'contain' }} onError={e => e.target.style.display = 'none'} />}
                      <span style={{ color: hl ? '#f1f5f9' : '#94a3b8', fontWeight: hl ? 700 : 400, whiteSpace: 'nowrap' }}>{t.team?.name || ''}</span>
                    </div>
                  </td>
                  <td style={{ padding: '6px 8px', textAlign: 'center', color: '#64748b' }}>{t.all?.played ?? '—'}</td>
                  <td style={{ padding: '6px 8px', textAlign: 'center', color: '#22c55e' }}>{t.all?.win ?? '—'}</td>
                  <td style={{ padding: '6px 8px', textAlign: 'center', color: '#eab308' }}>{t.all?.draw ?? '—'}</td>
                  <td style={{ padding: '6px 8px', textAlign: 'center', color: '#f87171' }}>{t.all?.lose ?? '—'}</td>
                  <td style={{ padding: '6px 8px', textAlign: 'center', color: '#f1f5f9', fontWeight: 700 }}>{t.points ?? '—'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function ScriptTaticoCard({ script, reasoning }) {
  const [showReasoning, setShowReasoning] = useState(false)
  const info = SCRIPT_LABELS[script] || { label: script, color: '#818cf8', icon: '📋' }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <button
        onClick={() => reasoning && setShowReasoning(o => !o)}
        style={{
          display: 'inline-flex', alignItems: 'center', gap: 8, padding: '6px 14px',
          borderRadius: 10, background: `${info.color}12`, border: `1px solid ${info.color}30`,
          cursor: reasoning ? 'pointer' : 'default',
        }}
      >
        <span style={{ fontSize: 16 }}>{info.icon}</span>
        <div>
          <div style={{ fontSize: 10, color: '#64748b', fontWeight: 600 }}>Script Tático</div>
          <div style={{ fontSize: 13, fontWeight: 700, color: info.color }}>{info.label}</div>
        </div>
        {reasoning && <span style={{ fontSize: 10, color: '#475569', marginLeft: 4 }}>{showReasoning ? '▲' : '▼'}</span>}
      </button>
      {showReasoning && reasoning && (
        <div style={{
          padding: '10px 14px', borderRadius: 8,
          background: `${info.color}08`, border: `1px solid ${info.color}20`,
          fontSize: 12, color: '#94a3b8', lineHeight: 1.6, maxWidth: 480,
        }}>
          {reasoning}
        </div>
      )}
    </div>
  )
}

function FixtureMetadata({ metadata, jogoInfo }) {
  const rodada = metadata?.rodada || jogoInfo?.rodada || ''
  const venue = metadata?.venue || jogoInfo?.venue || ''
  const cidade = metadata?.venue_cidade || jogoInfo?.venue_cidade || ''
  const arbitro = metadata?.arbitro || jogoInfo?.arbitro || ''
  const dataAnalise = metadata?.data_analise || ''

  const items = [
    rodada && { icon: '📅', label: 'Rodada', value: rodada },
    (venue || cidade) && { icon: '🏟️', label: 'Estádio', value: [venue, cidade].filter(Boolean).join(', ') },
    arbitro && { icon: '🟨', label: 'Árbitro', value: arbitro },
    dataAnalise && { icon: '🕐', label: 'Analisado', value: new Date(dataAnalise).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) },
  ].filter(Boolean)

  if (items.length === 0) return null

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 16 }}>
      {items.map((item, i) => (
        <div key={i} style={{
          display: 'flex', alignItems: 'center', gap: 6,
          background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(99,102,241,0.1)',
          borderRadius: 8, padding: '5px 10px',
        }}>
          <span style={{ fontSize: 13 }}>{item.icon}</span>
          <span style={{ fontSize: 10, color: '#64748b' }}>{item.label}:</span>
          <span style={{ fontSize: 11, color: '#94a3b8', fontWeight: 600 }}>{item.value}</span>
        </div>
      ))}
    </div>
  )
}

function SkeletonCard({ height = 80 }) {
  return <div className="skeleton-card" style={{ height, borderRadius: 12, marginBottom: 14 }} />
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
        if (d.status === 'ready') { setAnalise(d); setProcessing(false); setLoading(false); return true }
        if (d.status === 'processing') { setProcessing(true); setLoading(false); return false }
      } else if (r.status === 404) { setLoading(false); return false }
    } catch { setLoading(false) }
    return false
  }, [fixtureId])

  const triggerAnalise = useCallback(async () => {
    setProcessing(true)
    try {
      const r = await fetch(`/api/analisar/${fixtureId}`, { method: 'POST' })
      if (r.status === 404) {
        setProcessing(false)
        setError('Este jogo é de demonstração e não pode ser analisado. Está disponível apenas em modo de exibição.')
        return
      }
      const d = await r.json()
      if (d.status === 'ready') await checkStatus()
      else if (d.status === 'error') { setError(d.message || 'Erro na análise'); setProcessing(false) }
    } catch { setError('Erro ao iniciar análise'); setProcessing(false) }
  }, [fixtureId, checkStatus])

  useEffect(() => {
    const run = async () => {
      const found = await checkStatus()
      if (!found && !processing) await triggerAnalise()
    }
    run()
  }, [fixtureId])

  useEffect(() => {
    if (!processing) return
    const poll = setInterval(async () => { if (await checkStatus()) clearInterval(poll) }, 3000)
    return () => clearInterval(poll)
  }, [processing, checkStatus])

  useEffect(() => {
    const loadJogoInfo = async () => {
      try {
        const r = await fetch('/api/jogos/hoje')
        if (!r.ok) return
        const d = await r.json()
        const grupos = d.por_pais ? d.por_pais.flatMap(p => p.ligas || []) : (d.ligas || [])
        for (const grupo of grupos) {
          for (const j of grupo.jogos || []) {
            if (j.fixture_id === parseInt(fixtureId)) { setJogoInfo(j); return }
          }
        }
      } catch {}
    }
    loadJogoInfo()
  }, [fixtureId])

  const countdown = useCountdown(jogoInfo?.data_iso || analise?.data_jogo_iso)
  const isLast30 = (() => {
    const iso = jogoInfo?.data_iso || analise?.data_jogo_iso
    if (!iso) return false
    const ms = new Date(iso).getTime() - Date.now()
    return ms > 0 && ms < 30 * 60 * 1000
  })()

  if (loading) return (
    <div style={{ paddingTop: 24 }}>
      <div style={{ height: 16, width: 120, borderRadius: 6, background: 'rgba(99,102,241,0.1)', marginBottom: 24 }} />
      <SkeletonCard height={200} /><SkeletonCard height={50} /><SkeletonCard /><SkeletonCard /><SkeletonCard />
    </div>
  )

  if (processing) return (
    <div className="flex flex-col items-center justify-center" style={{ minHeight: 400, gap: 16, paddingTop: 80, textAlign: 'center' }}>
      <div className="spinner" style={{ width: 48, height: 48 }} />
      <p style={{ color: '#c7d2fe', fontSize: 16, fontWeight: 600 }}>Analisando o jogo...</p>
      <p style={{ color: '#64748b', fontSize: 13, maxWidth: 360 }}>
        O sistema está processando estatísticas, odds e dados táticos. Isso pode levar até 60 segundos.
      </p>
      <div style={{ display: 'flex', gap: 6, marginTop: 8, flexWrap: 'wrap', justifyContent: 'center' }}>
        {['Estatísticas', 'Odds', 'H2H', 'Analistas', 'Palpites'].map((s, i) => (
          <span key={i} style={{ fontSize: 11, padding: '3px 8px', background: 'rgba(99,102,241,0.1)', color: '#818cf8', border: '1px solid rgba(99,102,241,0.2)', borderRadius: 6 }}>{s}</span>
        ))}
      </div>
    </div>
  )

  if (error) return (
    <div style={{ textAlign: 'center', paddingTop: 80 }}>
      <p style={{ color: '#f87171', fontSize: 14 }}>{error}</p>
      <Link to="/" style={{ color: '#818cf8', fontSize: 13, marginTop: 12, display: 'block' }}>← Voltar aos jogos</Link>
    </div>
  )

  if (!analise) return (
    <div style={{ textAlign: 'center', paddingTop: 80 }}>
      <p style={{ color: '#64748b', fontSize: 14 }}>Análise não encontrada.</p>
      <Link to="/" style={{ color: '#818cf8', fontSize: 13, marginTop: 12, display: 'block' }}>← Voltar</Link>
    </div>
  )

  const todosMercados = [...(analise.mercados || [])].sort((a, b) => {
    const aMax = Math.max(...(a.palpites || []).map(p => p.confianca || 0))
    const bMax = Math.max(...(b.palpites || []).map(p => p.confianca || 0))
    return bMax - aMax
  })

  const mercadosDisponiveis = ['Todos', ...todosMercados.map(m => m.mercado)]
  const mercadosFiltrados = filtroMercado === 'Todos'
    ? todosMercados
    : todosMercados.filter(m => m.mercado === filtroMercado)

  const totalPalpitesVisiveis = mercadosFiltrados.reduce(
    (acc, m) => acc + (m.palpites || []).filter(p => (p.confianca || 0) >= minConfianca).length, 0
  )

  const topPick = todosMercados
    .flatMap(m => (m.palpites || []))
    .sort((a, b) => (b.confianca || 0) - (a.confianca || 0))[0]
  const topMercado = todosMercados[0]

  const arbitroNome = analise.fixture_metadata?.arbitro || jogoInfo?.arbitro || ''

  const tabs = [
    { id: 'palpites', label: '🎯 Palpites' },
    { id: 'analise', label: '📊 Análise' },
    { id: 'h2h', label: '⚔️ H2H' },
    { id: 'jogadores', label: '👥 Jogadores' },
    { id: 'arbitro', label: '🟨 Árbitro' },
    ...(analise.classificacao?.length > 0 ? [{ id: 'tabela', label: '🏆 Tabela' }] : []),
  ]

  return (
    <div style={{ paddingTop: 24 }}>
      <Link to="/" style={{ fontSize: 13, color: '#64748b', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 4, marginBottom: 20 }}>
        ← Voltar aos jogos
      </Link>

      {/* ── HERO CARD ─────────────────────────────────────────────── */}
      <div style={{ background: 'linear-gradient(135deg, #131729 0%, #1a1d2e 100%)', border: '1px solid rgba(99,102,241,0.2)', borderRadius: 16, padding: 24, marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8, marginBottom: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {jogoInfo?.liga?.logo && <img src={jogoInfo.liga.logo} alt="" style={{ width: 20, height: 20, objectFit: 'contain' }} onError={e => e.target.style.display = 'none'} />}
            <span style={{ fontSize: 12, color: '#818cf8', fontWeight: 600 }}>{jogoInfo?.liga?.nome || analise.liga}</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            {analise.script_tatico && <ScriptTaticoCard script={analise.script_tatico} reasoning={analise.script_reasoning} />}
            {isLast30 && (
              <span style={{ fontSize: 11, fontWeight: 700, padding: '4px 10px', borderRadius: 8, background: 'rgba(239,68,68,0.15)', color: '#f87171', border: '1px solid rgba(239,68,68,0.3)' }}>
                🔴 Análise Final
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center justify-center gap-6" style={{ marginBottom: 20 }}>
          <div className="flex flex-col items-center gap-2">
            <TeamLogo logo={jogoInfo?.time_casa?.logo} name={analise.time_casa} />
            <span style={{ fontSize: 14, fontWeight: 700, color: '#f1f5f9', textAlign: 'center', maxWidth: 120 }}>{analise.time_casa}</span>
            {analise.pos_casa && <span style={{ fontSize: 11, color: '#64748b' }}>#{analise.pos_casa} na tabela</span>}
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 22, fontWeight: 800, color: '#e2e8f0', letterSpacing: '0.1em' }}>VS</div>
            {countdown && (
              <div style={{ fontSize: countdown === 'AO VIVO' ? 13 : 12, color: countdown === 'AO VIVO' ? '#22c55e' : '#818cf8', fontWeight: 700, marginTop: 6 }}>
                {countdown === 'AO VIVO' ? '🟢 AO VIVO' : `⏱ ${countdown}`}
              </div>
            )}
            {!countdown && jogoInfo?.horario_brt && <div style={{ fontSize: 11, color: '#475569', marginTop: 4 }}>{jogoInfo.horario_brt}</div>}
          </div>
          <div className="flex flex-col items-center gap-2">
            <TeamLogo logo={jogoInfo?.time_fora?.logo} name={analise.time_fora} />
            <span style={{ fontSize: 14, fontWeight: 700, color: '#f1f5f9', textAlign: 'center', maxWidth: 120 }}>{analise.time_fora}</span>
            {analise.pos_fora && <span style={{ fontSize: 11, color: '#64748b' }}>#{analise.pos_fora} na tabela</span>}
          </div>
        </div>

        {(analise.forma_recente_casa?.length > 0 || analise.forma_recente_fora?.length > 0) && (
          <div style={{ display: 'flex', justifyContent: 'space-around', marginBottom: 20, flexWrap: 'wrap', gap: 12 }}>
            <FormaRecente forma={analise.forma_recente_casa} label="Últimos 5 (Casa)" />
            <FormaRecente forma={analise.forma_recente_fora} label="Últimos 5 (Fora)" />
          </div>
        )}

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

      <FixtureMetadata metadata={analise.fixture_metadata} jogoInfo={jogoInfo} />

      {/* ── TABS ─────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 16, overflowX: 'auto', paddingBottom: 2 }}>
        {tabs.map(tab => (
          <button key={tab.id} onClick={() => setActiveTab(tab.id)} style={{
            padding: '8px 16px', borderRadius: 10, cursor: 'pointer',
            fontSize: 13, fontWeight: 600, whiteSpace: 'nowrap',
            background: activeTab === tab.id ? 'rgba(99,102,241,0.2)' : 'rgba(255,255,255,0.04)',
            color: activeTab === tab.id ? '#818cf8' : '#64748b',
            border: activeTab === tab.id ? '1px solid rgba(99,102,241,0.4)' : '1px solid rgba(255,255,255,0.06)',
            transition: 'all 0.15s ease',
          }}>
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── FILTROS (Palpites) ────────────────────────────────────────── */}
      {activeTab === 'palpites' && (
        <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(99,102,241,0.1)', borderRadius: 12, padding: '14px 16px', marginBottom: 16 }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'center' }}>
            <div style={{ flex: 1, minWidth: 200 }}>
              <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, marginBottom: 8 }}>
                Confiança mínima: <span style={{ color: '#818cf8' }}>{minConfianca.toFixed(1)}</span>
              </div>
              <input type="range" min="0" max="9" step="0.5" value={minConfianca}
                onChange={e => setMinConfianca(Number(e.target.value))}
                style={{ width: '100%', accentColor: '#6366f1' }} />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: '#475569', marginTop: 2 }}>
                <span>0 (todos)</span><span>5.5 (bom)</span><span>7+ (top)</span><span>9 (elite)</span>
              </div>
            </div>
            <div style={{ minWidth: 160 }}>
              <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, marginBottom: 8 }}>Mercado</div>
              <select value={filtroMercado} onChange={e => setFiltroMercado(e.target.value)} style={{
                width: '100%', background: 'rgba(255,255,255,0.06)',
                border: '1px solid rgba(99,102,241,0.2)', borderRadius: 8,
                color: '#e2e8f0', padding: '6px 10px', fontSize: 13, cursor: 'pointer',
              }}>
                {mercadosDisponiveis.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
          </div>
        </div>
      )}

      {/* ── CONTEÚDO POR TAB ──────────────────────────────────────────── */}
      {activeTab === 'palpites' && (
        <>
          {totalPalpitesVisiveis === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px 0', color: '#64748b' }}>
              <div style={{ fontSize: 32, marginBottom: 10 }}>🔍</div>
              <p style={{ fontSize: 14 }}>Nenhum palpite com confiança ≥ {minConfianca.toFixed(1)}</p>
              <button onClick={() => { setMinConfianca(0); setFiltroMercado('Todos') }} style={{
                marginTop: 12, fontSize: 12, padding: '6px 16px', borderRadius: 8,
                background: 'rgba(99,102,241,0.12)', color: '#818cf8',
                border: '1px solid rgba(99,102,241,0.25)', cursor: 'pointer',
              }}>
                Limpar filtros
              </button>
            </div>
          ) : (
            mercadosFiltrados.map((m, i) => <MarketCard key={i} mercado={m} minConfianca={minConfianca} />)
          )}
          {analise.mercados_vetados?.length > 0 && (
            <div style={{ marginTop: 20, padding: '14px 16px', background: 'rgba(239,68,68,0.04)', border: '1px solid rgba(239,68,68,0.12)', borderRadius: 12 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: '#64748b', marginBottom: 10 }}>
                ⛔ Mercados sem palpite (baixa confiança / dados insuficientes)
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {analise.mercados_vetados.map((v, i) => (
                  <div key={i} title={v.motivo} style={{
                    fontSize: 11, padding: '3px 10px', borderRadius: 6,
                    background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.15)',
                    color: '#94a3b8', display: 'flex', alignItems: 'center', gap: 6, cursor: 'default',
                  }}>
                    <span style={{ color: '#64748b' }}>⛔</span>
                    <span>{v.mercado}</span>
                  </div>
                ))}
              </div>
              <p style={{ fontSize: 10, color: '#475569', marginTop: 8, marginBottom: 0 }}>
                Passe o mouse sobre cada mercado para ver o motivo.
              </p>
            </div>
          )}
        </>
      )}

      {activeTab === 'analise' && (
        <StatsComparativas stats={analise.stats_comparativas} timeCasa={analise.time_casa} timeFora={analise.time_fora} />
      )}

      {activeTab === 'h2h' && (
        <H2HSection h2h={analise.h2h} h2hSummary={analise.h2h_summary} timeCasa={analise.time_casa} timeFora={analise.time_fora} />
      )}

      {activeTab === 'jogadores' && (
        <JogadoresSection fixtureId={fixtureId} timeCasa={analise.time_casa} timeFora={analise.time_fora} />
      )}

      {activeTab === 'arbitro' && (
        <ArbitroSection arbitro={arbitroNome} metadata={analise.fixture_metadata} />
      )}

      {activeTab === 'tabela' && (
        <TabelaClassificacao classificacao={analise.classificacao} timeCasa={analise.time_casa} timeFora={analise.time_fora} />
      )}
    </div>
  )
}

const statBoxStyle = {
  background: 'rgba(99,102,241,0.06)', border: '1px solid rgba(99,102,241,0.12)',
  borderRadius: 10, padding: '12px 16px', flex: 1, minWidth: 120,
}
const statLabelStyle = { fontSize: 11, color: '#64748b', fontWeight: 600, marginBottom: 4 }
const statValueStyle = { fontSize: 22, fontWeight: 800, color: '#f1f5f9' }
const statSubStyle = { fontSize: 11, color: '#475569', marginTop: 2 }
