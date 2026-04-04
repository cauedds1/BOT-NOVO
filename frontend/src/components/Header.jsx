import { Link, useLocation } from 'react-router-dom'

export default function Header() {
  const location = useLocation()
  const isHome = location.pathname === '/'
  const isPerformance = location.pathname === '/performance'

  return (
    <header style={{
      background: 'rgba(9,9,14,0.85)',
      borderBottom: '1px solid var(--border)',
      position: 'sticky', top: 0, zIndex: 50,
      backdropFilter: 'blur(16px)', WebkitBackdropFilter: 'blur(16px)',
    }}>
      <div style={{
        maxWidth: 1400, margin: '0 auto', padding: '0 24px',
        height: 56, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: 10, textDecoration: 'none' }}>
          <div style={{
            width: 32, height: 32, borderRadius: 9,
            background: 'linear-gradient(135deg, var(--accent) 0%, #8b5cf6 100%)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 16, flexShrink: 0, boxShadow: '0 2px 10px rgba(99,102,241,0.4)',
          }}>
            ⚽
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 15, color: 'var(--text-primary)', letterSpacing: '-0.03em', lineHeight: 1.1 }}>
              AnalyTips
            </div>
            <div style={{ fontSize: 10, color: 'var(--text-faint)', fontWeight: 500, letterSpacing: '0.04em' }}>
              Football Intelligence
            </div>
          </div>
        </Link>

        <nav style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <Link to="/" className={`nav-link${isHome ? ' nav-link-active' : ''}`}>Jogos Hoje</Link>
          <Link to="/performance" className={`nav-link${isPerformance ? ' nav-link-active' : ''}`}>Performance</Link>

          <div style={{ width: 1, height: 20, background: 'var(--border)', margin: '0 8px' }} />

          <div style={{
            display: 'flex', alignItems: 'center', gap: 6,
            fontSize: 11, color: 'var(--green-light)',
            background: 'var(--green-dim)', border: '1px solid var(--green-border)',
            borderRadius: 'var(--radius-sm)', padding: '4px 10px', fontWeight: 600,
          }}>
            <div className="pulse-dot" />
            Live
          </div>
        </nav>
      </div>
    </header>
  )
}
