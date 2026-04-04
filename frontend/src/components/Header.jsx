import { Link, useLocation } from 'react-router-dom'

export default function Header() {
  const location = useLocation()
  const isHome = location.pathname === '/'
  const isPerformance = location.pathname === '/performance'

  return (
    <header style={{
      background: 'rgba(8,8,16,0.88)',
      borderBottom: '1px solid rgba(255,255,255,0.065)',
      position: 'sticky', top: 0, zIndex: 50,
      backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
      boxShadow: '0 1px 0 rgba(99,102,241,0.12)',
    }}>
      <div style={{
        maxWidth: 1400, margin: '0 auto', padding: '0 24px',
        height: 48, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: 8, textDecoration: 'none' }}>
          <div style={{
            width: 28, height: 28, borderRadius: 8,
            background: 'linear-gradient(135deg, var(--accent) 0%, #8b5cf6 100%)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 14, flexShrink: 0, boxShadow: '0 2px 8px rgba(99,102,241,0.45)',
          }}>
            ⚽
          </div>
          <div>
            <div style={{ fontWeight: 800, fontSize: 14, color: 'var(--text-primary)', letterSpacing: '-0.03em', lineHeight: 1.1 }}>
              AnalyTips
            </div>
            <div style={{ fontSize: 9, color: 'var(--text-faint)', fontWeight: 500, letterSpacing: '0.05em', textTransform: 'uppercase' }}>
              Football Intel
            </div>
          </div>
        </Link>

        <nav style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Link to="/" style={{
            fontSize: 12, fontWeight: 600,
            color: isHome ? '#c7d2fe' : 'var(--text-muted)',
            textDecoration: 'none', padding: '5px 11px',
            borderRadius: 'var(--radius-sm)',
            background: isHome ? 'var(--accent-dim)' : 'transparent',
            border: `1px solid ${isHome ? 'rgba(99,102,241,0.22)' : 'transparent'}`,
            transition: 'var(--transition)',
            position: 'relative',
          }}>
            Jogos Hoje
          </Link>
          <Link to="/performance" style={{
            fontSize: 12, fontWeight: 600,
            color: isPerformance ? '#c7d2fe' : 'var(--text-muted)',
            textDecoration: 'none', padding: '5px 11px',
            borderRadius: 'var(--radius-sm)',
            background: isPerformance ? 'var(--accent-dim)' : 'transparent',
            border: `1px solid ${isPerformance ? 'rgba(99,102,241,0.22)' : 'transparent'}`,
            transition: 'var(--transition)',
          }}>
            Performance
          </Link>

          <div style={{ width: 1, height: 16, background: 'var(--border)', margin: '0 6px' }} />

          <div style={{
            display: 'flex', alignItems: 'center', gap: 5,
            fontSize: 10, color: 'var(--green-light)',
            background: 'var(--green-dim)', border: '1px solid var(--green-border)',
            borderRadius: 'var(--radius-sm)', padding: '3px 8px', fontWeight: 700,
            letterSpacing: '0.04em',
          }}>
            <div className="pulse-dot" style={{ width: 6, height: 6 }} />
            Live
          </div>
        </nav>
      </div>
    </header>
  )
}
