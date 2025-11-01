-- Schema para o banco de dados PostgreSQL do AnalytipsBot
-- Execute este script no seu banco de dados PostgreSQL

-- Tabela principal de análises de jogos (cache)
CREATE TABLE IF NOT EXISTS analises_jogos (
    id SERIAL PRIMARY KEY,
    fixture_id INTEGER UNIQUE NOT NULL,
    data_jogo TIMESTAMP WITH TIME ZONE NOT NULL,
    liga VARCHAR(255),
    time_casa VARCHAR(255),
    time_fora VARCHAR(255),
    stats_casa JSONB,
    stats_fora JSONB,
    classificacao JSONB,
    analise_gols JSONB,
    analise_cantos JSONB,
    analise_btts JSONB,
    analise_resultado JSONB,
    analise_cartoes JSONB,
    analise_contexto JSONB,
    palpites_totais INTEGER DEFAULT 0,
    confianca_media DECIMAL(3,1) DEFAULT 0,
    data_analise TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    atualizado_em TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_analises_jogos_fixture_id ON analises_jogos(fixture_id);
CREATE INDEX IF NOT EXISTS idx_analises_jogos_data_jogo ON analises_jogos(data_jogo);
CREATE INDEX IF NOT EXISTS idx_analises_jogos_atualizado_em ON analises_jogos(atualizado_em);

-- Nova tabela para sistema de fila de análises diárias
CREATE TABLE IF NOT EXISTS daily_analyses (
    id SERIAL PRIMARY KEY,
    fixture_id INTEGER NOT NULL,
    analysis_type VARCHAR(50) NOT NULL,
    dossier_json TEXT NOT NULL,
    user_id BIGINT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT daily_analyses_unique UNIQUE (fixture_id, analysis_type, user_id)
);

-- Índices para performance na tabela daily_analyses
CREATE INDEX IF NOT EXISTS idx_daily_analyses_user_type ON daily_analyses(user_id, analysis_type);
CREATE INDEX IF NOT EXISTS idx_daily_analyses_created_at ON daily_analyses(created_at);
CREATE INDEX IF NOT EXISTS idx_daily_analyses_fixture_id ON daily_analyses(fixture_id);

-- Comentários para documentação
COMMENT ON TABLE analises_jogos IS 'Cache de análises completas de jogos processados';
COMMENT ON TABLE daily_analyses IS 'Análises processadas em batch pelo sistema de fila assíncrona';
COMMENT ON COLUMN daily_analyses.analysis_type IS 'Tipo: full, goals_only, corners_only, btts_only, result_only, simple_bet, multiple_bet, bingo';
COMMENT ON COLUMN daily_analyses.dossier_json IS 'JSON completo do dossier de análise gerado pelo master_analyzer';
