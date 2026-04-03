import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Home from './pages/Home'
import MatchDetail from './pages/MatchDetail'
import Header from './components/Header'

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen" style={{ background: '#0d0f1a' }}>
        <Header />
        <main className="max-w-6xl mx-auto px-4 pb-16">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/jogo/:fixtureId" element={<MatchDetail />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
