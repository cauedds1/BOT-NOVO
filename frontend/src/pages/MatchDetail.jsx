import { useState, useEffect, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'

const MARKET_ICONS = {
  'Gols': '⚽', 'Resultado': '🏁', 'BTTS': '🎲', 'Cantos': '🚩',
  'Cartões': '🟨', 'Finalizações': '🎯', 'Handicaps': '⚖️', 'Dupla Chance': '🔀',
  'Gols Ambos Tempos': '⏱️', 'Placar Exato': '🔢', 'Handicap Europeu': '🏷️', 'Primeiro a Marcar': '🥇',
}

const SCRIPT_LABELS = {
  'high_scoring': { label: 'Alto Placar', color: 'var(--amber)', icon: '⚡' },
  'defensive':    { label: 'Defensivo', color: 'var(--accent)', icon: '🛡️' },
  'balanced':     { label: 'Equilibrado', color: 'var(--green)', icon: '⚖️' },
  'home_dominant':{ label: 'Mandante Dom.', color: 'var(--accent-light)', icon: '🏠' },
  'away_upset':   { label: 'Visitante Perigoso', color: 'var(--red)', icon: '⚠️' },
  'cup_game':     { label: 'Jogo de Copa', color: '#8b5cf6', icon: '🏆' },
  'derby':        { label: 'Derby/Clássico', color: '#ec4899', icon: '🔥' },
}

function useCountdown(isoDate) {
  const [diff, setDiff] = useState(null)
  useEffect(() => {
    if (!isoDate) return
    const update = () => setDiff(new Date(isoDate).getTime() - Date.now())
    update(); const t = setInterval(update, 1000); return () => clearInterval(t)
  }, [isoDate])
  if (diff === null) return null
  if (diff <= 0) return 'AO VIVO'
  const h = Math.floor(diff / 3600000); const m = Math.floor((diff % 3600000) / 60000); const s = Math.floor((diff % 60000) / 1000)
  if (h > 23) return null
  return `${h > 0 ? `${h}h ` : ''}${String(m).padStart(2, '0')}m ${String(s).padStart(2, '0')}s`
}

function TeamLogo({ logo, name, size = 48 }) {
  const [err, setErr] = useState(false)
  if (!logo || err) return (
    <div style={{ width: size, height: size, borderRadius: '50%', background: 'var(--accent-dim)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: size * 0.38, color: 'var(--accent-light)', fontWeight: 700, flexShrink: 0 }}>
      {name?.[0] || '?'}
    </div>
  )
  return <img src={logo} alt={name} style={{ width: size, height: size, objectFit: 'contain', flexShrink: 0 }} onError={() => setErr(true)} />
}

function ConfidenceBar({ value, max = 10 }) {
  const pct = Math.min(100, (value / max) * 100)
  let color = 'var(--red)'; if (value >= 7) color = 'var(--green)'; else if (value >= 5.5) color = 'var(--amber)'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1 }}>
      <div className="confidence-bar-track" style={{ flex: 1 }}>
        <div className="confidence-bar-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span style={{ fontSize: 12, fontWeight: 700, color, minWidth: 32, textAlign: 'right' }}>{value?.toFixed(1)}</span>
    </div>
  )
}

function OddsTrafficLight({ odd, probabilidade }) {
  if (!odd || !probabilidade) return null
  const edge = probabilidade - (1 / odd) * 100
  let color, label, cls
  if (edge >= 5) { color = 'var(--green)'; label = 'Valor'; cls = 'chip chip-green' }
  else if (edge >= -3) { color = 'var(--amber)'; label = 'Justo'; cls = 'chip chip-amber' }
  else { color = 'var(--red)'; label = 'Caro'; cls = 'chip chip-red' }
  return <span className={cls}>{label} {edge >= 0 ? '+' : ''}{edge.toFixed(1)}%</span>
}

function ConfidenceBreakdown({ bd }) {
  const [open, setOpen] = useState(false)
  const keys = Object.keys(bd).filter(k => k !== 'confianca_final' && k !== 'modificador_historico')
  if (keys.length === 0) return null
  return (
    <div style={{ marginTop: 6 }}>
      <button onClick={() => setOpen(o => !o)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 10, color: 'var(--text-faint)', padding: 0 }}>
        {open ? '▴' : '▾'} Detalhes de confiança
      </button>
      {open && (
        <div style={{ marginTop: 6, padding: '8px 10px', borderRadius: 'var(--radius-sm)', background: 'var(--accent-dim)', border: '1px solid rgba(99,102,241,0.1)', display: 'flex', flexWrap: 'wrap', gap: '4px 16px' }}>
          {keys.map(k => (
            <div key={k} style={{ fontSize: 10, color: 'var(--text-muted)' }}>
              <span style={{ color: 'var(--text-faint)' }}>{k.replace(/_/g, ' ')}: </span>
              <span style={{ color: 'var(--accent-light)', fontWeight: 600 }}>{typeof bd[k] === 'number' ? bd[k].toFixed(2) : String(bd[k])}</span>
            </div>
          ))}
          {bd.modificador_historico !== undefined && (
            <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>
              <span style={{ color: 'var(--text-faint)' }}>ajuste histórico: </span>
              <span style={{ color: bd.modificador_historico >= 0 ? 'var(--green)' : 'var(--red)', fontWeight: 600 }}>
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
  const isValue = palpite.is_value === true
  const edge = palpite.edge || 0
  return (
    <div style={{ padding: '13px 0', borderBottom: '1px solid var(--border-subtle)', display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, flexWrap: 'wrap' }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7, flexWrap: 'wrap', marginBottom: 5 }}>
            {rank === 0 && <span className="chip chip-accent">#1</span>}
            {isValue && (
              <span className="chip chip-green" style={{ fontWeight: 800, letterSpacing: '0.04em', fontSize: 10, padding: '2px 7px', background: 'rgba(34,197,94,0.18)', border: '1px solid rgba(34,197,94,0.4)' }}>
                🔥 VALUE +{edge.toFixed(1)}%
              </span>
            )}
            <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.01em' }}>{palpite.tipo}</span>
            {palpite.periodo && palpite.periodo !== 'FT' && (
              <span style={{ fontSize: 10, color: 'var(--text-muted)', background: 'var(--surface)', borderRadius: 'var(--radius-xs)', padding: '1px 5px' }}>{palpite.periodo}</span>
            )}
            {palpite.odd && <span style={{ fontSize: 12, color: 'var(--accent-light)', fontWeight: 700, marginLeft: 'auto' }}>@{typeof palpite.odd === 'number' ? palpite.odd.toFixed(2) : palpite.odd}</span>}
            <OddsTrafficLight odd={palpite.odd} probabilidade={palpite.probabilidade} />
          </div>
          {palpite.justificativa && <p style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.55, marginBottom: 7 }}>{palpite.justificativa}</p>}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 11, color: 'var(--text-faint)', minWidth: 60 }}>Confiança</span>
            <ConfidenceBar value={conf} />
          </div>
          {palpite.probabilidade > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 4 }}>
              <span style={{ fontSize: 11, color: 'var(--text-faint)', minWidth: 60 }}>Prob. Bot</span>
              <ConfidenceBar value={palpite.probabilidade} max={100} />
              <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: -20 }}>%</span>
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
  const filtrados = (mercado.palpites || []).filter(p => (p.confianca || 0) >= minConfianca)
  const topConf = filtrados[0]?.confianca || 0
  const hasValueBet = filtrados.some(p => p.is_value === true)
  if (filtrados.length === 0) return null
  return (
    <div className="card" style={{ marginBottom: 12, overflow: 'hidden', border: hasValueBet ? '1px solid rgba(34,197,94,0.35)' : undefined }}>
      <button onClick={() => setOpen(o => !o)} style={{
        width: '100%', display: 'flex', alignItems: 'center', gap: 10,
        padding: '12px 16px', cursor: 'pointer', background: 'transparent', border: 'none',
        borderBottom: open ? '1px solid var(--border-subtle)' : 'none',
      }}>
        <div style={{ width: 32, height: 32, borderRadius: 'var(--radius-sm)', background: 'var(--accent-dim)', border: '1px solid var(--accent-border)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 15, flexShrink: 0 }}>
          {icon}
        </div>
        <div style={{ flex: 1, textAlign: 'left' }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-secondary)', letterSpacing: '-0.01em' }}>{mercado.mercado}</div>
          <div style={{ fontSize: 11, color: 'var(--text-faint)', marginTop: 1 }}>{filtrados.length} palpite{filtrados.length !== 1 ? 's' : ''}</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
          {hasValueBet && <span style={{ fontSize: 10, fontWeight: 800, color: 'rgb(34,197,94)', background: 'rgba(34,197,94,0.12)', border: '1px solid rgba(34,197,94,0.35)', borderRadius: 4, padding: '2px 6px' }}>🔥 VALUE</span>}
          {topConf >= 7 && <span className="badge badge-green" style={{ fontSize: 10 }}>⭐ Top</span>}
          <span style={{ fontSize: 11, color: 'var(--text-faint)' }}>{open ? '▴' : '▾'}</span>
        </div>
      </button>
      {open && <div style={{ padding: '0 16px 4px' }}>{filtrados.map((p, i) => <PredictionRow key={i} palpite={p} rank={i} />)}</div>}
    </div>
  )
}

function FormaRecente({ forma, label, mediaMarcados, mediaSofridos }) {
  if (!forma || forma.length === 0) return null
  const getClass = r => { const u = String(r).toUpperCase(); if (u === 'W' || u === 'V') return 'forma-badge forma-w'; if (u === 'D' || u === 'E') return 'forma-badge forma-d'; return 'forma-badge forma-l' }
  const getLabel = r => { const u = String(r).toUpperCase(); if (u === 'W') return 'V'; if (u === 'L') return 'D'; return u }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
      <div style={{ fontSize: 10, color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</div>
      <div style={{ display: 'flex', gap: 4 }}>
        {forma.slice(0, 5).map((r, i) => <div key={i} className={getClass(r)}>{getLabel(r)}</div>)}
      </div>
      {(mediaMarcados != null || mediaSofridos != null) && (
        <div style={{ display: 'flex', gap: 8, marginTop: 1 }}>
          {mediaMarcados != null && <span style={{ fontSize: 9, color: 'var(--green)', fontWeight: 600 }}>⚽ {Number(mediaMarcados).toFixed(2)} marc.</span>}
          {mediaSofridos != null && <span style={{ fontSize: 9, color: 'var(--red)', fontWeight: 600 }}>🥅 {Number(mediaSofridos).toFixed(2)} sofr.</span>}
        </div>
      )}
    </div>
  )
}

function StatBar({ valCasa, valFora, label }) {
  const numC = parseFloat(valCasa) || 0; const numF = parseFloat(valFora) || 0; const total = numC + numF
  const pctC = total > 0 ? (numC / total) * 100 : 50; const pctF = 100 - pctC
  return (
    <>
      <div style={{ fontSize: 16, fontWeight: 800, textAlign: 'right', color: numC > numF ? 'var(--green)' : 'var(--text-primary)', letterSpacing: '-0.02em' }}>
        {valCasa !== undefined ? valCasa : '—'}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3, minWidth: 100 }}>
        <div style={{ fontSize: 10, color: 'var(--text-faint)', textAlign: 'center', fontWeight: 600, letterSpacing: '0.01em', whiteSpace: 'nowrap' }}>{label}</div>
        {total > 0 && (
          <div style={{ width: '100%', height: 3, borderRadius: 3, display: 'flex', overflow: 'hidden', background: 'var(--border)' }}>
            <div style={{ width: `${pctC}%`, background: 'var(--accent)', borderRadius: '3px 0 0 3px', transition: 'width 0.5s' }} />
            <div style={{ width: `${pctF}%`, background: 'var(--green)', borderRadius: '0 3px 3px 0', transition: 'width 0.5s' }} />
          </div>
        )}
      </div>
      <div style={{ fontSize: 16, fontWeight: 800, color: numF > numC ? 'var(--green)' : 'var(--text-primary)', letterSpacing: '-0.02em' }}>
        {valFora !== undefined ? valFora : '—'}
      </div>
    </>
  )
}

function StatsComparativas({ stats, timeCasa, timeFora }) {
  const emptyState = (msg = 'Estatísticas comparativas disponíveis após análise completa.') => (
    <div style={{ textAlign: 'center', padding: '40px 24px', color: 'var(--text-muted)', background: 'var(--surface)', borderRadius: 'var(--radius)', border: '1px dashed var(--border)' }}>
      <div style={{ fontSize: 32, marginBottom: 10 }}>📊</div>
      <p style={{ fontSize: 14 }}>{msg}</p>
    </div>
  )
  if (!stats || Object.keys(stats).length === 0) return emptyState()
  const rows = [
    { key: 'media_gols_marcados', label: 'Gols Marcados (méd.)' },
    { key: 'media_gols_sofridos', label: 'Gols Sofridos (méd.)' },
    { key: 'btts_percent', label: 'BTTS %' },
    { key: 'over25_percent', label: 'Over 2.5 %' },
    { key: 'media_cantos', label: 'Escanteios (méd.)' },
    { key: 'media_cartoes', label: 'Cartões (méd.)' },
    { key: 'media_finalizacoes', label: 'Finalizações (méd.)' },
    { key: 'avg_shots', label: 'Chutes (méd.)' },
    { key: 'posse_media', label: 'Posse de Bola %' },
    { key: 'avg_possession', label: 'Posse %' },
  ].filter(r => stats[`${r.key}_casa`] !== undefined || stats[`${r.key}_fora`] !== undefined)
  if (rows.length === 0) return emptyState('Sem métricas comparativas disponíveis para este jogo.')
  return (
    <div className="card" style={{ padding: '16px 18px' }}>
      <div className="stats-grid">
        <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--accent-light)', textAlign: 'right', paddingBottom: 6 }}>{timeCasa}</div>
        <div />
        <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--green)', paddingBottom: 6 }}>{timeFora}</div>
        {rows.map(r => <StatBar key={r.key} valCasa={stats[`${r.key}_casa`]} valFora={stats[`${r.key}_fora`]} label={r.label} />)}
      </div>
    </div>
  )
}

function PlayerStatRow({ record, color }) {
  const u5g = record.ultimos_5_gols || []; const u5a = record.ultimos_5_assistencias || []
  return (
    <div style={{ padding: '8px 0', borderBottom: '1px solid var(--border-subtle)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
        <div style={{ width: 24, height: 24, borderRadius: '50%', border: `1.5px solid ${color}40`, background: `${color}0e`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 8, fontWeight: 700, color, flexShrink: 0 }}>
          {record.nome?.split(' ').pop()?.slice(0, 3).toUpperCase() || '?'}
        </div>
        <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-primary)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {record.nome?.split(' ').pop() || `#${record.jogador_id}`}
        </span>
        <div style={{ display: 'flex', gap: 3, flexShrink: 0 }}>
          {record.gols > 0 && <span style={{ fontSize: 9 }}>⚽{record.gols > 1 ? record.gols : ''}</span>}
          {record.cartao_amarelo && <span style={{ fontSize: 9 }}>🟨</span>}
          {record.cartao_vermelho && <span style={{ fontSize: 9 }}>🟥</span>}
          {record.lesionado && <span style={{ fontSize: 9 }}>🏥</span>}
          {record.suspenso && <span style={{ fontSize: 9 }}>🚫</span>}
        </div>
      </div>
      <div style={{ display: 'flex', gap: 10, fontSize: 10, color: 'var(--text-muted)', flexWrap: 'wrap', paddingLeft: 30 }}>
        {record.media_gols != null && <span>⚽ Méd: <strong style={{ color: 'var(--text-secondary)' }}>{Number(record.media_gols).toFixed(2)}</strong></span>}
        {record.media_gols_casa != null && <span>🏠 <strong style={{ color: 'var(--accent-light)' }}>{Number(record.media_gols_casa).toFixed(2)}</strong></span>}
        {record.media_gols_fora != null && <span>✈️ <strong style={{ color: 'var(--green)' }}>{Number(record.media_gols_fora).toFixed(2)}</strong></span>}
        {record.n_jogos > 0 && <span>🎮 {record.n_jogos}j</span>}
        {record.amostra_pequena && <span style={{ color: 'var(--amber)' }}>⚠️ n&lt;6</span>}
      </div>
      {u5g.length > 0 && (
        <div style={{ display: 'flex', gap: 3, marginTop: 4, alignItems: 'center', paddingLeft: 30 }}>
          <span style={{ fontSize: 9, color: 'var(--text-faint)' }}>Gols ult.{u5g.length}:</span>
          {u5g.map((v, i) => <span key={i} style={{ fontSize: 9, fontWeight: 700, color: v > 0 ? 'var(--green)' : 'var(--text-faint)', background: v > 0 ? 'var(--green-dim)' : 'var(--surface)', borderRadius: 3, padding: '0 4px' }}>{v}</span>)}
          {u5a.length > 0 && <>
            <span style={{ fontSize: 9, color: 'var(--text-faint)', marginLeft: 4 }}>Ast:</span>
            {u5a.map((v, i) => <span key={i} style={{ fontSize: 9, fontWeight: 700, color: v > 0 ? 'var(--accent-light)' : 'var(--text-faint)', background: v > 0 ? 'var(--accent-dim)' : 'var(--surface)', borderRadius: 3, padding: '0 4px' }}>{v}</span>)}
          </>}
        </div>
      )}
    </div>
  )
}

function EscalacaoSection({ mandantes, visitantes, timeCasa, timeFora, lineupConfirmado = false }) {
  const titularesCasa = mandantes.filter(j => j.foi_titular); const reservasCasa = mandantes.filter(j => !j.foi_titular)
  const titularesFora = visitantes.filter(j => j.foi_titular); const reservasFora = visitantes.filter(j => !j.foi_titular)
  const semDados = titularesCasa.length === 0 && titularesFora.length === 0

  const toFormationRows = (players) => {
    const n = players.length
    if (n <= 1) return [players]
    if (n <= 4) return [[players[0]], players.slice(1)]
    if (n <= 7) return [[players[0]], players.slice(1, 4), players.slice(4)]
    if (n <= 9) return [[players[0]], players.slice(1, 5), players.slice(5, 8), players.slice(8)]
    return [[players[0]], players.slice(1, 5), players.slice(5, 8), players.slice(8, 11)]
  }

  if (semDados) return (
    <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-muted)', background: 'var(--surface)', borderRadius: 'var(--radius)', border: '1px dashed var(--border)' }}>
      <div style={{ fontSize: 32, marginBottom: 10 }}>🟩</div>
      <p style={{ fontSize: 14 }}>Escalação não confirmada para este jogo.</p>
      <p style={{ fontSize: 12, marginTop: 6, color: 'var(--text-faint)' }}>O lineup é divulgado normalmente 1 hora antes do jogo.</p>
    </div>
  )

  const PitchSVG = ({ players, teamName, color, flipped = false }) => {
    const W = 260; const H = 340
    const rows = toFormationRows(players)
    const rowsOrdered = flipped ? [...rows].reverse() : rows
    const formation = rows.map(r => r.length).slice(1).join('-')
    return (
      <div style={{ flex: 1, minWidth: 240 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
          <span style={{ fontSize: 12, fontWeight: 700, color }}>{flipped ? '✈️' : '🏠'} {teamName}</span>
          {formation && <span className="chip chip-accent">{formation}</span>}
        </div>
        <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: 'block', borderRadius: 10, overflow: 'hidden' }}>
          <rect x={0} y={0} width={W} height={H} rx={8} fill="rgba(34,197,94,0.03)" stroke="rgba(34,197,94,0.12)" strokeWidth={1} />
          <line x1={W/2} y1={0} x2={W/2} y2={H} stroke="rgba(34,197,94,0.09)" strokeWidth={1} />
          <line x1={0} y1={H/2} x2={W} y2={H/2} stroke="rgba(34,197,94,0.09)" strokeWidth={1} />
          <ellipse cx={W/2} cy={H/2} rx={40} ry={28} fill="none" stroke="rgba(34,197,94,0.1)" strokeWidth={1} />
          <rect x={W/2-36} y={0} width={72} height={44} rx={2} fill="none" stroke="rgba(34,197,94,0.1)" strokeWidth={1} />
          <rect x={W/2-36} y={H-44} width={72} height={44} rx={2} fill="none" stroke="rgba(34,197,94,0.1)" strokeWidth={1} />
          {rowsOrdered.map((row, ri) => {
            const yPct = (ri + 0.5) / rowsOrdered.length; const y = 24 + yPct * (H - 48)
            return row.map((j, pi) => {
              const xPct = (pi + 0.5) / row.length; const x = 20 + xPct * (W - 40)
              const label = j.nome ? j.nome.split(' ').pop()?.slice(0, 6) : `#${j.jogador_id}`
              const dotColor = j.lesionado ? '#ef4444' : j.suspenso ? '#f59e0b' : color
              return (
                <g key={`${ri}-${pi}`}>
                  <circle cx={x} cy={y} r={16} fill={`${dotColor}14`} stroke={dotColor} strokeWidth={1.5} />
                  <text x={x} y={y + 4} textAnchor="middle" fontSize={9} fontWeight="bold" fill={dotColor} style={{ fontFamily: 'system-ui, sans-serif', pointerEvents: 'none' }}>{label.slice(0, 4)}</text>
                  <text x={x} y={y + 26} textAnchor="middle" fontSize={8} fill="#94a3b8" style={{ fontFamily: 'system-ui, sans-serif', pointerEvents: 'none' }}>{label}</text>
                  {j.gols > 0 && <text x={x + 12} y={y - 8} fontSize={10} textAnchor="middle">⚽</text>}
                  {j.cartao_amarelo && !j.cartao_vermelho && <text x={x - 12} y={y - 8} fontSize={10} textAnchor="middle">🟨</text>}
                  {j.cartao_vermelho && <text x={x - 12} y={y - 8} fontSize={10} textAnchor="middle">🟥</text>}
                  {j.lesionado && <text x={x + 12} y={y + 10} fontSize={9} textAnchor="middle">🏥</text>}
                  {j.suspenso && !j.lesionado && <text x={x + 12} y={y + 10} fontSize={9} textAnchor="middle">🚫</text>}
                </g>
              )
            })
          })}
        </svg>
      </div>
    )
  }

  const BenchRow = ({ j, color }) => (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '3px 5px', borderRadius: 'var(--radius-xs)', background: 'var(--surface)' }}>
      <div style={{ width: 18, height: 18, borderRadius: '50%', border: `1px dashed ${color}38`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 7, color: 'var(--text-faint)', flexShrink: 0 }}>S</div>
      <span style={{ fontSize: 10, color: 'var(--text-muted)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {j.nome?.split(' ').pop() || `#${j.jogador_id}`}
      </span>
      <div style={{ display: 'flex', gap: 2, flexShrink: 0 }}>
        {j.gols > 0 && <span style={{ fontSize: 8 }}>⚽</span>}
        {j.cartao_amarelo && <span style={{ fontSize: 8 }}>🟨</span>}
        {j.cartao_vermelho && <span style={{ fontSize: 8 }}>🟥</span>}
        {j.lesionado && <span style={{ fontSize: 8 }}>🏥</span>}
        {j.suspenso && <span style={{ fontSize: 8 }}>🚫</span>}
      </div>
    </div>
  )

  return (
    <div>
      {lineupConfirmado
        ? <div style={{ padding: '6px 12px', background: 'var(--green-dim)', border: '1px solid var(--green-border)', borderRadius: 'var(--radius-sm)', marginBottom: 10, fontSize: 11, color: 'var(--green)', fontWeight: 600 }}>✅ Escalação confirmada</div>
        : <div style={{ padding: '6px 12px', background: 'var(--amber-dim)', border: '1px solid var(--amber-border)', borderRadius: 'var(--radius-sm)', marginBottom: 10, fontSize: 11, color: 'var(--amber)', fontWeight: 600 }}>⏳ Escalação não confirmada — provável lineup. 🏥 Lesionado · 🚫 Suspenso · 🟨 Amarelo · ⚽ Gol</div>
      }
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
        {titularesCasa.length > 0 && <PitchSVG players={titularesCasa} teamName={timeCasa} color="#818cf8" />}
        {titularesFora.length > 0 && <PitchSVG players={titularesFora} teamName={timeFora} color="#34d399" flipped />}
      </div>
      {(reservasCasa.length > 0 || reservasFora.length > 0) && (
        <div className="card" style={{ marginTop: 12, padding: '10px 14px' }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 6 }}>Banco de Reservas</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 4 }}>
            {reservasCasa.length > 0 && (
              <div>
                <div style={{ fontSize: 9, color: 'var(--text-faint)', fontWeight: 600, marginBottom: 3 }}>{timeCasa}</div>
                {reservasCasa.map((j, i) => <BenchRow key={i} j={j} color="#818cf8" />)}
              </div>
            )}
            {reservasFora.length > 0 && (
              <div>
                <div style={{ fontSize: 9, color: 'var(--text-faint)', fontWeight: 600, marginBottom: 3 }}>{timeFora}</div>
                {reservasFora.map((j, i) => <BenchRow key={i} j={j} color="#34d399" />)}
              </div>
            )}
          </div>
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
    fetch(`/api/jogadores/${fixtureId}`).then(r => r.json()).then(d => { setDados(d); setLoading(false) }).catch(() => setLoading(false))
  }, [fixtureId])

  if (loading) return (
    <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--text-muted)' }}>
      <div className="spinner" style={{ width: 28, height: 28, margin: '0 auto 8px' }} />
      <p style={{ fontSize: 13 }}>Carregando dados de jogadores...</p>
    </div>
  )

  const mandantes = dados?.mandantes || []; const visitantes = dados?.visitantes || []; const lineupConfirmado = dados?.lineup_confirmado ?? false
  if (mandantes.length === 0 && visitantes.length === 0) return (
    <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-muted)', background: 'var(--surface)', borderRadius: 'var(--radius)', border: '1px dashed var(--border)' }}>
      <div style={{ fontSize: 32, marginBottom: 10 }}>👥</div>
      <p style={{ fontSize: 14 }}>Sem dados de jogadores para este jogo.</p>
    </div>
  )

  return (
    <div>
      <div style={{ display: 'flex', gap: 4, marginBottom: 14 }}>
        {[{ id: 'escalacao', label: '👕 Escalação' }, { id: 'stats', label: '📊 Estatísticas' }].map(t => (
          <button key={t.id} onClick={() => setAba(t.id)} className={`pill${aba === t.id ? ' pill-active' : ''}`}>{t.label}</button>
        ))}
      </div>
      {aba === 'escalacao' && <EscalacaoSection mandantes={mandantes} visitantes={visitantes} timeCasa={timeCasa} timeFora={timeFora} lineupConfirmado={lineupConfirmado} />}
      {aba === 'stats' && (() => {
        const casa = mandantes.filter(r => r.foi_titular); const fora = visitantes.filter(r => r.foi_titular)
        if (casa.length === 0 && fora.length === 0) return (
          <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-muted)', background: 'var(--surface)', borderRadius: 'var(--radius)', border: '1px dashed var(--border)' }}>
            <p style={{ fontSize: 14 }}>Aguardando escalação confirmada para exibir estatísticas.</p>
          </div>
        )
        return (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 14 }}>
            <div className="card" style={{ padding: '14px 16px' }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--accent-light)', marginBottom: 10 }}>🏠 {timeCasa}</div>
              {casa.length === 0 ? <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>Sem titulares confirmados</p> : casa.map((r, i) => <PlayerStatRow key={i} record={r} color="#818cf8" />)}
            </div>
            <div className="card" style={{ padding: '14px 16px' }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--green)', marginBottom: 10 }}>✈️ {timeFora}</div>
              {fora.length === 0 ? <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>Sem titulares confirmados</p> : fora.map((r, i) => <PlayerStatRow key={i} record={r} color="#34d399" />)}
            </div>
          </div>
        )
      })()}
    </div>
  )
}

function H2HSection({ h2h, h2hSummary, timeCasa, timeFora }) {
  if (!h2h || h2h.length === 0) return (
    <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-muted)', background: 'var(--surface)', borderRadius: 'var(--radius)', border: '1px dashed var(--border)' }}>
      <div style={{ fontSize: 32, marginBottom: 10 }}>⚔️</div>
      <p style={{ fontSize: 14 }}>Sem dados de confrontos diretos armazenados.</p>
    </div>
  )
  return (
    <div>
      {h2hSummary && h2hSummary.total_jogos > 0 && (
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 14 }}>
          <div className="stat-box"><div className="stat-label">Gols/Jogo (H2H)</div><div className="stat-value">{h2hSummary.media_gols}</div><div className="stat-sub">{h2hSummary.total_jogos} confrontos</div></div>
          <div className="stat-box"><div className="stat-label">BTTS nos H2H</div><div className="stat-value">{h2hSummary.btts_freq}%</div><div className="stat-sub">ambos marcaram</div></div>
        </div>
      )}
      <div className="card" style={{ padding: '14px 16px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {h2h.map((jogo, i) => {
            const data = (jogo.data || jogo.date || '').slice(0, 4)
            const gc = jogo.gols_casa ?? jogo.home_goals ?? jogo.score_home ?? '?'
            const gf = jogo.gols_fora ?? jogo.away_goals ?? jogo.score_away ?? '?'
            const home = jogo.time_casa || jogo.home_team || timeCasa
            const away = jogo.time_fora || jogo.away_team || timeFora
            return (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '7px 10px', borderRadius: 'var(--radius-sm)', background: 'var(--surface)', border: '1px solid var(--border-subtle)' }}>
                <span style={{ fontSize: 11, color: 'var(--text-faint)', minWidth: 32, fontWeight: 500 }}>{data}</span>
                <span style={{ fontSize: 12, color: 'var(--text-secondary)', flex: 1, textAlign: 'right', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{home}</span>
                <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', background: 'var(--accent-dim)', borderRadius: 'var(--radius-sm)', padding: '2px 10px', minWidth: 50, textAlign: 'center', flexShrink: 0 }}>{gc} – {gf}</span>
                <span style={{ fontSize: 12, color: 'var(--text-secondary)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{away}</span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

function ArbitroSection({ arbitro, metadata }) {
  const nomeArbitro = arbitro || metadata?.arbitro || ''
  if (!nomeArbitro) return (
    <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-muted)', background: 'var(--surface)', borderRadius: 'var(--radius)', border: '1px dashed var(--border)' }}>
      <div style={{ fontSize: 32, marginBottom: 10 }}>🟨</div>
      <p style={{ fontSize: 14 }}>Árbitro não informado para este jogo.</p>
    </div>
  )
  const cartoesPorJogo = metadata?.arbitro_cartoes_por_jogo ?? null
  const penalusPorJogo = metadata?.arbitro_penaltis_por_jogo ?? null
  const estiloArbitro = metadata?.arbitro_estilo ?? null
  const estiloMap = { rigoroso: 'var(--red)', moderado: 'var(--amber)', permissivo: 'var(--green)' }
  const estiloCor = estiloArbitro ? (estiloMap[estiloArbitro] ?? 'var(--accent-light)') : null
  const hasRealStats = cartoesPorJogo !== null || penalusPorJogo !== null || estiloArbitro !== null
  return (
    <div className="card" style={{ padding: '18px 20px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: hasRealStats ? 16 : 0 }}>
        <div style={{ width: 48, height: 48, borderRadius: 13, background: 'var(--accent-dim)', border: '1px solid var(--border-accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 22, flexShrink: 0 }}>🟨</div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.01em' }}>{nomeArbitro}</div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>Árbitro Principal</div>
        </div>
        {estiloArbitro && (
          <div style={{ padding: '6px 12px', borderRadius: 'var(--radius)', background: `${estiloCor}10`, border: `1px solid ${estiloCor}28` }}>
            <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Estilo</div>
            <div style={{ fontSize: 13, fontWeight: 700, color: estiloCor, textTransform: 'capitalize' }}>{estiloArbitro}</div>
          </div>
        )}
      </div>
      {hasRealStats && (
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 4 }}>
          {cartoesPorJogo !== null && (
            <div className="stat-box">
              <div className="stat-label">Cartões / Jogo</div>
              <div className="stat-value" style={{ fontSize: 22, color: cartoesPorJogo >= 4 ? 'var(--red)' : cartoesPorJogo >= 3 ? 'var(--amber)' : 'var(--green)' }}>{Number(cartoesPorJogo).toFixed(1)}</div>
              <div className="stat-sub">média real</div>
            </div>
          )}
          {penalusPorJogo !== null && (
            <div className="stat-box">
              <div className="stat-label">Penaltis / Jogo</div>
              <div className="stat-value" style={{ fontSize: 22, color: penalusPorJogo >= 0.15 ? 'var(--red)' : 'var(--text-secondary)' }}>{Number(penalusPorJogo).toFixed(2)}</div>
              <div className="stat-sub">frequência real</div>
            </div>
          )}
        </div>
      )}
      {!hasRealStats && (
        <div style={{ marginTop: 14, padding: '10px 14px', background: 'var(--surface)', border: '1px dashed var(--border)', borderRadius: 'var(--radius-sm)' }}>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: 0 }}>Histórico detalhado do árbitro não disponível. Apenas o nome foi fornecido pela fonte de dados.</p>
        </div>
      )}
    </div>
  )
}

function TabelaClassificacao({ classificacao, timeCasa, timeFora }) {
  if (!classificacao || classificacao.length === 0) return (
    <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-muted)' }}><p style={{ fontSize: 14 }}>Sem dados de classificação disponíveis.</p></div>
  )
  const relevantes = classificacao.filter(t => t.team?.name === timeCasa || t.team?.name === timeFora || (t.rank && t.rank <= 5)).slice(0, 10)
  if (relevantes.length === 0) return null
  return (
    <div className="card" style={{ padding: '14px 16px' }}>
      <div style={{ overflowX: 'auto' }}>
        <table className="data-table">
          <thead>
            <tr>
              {['#', 'Time', 'J', 'V', 'E', 'D', 'Pts'].map(h => <th key={h} style={{ textAlign: h === 'Time' ? 'left' : 'center' }}>{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {relevantes.map((t, i) => {
              const hl = t.team?.name === timeCasa || t.team?.name === timeFora
              return (
                <tr key={i} style={{ background: hl ? 'var(--accent-dim)' : 'transparent' }}>
                  <td style={{ textAlign: 'center', color: 'var(--text-muted)', fontWeight: 600 }}>{t.rank}</td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      {t.team?.logo && <img src={t.team.logo} alt="" style={{ width: 15, height: 15, objectFit: 'contain' }} onError={e => e.target.style.display = 'none'} />}
                      <span style={{ color: hl ? 'var(--text-primary)' : 'var(--text-secondary)', fontWeight: hl ? 700 : 400, whiteSpace: 'nowrap' }}>{t.team?.name || ''}</span>
                    </div>
                  </td>
                  <td style={{ textAlign: 'center', color: 'var(--text-muted)' }}>{t.all?.played ?? '—'}</td>
                  <td style={{ textAlign: 'center', color: 'var(--green)' }}>{t.all?.win ?? '—'}</td>
                  <td style={{ textAlign: 'center', color: 'var(--amber)' }}>{t.all?.draw ?? '—'}</td>
                  <td style={{ textAlign: 'center', color: 'var(--red)' }}>{t.all?.lose ?? '—'}</td>
                  <td style={{ textAlign: 'center', color: 'var(--text-primary)', fontWeight: 700 }}>{t.points ?? '—'}</td>
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
  const info = SCRIPT_LABELS[script] || { label: script, color: 'var(--accent-light)', icon: '📋' }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <button onClick={() => reasoning && setShowReasoning(o => !o)} style={{
        display: 'inline-flex', alignItems: 'center', gap: 8, padding: '5px 12px',
        borderRadius: 'var(--radius)', background: 'var(--accent-dim)', border: '1px solid var(--border-accent)',
        cursor: reasoning ? 'pointer' : 'default',
      }}>
        <span style={{ fontSize: 15 }}>{info.icon}</span>
        <div>
          <div style={{ fontSize: 9, color: 'var(--text-muted)', fontWeight: 600 }}>Script Tático</div>
          <div style={{ fontSize: 12, fontWeight: 700, color: info.color }}>{info.label}</div>
        </div>
        {reasoning && <span style={{ fontSize: 10, color: 'var(--text-faint)', marginLeft: 2 }}>{showReasoning ? '▴' : '▾'}</span>}
      </button>
      {showReasoning && reasoning && (
        <div style={{ padding: '10px 14px', borderRadius: 'var(--radius-sm)', background: 'var(--accent-dim)', border: '1px solid var(--border-accent)', fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6, maxWidth: 480 }}>
          {reasoning}
        </div>
      )}
    </div>
  )
}

function SkeletonCard({ height = 80 }) {
  return <div className="skeleton-card" style={{ height, borderRadius: 'var(--radius)', marginBottom: 12 }} />
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
      if (r.status === 404) { setProcessing(false); setError('Jogo não encontrado. Verifique se o fixture é válido.'); return }
      const d = await r.json()
      if (d.status === 'ready') await checkStatus()
      else if (d.status === 'error') { setError(d.message || 'Erro na análise'); setProcessing(false) }
    } catch { setError('Erro ao iniciar análise'); setProcessing(false) }
  }, [fixtureId, checkStatus])

  useEffect(() => { const run = async () => { const found = await checkStatus(); if (!found && !processing) await triggerAnalise() }; run() }, [fixtureId])

  useEffect(() => {
    if (!processing) return
    const poll = setInterval(async () => { if (await checkStatus()) clearInterval(poll) }, 3000)
    return () => clearInterval(poll)
  }, [processing, checkStatus])

  useEffect(() => {
    const load = async () => {
      try {
        const r = await fetch('/api/jogos/hoje'); if (!r.ok) return
        const d = await r.json()
        const grupos = d.por_pais ? d.por_pais.flatMap(p => p.ligas || []) : (d.ligas || [])
        for (const g of grupos) for (const j of g.jogos || []) { if (j.fixture_id === parseInt(fixtureId)) { setJogoInfo(j); return } }
      } catch {}
    }; load()
  }, [fixtureId])

  const countdown = useCountdown(jogoInfo?.data_iso || analise?.data_jogo_iso)
  const isLast30 = (() => { const iso = jogoInfo?.data_iso || analise?.data_jogo_iso; if (!iso) return false; const ms = new Date(iso).getTime() - Date.now(); return ms > 0 && ms < 30 * 60 * 1000 })()

  if (loading) return (
    <div style={{ paddingTop: 24 }}>
      <div style={{ height: 14, width: 110, borderRadius: 5, background: 'var(--surface)', marginBottom: 24 }} />
      <SkeletonCard height={200} /><SkeletonCard height={48} /><SkeletonCard /><SkeletonCard /><SkeletonCard />
    </div>
  )

  if (processing) return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 400, gap: 14, paddingTop: 80, textAlign: 'center' }}>
      <div className="spinner" style={{ width: 44, height: 44 }} />
      <p style={{ color: '#c7d2fe', fontSize: 16, fontWeight: 700, letterSpacing: '-0.02em' }}>Analisando o jogo...</p>
      <p style={{ color: 'var(--text-muted)', fontSize: 13, maxWidth: 360, lineHeight: 1.5 }}>O sistema está processando estatísticas, odds e dados táticos. Isso pode levar até 60 segundos.</p>
      <div style={{ display: 'flex', gap: 5, marginTop: 6, flexWrap: 'wrap', justifyContent: 'center' }}>
        {['Estatísticas', 'Odds', 'H2H', 'Analistas', 'Palpites'].map((s, i) => <span key={i} className="chip chip-accent">{s}</span>)}
      </div>
    </div>
  )

  if (error) return (
    <div style={{ textAlign: 'center', paddingTop: 80 }}>
      <p style={{ color: 'var(--red)', fontSize: 14 }}>{error}</p>
      <Link to="/" style={{ color: 'var(--accent-light)', fontSize: 13, marginTop: 12, display: 'block' }}>← Voltar aos jogos</Link>
    </div>
  )

  if (!analise) return (
    <div style={{ textAlign: 'center', paddingTop: 80 }}>
      <p style={{ color: 'var(--text-muted)', fontSize: 14 }}>Análise não encontrada.</p>
      <Link to="/" style={{ color: 'var(--accent-light)', fontSize: 13, marginTop: 12, display: 'block' }}>← Voltar</Link>
    </div>
  )

  const todosMercados = [...(analise.mercados || [])].sort((a, b) => {
    const aMax = Math.max(...(a.palpites || []).map(p => p.confianca || 0))
    const bMax = Math.max(...(b.palpites || []).map(p => p.confianca || 0))
    return bMax - aMax
  })
  const mercadosDisponiveis = ['Todos', ...todosMercados.map(m => m.mercado)]
  const mercadosFiltrados = filtroMercado === 'Todos' ? todosMercados : todosMercados.filter(m => m.mercado === filtroMercado)
  const totalPalpitesVisiveis = mercadosFiltrados.reduce((acc, m) => acc + (m.palpites || []).filter(p => (p.confianca || 0) >= minConfianca).length, 0)
  const topPick = todosMercados.flatMap(m => m.palpites || []).sort((a, b) => (b.confianca || 0) - (a.confianca || 0))[0]
  const topMercado = todosMercados[0]
  const arbitroNome = analise.fixture_metadata?.arbitro || jogoInfo?.arbitro || ''
  const tabs = [
    { id: 'palpites', label: '🎯 Palpites' }, { id: 'analise', label: '📊 Análise' },
    { id: 'h2h', label: '⚔️ H2H' }, { id: 'jogadores', label: '👥 Jogadores' }, { id: 'arbitro', label: '🟨 Árbitro' },
    ...(analise.classificacao?.length > 0 ? [{ id: 'tabela', label: '🏆 Tabela' }] : []),
  ]

  const metaItems = [
    (analise.fixture_metadata?.rodada || jogoInfo?.rodada) && { icon: '📅', label: 'Rodada', value: analise.fixture_metadata?.rodada || jogoInfo?.rodada },
    (analise.fixture_metadata?.venue || jogoInfo?.venue) && { icon: '🏟️', label: 'Estádio', value: [analise.fixture_metadata?.venue || jogoInfo?.venue, analise.fixture_metadata?.venue_cidade || jogoInfo?.venue_cidade].filter(Boolean).join(', ') },
    arbitroNome && { icon: '🟨', label: 'Árbitro', value: arbitroNome },
    analise.fixture_metadata?.data_analise && { icon: '🕐', label: 'Analisado', value: new Date(analise.fixture_metadata.data_analise).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) },
  ].filter(Boolean)

  return (
    <div style={{ paddingTop: 24 }}>
      <Link to="/" style={{ fontSize: 13, color: 'var(--text-muted)', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 4, marginBottom: 20 }}>
        ← Voltar aos jogos
      </Link>

      {/* ── HERO ── */}
      <div className="section-card" style={{ marginBottom: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8, marginBottom: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            {jogoInfo?.liga?.logo && <img src={jogoInfo.liga.logo} alt="" style={{ width: 18, height: 18, objectFit: 'contain' }} onError={e => e.target.style.display = 'none'} />}
            <span style={{ fontSize: 11, color: 'var(--accent-light)', fontWeight: 700, letterSpacing: '0.02em' }}>{jogoInfo?.liga?.nome || analise.liga}</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            {analise.script_tatico && <ScriptTaticoCard script={analise.script_tatico} reasoning={analise.script_reasoning} />}
            {isLast30 && <span className="chip chip-red">🔴 Análise Final</span>}
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 24, marginBottom: 20, flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
            <TeamLogo logo={jogoInfo?.time_casa?.logo} name={analise.time_casa} size={52} />
            <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', textAlign: 'center', maxWidth: 120, letterSpacing: '-0.02em' }}>{analise.time_casa}</span>
            {analise.pos_casa && <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>#{analise.pos_casa} na tabela</span>}
            {analise.qsc_home != null && <span className="chip chip-accent">QSC {Number(analise.qsc_home).toFixed(0)}</span>}
          </div>
          <div style={{ textAlign: 'center', minWidth: 80 }}>
            <div style={{ fontSize: 20, fontWeight: 800, color: 'var(--text-secondary)', letterSpacing: '0.15em' }}>VS</div>
            {countdown && (
              <div style={{ fontSize: countdown === 'AO VIVO' ? 13 : 12, color: countdown === 'AO VIVO' ? 'var(--green)' : 'var(--accent-light)', fontWeight: 700, marginTop: 6 }}>
                {countdown === 'AO VIVO' ? '🟢 AO VIVO' : `⏱ ${countdown}`}
              </div>
            )}
            {!countdown && jogoInfo?.horario_brt && <div style={{ fontSize: 11, color: 'var(--text-faint)', marginTop: 4 }}>{jogoInfo.horario_brt}</div>}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
            <TeamLogo logo={jogoInfo?.time_fora?.logo} name={analise.time_fora} size={52} />
            <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', textAlign: 'center', maxWidth: 120, letterSpacing: '-0.02em' }}>{analise.time_fora}</span>
            {analise.pos_fora && <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>#{analise.pos_fora} na tabela</span>}
            {analise.qsc_away != null && <span className="chip chip-accent">QSC {Number(analise.qsc_away).toFixed(0)}</span>}
          </div>
        </div>

        {(analise.forma_recente_casa?.length > 0 || analise.forma_recente_fora?.length > 0) && (
          <div style={{ display: 'flex', justifyContent: 'space-around', marginBottom: 20, flexWrap: 'wrap', gap: 12 }}>
            <FormaRecente forma={analise.forma_recente_casa} label="Últimos 5 (Casa)" mediaMarcados={analise.stats_comparativas?.media_gols_marcados_casa} mediaSofridos={analise.stats_comparativas?.media_gols_sofridos_casa} />
            <FormaRecente forma={analise.forma_recente_fora} label="Últimos 5 (Fora)" mediaMarcados={analise.stats_comparativas?.media_gols_marcados_fora} mediaSofridos={analise.stats_comparativas?.media_gols_sofridos_fora} />
          </div>
        )}

        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <div className="stat-box"><div className="stat-label">Palpites</div><div className="stat-value">{analise.total_palpites}</div><div className="stat-sub">{analise.mercados?.length || 0} mercados</div></div>
          <div className="stat-box">
            <div className="stat-label">Top Confiança</div>
            <div className="stat-value" style={{ color: analise.melhor_confianca >= 7 ? 'var(--green)' : analise.melhor_confianca >= 5.5 ? 'var(--amber)' : 'var(--red)' }}>{analise.melhor_confianca?.toFixed(1)}/10</div>
            <div className="stat-sub">score máximo</div>
          </div>
          {topPick && (
            <div className="stat-box"><div className="stat-label">Top Pick</div><div className="stat-value" style={{ fontSize: 14 }}>{topPick.tipo}</div><div className="stat-sub">{topMercado?.mercado} · {topPick.confianca?.toFixed(1)}</div></div>
          )}
        </div>
      </div>

      {/* ── Meta chips ── */}
      {metaItems.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7, marginBottom: 14 }}>
          {metaItems.map((item, i) => (
            <div key={i} className="meta-chip">
              <span style={{ fontSize: 12 }}>{item.icon}</span>
              <span className="meta-chip-label">{item.label}:</span>
              <span className="meta-chip-value">{item.value}</span>
            </div>
          ))}
        </div>
      )}

      {/* ── Tabs ── */}
      <div style={{ display: 'flex', gap: 3, marginBottom: 14, overflowX: 'auto', paddingBottom: 2 }}>
        {tabs.map(tab => (
          <button key={tab.id} onClick={() => setActiveTab(tab.id)} className={`pill${activeTab === tab.id ? ' pill-active' : ''}`} style={{ whiteSpace: 'nowrap' }}>
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── Filter row (Palpites only) ── */}
      {activeTab === 'palpites' && (
        <div className="panel" style={{ marginBottom: 14 }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'center' }}>
            <div style={{ flex: 1, minWidth: 200 }}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Confiança mínima: <span style={{ color: 'var(--accent-light)', textTransform: 'none', letterSpacing: 0, fontWeight: 700 }}>{minConfianca.toFixed(1)}</span>
              </div>
              <input type="range" min="0" max="9" step="0.5" value={minConfianca} onChange={e => setMinConfianca(Number(e.target.value))} style={{ width: '100%', accentColor: 'var(--accent)' }} />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: 'var(--text-faint)', marginTop: 3 }}>
                <span>0 (todos)</span><span>5.5 (bom)</span><span>7+ (top)</span><span>9 (elite)</span>
              </div>
            </div>
            <div style={{ minWidth: 160 }}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Mercado</div>
              <select value={filtroMercado} onChange={e => setFiltroMercado(e.target.value)} className="token-select">
                {mercadosDisponiveis.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
          </div>
        </div>
      )}

      {/* ── Tab content ── */}
      {activeTab === 'palpites' && (
        <>
          {totalPalpitesVisiveis === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-muted)' }}>
              <div style={{ fontSize: 32, marginBottom: 10 }}>🔍</div>
              <p style={{ fontSize: 14 }}>Nenhum palpite com confiança ≥ {minConfianca.toFixed(1)}</p>
              <button onClick={() => { setMinConfianca(0); setFiltroMercado('Todos') }} className="pill pill-active" style={{ marginTop: 12, fontSize: 12, padding: '6px 16px' }}>Limpar filtros</button>
            </div>
          ) : (
            mercadosFiltrados.map((m, i) => <MarketCard key={i} mercado={m} minConfianca={minConfianca} />)
          )}
          {analise.mercados_vetados?.length > 0 && (
            <div style={{ marginTop: 18, padding: '13px 16px', background: 'var(--red-dim)', border: '1px solid var(--red-border)', borderRadius: 'var(--radius)' }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 10 }}>⛔ Mercados sem palpite (baixa confiança / dados insuficientes)</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                {analise.mercados_vetados.map((v, i) => (
                  <div key={i} title={v.motivo} className="chip chip-red" style={{ cursor: 'default' }}>⛔ {v.mercado}</div>
                ))}
              </div>
              <p style={{ fontSize: 10, color: 'var(--text-faint)', marginTop: 8, marginBottom: 0 }}>Passe o mouse sobre cada mercado para ver o motivo.</p>
            </div>
          )}
        </>
      )}

      {activeTab === 'analise' && <StatsComparativas stats={analise.stats_comparativas} timeCasa={analise.time_casa} timeFora={analise.time_fora} />}
      {activeTab === 'h2h' && <H2HSection h2h={analise.h2h} h2hSummary={analise.h2h_summary} timeCasa={analise.time_casa} timeFora={analise.time_fora} />}
      {activeTab === 'jogadores' && <JogadoresSection fixtureId={fixtureId} timeCasa={analise.time_casa} timeFora={analise.time_fora} />}
      {activeTab === 'arbitro' && <ArbitroSection arbitro={arbitroNome} metadata={analise.fixture_metadata} />}
      {activeTab === 'tabela' && <TabelaClassificacao classificacao={analise.classificacao} timeCasa={analise.time_casa} timeFora={analise.time_fora} />}
    </div>
  )
}
