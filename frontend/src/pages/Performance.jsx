import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

function TaxaBadge({ taxa }) {
  const pct = parseFloat(taxa) || 0
  let cls = 'badge-red'
  if (pct >= 65) cls = 'badge-green'
  else if (pct >= 50) cls = 'badge-blue'
  else if (pct >= 40) cls = 'badge-yellow'
  return <span className={`badge ${cls}`} style={{ minWidth: 52, justifyContent: 'center' }}>{pct.toFixed(1)}%</span>
}

function RoiBadge({ roi }) {
  const val = parseFloat(roi) || 0
  return <span style={{ color: val >= 0 ? 'var(--green-light)' : 'var(--red)', fontWeight: 700, fontSize: 12 }}>{val >= 0 ? '+' : ''}{val.toFixed(2)}u</span>
}

function AcertouBadge({ acertou }) {
  if (acertou === true)  return <span style={{ color: 'var(--green-light)', fontWeight: 700, fontSize: 12 }}>✓ Acertou</span>
  if (acertou === false) return <span style={{ color: 'var(--red)', fontWeight: 700, fontSize: 12 }}>✗ Errou</span>
  return <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>—</span>
}

function EvolucaoChart({ evolucao }) {
  if (!evolucao || evolucao.length === 0) return (
    <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--text-muted)', fontSize: 13 }}>
      Sem dados de evolução nos últimos 30 dias
    </div>
  )

  const W = 700; const H = 160; const PAD_L = 44; const PAD_R = 16; const PAD_T = 16; const PAD_B = 32
  const chartW = W - PAD_L - PAD_R; const chartH = H - PAD_T - PAD_B
  const taxas = evolucao.map(d => d.taxa_acerto)
  const minTaxa = Math.max(0, Math.min(...taxas) - 5); const maxTaxa = Math.min(100, Math.max(...taxas) + 5)
  const toX = i => PAD_L + (i / (evolucao.length - 1 || 1)) * chartW
  const toY = t => PAD_T + chartH - ((t - minTaxa) / (maxTaxa - minTaxa || 1)) * chartH
  const pts = evolucao.map((d, i) => `${toX(i)},${toY(d.taxa_acerto)}`).join(' ')
  const areaPoints = [`${toX(0)},${PAD_T + chartH}`, ...evolucao.map((d, i) => `${toX(i)},${toY(d.taxa_acerto)}`), `${toX(evolucao.length - 1)},${PAD_T + chartH}`].join(' ')
  const yLabels = [minTaxa, (minTaxa + maxTaxa) / 2, maxTaxa].map(v => Math.round(v))
  const formatDate = str => { const p = str.split('-'); return p.length === 3 ? `${p[2]}/${p[1]}` : str }
  const xLabels = evolucao.length <= 10
    ? evolucao.map((d, i) => ({ i, label: formatDate(d.data) }))
    : [0, Math.floor(evolucao.length / 2), evolucao.length - 1].map(i => ({ i, label: formatDate(evolucao[i].data) }))

  return (
    <div style={{ overflowX: 'auto' }}>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', maxWidth: W, display: 'block' }}>
        <defs>
          <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.2" />
            <stop offset="100%" stopColor="var(--accent)" stopOpacity="0.01" />
          </linearGradient>
        </defs>
        {yLabels.map(v => <line key={v} x1={PAD_L} y1={toY(v)} x2={W - PAD_R} y2={toY(v)} stroke="var(--border)" strokeWidth={1} />)}
        {55 >= minTaxa && 55 <= maxTaxa && <line x1={PAD_L} y1={toY(55)} x2={W - PAD_R} y2={toY(55)} stroke="rgba(245,158,11,0.3)" strokeWidth={1} strokeDasharray="4,3" />}
        <polygon points={areaPoints} fill="url(#areaGrad)" />
        <polyline points={pts} fill="none" stroke="var(--accent)" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
        {evolucao.map((d, i) => <circle key={i} cx={toX(i)} cy={toY(d.taxa_acerto)} r={evolucao.length > 20 ? 2 : 3} fill={d.taxa_acerto >= 55 ? 'var(--green)' : d.taxa_acerto >= 40 ? 'var(--accent)' : 'var(--red)'} />)}
        {yLabels.map(v => <text key={v} x={PAD_L - 6} y={toY(v) + 4} textAnchor="end" fill="var(--text-faint)" fontSize={10}>{v}%</text>)}
        {xLabels.map(({ i, label }) => <text key={i} x={toX(i)} y={H - 4} textAnchor="middle" fill="var(--text-faint)" fontSize={10}>{label}</text>)}
        {55 >= minTaxa && 55 <= maxTaxa && <text x={W - PAD_R - 2} y={toY(55) - 3} textAnchor="end" fill="rgba(245,158,11,0.5)" fontSize={9}>55%</text>}
      </svg>
      <div style={{ display: 'flex', gap: 14, marginTop: 8, flexWrap: 'wrap', fontSize: 11, color: 'var(--text-muted)' }}>
        <span><span style={{ color: 'var(--green)' }}>●</span> ≥ 55% acerto</span>
        <span><span style={{ color: 'var(--accent)' }}>●</span> 40–55%</span>
        <span><span style={{ color: 'var(--red)' }}>●</span> &lt; 40%</span>
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
    fetch('/api/performance').then(r => r.json()).then(d => { setData(d); setLoading(false) }).catch(e => { setError(e.message); setLoading(false) })
  }, [])

  if (loading) return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 320, gap: 14, paddingTop: 60 }}>
      <div className="spinner" style={{ width: 40, height: 40 }} />
      <div style={{ color: 'var(--text-muted)', fontSize: 14 }}>Carregando performance...</div>
    </div>
  )

  if (error) return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 320, gap: 12, paddingTop: 60 }}>
      <div style={{ fontSize: 32 }}>⚠️</div>
      <div style={{ color: 'var(--red)', fontSize: 14 }}>Erro ao carregar dados de performance</div>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>{error}</div>
    </div>
  )

  const resumo = data?.resumo || {}
  const mercados = data?.mercados || []
  const evolucao = data?.evolucao || []
  const porLiga = data?.por_liga || []
  const ultimos = data?.ultimos_palpites || []
  const semDados = mercados.length === 0 && ultimos.length === 0

  const ligasDisponiveis = [...new Set(porLiga.map(r => r.liga_nome))].sort()
  const porLigaFiltrado = ligaFiltro ? porLiga.filter(r => r.liga_nome === ligaFiltro) : porLiga

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', paddingTop: 32 }}>
      <div style={{ marginBottom: 28 }}>
        <h1 className="page-title">Performance Histórica</h1>
        <p className="page-subtitle">Acurácia e ROI acumulado por mercado — atualizado nightly às 03:00 BRT</p>
      </div>

      {semDados ? (
        <div className="card" style={{ textAlign: 'center', padding: '56px 24px' }}>
          <div style={{ fontSize: 40, marginBottom: 16 }}>📊</div>
          <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 8, letterSpacing: '-0.02em' }}>Ainda sem dados de performance</div>
          <div style={{ fontSize: 13, color: 'var(--text-muted)', maxWidth: 420, margin: '0 auto', lineHeight: 1.6 }}>
            Os dados aparecem automaticamente após os primeiros jogos analisados e avaliados pelo job noturno (03:00 BRT). Analise alguns jogos e aguarde o encerramento deles.
          </div>
          <Link to="/" style={{
            display: 'inline-block', marginTop: 24, padding: '10px 22px',
            background: 'linear-gradient(135deg, var(--accent), #8b5cf6)',
            borderRadius: 'var(--radius)', color: '#fff', fontWeight: 700, fontSize: 14, textDecoration: 'none',
          }}>
            Ver Jogos de Hoje
          </Link>
        </div>
      ) : (
        <>
          {/* ── Resumo Global ── */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(175px, 1fr))', gap: 14, marginBottom: 28 }}>
            {[
              { label: 'Palpites Avaliados', value: resumo.total_palpites_avaliados ?? 0 },
              { label: 'Total de Acertos', value: resumo.total_acertos ?? 0 },
              { label: 'Taxa de Acerto Geral', value: `${(resumo.taxa_acerto_geral ?? 0).toFixed(1)}%`, color: (resumo.taxa_acerto_geral ?? 0) >= 55 ? 'var(--green-light)' : 'var(--red)' },
              { label: 'ROI Total', value: `${(resumo.roi_total ?? 0) >= 0 ? '+' : ''}${(resumo.roi_total ?? 0).toFixed(2)}u`, color: (resumo.roi_total ?? 0) >= 0 ? 'var(--green-light)' : 'var(--red)' },
            ].map(({ label, value, color }) => (
              <div key={label} className="stat-box">
                <div className="stat-label">{label}</div>
                <div className="stat-value" style={color ? { color } : {}}>{value}</div>
              </div>
            ))}
          </div>

          {/* ── Evolução ── */}
          <div className="card" style={{ padding: '18px 22px', marginBottom: 28 }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4, letterSpacing: '-0.01em' }}>Evolução de Acerto — Últimos 30 Dias</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 18 }}>Taxa de acerto diária dos palpites avaliados</div>
            <EvolucaoChart evolucao={evolucao} />
          </div>

          {/* ── Por Mercado ── */}
          {mercados.length > 0 && (
            <div className="card" style={{ padding: '18px 22px', marginBottom: 28 }}>
              <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 18, letterSpacing: '-0.01em' }}>Performance por Mercado</div>
              <div style={{ overflowX: 'auto' }}>
                <table className="data-table">
                  <thead>
                    <tr>
                      {['Mercado', 'Palpites', 'Acertos', 'Erros', 'Taxa de Acerto', 'ROI Total'].map(h => (
                        <th key={h} style={{ textAlign: h === 'Mercado' ? 'left' : 'center' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {mercados.map(m => (
                      <tr key={m.mercado}>
                        <td style={{ color: 'var(--text-primary)', fontWeight: 700, fontSize: 13 }}>{m.mercado}</td>
                        <td style={{ textAlign: 'center', color: 'var(--text-secondary)' }}>{m.total_palpites}</td>
                        <td style={{ textAlign: 'center', color: 'var(--green-light)' }}>{m.total_acertos}</td>
                        <td style={{ textAlign: 'center', color: 'var(--red)' }}>{m.total_erros}</td>
                        <td style={{ textAlign: 'center' }}><TaxaBadge taxa={m.taxa_acerto} /></td>
                        <td style={{ textAlign: 'center' }}><RoiBadge roi={m.roi_total} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ── Por Liga ── */}
          {porLiga.length > 0 && (
            <div className="card" style={{ padding: '18px 22px', marginBottom: 28 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12, marginBottom: 18 }}>
                <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.01em' }}>Performance por Liga</div>
                <select value={ligaFiltro || ''} onChange={e => setLigaFiltro(e.target.value || null)} className="token-select" style={{ width: 'auto' }}>
                  <option value="">Todas as ligas</option>
                  {ligasDisponiveis.map(l => <option key={l} value={l}>{l}</option>)}
                </select>
              </div>
              <div style={{ overflowX: 'auto' }}>
                <table className="data-table">
                  <thead>
                    <tr>
                      {['Mercado', 'Liga', 'Amostras', 'Acertos', 'Taxa de Acerto', 'ROI'].map(h => (
                        <th key={h} style={{ textAlign: h === 'Mercado' || h === 'Liga' ? 'left' : 'center' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {porLigaFiltrado.slice(0, 50).map((r, i) => (
                      <tr key={`${r.mercado}-${r.liga_id}-${i}`}>
                        <td style={{ color: 'var(--text-primary)', fontWeight: 700 }}>{r.mercado}</td>
                        <td style={{ color: 'var(--text-secondary)' }}>{r.liga_nome}</td>
                        <td style={{ textAlign: 'center', color: 'var(--text-secondary)' }}>{r.n_amostras}</td>
                        <td style={{ textAlign: 'center', color: 'var(--green-light)' }}>{r.total_acertos}</td>
                        <td style={{ textAlign: 'center' }}><TaxaBadge taxa={r.taxa_acerto} /></td>
                        <td style={{ textAlign: 'center' }}><RoiBadge roi={r.roi_total} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {porLigaFiltrado.length > 50 && (
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 12, textAlign: 'center' }}>
                  Mostrando 50 de {porLigaFiltrado.length} entradas
                </div>
              )}
            </div>
          )}

          {/* ── Últimos Palpites ── */}
          {ultimos.length > 0 && (
            <div className="card" style={{ padding: '18px 22px' }}>
              <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 16, letterSpacing: '-0.01em' }}>Últimos Palpites Avaliados</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {ultimos.map(p => (
                  <div key={p.id} style={{
                    background: 'var(--surface)',
                    border: `1px solid ${p.acertou ? 'var(--green-border)' : 'var(--red-border)'}`,
                    borderRadius: 'var(--radius)', padding: '11px 14px',
                    display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 10,
                  }}>
                    <AcertouBadge acertou={p.acertou} />
                    <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)', flex: 1, minWidth: 120 }}>
                      {p.linha || p.tipo || '—'}
                    </span>
                    <span className="chip chip-accent">{p.mercado}</span>
                    {p.odd && <span style={{ fontSize: 11, color: 'var(--accent-light)', fontWeight: 700 }}>@{Number(p.odd).toFixed(2)}</span>}
                    <RoiBadge roi={p.roi_unitario ?? p.roi} />
                    {(p.liga || p.liga_nome) && (
                      <span style={{ fontSize: 10, color: 'var(--text-faint)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 140 }}>
                        {p.liga || p.liga_nome}
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
