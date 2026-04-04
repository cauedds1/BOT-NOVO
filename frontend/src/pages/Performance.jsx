import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

const API_BASE = ''

function TaxaBadge({ taxa }) {
  const pct = parseFloat(taxa) || 0
  let bg, color
  if (pct >= 65) { bg = 'rgba(34,197,94,0.1)'; color = '#4ade80' }
  else if (pct >= 50) { bg = 'rgba(99,102,241,0.1)'; color = '#818cf8' }
  else if (pct >= 40) { bg = 'rgba(245,158,11,0.1)'; color = '#fbbf24' }
  else { bg = 'rgba(239,68,68,0.1)'; color = '#f87171' }

  return (
    <span
      style={{
        background: bg,
        color,
        padding: '2px 10px',
        borderRadius: 99,
        fontWeight: 700,
        fontSize: 12,
        minWidth: 52,
        display: 'inline-block',
        textAlign: 'center',
      }}
    >
      {pct.toFixed(1)}%
    </span>
  )
}

function RoiBadge({ roi }) {
  const val = parseFloat(roi) || 0
  const positive = val >= 0
  return (
    <span style={{ color: positive ? '#4ade80' : '#f87171', fontWeight: 700, fontSize: 12 }}>
      {positive ? '+' : ''}{val.toFixed(2)}u
    </span>
  )
}

function AcertouBadge({ acertou }) {
  if (acertou === true) return (
    <span style={{ color: '#4ade80', fontWeight: 700, fontSize: 12 }}>✓ Acertou</span>
  )
  if (acertou === false) return (
    <span style={{ color: '#f87171', fontWeight: 700, fontSize: 12 }}>✗ Errou</span>
  )
  return <span style={{ color: '#64748b', fontSize: 12 }}>—</span>
}

function EvolucaoChart({ evolucao }) {
  if (!evolucao || evolucao.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '32px 0', color: '#64748b', fontSize: 13 }}>
        Sem dados de evolução nos últimos 30 dias
      </div>
    )
  }

  const W = 700
  const H = 160
  const PAD_L = 44
  const PAD_R = 16
  const PAD_T = 16
  const PAD_B = 32

  const chartW = W - PAD_L - PAD_R
  const chartH = H - PAD_T - PAD_B

  const taxas = evolucao.map(d => d.taxa_acerto)
  const minTaxa = Math.max(0, Math.min(...taxas) - 5)
  const maxTaxa = Math.min(100, Math.max(...taxas) + 5)

  const toX = (i) => PAD_L + (i / (evolucao.length - 1 || 1)) * chartW
  const toY = (t) => PAD_T + chartH - ((t - minTaxa) / (maxTaxa - minTaxa || 1)) * chartH

  const pts = evolucao.map((d, i) => `${toX(i)},${toY(d.taxa_acerto)}`).join(' ')
  const areaPoints = [
    `${toX(0)},${PAD_T + chartH}`,
    ...evolucao.map((d, i) => `${toX(i)},${toY(d.taxa_acerto)}`),
    `${toX(evolucao.length - 1)},${PAD_T + chartH}`,
  ].join(' ')

  const yLabels = [minTaxa, (minTaxa + maxTaxa) / 2, maxTaxa].map(v => Math.round(v))

  const formatDate = (str) => {
    const parts = str.split('-')
    if (parts.length === 3) return `${parts[2]}/${parts[1]}`
    return str
  }

  const xLabels = evolucao.length <= 10
    ? evolucao.map((d, i) => ({ i, label: formatDate(d.data) }))
    : [0, Math.floor(evolucao.length / 2), evolucao.length - 1].map(i => ({
        i,
        label: formatDate(evolucao[i].data),
      }))

  return (
    <div style={{ overflowX: 'auto' }}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        style={{ width: '100%', maxWidth: W, display: 'block' }}
        aria-label="Evolução da taxa de acerto diária"
      >
        <defs>
          <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#6366f1" stopOpacity="0.2" />
            <stop offset="100%" stopColor="#6366f1" stopOpacity="0.01" />
          </linearGradient>
        </defs>

        {yLabels.map(v => (
          <line
            key={v}
            x1={PAD_L} y1={toY(v)} x2={W - PAD_R} y2={toY(v)}
            stroke="rgba(255,255,255,0.05)" strokeWidth={1}
          />
        ))}

        {55 >= minTaxa && 55 <= maxTaxa && (
          <line
            x1={PAD_L} y1={toY(55)} x2={W - PAD_R} y2={toY(55)}
            stroke="rgba(245,158,11,0.3)" strokeWidth={1} strokeDasharray="4,3"
          />
        )}

        <polygon points={areaPoints} fill="url(#areaGrad)" />

        <polyline
          points={pts}
          fill="none"
          stroke="#6366f1"
          strokeWidth={2}
          strokeLinejoin="round"
          strokeLinecap="round"
        />

        {evolucao.map((d, i) => (
          <circle
            key={i}
            cx={toX(i)}
            cy={toY(d.taxa_acerto)}
            r={evolucao.length > 20 ? 2 : 3}
            fill={d.taxa_acerto >= 55 ? '#22c55e' : d.taxa_acerto >= 40 ? '#6366f1' : '#f87171'}
          />
        ))}

        {yLabels.map(v => (
          <text
            key={v}
            x={PAD_L - 6}
            y={toY(v) + 4}
            textAnchor="end"
            fill="#4b5563"
            fontSize={10}
          >
            {v}%
          </text>
        ))}

        {xLabels.map(({ i, label }) => (
          <text
            key={i}
            x={toX(i)}
            y={H - 4}
            textAnchor="middle"
            fill="#4b5563"
            fontSize={10}
          >
            {label}
          </text>
        ))}

        {55 >= minTaxa && 55 <= maxTaxa && (
          <text x={W - PAD_R - 2} y={toY(55) - 3} textAnchor="end" fill="rgba(245,158,11,0.5)" fontSize={9}>
            55%
          </text>
        )}
      </svg>

      <div style={{ display: 'flex', gap: 14, marginTop: 8, flexWrap: 'wrap', fontSize: 11, color: '#64748b' }}>
        <span><span style={{ color: '#22c55e' }}>●</span> ≥ 55% acerto</span>
        <span><span style={{ color: '#6366f1' }}>●</span> 40–55%</span>
        <span><span style={{ color: '#f87171' }}>●</span> &lt; 40%</span>
        <span style={{ color: 'rgba(245,158,11,0.65)' }}>— meta 55%</span>
      </div>
    </div>
  )
}

export default function Performance() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [ligaFiltro, setLigaFiltro] = useState(null)

  useEffect(() => {
    setLoading(true)
    fetch(`${API_BASE}/api/performance`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [])

  const cardStyle = {
    background: 'rgba(255,255,255,0.03)',
    border: '1px solid rgba(255,255,255,0.07)',
    borderRadius: 14,
    padding: '18px 22px',
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 320, gap: 14, paddingTop: 60 }}>
        <div className="spinner" style={{ width: 40, height: 40 }} />
        <div style={{ color: '#64748b', fontSize: 14 }}>Carregando performance...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 320, gap: 12, paddingTop: 60 }}>
        <div style={{ fontSize: 32 }}>⚠️</div>
        <div style={{ color: '#f87171', fontSize: 14 }}>Erro ao carregar dados de performance</div>
        <div style={{ fontSize: 12, color: '#64748b', marginTop: 4 }}>{error}</div>
      </div>
    )
  }

  const resumo = data?.resumo || {}
  const mercados = data?.mercados || []
  const evolucao = data?.evolucao || []
  const porLiga = data?.por_liga || []
  const ultimos = data?.ultimos_palpites || []
  const semDados = mercados.length === 0 && ultimos.length === 0

  const ligasDisponiveis = [...new Set(porLiga.map(r => r.liga_nome))].sort()
  const porLigaFiltrado = ligaFiltro
    ? porLiga.filter(r => r.liga_nome === ligaFiltro)
    : porLiga

  const thStyle = {
    padding: '7px 12px',
    color: '#64748b',
    fontWeight: 600,
    borderBottom: '1px solid rgba(255,255,255,0.06)',
    whiteSpace: 'nowrap',
    fontSize: 11,
    textTransform: 'uppercase',
    letterSpacing: '0.04em',
  }

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', paddingTop: 32 }}>
      <div style={{ marginBottom: 28 }}>
        <div style={{ fontSize: 22, fontWeight: 700, color: '#f1f5f9', marginBottom: 4, letterSpacing: '-0.03em' }}>
          Performance Histórica
        </div>
        <div style={{ fontSize: 13, color: '#64748b' }}>
          Acurácia e ROI acumulado por mercado — atualizado nightly às 03:00 BRT
        </div>
      </div>

      {semDados ? (
        <div style={{ ...cardStyle, textAlign: 'center', padding: '56px 24px' }}>
          <div style={{ fontSize: 40, marginBottom: 16 }}>📊</div>
          <div style={{ fontSize: 16, fontWeight: 700, color: '#f1f5f9', marginBottom: 8, letterSpacing: '-0.02em' }}>
            Ainda sem dados de performance
          </div>
          <div style={{ fontSize: 13, color: '#64748b', maxWidth: 420, margin: '0 auto', lineHeight: 1.6 }}>
            Os dados aparecem automaticamente após os primeiros jogos analisados e avaliados
            pelo job noturno (03:00 BRT). Analise alguns jogos e aguarde o encerramento deles.
          </div>
          <Link
            to="/"
            style={{
              display: 'inline-block',
              marginTop: 24,
              padding: '10px 22px',
              background: 'linear-gradient(135deg,#6366f1,#8b5cf6)',
              borderRadius: 9,
              color: '#fff',
              fontWeight: 700,
              fontSize: 14,
              textDecoration: 'none',
              letterSpacing: '-0.01em',
            }}
          >
            Ver Jogos de Hoje
          </Link>
        </div>
      ) : (
        <>
          {/* ── Resumo Global ── */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(175px, 1fr))',
              gap: 14,
              marginBottom: 28,
            }}
          >
            {[
              { label: 'Palpites Avaliados', value: resumo.total_palpites_avaliados ?? 0 },
              { label: 'Total de Acertos', value: resumo.total_acertos ?? 0 },
              {
                label: 'Taxa de Acerto Geral',
                value: `${(resumo.taxa_acerto_geral ?? 0).toFixed(1)}%`,
                color: (resumo.taxa_acerto_geral ?? 0) >= 55 ? '#4ade80' : '#f87171',
              },
              {
                label: 'ROI Total',
                value: `${(resumo.roi_total ?? 0) >= 0 ? '+' : ''}${(resumo.roi_total ?? 0).toFixed(2)}u`,
                color: (resumo.roi_total ?? 0) >= 0 ? '#4ade80' : '#f87171',
              },
            ].map(({ label, value, color }) => (
              <div key={label} style={cardStyle}>
                <div style={{ fontSize: 10, color: '#64748b', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 9 }}>
                  {label}
                </div>
                <div style={{ fontSize: 28, fontWeight: 800, color: color || '#f1f5f9', letterSpacing: '-0.03em' }}>
                  {value}
                </div>
              </div>
            ))}
          </div>

          {/* ── Evolução de Acerto (30 dias) ── */}
          <div style={{ ...cardStyle, marginBottom: 28 }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: '#f1f5f9', marginBottom: 4, letterSpacing: '-0.01em' }}>
              Evolução de Acerto — Últimos 30 Dias
            </div>
            <div style={{ fontSize: 12, color: '#64748b', marginBottom: 18 }}>
              Taxa de acerto diária dos palpites avaliados
            </div>
            <EvolucaoChart evolucao={evolucao} />
          </div>

          {/* ── Performance por Mercado ── */}
          {mercados.length > 0 && (
            <div style={{ ...cardStyle, marginBottom: 28 }}>
              <div style={{ fontSize: 14, fontWeight: 700, color: '#f1f5f9', marginBottom: 18, letterSpacing: '-0.01em' }}>
                Performance por Mercado
              </div>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                  <thead>
                    <tr>
                      {['Mercado', 'Palpites', 'Acertos', 'Erros', 'Taxa de Acerto', 'ROI Total'].map(h => (
                        <th
                          key={h}
                          style={{
                            ...thStyle,
                            textAlign: h === 'Mercado' ? 'left' : 'center',
                          }}
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {mercados.map((m, i) => (
                      <tr
                        key={m.mercado}
                        style={{ background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.015)' }}
                      >
                        <td style={{ padding: '10px 12px', color: '#f1f5f9', fontWeight: 700, fontSize: 13 }}>
                          {m.mercado}
                        </td>
                        <td style={{ padding: '10px 12px', textAlign: 'center', color: '#94a3b8', fontSize: 13 }}>
                          {m.total_palpites}
                        </td>
                        <td style={{ padding: '10px 12px', textAlign: 'center', color: '#4ade80', fontSize: 13 }}>
                          {m.total_acertos}
                        </td>
                        <td style={{ padding: '10px 12px', textAlign: 'center', color: '#f87171', fontSize: 13 }}>
                          {m.total_erros}
                        </td>
                        <td style={{ padding: '10px 12px', textAlign: 'center' }}>
                          <TaxaBadge taxa={m.taxa_acerto} />
                        </td>
                        <td style={{ padding: '10px 12px', textAlign: 'center' }}>
                          <RoiBadge roi={m.roi_total} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ── Performance por Liga ── */}
          {porLiga.length > 0 && (
            <div style={{ ...cardStyle, marginBottom: 28 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12, marginBottom: 18 }}>
                <div style={{ fontSize: 14, fontWeight: 700, color: '#f1f5f9', letterSpacing: '-0.01em' }}>
                  Performance por Liga
                </div>
                <select
                  value={ligaFiltro || ''}
                  onChange={e => setLigaFiltro(e.target.value || null)}
                  style={{
                    background: 'rgba(255,255,255,0.05)',
                    border: '1px solid rgba(255,255,255,0.1)',
                    borderRadius: 7,
                    color: '#e2e8f0',
                    padding: '5px 12px',
                    fontSize: 12,
                    cursor: 'pointer',
                    outline: 'none',
                  }}
                >
                  <option value="">Todas as ligas</option>
                  {ligasDisponiveis.map(l => (
                    <option key={l} value={l}>{l}</option>
                  ))}
                </select>
              </div>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                  <thead>
                    <tr>
                      {['Mercado', 'Liga', 'Amostras', 'Acertos', 'Taxa de Acerto', 'ROI'].map(h => (
                        <th
                          key={h}
                          style={{
                            ...thStyle,
                            textAlign: h === 'Mercado' || h === 'Liga' ? 'left' : 'center',
                          }}
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {porLigaFiltrado.slice(0, 50).map((r, i) => (
                      <tr
                        key={`${r.mercado}-${r.liga_id}`}
                        style={{ background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.015)' }}
                      >
                        <td style={{ padding: '9px 12px', color: '#f1f5f9', fontWeight: 700 }}>
                          {r.mercado}
                        </td>
                        <td style={{ padding: '9px 12px', color: '#94a3b8' }}>
                          {r.liga_nome}
                        </td>
                        <td style={{ padding: '9px 12px', textAlign: 'center', color: '#94a3b8' }}>
                          {r.n_amostras}
                        </td>
                        <td style={{ padding: '9px 12px', textAlign: 'center', color: '#4ade80' }}>
                          {r.total_acertos}
                        </td>
                        <td style={{ padding: '9px 12px', textAlign: 'center' }}>
                          <TaxaBadge taxa={r.taxa_acerto} />
                        </td>
                        <td style={{ padding: '9px 12px', textAlign: 'center' }}>
                          <RoiBadge roi={r.roi_total} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {porLigaFiltrado.length > 50 && (
                <div style={{ fontSize: 12, color: '#64748b', marginTop: 12, textAlign: 'center' }}>
                  Mostrando 50 de {porLigaFiltrado.length} entradas
                </div>
              )}
            </div>
          )}

          {/* ── Últimos Palpites Avaliados ── */}
          {ultimos.length > 0 && (
            <div style={cardStyle}>
              <div style={{ fontSize: 14, fontWeight: 700, color: '#f1f5f9', marginBottom: 16, letterSpacing: '-0.01em' }}>
                Últimos Palpites Avaliados
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {ultimos.map(p => (
                  <div
                    key={p.id}
                    style={{
                      background: 'rgba(255,255,255,0.025)',
                      border: `1px solid ${p.acertou ? 'rgba(34,197,94,0.15)' : 'rgba(239,68,68,0.15)'}`,
                      borderRadius: 9,
                      padding: '11px 14px',
                      display: 'flex',
                      flexWrap: 'wrap',
                      alignItems: 'center',
                      gap: 10,
                    }}
                  >
                    <AcertouBadge acertou={p.acertou} />
                    <span style={{ fontSize: 12, fontWeight: 700, color: '#e2e8f0', flex: 1, minWidth: 120 }}>
                      {p.tipo}
                    </span>
                    <span style={{ fontSize: 11, color: '#64748b', background: 'rgba(255,255,255,0.04)', borderRadius: 5, padding: '2px 8px' }}>
                      {p.mercado}
                    </span>
                    {p.odd && (
                      <span style={{ fontSize: 11, color: '#818cf8', fontWeight: 700 }}>
                        @{Number(p.odd).toFixed(2)}
                      </span>
                    )}
                    <RoiBadge roi={p.roi} />
                    {p.liga_nome && (
                      <span style={{ fontSize: 10, color: '#4b5563', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 140 }}>
                        {p.liga_nome}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
