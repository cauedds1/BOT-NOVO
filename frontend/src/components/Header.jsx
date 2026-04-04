import { Link, useLocation } from 'react-router-dom'
import { useState, useEffect } from 'react'

export default function Header() {
  const location = useLocation()
  const isHome = location.pathname === '/'
  const isPerformance = location.pathname === '/performance'
  const [isDemo, setIsDemo] = useState(null)

  useEffect(() => {
    fetch('/api/health')
      .then(r => r.json())
      .then(d => setIsDemo(d.is_demo ?? false))
      .catch(() => setIsDemo(false))
  }, [])

  return (
    <header
      style={{
        background: 'linear-gradient(to bottom, #0d0f1a, #0d0f1a)',
        borderBottom: '1px solid rgba(99,102,241,0.15)',
        position: 'sticky',
        top: 0,
        zIndex: 50,
        backdropFilter: 'blur(12px)',
      }}
    >
      <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-3 no-underline">
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: 10,
              background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 18,
            }}
          >
            ⚽
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 16, color: '#f1f5f9', letterSpacing: '-0.02em' }}>
              AnalyTips
            </div>
            <div style={{ fontSize: 11, color: '#64748b', fontWeight: 500 }}>
              Football Intelligence
            </div>
          </div>
        </Link>

        <nav className="flex items-center gap-6">
          <Link
            to="/"
            style={{
              fontSize: 13,
              fontWeight: 500,
              color: isHome ? '#818cf8' : '#94a3b8',
              textDecoration: 'none',
              borderBottom: isHome ? '2px solid #818cf8' : '2px solid transparent',
              paddingBottom: 2,
            }}
          >
            Jogos Hoje
          </Link>
          <Link
            to="/performance"
            style={{
              fontSize: 13,
              fontWeight: 500,
              color: isPerformance ? '#818cf8' : '#94a3b8',
              textDecoration: 'none',
              borderBottom: isPerformance ? '2px solid #818cf8' : '2px solid transparent',
              paddingBottom: 2,
            }}
          >
            Performance
          </Link>

          {isDemo === null ? null : isDemo ? (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                fontSize: 12,
                color: '#fb923c',
                background: 'rgba(251,146,60,0.10)',
                border: '1px solid rgba(251,146,60,0.30)',
                borderRadius: 8,
                padding: '4px 10px',
                fontWeight: 600,
              }}
            >
              <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#fb923c', display: 'inline-block', animation: 'pulse 2s infinite' }} />
              Demo
            </div>
          ) : (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                fontSize: 12,
                color: '#64748b',
                background: 'rgba(99,102,241,0.08)',
                border: '1px solid rgba(99,102,241,0.15)',
                borderRadius: 8,
                padding: '4px 10px',
              }}
            >
              <div className="pulse-dot" />
              API Live
            </div>
          )}
        </nav>
      </div>
    </header>
  )
}
