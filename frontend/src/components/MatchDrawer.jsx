import { useState, useEffect, useCallback } from 'react'

const MARKET_ICONS = {
  'Gols': '⚽', 'Resultado': '🏁', 'BTTS': '🎲', 'Cantos': '🚩',
  'Cartões': '🟨', 'Finalizações': '🎯', 'Handicaps': '⚖️', 'Dupla Chance': '🔀',
  'Gols Ambos Tempos': '⏱️', 'Placar Exato': '🔢', 'Handicap Europeu': '🏷️', 'Primeiro a Marcar': '🥇',
}

const TABS = [
  { id: 'overview',  label: 'Visão Geral',   icon: '📊' },
  { id: 'lineup',    label: 'Escalações',    icon: '🟩' },
  { id: 'recent',    label: 'Últimos Jogos', icon: '🕐' },
  { id: 'stats',     label: 'Estatísticas',  icon: '📈' },
  { id: 'picks',     label: 'Previsões',     icon: '🎯' },
]

function TeamLogo({ logo, name, size = 48 }) {
  const [err, setErr] = useState(false)
  if (!logo || err) return (
    <div style={{
      width: size, height: size, borderRadius: '50%',
      background: 'var(--accent-dim)', border: '1px solid var(--accent-border)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: size * 0.38, color: 'var(--accent-light)', fontWeight: 700, flexShrink: 0,
    }}>
      {name?.[0] || '?'}
    </div>
  )
  return <img src={logo} alt={name} style={{ width: size, height: size, objectFit: 'contain', flexShrink: 0 }} onError={() => setErr(true)} />
}

function useCountdown(isoDate) {
  const [diff, setDiff] = useState(null)
  useEffect(() => {
    if (!isoDate) return
    const update = () => setDiff(new Date(isoDate).getTime() - Date.now())
    update(); const t = setInterval(update, 1000); return () => clearInterval(t)
  }, [isoDate])
  if (diff === null) return null
  if (diff <= 0) return '🔴 AO VIVO'
  const h = Math.floor(diff / 3600000); const m = Math.floor((diff % 3600000) / 60000); const s = Math.floor((diff % 60000) / 1000)
  if (h > 24) return null
  return h > 0 ? `${h}h ${String(m).padStart(2,'0')}m` : `${m}m ${String(s).padStart(2,'0')}s`
}

function ArcGauge({ pct, color, label, size = 90 }) {
  const r = 34; const cx = size / 2; const cy = size / 2
  const circumference = 2 * Math.PI * r
  const filled = (pct / 100) * circumference
  const gap = circumference - filled
  const startAngle = -Math.PI / 2
  const startX = cx + r * Math.cos(startAngle)
  const startY = cy + r * Math.sin(startAngle)
  return (
    <div className="prob-block" style={{ padding: '12px 6px' }}>
      <div style={{ position: 'relative', width: size, height: size }}>
        <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
          <circle cx={cx} cy={cy} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={7} />
          <circle
            cx={cx} cy={cy} r={r} fill="none"
            stroke={color} strokeWidth={7}
            strokeDasharray={`${filled} ${gap}`}
            strokeLinecap="round"
            style={{ transition: 'stroke-dasharray 0.8s cubic-bezier(0.4,0,0.2,1)' }}
          />
        </svg>
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        }}>
          <span style={{ fontSize: 15, fontWeight: 800, color, letterSpacing: '-0.03em', lineHeight: 1 }}>{pct}%</span>
        </div>
      </div>
      <div className="prob-label" style={{ marginTop: 4 }}>{label}</div>
    </div>
  )
}

function ProbArcs({ home, draw, away }) {
  return (
    <div className="prob-section" style={{ margin: '16px 0' }}>
      <ArcGauge pct={Number(home) || 33} color="#818cf8" label="Casa" />
      <ArcGauge pct={Number(draw) || 33} color="#fbbf24" label="Empate" />
      <ArcGauge pct={Number(away) || 34} color="#4ade80" label="Fora" />
    </div>
  )
}

function OverviewTab({ analise, jogadores }) {
  const data = analise?.dados || analise
  const jogo = data?.jogo || data?.fixture || {}
  const timeCasa = jogo.time_casa || data?.time_casa || {}
  const timeFora = jogo.time_fora || data?.time_fora || {}
  const liga = jogo.liga || data?.liga || {}
  const palpites = data?.palpites || data?.best_palpites || []

  const homeProb = data?.prob_casa ?? data?.probabilidade_casa
  const drawProb = data?.prob_empate ?? data?.probabilidade_empate
  const awayProb = data?.prob_fora ?? data?.probabilidade_fora

  const h2h = data?.h2h || []
  const topPicks = [...palpites].sort((a, b) => (b.confianca || 0) - (a.confianca || 0)).slice(0, 3)

  const countdown = useCountdown(jogo.data_iso || data?.data_iso)
  const lineupOk = data?.fixture_metadata?.lineup_confirmado || jogadores?.lineup_confirmado

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 16px', background: 'var(--surface)', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
        {liga.logo && <img src={liga.logo} alt="" style={{ width: 20, height: 20, objectFit: 'contain' }} onError={e => e.target.style.display='none'} />}
        <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--accent-light)', flex: 1 }}>{liga.nome || '—'}</span>
        {(jogo.horario_brt || data?.horario_brt) && (
          <span style={{ fontSize: 12, color: 'var(--text-secondary)', fontWeight: 700 }}>{jogo.horario_brt || data?.horario_brt}</span>
        )}
        {countdown && (
          <span style={{ fontSize: 11, color: countdown.includes('VIVO') ? 'var(--red)' : 'var(--text-muted)', fontWeight: 600 }}>{countdown}</span>
        )}
      </div>

      {lineupOk !== undefined && (
        <div style={{
          padding: '7px 12px',
          borderRadius: 'var(--radius-sm)',
          background: lineupOk ? 'var(--green-dim)' : 'var(--amber-dim)',
          border: `1px solid ${lineupOk ? 'var(--green-border)' : 'var(--amber-border)'}`,
          fontSize: 12, fontWeight: 600,
          color: lineupOk ? 'var(--green-light)' : 'var(--amber-light)',
        }}>
          {lineupOk ? '✅ Escalação confirmada' : '⏳ Lineup provável — confirma ~1h antes'}
        </div>
      )}

      {(homeProb != null || drawProb != null || awayProb != null) && (
        <div>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>Probabilidades</div>
          <ProbArcs home={homeProb != null ? Number(homeProb).toFixed(0) : null} draw={drawProb != null ? Number(drawProb).toFixed(0) : null} away={awayProb != null ? Number(awayProb).toFixed(0) : null} />
        </div>
      )}

      {topPicks.length > 0 && (
        <div>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>Top Previsões</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {topPicks.map((p, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '10px 14px', borderRadius: 'var(--radius)',
                background: 'var(--surface)', border: `1px solid ${(p.confianca||0) >= 7 ? 'var(--green-border)' : 'var(--border)'}`,
              }}>
                <span style={{ fontSize: 14 }}>{MARKET_ICONS[p.mercado] || '📊'}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>{p.tipo}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-faint)' }}>{p.mercado}</div>
                </div>
                {p.probabilidade != null && (
                  <span style={{ fontSize: 13, fontWeight: 800, color: (p.confianca||0) >= 7 ? 'var(--green-light)' : 'var(--amber-light)' }}>
                    {Number(p.probabilidade).toFixed(0)}%
                  </span>
                )}
                {p.odd && <span style={{ fontSize: 12, color: 'var(--accent-light)', fontWeight: 700 }}>@{Number(p.odd).toFixed(2)}</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {h2h.length > 0 && (
        <div>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>H2H Recente</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {h2h.slice(0, 3).map((g, i) => {
              const casa = g.time_casa?.nome || g.mandante || '?'
              const fora = g.time_fora?.nome || g.visitante || '?'
              const plac = g.placar || g.score || `${g.gols_casa ?? '?'}-${g.gols_fora ?? '?'}`
              return (
                <div key={i} className="last-game-row">
                  <span style={{ fontSize: 11, color: 'var(--text-secondary)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {casa} <span style={{ color: 'var(--text-faint)' }}>vs</span> {fora}
                  </span>
                  <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)', flexShrink: 0 }}>{plac}</span>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

function toFormationRows(players) {
  const n = players.length
  if (n <= 1) return [players]
  if (n <= 4) return [[players[0]], players.slice(1)]
  if (n <= 7) return [[players[0]], players.slice(1, 4), players.slice(4)]
  if (n <= 9) return [[players[0]], players.slice(1, 5), players.slice(5, 8), players.slice(8)]
  return [[players[0]], players.slice(1, 5), players.slice(5, 8), players.slice(8, 11)]
}

function PitchSVG({ players, teamName, color, flipped = false }) {
  const W = 240; const H = 320
  const rows = toFormationRows(players)
  const rowsOrdered = flipped ? [...rows].reverse() : rows
  const formation = rows.map(r => r.length).slice(1).join('-')
  return (
    <div style={{ flex: 1, minWidth: 220 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
        <span style={{ fontSize: 11, fontWeight: 700, color }}>{flipped ? '✈️' : '🏠'} {teamName}</span>
        {formation && <span className="chip chip-accent">{formation}</span>}
      </div>
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: 'block', borderRadius: 10, overflow: 'hidden' }}>
        <rect x={0} y={0} width={W} height={H} rx={8} fill="rgba(34,197,94,0.03)" stroke="rgba(34,197,94,0.12)" strokeWidth={1} />
        <line x1={W/2} y1={0} x2={W/2} y2={H} stroke="rgba(34,197,94,0.08)" strokeWidth={1} />
        <line x1={0} y1={H/2} x2={W} y2={H/2} stroke="rgba(34,197,94,0.08)" strokeWidth={1} />
        <ellipse cx={W/2} cy={H/2} rx={36} ry={24} fill="none" stroke="rgba(34,197,94,0.09)" strokeWidth={1} />
        <rect x={W/2-34} y={0} width={68} height={40} rx={2} fill="none" stroke="rgba(34,197,94,0.09)" strokeWidth={1} />
        <rect x={W/2-34} y={H-40} width={68} height={40} rx={2} fill="none" stroke="rgba(34,197,94,0.09)" strokeWidth={1} />
        {rowsOrdered.map((row, ri) => {
          const yPct = (ri + 0.5) / rowsOrdered.length; const y = 22 + yPct * (H - 44)
          return row.map((j, pi) => {
            const xPct = (pi + 0.5) / row.length; const x = 18 + xPct * (W - 36)
            const label = j.nome ? j.nome.split(' ').pop()?.slice(0, 5) : `#${j.jogador_id}`
            const dotColor = j.lesionado ? '#ef4444' : j.suspenso ? '#f59e0b' : color
            return (
              <g key={`${ri}-${pi}`}>
                <circle cx={x} cy={y} r={15} fill={`${dotColor}14`} stroke={dotColor} strokeWidth={1.5} />
                <text x={x} y={y+4} textAnchor="middle" fontSize={8} fontWeight="bold" fill={dotColor} style={{ fontFamily: 'system-ui, sans-serif', pointerEvents: 'none' }}>{label.slice(0,4)}</text>
                <text x={x} y={y+24} textAnchor="middle" fontSize={7} fill="#94a3b8" style={{ fontFamily: 'system-ui, sans-serif', pointerEvents: 'none' }}>{label}</text>
                {j.gols > 0 && <text x={x+11} y={y-7} fontSize={9} textAnchor="middle">⚽</text>}
                {j.cartao_amarelo && !j.cartao_vermelho && <text x={x-11} y={y-7} fontSize={9} textAnchor="middle">🟨</text>}
                {j.cartao_vermelho && <text x={x-11} y={y-7} fontSize={9} textAnchor="middle">🟥</text>}
                {j.lesionado && <text x={x+11} y={y+10} fontSize={8} textAnchor="middle">🏥</text>}
                {j.suspenso && !j.lesionado && <text x={x+11} y={y+10} fontSize={8} textAnchor="middle">🚫</text>}
              </g>
            )
          })
        })}
      </svg>
    </div>
  )
}

function LineupTab({ analise, jogadores }) {
  const data = analise?.dados || analise
  const jog = jogadores || {}
  const mandantes = jog.mandantes || []
  const visitantes = jog.visitantes || []
  const timeCasa = data?.jogo?.time_casa?.nome || data?.time_casa?.nome || ''
  const timeFora = data?.jogo?.time_fora?.nome || data?.time_fora?.nome || ''
  const lineupOk = jog.lineup_confirmado ?? data?.fixture_metadata?.lineup_confirmado

  const titCasa = mandantes.filter(j => j.foi_titular)
  const reseCasa = mandantes.filter(j => !j.foi_titular)
  const titFora = visitantes.filter(j => j.foi_titular)
  const reseFora = visitantes.filter(j => !j.foi_titular)

  if (titCasa.length === 0 && titFora.length === 0) return (
    <div style={{ textAlign: 'center', padding: '60px 24px', color: 'var(--text-muted)' }}>
      <div style={{ fontSize: 40, marginBottom: 12 }}>🟩</div>
      <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 6 }}>Escalação não disponível</div>
      <div style={{ fontSize: 12, color: 'var(--text-faint)' }}>O lineup é divulgado ~1h antes do jogo</div>
    </div>
  )

  return (
    <div>
      <div style={{ padding: '7px 12px', borderRadius: 'var(--radius-sm)', marginBottom: 12, fontSize: 11, fontWeight: 600,
        background: lineupOk ? 'var(--green-dim)' : 'var(--amber-dim)',
        border: `1px solid ${lineupOk ? 'var(--green-border)' : 'var(--amber-border)'}`,
        color: lineupOk ? 'var(--green-light)' : 'var(--amber-light)',
      }}>
        {lineupOk ? '✅ Escalação confirmada' : '⏳ Provável lineup — 🏥 Lesionado · 🚫 Suspenso · 🟨 Amarelo · ⚽ Gol'}
      </div>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        {titCasa.length > 0 && <PitchSVG players={titCasa} teamName={timeCasa} color="#818cf8" />}
        {titFora.length > 0 && <PitchSVG players={titFora} teamName={timeFora} color="#34d399" flipped />}
      </div>
      {(reseCasa.length > 0 || reseFora.length > 0) && (
        <div style={{ marginTop: 12, padding: '10px 14px', background: 'var(--surface)', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 8 }}>Banco de Reservas</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4 }}>
            {[...reseCasa.map(j => ({ ...j, _team: 'casa' })), ...reseFora.map(j => ({ ...j, _team: 'fora' }))].map((j, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '3px 5px', borderRadius: 'var(--radius-xs)', background: 'var(--surface-2)' }}>
                <div style={{ width: 16, height: 16, borderRadius: '50%', border: `1px dashed ${j._team === 'casa' ? '#818cf880' : '#34d39980'}`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 7, color: 'var(--text-faint)', flexShrink: 0 }}>S</div>
                <span style={{ fontSize: 10, color: 'var(--text-muted)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{j.nome?.split(' ').pop() || `#${j.jogador_id}`}</span>
                <div style={{ display: 'flex', gap: 2 }}>
                  {j.gols > 0 && <span style={{ fontSize: 8 }}>⚽</span>}
                  {j.cartao_amarelo && <span style={{ fontSize: 8 }}>🟨</span>}
                  {j.cartao_vermelho && <span style={{ fontSize: 8 }}>🟥</span>}
                  {j.lesionado && <span style={{ fontSize: 8 }}>🏥</span>}
                  {j.suspenso && <span style={{ fontSize: 8 }}>🚫</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function RecentTab({ analise }) {
  const data = analise?.dados || analise
  const timeCasa = data?.jogo?.time_casa?.nome || data?.time_casa?.nome || 'Casa'
  const timeFora = data?.jogo?.time_fora?.nome || data?.time_fora?.nome || 'Fora'

  const recentCasa = data?.ultimos_jogos_casa || data?.recent_home || []
  const recentFora = data?.ultimos_jogos_fora || data?.recent_away || []
  const formaCasa = data?.forma_casa || data?.jogo?.forma_casa || []
  const formaFora = data?.forma_fora || data?.jogo?.forma_fora || []

  const getResult = (r) => {
    const u = String(r || '').toUpperCase()
    if (u === 'W' || u === 'V') return { label: 'V', cls: 'forma-w' }
    if (u === 'D' || u === 'E') return { label: 'E', cls: 'forma-d' }
    return { label: 'D', cls: 'forma-l' }
  }

  if (recentCasa.length === 0 && recentFora.length === 0 && formaCasa.length === 0 && formaFora.length === 0) return (
    <div style={{ textAlign: 'center', padding: '60px 24px', color: 'var(--text-muted)' }}>
      <div style={{ fontSize: 40, marginBottom: 12 }}>🕐</div>
      <div style={{ fontSize: 14 }}>Dados de últimos jogos não disponíveis</div>
    </div>
  )

  const TeamRecent = ({ nome, jogos, forma }) => (
    <div style={{ flex: 1, minWidth: 200 }}>
      <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 8 }}>{nome}</div>
      {forma.length > 0 && (
        <div style={{ display: 'flex', gap: 4, marginBottom: 10 }}>
          {forma.slice(0, 5).map((r, i) => {
            const res = getResult(r)
            return <div key={i} className={`forma-badge ${res.cls}`}>{res.label}</div>
          })}
        </div>
      )}
      {jogos.length > 0 ? jogos.slice(0, 5).map((j, i) => {
        const oponent = j.adversario || j.opponent || j.time_fora?.nome || j.time_casa?.nome || '?'
        const score = j.placar || j.score || `${j.gols_marcados ?? '?'}-${j.gols_sofridos ?? '?'}`
        const res = getResult(j.resultado)
        const data = j.data ? j.data.slice(0, 10) : ''
        return (
          <div key={i} className="last-game-row" style={{ marginBottom: 4 }}>
            <div className={`forma-badge ${res.cls}`} style={{ flexShrink: 0 }}>{res.label}</div>
            <span style={{ fontSize: 11, color: 'var(--text-secondary)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{oponent}</span>
            <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)', flexShrink: 0 }}>{score}</span>
            {data && <span style={{ fontSize: 9, color: 'var(--text-faint)', flexShrink: 0 }}>{data.slice(5)}</span>}
          </div>
        )
      }) : (
        <div style={{ fontSize: 11, color: 'var(--text-faint)', padding: '8px 0' }}>Sem dados detalhados</div>
      )}
    </div>
  )

  return (
    <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
      <TeamRecent nome={timeCasa} jogos={recentCasa} forma={formaCasa} />
      <TeamRecent nome={timeFora} jogos={recentFora} forma={formaFora} />
    </div>
  )
}

function StatBar({ valCasa, valFora, label }) {
  const numC = parseFloat(valCasa) || 0; const numF = parseFloat(valFora) || 0; const total = numC + numF
  const pctC = total > 0 ? (numC / total) * 100 : 50; const pctF = 100 - pctC
  return (
    <>
      <div style={{ fontSize: 14, fontWeight: 800, textAlign: 'right', color: numC > numF ? 'var(--green)' : 'var(--text-primary)', letterSpacing: '-0.02em' }}>
        {valCasa !== undefined ? valCasa : '—'}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3, minWidth: 90 }}>
        <div style={{ fontSize: 9, color: 'var(--text-faint)', textAlign: 'center', fontWeight: 600, letterSpacing: '0.01em', whiteSpace: 'nowrap' }}>{label}</div>
        {total > 0 && (
          <div style={{ width: '100%', height: 3, borderRadius: 3, display: 'flex', overflow: 'hidden', background: 'var(--border)' }}>
            <div style={{ width: `${pctC}%`, background: 'var(--accent)', borderRadius: '3px 0 0 3px', transition: 'width 0.5s' }} />
            <div style={{ width: `${pctF}%`, background: 'var(--green)', borderRadius: '0 3px 3px 0', transition: 'width 0.5s' }} />
          </div>
        )}
      </div>
      <div style={{ fontSize: 14, fontWeight: 800, color: numF > numC ? 'var(--green)' : 'var(--text-primary)', letterSpacing: '-0.02em' }}>
        {valFora !== undefined ? valFora : '—'}
      </div>
    </>
  )
}

function StatsTab({ analise }) {
  const data = analise?.dados || analise
  const stats = data?.stats_comparativas || data?.estatisticas || {}
  const timeCasa = data?.jogo?.time_casa?.nome || data?.time_casa?.nome || 'Casa'
  const timeFora = data?.jogo?.time_fora?.nome || data?.time_fora?.nome || 'Fora'

  if (!stats || Object.keys(stats).length === 0) return (
    <div style={{ textAlign: 'center', padding: '60px 24px', color: 'var(--text-muted)' }}>
      <div style={{ fontSize: 40, marginBottom: 12 }}>📈</div>
      <div style={{ fontSize: 14 }}>Estatísticas comparativas não disponíveis</div>
    </div>
  )

  const rows = [
    { key: 'media_gols_marcados', label: 'Gols Marc. (méd.)' },
    { key: 'media_gols_sofridos', label: 'Gols Sofr. (méd.)' },
    { key: 'btts_percent',        label: 'BTTS %' },
    { key: 'over25_percent',      label: 'Over 2.5 %' },
    { key: 'media_cantos',        label: 'Escanteios (méd.)' },
    { key: 'media_cartoes',       label: 'Cartões (méd.)' },
    { key: 'media_finalizacoes',  label: 'Finalizações (méd.)' },
    { key: 'avg_shots',           label: 'Chutes (méd.)' },
    { key: 'posse_media',         label: 'Posse de Bola %' },
    { key: 'avg_possession',      label: 'Posse %' },
  ].filter(r => stats[`${r.key}_casa`] !== undefined || stats[`${r.key}_fora`] !== undefined)

  return (
    <div style={{ background: 'var(--surface)', borderRadius: 'var(--radius)', border: '1px solid var(--border)', padding: '14px 16px' }}>
      <div className="stats-grid">
        <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--accent-light)', textAlign: 'right', paddingBottom: 6, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{timeCasa}</div>
        <div />
        <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--green)', paddingBottom: 6, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{timeFora}</div>
        {rows.map(r => <StatBar key={r.key} valCasa={stats[`${r.key}_casa`]} valFora={stats[`${r.key}_fora`]} label={r.label} />)}
      </div>
    </div>
  )
}

function ConfidenceBar({ value, max = 10 }) {
  const pct = Math.min(100, (value / max) * 100)
  let color = 'var(--red)'; if (value >= 7) color = 'var(--green)'; else if (value >= 5.5) color = 'var(--amber)'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1 }}>
      <div className="confidence-bar-track" style={{ flex: 1 }}>
        <div className="confidence-bar-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span style={{ fontSize: 11, fontWeight: 700, color, minWidth: 28, textAlign: 'right' }}>{typeof value === 'number' ? value.toFixed(1) : value}</span>
    </div>
  )
}

function MarketCard({ mercado, minConfianca = 0 }) {
  const [open, setOpen] = useState(true)
  const icon = MARKET_ICONS[mercado.mercado] || '📊'
  const filtrados = (mercado.palpites || []).filter(p => (p.confianca || 0) >= minConfianca)
  const hasValueBet = filtrados.some(p => p.is_value === true)
  if (filtrados.length === 0) return null

  return (
    <div style={{ marginBottom: 10, borderRadius: 'var(--radius)', border: hasValueBet ? '1px solid rgba(34,197,94,0.35)' : '1px solid var(--border)', background: 'var(--surface)', overflow: 'hidden' }}>
      <button onClick={() => setOpen(o => !o)} style={{
        width: '100%', display: 'flex', alignItems: 'center', gap: 10,
        padding: '11px 14px', cursor: 'pointer', background: 'transparent', border: 'none',
        borderBottom: open ? '1px solid var(--border-subtle)' : 'none',
      }}>
        <div style={{ width: 28, height: 28, borderRadius: 'var(--radius-sm)', background: 'var(--accent-dim)', border: '1px solid var(--accent-border)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, flexShrink: 0 }}>
          {icon}
        </div>
        <div style={{ flex: 1, textAlign: 'left' }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-secondary)' }}>{mercado.mercado}</div>
          <div style={{ fontSize: 10, color: 'var(--text-faint)', marginTop: 1 }}>{filtrados.length} palpite{filtrados.length !== 1 ? 's' : ''}</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {hasValueBet && <span style={{ fontSize: 9, fontWeight: 800, color: 'rgb(34,197,94)', background: 'rgba(34,197,94,0.12)', border: '1px solid rgba(34,197,94,0.35)', borderRadius: 4, padding: '2px 5px' }}>🔥 VALUE</span>}
          <span style={{ fontSize: 10, color: 'var(--text-faint)' }}>{open ? '▴' : '▾'}</span>
        </div>
      </button>
      {open && (
        <div style={{ padding: '0 14px 4px' }}>
          {filtrados.map((p, i) => (
            <div key={i} style={{ padding: '10px 0', borderBottom: i < filtrados.length - 1 ? '1px solid var(--border-subtle)' : 'none', display: 'flex', flexDirection: 'column', gap: 6 }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, flexWrap: 'wrap' }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap', marginBottom: 4 }}>
                    {i === 0 && <span className="chip chip-accent">#1</span>}
                    {p.is_value && <span style={{ fontSize: 9, fontWeight: 800, color: 'var(--green-light)', background: 'var(--green-dim)', border: '1px solid var(--green-border)', borderRadius: 4, padding: '1px 5px' }}>🔥 VALUE +{(p.edge||0).toFixed(1)}%</span>}
                    <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)' }}>{p.tipo}</span>
                    {p.odd && <span style={{ fontSize: 11, color: 'var(--accent-light)', fontWeight: 700, marginLeft: 'auto' }}>@{Number(p.odd).toFixed(2)}</span>}
                  </div>
                  {p.justificativa && <p style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.5, marginBottom: 5 }}>{p.justificativa}</p>}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 10, color: 'var(--text-faint)', minWidth: 54 }}>Confiança</span>
                    <ConfidenceBar value={p.confianca || 0} />
                  </div>
                  {p.probabilidade > 0 && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 3 }}>
                      <span style={{ fontSize: 10, color: 'var(--text-faint)', minWidth: 54 }}>Prob. Bot</span>
                      <ConfidenceBar value={p.probabilidade} max={100} />
                      <span style={{ fontSize: 10, color: 'var(--text-muted)', marginLeft: -18 }}>%</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function PicksTab({ analise }) {
  const data = analise?.dados || analise
  const mercados = data?.mercados || []

  if (mercados.length === 0) return (
    <div style={{ textAlign: 'center', padding: '60px 24px', color: 'var(--text-muted)' }}>
      <div style={{ fontSize: 40, marginBottom: 12 }}>🎯</div>
      <div style={{ fontSize: 14 }}>Sem previsões disponíveis</div>
    </div>
  )

  return (
    <div>
      {mercados.map((m, i) => <MarketCard key={i} mercado={m} />)}
    </div>
  )
}

export default function MatchDrawer({ fixtureId, jogo, onClose, initialReady = false }) {
  const [tab, setTab] = useState('overview')
  const [analise, setAnalise] = useState(null)
  const [jogadores, setJogadores] = useState(null)
  const [status, setStatus] = useState((jogo?.tem_analise || initialReady) ? 'ready' : 'none')
  const [loadingAnalise, setLoadingAnalise] = useState(false)

  useEffect(() => {
    setTab('overview')
    setAnalise(null)
    setJogadores(null)
    setStatus((jogo?.tem_analise || initialReady) ? 'ready' : 'none')
  }, [fixtureId, jogo?.tem_analise, initialReady])

  useEffect(() => {
    if (status !== 'ready' || !fixtureId) return
    setLoadingAnalise(true)
    Promise.all([
      fetch(`/api/analise/${fixtureId}`).then(r => r.json()).catch(() => null),
      fetch(`/api/jogadores/${fixtureId}`).then(r => r.json()).catch(() => null),
    ]).then(([a, j]) => {
      setAnalise(a)
      setJogadores(j)
      setLoadingAnalise(false)
    })
  }, [status, fixtureId])

  useEffect(() => {
    if (status !== 'processing') return
    const poll = setInterval(async () => {
      try {
        const r = await fetch(`/api/status/${fixtureId}`)
        const d = await r.json()
        if (d.status === 'ready') { setStatus('ready'); clearInterval(poll) }
        if (d.status === 'error') { setStatus('none'); clearInterval(poll) }
      } catch { clearInterval(poll) }
    }, 3000)
    return () => clearInterval(poll)
  }, [status, fixtureId])

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const handleAnalyze = async () => {
    if (status === 'processing') return
    setStatus('processing')
    try {
      const r = await fetch(`/api/analisar/${fixtureId}`, { method: 'POST' })
      const d = await r.json()
      if (d.status === 'ready') setStatus('ready')
    } catch { setStatus('none') }
  }

  const isProcessing = status === 'processing'
  const isReady = status === 'ready'

  const data = analise?.dados || analise
  const timeCasa = jogo?.time_casa || data?.jogo?.time_casa || data?.time_casa || {}
  const timeFora = jogo?.time_fora || data?.jogo?.time_fora || data?.time_fora || {}
  const liga = jogo?.liga || data?.jogo?.liga || data?.liga || {}

  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} />
      <div className="drawer-panel">
        <div className="drawer-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
            <button onClick={onClose} style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', color: 'var(--text-muted)', cursor: 'pointer', padding: '4px 10px', fontSize: 13, flexShrink: 0, lineHeight: 1.5 }}>
              ✕
            </button>
            <div style={{ flex: 1, minWidth: 0 }}>
              {liga.logo && <img src={liga.logo} alt="" style={{ width: 14, height: 14, objectFit: 'contain', marginRight: 5, verticalAlign: 'middle' }} onError={e => e.target.style.display='none'} />}
              <span style={{ fontSize: 11, color: 'var(--accent-light)', fontWeight: 600 }}>{liga.nome}</span>
            </div>
            {isProcessing && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'var(--accent-light)' }}>
                <div className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} />
                Analisando...
              </div>
            )}
            {!isReady && !isProcessing && (
              <button onClick={handleAnalyze} style={{
                background: 'linear-gradient(135deg, var(--accent), #8b5cf6)',
                color: '#fff', border: 'none', borderRadius: 'var(--radius-sm)',
                padding: '6px 14px', fontSize: 12, fontWeight: 700, cursor: 'pointer',
                boxShadow: '0 2px 12px rgba(99,102,241,0.4)',
              }}>
                Analisar →
              </button>
            )}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 0, paddingBottom: 16 }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, flex: 1 }}>
              <TeamLogo logo={timeCasa.logo} name={timeCasa.nome} size={52} />
              <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', textAlign: 'center', lineHeight: 1.2 }}>{timeCasa.nome || '—'}</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, padding: '0 12px', flexShrink: 0 }}>
              <span style={{ fontSize: 11, color: 'var(--text-faint)', fontWeight: 700, letterSpacing: '0.06em' }}>VS</span>
              {(jogo?.horario_brt || data?.horario_brt) && (
                <span style={{ fontSize: 13, color: 'var(--text-secondary)', fontWeight: 700 }}>
                  {jogo?.horario_brt || data?.horario_brt}
                </span>
              )}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, flex: 1 }}>
              <TeamLogo logo={timeFora.logo} name={timeFora.nome} size={52} />
              <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', textAlign: 'center', lineHeight: 1.2 }}>{timeFora.nome || '—'}</span>
            </div>
          </div>
        </div>

        {isReady && (
          <div className="drawer-tabs">
            {TABS.map(t => (
              <button key={t.id} className={`drawer-tab${tab === t.id ? ' active' : ''}`} onClick={() => setTab(t.id)}>
                <span>{t.icon}</span>
                <span>{t.label}</span>
              </button>
            ))}
          </div>
        )}

        <div className="drawer-body">
          {isProcessing && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 200, gap: 14 }}>
              <div className="spinner" style={{ width: 40, height: 40 }} />
              <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>Processando análise...</div>
            </div>
          )}

          {!isReady && !isProcessing && (
            <div style={{ textAlign: 'center', padding: '48px 24px', color: 'var(--text-muted)' }}>
              <div style={{ fontSize: 40, marginBottom: 12 }}>🔮</div>
              <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 6 }}>Jogo não analisado</div>
              <div style={{ fontSize: 12, color: 'var(--text-faint)', marginBottom: 20 }}>Clique em "Analisar" para gerar previsões e estatísticas para este jogo.</div>
              <button onClick={handleAnalyze} style={{
                background: 'linear-gradient(135deg, var(--accent), #8b5cf6)',
                color: '#fff', border: 'none', borderRadius: 'var(--radius)',
                padding: '10px 24px', fontSize: 13, fontWeight: 700, cursor: 'pointer',
                boxShadow: '0 4px 16px rgba(99,102,241,0.4)',
              }}>
                Analisar Agora →
              </button>
            </div>
          )}

          {isReady && loadingAnalise && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 200, gap: 14 }}>
              <div className="spinner" style={{ width: 32, height: 32 }} />
              <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>Carregando dados...</div>
            </div>
          )}

          {isReady && !loadingAnalise && (
            <>
              {tab === 'overview' && <OverviewTab analise={analise} jogadores={jogadores} />}
              {tab === 'lineup' && <LineupTab analise={analise} jogadores={jogadores} />}
              {tab === 'recent' && <RecentTab analise={analise} />}
              {tab === 'stats' && <StatsTab analise={analise} />}
              {tab === 'picks' && <PicksTab analise={analise} />}
            </>
          )}
        </div>
      </div>
    </>
  )
}
