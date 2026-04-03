import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

const API_BASE = ''

function TaxaBadge({ taxa }) {
  const pct = parseFloat(taxa) || 0
  let bg, color
  if (pct >= 65) { bg = 'rgba(34,197,94,0.15)'; color = '#22c55e' }
  else if (pct >= 50) { bg = 'rgba(99,102,241,0.15)'; color = '#818cf8' }
  else if (pct >= 40) { bg = 'rgba(234,179,8,0.15)'; color = '#eab308' }
  else { bg = 'rgba(239,68,68,0.15)'; color = '#f87171' }

  return (
    <span
      style={{
        background: bg,
        color,
        padding: '2px 10px',
        borderRadius: 99,
        fontWeight: 700,
        fontSize: 13,
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
    <span style={{ color: positive ? '#22c55e' : '#f87171', fontWeight: 600, fontSize: 13 }}>
      {positive ? '+' : ''}{val.toFixed(2)}u
    </span>
  )
}

function AcertouBadge({ acertou }) {
  if (acertou === true) return (
    <span style={{ color: '#22c55e', fontWeight: 700, fontSize: 13 }}>✓ Acertou</span>
  )
  if (acertou === false) return (
    <span style={{ color: '#f87171', fontWeight: 700, fontSize: 13 }}>✗ Errou</span>
  )
  return <span style={{ color: '#64748b', fontSize: 13 }}>—</span>
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
            <stop offset="0%" stopColor="#6366f1" stopOpacity="0.25" />
            <stop offset="100%" stopColor="#6366f1" stopOpacity="0.02" />
          </linearGradient>
        </defs>

        {/* Grid lines */}
        {yLabels.map(v => (
          <line
            key={v}
            x1={PAD_L} y1={toY(v)} x2={W - PAD_R} y2={toY(v)}
            stroke="rgba(99,102,241,0.12)" strokeWidth={1}
          />
        ))}

        {/* 55% reference line */}
        {55 >= minTaxa && 55 <= maxTaxa && (
          <line
            x1={PAD_L} y1={toY(55)} x2={W - PAD_R} y2={toY(55)}
            stroke="rgba(234,179,8,0.35)" strokeWidth={1} strokeDasharray="4,3"
          />
        )}

        {/* Area fill */}
        <polygon points={areaPoints} fill="url(#areaGrad)" />

        {/* Line */}
        <polyline
          points={pts}
          fill="none"
          stroke="#6366f1"
          strokeWidth={2}
          strokeLinejoin="round"
          strokeLinecap="round"
        />

        {/* Dots */}
        {evolucao.map((d, i) => (
          <circle
            key={i}
            cx={toX(i)}
            cy={toY(d.taxa_acerto)}
            r={evolucao.length > 20 ? 2 : 3}
            fill={d.taxa_acerto >= 55 ? '#22c55e' : d.taxa_acerto >= 40 ? '#6366f1' : '#f87171'}
          />
        ))}

        {/* Y-axis labels */}
        {yLabels.map(v => (
          <text
            key={v}
            x={PAD_L - 6}
            y={toY(v) + 4}
            textAnchor="end"
            fill="#64748b"
            fontSize={10}
          >
            {v}%
          </text>
        ))}

        {/* X-axis labels */}
        {xLabels.map(({ i, label }) => (
          <text
            key={i}
            x={toX(i)}
            y={H - 4}
            textAnchor="middle"
            fill="#64748b"
            fontSize={10}
          >
            {label}
          </text>
        ))}

        {/* 55% label */}
        {55 >= minTaxa && 55 <= maxTaxa && (
          <text x={W - PAD_R - 2} y={toY(55) - 3} textAnchor="end" fill="rgba(234,179,8,0.6)" fontSize={9}>
            55%
          </text>
        )}
      </svg>

      {/* Tooltip legend */}
      <div style={{ display: 'flex', gap: 16, marginTop: 8, flexWrap: 'wrap', fontSize: 11, color: '#64748b' }}>
        <span><span style={{ color: '#22c55e' }}>●</span> ≥ 55% acerto</span>
        <span><span style={{ color: '#6366f1' }}>●</span> 40-55%</span>
        <span><span style={{ color: '#f87171' }}>●</span> &lt; 40%</span>
        <span style={{ color: 'rgba(234,179,8,0.7)' }}>— meta 55%</span>
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
    background: 'rgba(255,255,255,0.04)',
    border: '1px solid rgba(99,102,241,0.12)',
    borderRadius: 14,
    padding: '20px 24px',
  }

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '80px 0', color: '#94a3b8' }}>
        <div style={{ fontSize: 32, marginBottom: 12 }}>⏳</div>
        <div>Carregando performance...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div style={{ textAlign: 'center', padding: '80px 0', color: '#f87171' }}>
        <div style={{ fontSize: 32, marginBottom: 12 }}>⚠️</div>
        <div>Erro ao carregar dados de performance</div>
        <div style={{ fontSize: 12, color: '#64748b', marginTop: 8 }}>{error}</div>
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

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', paddingTop: 32 }}>
      <div style={{ marginBottom: 28 }}>
        <div style={{ fontSize: 22, fontWeight: 700, color: '#f1f5f9', marginBottom: 4 }}>
          Performance Histórica
        </div>
        <div style={{ fontSize: 13, color: '#64748b' }}>
          Acurácia e ROI acumulado por mercado — atualizado nightly às 03:00 BRT
        </div>
      </div>

      {semDados ? (
        <div style={{ ...cardStyle, textAlign: 'center', padding: '60px 24px' }}>
          <div style={{ fontSize: 40, marginBottom: 16 }}>📊</div>
          <div style={{ fontSize: 16, fontWeight: 600, color: '#f1f5f9', marginBottom: 8 }}>
            Ainda sem dados de performance
          </div>
          <div style={{ fontSize: 13, color: '#64748b', maxWidth: 420, margin: '0 auto' }}>
            Os dados aparecem automaticamente após os primeiros jogos analisados e avaliados
            pelo job noturno (03:00 BRT). Analise alguns jogos e aguarde o encerramento deles.
          </div>
          <Link
            to="/"
            style={{
              display: 'inline-block',
              marginTop: 24,
              padding: '10px 24px',
              background: 'linear-gradient(135deg,#6366f1,#8b5cf6)',
              borderRadius: 10,
              color: '#fff',
              fontWeight: 600,
              fontSize: 14,
              textDecoration: 'none',
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
              gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
              gap: 16,
              marginBottom: 32,
            }}
          >
            {[
              { label: 'Palpites Avaliados', value: resumo.total_palpites_avaliados ?? 0 },
              { label: 'Total de Acertos', value: resumo.total_acertos ?? 0 },
              {
                label: 'Taxa de Acerto Geral',
                value: `${(resumo.taxa_acerto_geral ?? 0).toFixed(1)}%`,
                color: (resumo.taxa_acerto_geral ?? 0) >= 55 ? '#22c55e' : '#f87171',
              },
              {
                label: 'ROI Total',
                value: `${(resumo.roi_total ?? 0) >= 0 ? '+' : ''}${(resumo.roi_total ?? 0).toFixed(2)}u`,
                color: (resumo.roi_total ?? 0) >= 0 ? '#22c55e' : '#f87171',
              },
            ].map(({ label, value, color }) => (
              <div key={label} style={cardStyle}>
                <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
                  {label}
                </div>
                <div style={{ fontSize: 26, fontWeight: 700, color: color || '#f1f5f9' }}>
                  {value}
                </div>
              </div>
            ))}
          </div>

          {/* ── Evolução de Acerto (30 dias) ── */}
          <div style={{ ...cardStyle, marginBottom: 32 }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: '#f1f5f9', marginBottom: 6 }}>
              Evolução de Acerto — Últimos 30 Dias
            </div>
            <div style={{ fontSize: 12, color: '#64748b', marginBottom: 18 }}>
              Taxa de acerto diária dos palpites avaliados
            </div>
            <EvolucaoChart evolucao={evolucao} />
          </div>

          {/* ── Performance por Mercado ── */}
          {mercados.length > 0 && (
            <div style={{ ...cardStyle, marginBottom: 32 }}>
              <div style={{ fontSize: 15, fontWeight: 700, color: '#f1f5f9', marginBottom: 18 }}>
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
                            padding: '8px 12px',
                            textAlign: h === 'Mercado' ? 'left' : 'center',
                            color: '#64748b',
                            fontWeight: 600,
                            borderBottom: '1px solid rgba(99,102,241,0.12)',
                            whiteSpace: 'nowrap',
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
                        style={{ background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)' }}
                      >
                        <td style={{ padding: '10px 12px', color: '#f1f5f9', fontWeight: 600 }}>
                          {m.mercado}
                        </td>
                        <td style={{ padding: '10px 12px', textAlign: 'center', color: '#94a3b8' }}>
                          {m.total_palpites}
                        </td>
                        <td style={{ padding: '10px 12px', textAlign: 'center', color: '#22c55e' }}>
                          {m.total_acertos}
                        </td>
                        <td style={{ padding: '10px 12px', textAlign: 'center', color: '#f87171' }}>
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
            <div style={{ ...cardStyle, marginBottom: 32 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12, marginBottom: 18 }}>
                <div style={{ fontSize: 15, fontWeight: 700, color: '#f1f5f9' }}>
                  Performance por Liga
                </div>
                <select
                  value={ligaFiltro || ''}
                  onChange={e => setLigaFiltro(e.target.value || null)}
                  style={{
                    background: 'rgba(255,255,255,0.06)',
                    border: '1px solid rgba(99,102,241,0.2)',
                    borderRadius: 8,
                    color: '#e2e8f0',
                    padding: '6px 12px',
                    fontSize: 13,
                    cursor: 'pointer',
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
                            padding: '8px 12px',
                            textAlign: h === 'Mercado' || h === 'Liga' ? 'left' : 'center',
                            color: '#64748b',
                            fontWeight: 600,
                            borderBottom: '1px solid rgba(99,102,241,0.12)',
                            whiteSpace: 'nowrap',
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
                        style={{ background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)' }}
                      >
                        <td style={{ padding: '9px 12px', color: '#f1f5f9', fontWeight: 600 }}>
                          {r.mercado}
                        </td>
                        <td style={{ padding: '9px 12px', color: '#94a3b8' }}>
                          {r.liga_nome}
                        </td>
                        <td style={{ padding: '9px 12px', textAlign: 'center', color: '#94a3b8' }}>
                          {r.n_amostras}
                        </td>
                        <td style={{ padding: '9px 12px', textAlign: 'center', color: '#22c55e' }}>
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
              <div style={{ fontSize: 15, fontWeight: 700, color: '#f1f5f9', marginBottom: 18 }}>
                Últimos Palpites Avaliados
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {ultimos.map(p => (
                  <div
                    key={p.id}
                    style={{
                      background: 'rgba(255,255,255,0.03)',
                      border: `1px solid ${p.acertou ? 'rgba(34,197,94,0.18)' : 'rgba(239,68,68,0.18)'}`,
                      borderRadius: 10,
                      padding: '12px 16px',
                      display: 'flex',
                      flexWrap: 'wrap',
                      alignItems: 'center',
                      gap: 12,
                    }}
                  >
                    <AcertouBadge acertou={p.acertou} />

                    <div style={{ flex: 1, minWidth: 200 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: '#f1f5f9' }}>
                        {p.time_casa || '—'} vs {p.time_fora || '—'}
                      </div>
                      <div style={{ fontSize: 11, color: '#64748b', marginTop: 2 }}>
                        {p.liga || ''} {p.data_jogo ? `· ${p.data_jogo.slice(0, 10)}` : ''}
                      </div>
                    </div>

                    <div style={{ minWidth: 140 }}>
                      <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 2 }}>
                        {p.mercado} · {p.periodo}
                      </div>
                      <div style={{ fontSize: 13, fontWeight: 600, color: '#e2e8f0' }}>
                        {p.linha}
                      </div>
                    </div>

                    <div style={{ textAlign: 'right', minWidth: 90 }}>
                      <div style={{ fontSize: 11, color: '#64748b', marginBottom: 2 }}>
                        Conf. {p.confianca}/10
                        {p.odd != null ? ` · @${p.odd.toFixed(2)}` : ''}
                      </div>
                      <RoiBadge roi={p.roi_unitario} />
                    </div>
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
