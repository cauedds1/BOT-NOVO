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
    <span
      style={{
        color: positive ? '#22c55e' : '#f87171',
        fontWeight: 600,
        fontSize: 13,
      }}
    >
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

export default function Performance() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

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
  const ultimos = data?.ultimos_palpites || []
  const semDados = mercados.length === 0 && ultimos.length === 0

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
            Os dados aparecem automaticamente após os primeiros jogos analisados e avaliados pelo job noturno (03:00 BRT).
            Analise alguns jogos e aguarde o encerramento deles para ver as estatísticas aqui.
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
              { label: 'Palpites Avaliados', value: resumo.total_palpites_avaliados ?? 0, suffix: '' },
              { label: 'Total de Acertos', value: resumo.total_acertos ?? 0, suffix: '' },
              {
                label: 'Taxa de Acerto Geral',
                value: `${(resumo.taxa_acerto_geral ?? 0).toFixed(1)}%`,
                color: (resumo.taxa_acerto_geral ?? 0) >= 55 ? '#22c55e' : '#f87171',
                suffix: '',
              },
              {
                label: 'ROI Total',
                value: `${(resumo.roi_total ?? 0) >= 0 ? '+' : ''}${(resumo.roi_total ?? 0).toFixed(2)}u`,
                color: (resumo.roi_total ?? 0) >= 0 ? '#22c55e' : '#f87171',
                suffix: '',
              },
            ].map(({ label, value, color, suffix }) => (
              <div key={label} style={cardStyle}>
                <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
                  {label}
                </div>
                <div style={{ fontSize: 26, fontWeight: 700, color: color || '#f1f5f9' }}>
                  {value}{suffix}
                </div>
              </div>
            ))}
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
