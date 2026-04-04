# db_manager.py
import os
import json
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor, Json
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from zoneinfo import ZoneInfo
from contextlib import contextmanager
import cache_manager

# 🇧🇷 HORÁRIO DE BRASÍLIA: Todas as operações de datetime usam timezone de Brasília
BRASILIA_TZ = ZoneInfo("America/Sao_Paulo")

def agora_brasilia():
    """Retorna datetime atual no horário de Brasília"""
    return datetime.now(BRASILIA_TZ)


def calcular_ttl_analise(data_jogo: Optional[datetime]) -> Optional[int]:
    """
    Calcula o TTL (em horas) para cache de análise baseado no horário de kickoff.

    Regras:
      - data_jogo ausente           → 12h (padrão conservador)
      - kickoff em mais de 24h      → 12h TTL (dados estáveis)
      - kickoff entre 2h e 24h      → 2h TTL (escalação ainda pode mudar)
      - kickoff em menos de 2h      → None (sem cache; dados oficiais devem ser frescos)

    Returns:
        int com horas de TTL, ou None para desabilitar cache.
    """
    if data_jogo is None:
        return 12

    agora = agora_brasilia()
    # Garantir timezone aware
    if data_jogo.tzinfo is None:
        data_jogo = data_jogo.replace(tzinfo=BRASILIA_TZ)

    delta = data_jogo - agora
    horas_restantes = delta.total_seconds() / 3600

    if horas_restantes > 24:
        return 12   # Jogo distante → cache longo
    elif horas_restantes > 2:
        return 2    # Jogo hoje → cache curto
    else:
        return None  # Iminente → sem cache (escalação oficial)


class DatabaseManager:
    """
    Gerenciador de banco de dados para armazenar análises completas de jogos.
    Evita refazer análises desnecessárias e economiza créditos da API.
    Usa connection pooling para melhor performance e eficiência.
    """

    def __init__(self, min_conn=1, max_conn=10):
        self.database_url = os.getenv('DATABASE_URL')
        if not self.database_url:
            print("⚠️ DATABASE_URL não encontrado. Usando cache.json como fallback.")
            self.enabled = False
            self.pool = None
            self.use_cache_fallback = True
        else:
            self.enabled = True
            self.use_cache_fallback = False
            try:
                # Criar connection pool
                self.pool = psycopg2.pool.SimpleConnectionPool(
                    min_conn,
                    max_conn,
                    self.database_url
                )
                print(f"✅ Connection pool criado: {min_conn}-{max_conn} conexões")
            except Exception as e:
                print(f"❌ Erro ao criar connection pool: {e}")
                self.enabled = False
                self.pool = None
                self.use_cache_fallback = True
                print("⚠️ Usando cache.json como fallback.")

    @contextmanager
    def _get_connection(self):
        """Context manager para obter conexão do pool"""
        if not self.enabled or not self.pool:
            yield None
            return
        
        conn = None
        try:
            conn = self.pool.getconn()
            yield conn
        finally:
            if conn:
                self.pool.putconn(conn)
    
    def initialize_database(self):
        """
        Inicializa o schema do banco de dados, criando todas as tabelas necessárias.
        Executa CREATE TABLE IF NOT EXISTS para garantir que o schema está completo.
        """
        if not self.enabled:
            print("⚠️ Database não habilitado, pulando inicialização")
            return False
        
        schema_sql = """
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
            analise_gabt JSONB,
            analise_placar_exato JSONB,
            palpites_totais INTEGER DEFAULT 0,
            confianca_media DECIMAL(3,1) DEFAULT 0,
            data_analise TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            atualizado_em TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        -- Adicionar colunas GABT, Placar Exato e Handicap Europeu em tabelas existentes (migration segura)
        ALTER TABLE analises_jogos ADD COLUMN IF NOT EXISTS analise_gabt JSONB;
        ALTER TABLE analises_jogos ADD COLUMN IF NOT EXISTS analise_placar_exato JSONB;
        ALTER TABLE analises_jogos ADD COLUMN IF NOT EXISTS analise_handicap_europeu JSONB;
        ALTER TABLE analises_jogos ADD COLUMN IF NOT EXISTS analise_primeiro_marcador JSONB;
        ALTER TABLE analises_jogos ADD COLUMN IF NOT EXISTS analise_htft JSONB;
        ALTER TABLE analises_jogos ADD COLUMN IF NOT EXISTS analise_win_to_nil JSONB;
        ALTER TABLE analises_jogos ADD COLUMN IF NOT EXISTS analise_draw_no_bet JSONB;

        -- Índices para performance
        CREATE INDEX IF NOT EXISTS idx_analises_jogos_fixture_id ON analises_jogos(fixture_id);
        CREATE INDEX IF NOT EXISTS idx_analises_jogos_data_jogo ON analises_jogos(data_jogo);
        CREATE INDEX IF NOT EXISTS idx_analises_jogos_atualizado_em ON analises_jogos(atualizado_em);

        -- ═══════════════════════════════════════════════════════════════
        -- CAMADA DE CACHE PERSISTENTE (Task #9)
        -- Evita re-chamadas à API em restarts e entre sessões.
        -- Lógica: memória → DB → API
        -- ═══════════════════════════════════════════════════════════════

        -- Fixtures do dia (jogos por data+liga combinados)
        -- TTL: 8 horas — fixtures mudam ao longo do dia (novas ligas)
        -- Usa cache_key (não apenas date) porque após 20:30 BRT buscamos
        -- HOJE+AMANHÃ como bloco único, gerando uma chave composta como
        -- 'jogos_2026-04-04_2026-04-05_s2025' vs 'jogos_2026-04-04_s2025'.
        CREATE TABLE IF NOT EXISTS cache_fixtures_dia (
            cache_key TEXT PRIMARY KEY,
            data JSONB NOT NULL,
            fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        -- Estatísticas gerais de time por liga/temporada
        -- TTL: 48 horas — stats só mudam depois de jogos disputados
        CREATE TABLE IF NOT EXISTS cache_stats_time (
            team_id INTEGER NOT NULL,
            league_id INTEGER NOT NULL,
            data JSONB NOT NULL,
            fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (team_id, league_id)
        );
        CREATE INDEX IF NOT EXISTS idx_cache_stats_time_fetched ON cache_stats_time(fetched_at);

        -- Últimos jogos finalizados de um time
        -- TTL: 24 horas — lista muda só quando o time joga de novo
        CREATE TABLE IF NOT EXISTS cache_ultimos_jogos (
            team_id INTEGER NOT NULL,
            limite INTEGER NOT NULL,
            data JSONB NOT NULL,
            fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (team_id, limite)
        );
        CREATE INDEX IF NOT EXISTS idx_cache_ultimos_jogos_fetched ON cache_ultimos_jogos(fetched_at);

        -- Confrontos diretos (H2H) entre dois times
        -- TTL: 30 dias — histórico ultra-estável, muda só se os times se encontrarem
        CREATE TABLE IF NOT EXISTS cache_h2h (
            team1_id INTEGER NOT NULL,
            team2_id INTEGER NOT NULL,
            limite INTEGER NOT NULL,
            data JSONB NOT NULL,
            fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (team1_id, team2_id, limite)
        );
        CREATE INDEX IF NOT EXISTS idx_cache_h2h_fetched ON cache_h2h(fetched_at);

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

        -- Tabela de histórico de palpites individuais (rastreamento permanente)
        CREATE TABLE IF NOT EXISTS palpites_historico (
            id SERIAL PRIMARY KEY,
            fixture_id INTEGER NOT NULL,
            mercado VARCHAR(100) NOT NULL,
            linha VARCHAR(100) NOT NULL,
            time_aposta VARCHAR(50) DEFAULT 'Total',
            confianca INTEGER NOT NULL DEFAULT 0,
            odd DECIMAL(8,2),
            resultado_esperado VARCHAR(200),
            periodo VARCHAR(10) DEFAULT 'FT',
            acertou BOOLEAN,
            roi_unitario DECIMAL(8,4),
            criado_em TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            CONSTRAINT palpites_historico_unique UNIQUE (fixture_id, mercado, linha, periodo, time_aposta)
        );
        ALTER TABLE palpites_historico ADD COLUMN IF NOT EXISTS time_aposta VARCHAR(50) DEFAULT 'Total';
        CREATE INDEX IF NOT EXISTS idx_palpites_historico_fixture_id ON palpites_historico(fixture_id);
        CREATE INDEX IF NOT EXISTS idx_palpites_historico_mercado ON palpites_historico(mercado);
        CREATE INDEX IF NOT EXISTS idx_palpites_historico_acertou ON palpites_historico(acertou);
        CREATE INDEX IF NOT EXISTS idx_palpites_historico_criado_em ON palpites_historico(criado_em);

        -- Tabela de resultados reais dos jogos analisados
        CREATE TABLE IF NOT EXISTS resultado_jogos (
            id SERIAL PRIMARY KEY,
            fixture_id INTEGER UNIQUE NOT NULL,
            placar_casa INTEGER,
            placar_fora INTEGER,
            status_final VARCHAR(20),
            buscado_em TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_resultado_jogos_fixture_id ON resultado_jogos(fixture_id);
        CREATE INDEX IF NOT EXISTS idx_resultado_jogos_status_final ON resultado_jogos(status_final);

        COMMENT ON TABLE palpites_historico IS 'Palpites individuais gerados para cada jogo analisado com resultado real';
        COMMENT ON TABLE resultado_jogos IS 'Resultado real (placar final) dos jogos analisados';

        -- Tabela de performance por mercado+liga+script (atualizada após cada avaliação)
        CREATE TABLE IF NOT EXISTS performance_mercados (
            id SERIAL PRIMARY KEY,
            mercado VARCHAR(100) NOT NULL,
            liga_id INTEGER NOT NULL DEFAULT 0,
            script VARCHAR(100) NOT NULL DEFAULT '',
            n_amostras INTEGER NOT NULL DEFAULT 0,
            total_acertos INTEGER NOT NULL DEFAULT 0,
            total_erros INTEGER NOT NULL DEFAULT 0,
            taxa_acerto DECIMAL(5,2) DEFAULT 0,
            roi_total DECIMAL(10,4) DEFAULT 0,
            atualizado_em TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            CONSTRAINT performance_mercados_unique UNIQUE (mercado, liga_id, script)
        );
        CREATE INDEX IF NOT EXISTS idx_performance_mercados_mercado ON performance_mercados(mercado);
        COMMENT ON TABLE performance_mercados IS 'Acurácia e ROI por mercado+liga+script, atualizado após cada avaliação noturna';

        -- Tabela de estatísticas por jogador por partida
        CREATE TABLE IF NOT EXISTS estatisticas_jogadores (
            id SERIAL PRIMARY KEY,
            jogador_id INTEGER NOT NULL,
            fixture_id INTEGER NOT NULL,
            time_id INTEGER NOT NULL,
            minutos INTEGER DEFAULT 0,
            gols INTEGER DEFAULT 0,
            assistencias INTEGER DEFAULT 0,
            finalizacoes INTEGER DEFAULT 0,
            finalizacoes_no_gol INTEGER DEFAULT 0,
            cartao_amarelo BOOLEAN DEFAULT FALSE,
            cartao_vermelho BOOLEAN DEFAULT FALSE,
            eh_mandante BOOLEAN,
            foi_titular BOOLEAN DEFAULT TRUE,
            criado_em TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            CONSTRAINT estatisticas_jogadores_unique UNIQUE (jogador_id, fixture_id)
        );
        CREATE INDEX IF NOT EXISTS idx_estatisticas_jogadores_jogador ON estatisticas_jogadores(jogador_id);
        CREATE INDEX IF NOT EXISTS idx_estatisticas_jogadores_time ON estatisticas_jogadores(time_id);

        -- Tabela de perfis acumulados por jogador (médias + desvio padrão)
        CREATE TABLE IF NOT EXISTS perfis_jogadores (
            id SERIAL PRIMARY KEY,
            jogador_id INTEGER UNIQUE NOT NULL,
            time_id INTEGER NOT NULL,
            nome VARCHAR(255),
            n_jogos_total INTEGER DEFAULT 0,
            n_jogos_casa INTEGER DEFAULT 0,
            n_jogos_fora INTEGER DEFAULT 0,
            n_jogos_titular INTEGER DEFAULT 0,
            media_gols DECIMAL(6,3) DEFAULT 0,
            media_assistencias DECIMAL(6,3) DEFAULT 0,
            media_finalizacoes DECIMAL(6,3) DEFAULT 0,
            stddev_gols DECIMAL(6,3) DEFAULT 0,
            stddev_finalizacoes DECIMAL(6,3) DEFAULT 0,
            atualizado_em TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_perfis_jogadores_time ON perfis_jogadores(time_id);
        COMMENT ON TABLE estatisticas_jogadores IS 'Estatísticas individuais de jogadores por partida';
        COMMENT ON TABLE perfis_jogadores IS 'Perfil acumulado de cada jogador: médias, stddev, contagem por contexto';
        """
        
        try:
            with self._get_connection() as conn:
                if not conn:
                    print("❌ Não foi possível obter conexão para inicializar banco")
                    return False
                
                cursor = conn.cursor()
                
                # Executar todo o schema (CREATE TABLE IF NOT EXISTS — seguro re-executar)
                cursor.execute(schema_sql)
                conn.commit()

                # ── Migrações de schema incremental ──────────────────────────────────
                # Task #17: performance_mercados ganhou colunas compostas (liga_id, script)
                # e a coluna total_palpites foi renomeada para n_amostras.
                migrations = [
                    # Adicionar colunas novas na performance_mercados se não existirem
                    """
                    DO $$ BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name='performance_mercados' AND column_name='liga_id'
                        ) THEN
                            ALTER TABLE performance_mercados ADD COLUMN liga_id INTEGER NOT NULL DEFAULT 0;
                        END IF;
                    END $$;
                    """,
                    """
                    DO $$ BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name='performance_mercados' AND column_name='script'
                        ) THEN
                            ALTER TABLE performance_mercados ADD COLUMN script VARCHAR(100) NOT NULL DEFAULT '';
                        END IF;
                    END $$;
                    """,
                    # Renomear total_palpites → n_amostras se ainda existir com nome antigo
                    """
                    DO $$ BEGIN
                        IF EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name='performance_mercados' AND column_name='total_palpites'
                        ) AND NOT EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name='performance_mercados' AND column_name='n_amostras'
                        ) THEN
                            ALTER TABLE performance_mercados RENAME COLUMN total_palpites TO n_amostras;
                        END IF;
                    END $$;
                    """,
                    # Garantir coluna n_amostras existe (se tabela foi criada com nome antigo e já renomeada)
                    """
                    DO $$ BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name='performance_mercados' AND column_name='n_amostras'
                        ) THEN
                            ALTER TABLE performance_mercados ADD COLUMN n_amostras INTEGER NOT NULL DEFAULT 0;
                        END IF;
                    END $$;
                    """,
                    # Remover UNIQUE constraint antigo em mercado (agora é composto)
                    """
                    DO $$ BEGIN
                        IF EXISTS (
                            SELECT 1 FROM information_schema.table_constraints
                            WHERE table_name='performance_mercados'
                              AND constraint_type='UNIQUE'
                              AND constraint_name NOT LIKE '%performance_mercados_unique%'
                        ) THEN
                            -- Dropar qualquer unique que não seja o nosso composite
                            BEGIN
                                ALTER TABLE performance_mercados DROP CONSTRAINT IF EXISTS performance_mercados_mercado_key;
                            EXCEPTION WHEN OTHERS THEN NULL;
                            END;
                        END IF;
                    END $$;
                    """,
                    # Adicionar constraint composta se não existir
                    """
                    DO $$ BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.table_constraints
                            WHERE table_name='performance_mercados'
                              AND constraint_name='performance_mercados_unique'
                        ) THEN
                            BEGIN
                                ALTER TABLE performance_mercados
                                    ADD CONSTRAINT performance_mercados_unique
                                    UNIQUE (mercado, liga_id, script);
                            EXCEPTION WHEN OTHERS THEN NULL;
                            END;
                        END IF;
                    END $$;
                    """,
                    "CREATE INDEX IF NOT EXISTS idx_performance_mercados_liga ON performance_mercados(liga_id);",
                ]

                for migration_sql in migrations:
                    try:
                        cursor.execute(migration_sql)
                        conn.commit()
                    except Exception as m_err:
                        print(f"  ⚠️ Migração ignorada (provavelmente já aplicada): {m_err}")
                        conn.rollback()

                cursor.close()
                
                print("✅ Database schema inicializado com sucesso!")
                print("   📋 Tabelas: analises_jogos, daily_analyses, palpites_historico, resultado_jogos, performance_mercados, estatisticas_jogadores, perfis_jogadores")
                print("   📦 Cache persistente: cache_fixtures_dia, cache_stats_time, cache_ultimos_jogos, cache_h2h")
                return True
                
        except Exception as e:
            print(f"❌ Erro ao inicializar database schema: {e}")
            return False
    
    def close_pool(self):
        """Fecha o connection pool ao desligar a aplicação"""
        if self.pool:
            self.pool.closeall()
            print("✅ Connection pool fechado")

    # ─────────────────────────────────────────────────────────────────────────
    # CAMADA DE CACHE PERSISTENTE (Task #9)
    # Padrão: get retorna None em caso de miss/erro; set silencia erros
    # ─────────────────────────────────────────────────────────────────────────

    def get_cache_fixtures_dia(self, cache_key: str) -> Optional[list]:
        """Busca fixtures do dia no DB. TTL: 8 horas. Retorna None em caso de miss."""
        if not self.enabled:
            return None
        try:
            with self._get_connection() as conn:
                if not conn:
                    return None
                cur = conn.cursor()
                cur.execute(
                    "SELECT data, fetched_at FROM cache_fixtures_dia WHERE cache_key = %s",
                    (cache_key,)
                )
                row = cur.fetchone()
                cur.close()
                if row:
                    fetched_at = row[1]
                    if fetched_at.tzinfo is None:
                        fetched_at = fetched_at.replace(tzinfo=BRASILIA_TZ)
                    age_hours = (datetime.now(BRASILIA_TZ) - fetched_at).total_seconds() / 3600
                    if age_hours < 8:
                        print(f"✅ DB CACHE HIT: fixtures_dia '{cache_key}' ({age_hours:.1f}h atrás)")
                        return row[0]
                    print(f"⏰ DB CACHE EXPIRADO: fixtures_dia '{cache_key}' ({age_hours:.1f}h > 8h)")
                return None
        except Exception as e:
            print(f"⚠️ DB cache_fixtures_dia get erro: {e}")
            return None

    def set_cache_fixtures_dia(self, cache_key: str, data: list) -> None:
        """Salva fixtures do dia no DB."""
        if not self.enabled:
            return
        try:
            with self._get_connection() as conn:
                if not conn:
                    return
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO cache_fixtures_dia (cache_key, data, fetched_at)
                    VALUES (%s, %s, NOW())
                    ON CONFLICT (cache_key) DO UPDATE
                        SET data = EXCLUDED.data, fetched_at = NOW()
                    """,
                    (cache_key, Json(data))
                )
                conn.commit()
                cur.close()
                print(f"💾 DB CACHE SAVE: fixtures_dia '{cache_key}' ({len(data)} jogos)")
        except Exception as e:
            print(f"⚠️ DB cache_fixtures_dia set erro: {e}")

    def get_cache_stats_time(self, team_id: int, league_id: int) -> Optional[dict]:
        """Busca stats gerais de time no DB. TTL: 48 horas. Retorna None em caso de miss."""
        if not self.enabled:
            return None
        try:
            with self._get_connection() as conn:
                if not conn:
                    return None
                cur = conn.cursor()
                cur.execute(
                    "SELECT data, fetched_at FROM cache_stats_time WHERE team_id = %s AND league_id = %s",
                    (team_id, league_id)
                )
                row = cur.fetchone()
                cur.close()
                if row:
                    fetched_at = row[1]
                    if fetched_at.tzinfo is None:
                        fetched_at = fetched_at.replace(tzinfo=BRASILIA_TZ)
                    age_hours = (datetime.now(BRASILIA_TZ) - fetched_at).total_seconds() / 3600
                    if age_hours < 48:
                        print(f"✅ DB CACHE HIT: stats time {team_id} liga {league_id} ({age_hours:.1f}h atrás)")
                        return row[0]
                    print(f"⏰ DB CACHE EXPIRADO: stats time {team_id} ({age_hours:.1f}h > 48h)")
                return None
        except Exception as e:
            print(f"⚠️ DB cache_stats_time get erro: {e}")
            return None

    def set_cache_stats_time(self, team_id: int, league_id: int, data: dict) -> None:
        """Salva stats gerais de time no DB."""
        if not self.enabled:
            return
        try:
            with self._get_connection() as conn:
                if not conn:
                    return
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO cache_stats_time (team_id, league_id, data, fetched_at)
                    VALUES (%s, %s, %s, NOW())
                    ON CONFLICT (team_id, league_id) DO UPDATE
                        SET data = EXCLUDED.data, fetched_at = NOW()
                    """,
                    (team_id, league_id, Json(data))
                )
                conn.commit()
                cur.close()
                print(f"💾 DB CACHE SAVE: stats time {team_id} liga {league_id}")
        except Exception as e:
            print(f"⚠️ DB cache_stats_time set erro: {e}")

    def get_cache_ultimos_jogos(self, team_id: int, limite: int) -> Optional[list]:
        """Busca últimos jogos de um time no DB. TTL: 24 horas. Retorna None em caso de miss."""
        if not self.enabled:
            return None
        try:
            with self._get_connection() as conn:
                if not conn:
                    return None
                cur = conn.cursor()
                cur.execute(
                    "SELECT data, fetched_at FROM cache_ultimos_jogos WHERE team_id = %s AND limite = %s",
                    (team_id, limite)
                )
                row = cur.fetchone()
                cur.close()
                if row:
                    fetched_at = row[1]
                    if fetched_at.tzinfo is None:
                        fetched_at = fetched_at.replace(tzinfo=BRASILIA_TZ)
                    age_hours = (datetime.now(BRASILIA_TZ) - fetched_at).total_seconds() / 3600
                    if age_hours < 24:
                        print(f"✅ DB CACHE HIT: ultimos_jogos time {team_id} limite {limite} ({age_hours:.1f}h atrás)")
                        return row[0]
                    print(f"⏰ DB CACHE EXPIRADO: ultimos_jogos time {team_id} ({age_hours:.1f}h > 24h)")
                return None
        except Exception as e:
            print(f"⚠️ DB cache_ultimos_jogos get erro: {e}")
            return None

    def set_cache_ultimos_jogos(self, team_id: int, limite: int, data: list) -> None:
        """Salva últimos jogos de um time no DB."""
        if not self.enabled:
            return
        try:
            with self._get_connection() as conn:
                if not conn:
                    return
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO cache_ultimos_jogos (team_id, limite, data, fetched_at)
                    VALUES (%s, %s, %s, NOW())
                    ON CONFLICT (team_id, limite) DO UPDATE
                        SET data = EXCLUDED.data, fetched_at = NOW()
                    """,
                    (team_id, limite, Json(data))
                )
                conn.commit()
                cur.close()
                print(f"💾 DB CACHE SAVE: ultimos_jogos time {team_id} limite {limite} ({len(data)} jogos)")
        except Exception as e:
            print(f"⚠️ DB cache_ultimos_jogos set erro: {e}")

    def get_cache_h2h(self, team1_id: int, team2_id: int, limite: int) -> Optional[list]:
        """Busca H2H entre dois times no DB. TTL: 30 dias. Retorna None em caso de miss."""
        if not self.enabled:
            return None
        t1, t2 = min(team1_id, team2_id), max(team1_id, team2_id)
        try:
            with self._get_connection() as conn:
                if not conn:
                    return None
                cur = conn.cursor()
                cur.execute(
                    "SELECT data, fetched_at FROM cache_h2h WHERE team1_id = %s AND team2_id = %s AND limite = %s",
                    (t1, t2, limite)
                )
                row = cur.fetchone()
                cur.close()
                if row:
                    fetched_at = row[1]
                    if fetched_at.tzinfo is None:
                        fetched_at = fetched_at.replace(tzinfo=BRASILIA_TZ)
                    age_days = (datetime.now(BRASILIA_TZ) - fetched_at).total_seconds() / 86400
                    if age_days < 30:
                        print(f"✅ DB CACHE HIT: h2h {t1}x{t2} limite {limite} ({age_days:.1f}d atrás)")
                        return row[0]
                    print(f"⏰ DB CACHE EXPIRADO: h2h {t1}x{t2} ({age_days:.1f}d > 30d)")
                return None
        except Exception as e:
            print(f"⚠️ DB cache_h2h get erro: {e}")
            return None

    def set_cache_h2h(self, team1_id: int, team2_id: int, limite: int, data: list) -> None:
        """Salva H2H entre dois times no DB."""
        if not self.enabled:
            return
        t1, t2 = min(team1_id, team2_id), max(team1_id, team2_id)
        try:
            with self._get_connection() as conn:
                if not conn:
                    return
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO cache_h2h (team1_id, team2_id, limite, data, fetched_at)
                    VALUES (%s, %s, %s, %s, NOW())
                    ON CONFLICT (team1_id, team2_id, limite) DO UPDATE
                        SET data = EXCLUDED.data, fetched_at = NOW()
                    """,
                    (t1, t2, limite, Json(data))
                )
                conn.commit()
                cur.close()
                print(f"💾 DB CACHE SAVE: h2h {t1}x{t2} limite {limite} ({len(data)} confrontos)")
        except Exception as e:
            print(f"⚠️ DB cache_h2h set erro: {e}")

    def salvar_analise(self, fixture_id: int, dados_jogo: dict, analises: dict, stats: dict):
        """
        Salva análise completa de um jogo no banco de dados ou cache.json.

        Args:
            fixture_id: ID único do jogo na API-Football
            dados_jogo: Dict com {data_jogo, liga, time_casa, time_fora}
            analises: Dict com {gols, cantos, btts, resultado, cartoes, contexto}
            stats: Dict com {stats_casa, stats_fora, classificacao}
        """
        # Contar total de palpites
        total_palpites = 0
        confiancas = []

        for mercado in ['gols', 'cantos', 'btts', 'resultado', 'cartoes']:
            if mercado in analises and analises[mercado]:
                palpites = analises[mercado].get('palpites', [])
                total_palpites += len(palpites)
                for p in palpites:
                    confiancas.append(p.get('confianca', 0))

        confianca_media = round(sum(confiancas) / len(confiancas), 1) if confiancas else 0
        
        # Se banco de dados está habilitado, salvar lá
        if self.enabled:
            try:
                with self._get_connection() as conn:
                    if conn:
                        cursor = conn.cursor()

                        # INSERT ou UPDATE
                        query = """
                            INSERT INTO analises_jogos 
                            (fixture_id, data_jogo, liga, time_casa, time_fora, 
                             stats_casa, stats_fora, classificacao,
                             analise_gols, analise_cantos, analise_btts, analise_resultado, analise_cartoes, analise_contexto,
                             analise_gabt, analise_placar_exato, analise_handicap_europeu, analise_primeiro_marcador,
                             analise_htft, analise_win_to_nil, analise_draw_no_bet,
                             palpites_totais, confianca_media, data_analise, atualizado_em)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (fixture_id) 
                            DO UPDATE SET
                                stats_casa = EXCLUDED.stats_casa,
                                stats_fora = EXCLUDED.stats_fora,
                                classificacao = EXCLUDED.classificacao,
                                analise_gols = EXCLUDED.analise_gols,
                                analise_cantos = EXCLUDED.analise_cantos,
                                analise_btts = EXCLUDED.analise_btts,
                                analise_resultado = EXCLUDED.analise_resultado,
                                analise_cartoes = EXCLUDED.analise_cartoes,
                                analise_contexto = EXCLUDED.analise_contexto,
                                analise_gabt = EXCLUDED.analise_gabt,
                                analise_placar_exato = EXCLUDED.analise_placar_exato,
                                analise_handicap_europeu = EXCLUDED.analise_handicap_europeu,
                                analise_primeiro_marcador = EXCLUDED.analise_primeiro_marcador,
                                analise_htft = EXCLUDED.analise_htft,
                                analise_win_to_nil = EXCLUDED.analise_win_to_nil,
                                analise_draw_no_bet = EXCLUDED.analise_draw_no_bet,
                                palpites_totais = EXCLUDED.palpites_totais,
                                confianca_media = EXCLUDED.confianca_media,
                                atualizado_em = EXCLUDED.atualizado_em
                        """

                        cursor.execute(query, (
                            fixture_id,
                            dados_jogo['data_jogo'],
                            dados_jogo['liga'],
                            dados_jogo['time_casa'],
                            dados_jogo['time_fora'],
                            Json(stats.get('stats_casa', {})),
                            Json(stats.get('stats_fora', {})),
                            Json(stats.get('classificacao', {})),
                            Json(analises.get('gols', {})),
                            Json(analises.get('cantos', {})),
                            Json(analises.get('btts', {})),
                            Json(analises.get('resultado', {})),
                            Json(analises.get('cartoes', {})),
                            Json(analises.get('contexto', {})),
                            Json(analises.get('gabt', {})),
                            Json(analises.get('placar_exato', {})),
                            Json(analises.get('handicap_europeu', {})),
                            Json(analises.get('primeiro_marcador', {})),
                            Json(analises.get('htft', {})),
                            Json(analises.get('win_to_nil', {})),
                            Json(analises.get('draw_no_bet', {})),
                            total_palpites,
                            confianca_media,
                            agora_brasilia(),
                            agora_brasilia()
                        ))

                        conn.commit()
                        cursor.close()

                        print(f"✅ Análise salva no banco: Fixture #{fixture_id} ({total_palpites} palpites)")

                        # Salvar palpites individuais em palpites_historico
                        self._salvar_palpites_historico(fixture_id, analises, conn)

                        return True

            except Exception as e:
                print(f"❌ Erro ao salvar análise no banco: {e}")
        
        # Fallback: salvar no cache.json se banco não está disponível
        if self.use_cache_fallback:
            cache_key = f"analise_jogo_{fixture_id}_None_None"
            
            # Criar estrutura compatível com o banco de dados
            analise_completa = {
                'fixture_id': fixture_id,
                'data_jogo': dados_jogo.get('data_jogo'),
                'liga': dados_jogo.get('liga'),
                'time_casa': dados_jogo.get('time_casa'),
                'time_fora': dados_jogo.get('time_fora'),
                'stats_casa': stats.get('stats_casa', {}),
                'stats_fora': stats.get('stats_fora', {}),
                'classificacao': stats.get('classificacao', {}),
                'analise_gols': analises.get('gols', {}),
                'analise_cantos': analises.get('cantos', {}),
                'analise_btts': analises.get('btts', {}),
                'analise_resultado': analises.get('resultado', {}),
                'analise_cartoes': analises.get('cartoes', {}),
                'analise_contexto': analises.get('contexto', {}),
                'analise_gabt': analises.get('gabt', {}),
                'analise_placar_exato': analises.get('placar_exato', {}),
                'analise_handicap_europeu': analises.get('handicap_europeu', {}),
                'analise_primeiro_marcador': analises.get('primeiro_marcador', {}),
                'analise_htft': analises.get('htft', {}),
                'analise_win_to_nil': analises.get('win_to_nil', {}),
                'analise_draw_no_bet': analises.get('draw_no_bet', {}),
                'palpites_totais': total_palpites,
                'confianca_media': confianca_media,
                'data_analise': agora_brasilia().isoformat(),
                'atualizado_em': agora_brasilia().isoformat()
            }
            
            # Salvar no cache com TTL de 24 horas
            cache_manager.set(cache_key, analise_completa, expiration_minutes=1440)
            print(f"✅ Análise salva no cache.json: Fixture #{fixture_id} ({total_palpites} palpites)")
            return True
        
        return False

    def _salvar_palpites_historico(self, fixture_id: int, analises: dict, conn) -> None:
        """
        Insere palpites individuais em palpites_historico após análise de um jogo.
        Usa INSERT ... ON CONFLICT DO NOTHING para ser idempotente.

        Todos os mercados são persistidos. Mercados não avaliáveis automaticamente
        (Finalizações, Cartões, Primeiro Marcador, Asian Handicap) ficam com
        acertou=NULL até que um avaliador específico seja implementado.

        Args:
            fixture_id: ID do jogo
            analises: Dict com análises por mercado (gols, cantos, btts, etc.)
            conn: Conexão psycopg2 já aberta (mesma transação)
        """
        if not conn:
            return

        MERCADOS = [
            'gols', 'cantos', 'btts', 'resultado', 'cartoes',
            'finalizacoes', 'handicaps', 'dupla_chance', 'gabt',
            'placar_exato', 'handicap_europeu', 'primeiro_marcador',
        ]

        inseridos = 0
        try:
            cursor = conn.cursor()
            for mercado_key in MERCADOS:
                analise_mercado = analises.get(mercado_key)
                if not analise_mercado:
                    continue
                palpites = analise_mercado.get('palpites', [])
                if not palpites:
                    continue

                for p in palpites:
                    tipo = p.get('tipo', '')
                    mercado_nome = p.get('mercado') or mercado_key.capitalize()
                    confianca = int(p.get('confianca', 0))
                    odd = p.get('odd')
                    periodo = p.get('periodo', 'FT') or 'FT'
                    time_aposta = p.get('time') or 'Total'

                    try:
                        odd_val = float(odd) if odd is not None else None
                    except (TypeError, ValueError):
                        odd_val = None

                    cursor.execute(
                        """
                        INSERT INTO palpites_historico
                            (fixture_id, mercado, linha, time_aposta, confianca,
                             odd, resultado_esperado, periodo)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (fixture_id, mercado, linha, periodo, time_aposta) DO NOTHING
                        """,
                        (fixture_id, mercado_nome, tipo, time_aposta, confianca,
                         odd_val, tipo, periodo),
                    )
                    inseridos += 1

            conn.commit()
            cursor.close()
            if inseridos:
                print(f"📋 Palpites histórico: {inseridos} palpites salvos para Fixture #{fixture_id}")

        except Exception as e:
            print(f"❌ Erro ao salvar palpites_historico para Fixture #{fixture_id}: {e}")
            try:
                conn.rollback()
            except Exception:
                pass

    def buscar_analise(
        self,
        fixture_id: int,
        max_idade_horas: int = 12,
        data_jogo: Optional[datetime] = None,
        permitir_stale: bool = False,
    ) -> Optional[Dict]:
        """
        Busca análise existente no banco de dados ou cache.json.

        TTL Inteligente (quando data_jogo é fornecido):
          - kickoff em mais de 24h → 12h TTL
          - kickoff entre 2h e 24h → 2h TTL
          - kickoff em menos de 2h → sem cache (escalação oficial iminente)

        Graceful degradation: quando permitir_stale=True e nenhuma análise
        válida for encontrada, retorna qualquer análise armazenada (mesmo stale)
        para evitar falha total quando a API está indisponível.

        Args:
            fixture_id: ID único do jogo
            max_idade_horas: Idade máxima em horas (usado se data_jogo ausente)
            data_jogo: Horário do kickoff para TTL dinâmico
            permitir_stale: Retornar análise stale se não houver cache válido

        Returns:
            Dict com a análise completa ou None se não encontrar
        """
        # Determinar TTL efetivo
        if data_jogo is not None:
            ttl_horas = calcular_ttl_analise(data_jogo)
        else:
            ttl_horas = max_idade_horas

        # TTL=None → kickoff iminente, não retornar cache (mas stale ainda pode)
        if ttl_horas is None and not permitir_stale:
            print(f"⏱️  CACHE SKIP: Kickoff iminente para Fixture #{fixture_id} — análise fresca obrigatória")
            return None

        # Se banco de dados está habilitado, tentar buscar lá primeiro
        if self.enabled:
            try:
                with self._get_connection() as conn:
                    if conn:
                        cursor = conn.cursor(cursor_factory=RealDictCursor)

                        if ttl_horas is not None:
                            # Buscar apenas análises dentro do TTL
                            limite_tempo = agora_brasilia() - timedelta(hours=ttl_horas)
                            query = """
                                SELECT * FROM analises_jogos
                                WHERE fixture_id = %s
                                AND atualizado_em >= %s
                            """
                            cursor.execute(query, (fixture_id, limite_tempo))
                        else:
                            # Stale: buscar qualquer análise existente
                            query = "SELECT * FROM analises_jogos WHERE fixture_id = %s"
                            cursor.execute(query, (fixture_id,))

                        resultado = cursor.fetchone()

                        if not resultado and permitir_stale and ttl_horas is not None:
                            # Fallback gracioso: retornar análise stale se existir
                            cursor.execute(
                                "SELECT * FROM analises_jogos WHERE fixture_id = %s",
                                (fixture_id,),
                            )
                            resultado = cursor.fetchone()
                            if resultado:
                                print(f"⚠️  CACHE STALE (DB): Análise stale servida para Fixture #{fixture_id}")

                        cursor.close()

                        if resultado:
                            analise = dict(resultado)
                            stale_tag = " [STALE]" if permitir_stale and ttl_horas is None else ""
                            print(f"🎯 CACHE HIT (DB){stale_tag}: Análise encontrada para Fixture #{fixture_id} ({analise['palpites_totais']} palpites)")
                            return analise
                        else:
                            print(f"⚡ CACHE MISS (DB): Análise não encontrada para Fixture #{fixture_id}")
                            return None

            except Exception as e:
                print(f"❌ Erro ao buscar análise no banco: {e}")

        # Fallback: buscar no cache.json se banco não está disponível
        if self.use_cache_fallback:
            cache_key = f"analise_jogo_{fixture_id}_None_None"
            analise_cached = cache_manager.get(cache_key)

            if analise_cached:
                print(f"🎯 CACHE HIT (JSON): Análise encontrada para Fixture #{fixture_id}")
                return analise_cached
            else:
                print(f"⚡ CACHE MISS (JSON): Análise não encontrada para Fixture #{fixture_id}")
                return None

        return None

    def limpar_analises_antigas(self, dias: int = 7):
        """
        Remove análises antigas do banco de dados.

        Args:
            dias: Remover análises com mais de X dias (padrão: 7)
        """
        if not self.enabled:
            return 0

        try:
            with self._get_connection() as conn:
                if not conn:
                    return 0
                    
                cursor = conn.cursor()

                limite_tempo = agora_brasilia() - timedelta(days=dias)

                query = "DELETE FROM analises_jogos WHERE data_jogo < %s"
                cursor.execute(query, (limite_tempo,))

                deletados = cursor.rowcount
                conn.commit()
                cursor.close()

                print(f"🧹 Limpeza: {deletados} análises antigas removidas")
                return deletados

        except Exception as e:
            print(f"❌ Erro ao limpar análises antigas: {e}")
            return 0

    def obter_estatisticas_cache(self) -> Dict:
        """
        Retorna estatísticas sobre o cache de análises.
        """
        if not self.enabled:
            return {"enabled": False}

        try:
            with self._get_connection() as conn:
                if not conn:
                    return {"enabled": True, "erro": "Conexão não disponível"}
                    
                cursor = conn.cursor(cursor_factory=RealDictCursor)

                # Total de análises
                cursor.execute("SELECT COUNT(*) as total FROM analises_jogos")
                total = cursor.fetchone()['total']

                # Análises de hoje
                cursor.execute("SELECT COUNT(*) as hoje FROM analises_jogos WHERE data_jogo = CURRENT_DATE")
                hoje = cursor.fetchone()['hoje']

                # Análises nas últimas 24h
                cursor.execute("SELECT COUNT(*) as recentes FROM analises_jogos WHERE atualizado_em >= NOW() - INTERVAL '24 hours'")
                recentes = cursor.fetchone()['recentes']

                cursor.close()

                return {
                    "enabled": True,
                    "total_analises": total,
                    "analises_hoje": hoje,
                    "analises_24h": recentes
                }

        except Exception as e:
            print(f"❌ Erro ao obter estatísticas: {e}")
            return {"enabled": True, "erro": str(e)}

    def forcar_reanalisar(self, fixture_id: int):
        """
        Remove análise específica do cache, forçando reanálise.
        """
        if not self.enabled:
            return False

        try:
            with self._get_connection() as conn:
                if not conn:
                    return False
                    
                cursor = conn.cursor()

                cursor.execute("DELETE FROM analises_jogos WHERE fixture_id = %s", (fixture_id,))

                conn.commit()
                cursor.close()

                print(f"🔄 Análise do Fixture #{fixture_id} removida. Será reanalisado.")
                return True

        except Exception as e:
            print(f"❌ Erro ao forçar reanálise: {e}")
            return False

    def save_daily_analysis(self, fixture_id: int, analysis_type: str, dossier_json: str, user_id: int):
        """
        Salva análise processada em batch no sistema de fila.
        
        Args:
            fixture_id: ID do jogo
            analysis_type: Tipo de análise ('full', 'goals_only', 'corners_only', etc.')
            dossier_json: JSON completo da análise (dossier)
            user_id: ID do usuário que solicitou
        """
        if not self.enabled:
            return False
        
        try:
            with self._get_connection() as conn:
                if not conn:
                    return False
                    
                cursor = conn.cursor()
                
                query = """
                    INSERT INTO daily_analyses 
                    (fixture_id, analysis_type, dossier_json, user_id, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (fixture_id, analysis_type, user_id)
                    DO UPDATE SET
                        dossier_json = EXCLUDED.dossier_json,
                        created_at = EXCLUDED.created_at
                """
                
                cursor.execute(query, (
                    fixture_id,
                    analysis_type,
                    dossier_json,
                    user_id,
                    agora_brasilia()
                ))
                
                conn.commit()
                cursor.close()
                return True
            
        except Exception as e:
            print(f"❌ Erro ao salvar daily analysis: {e}")
            return False
    
    def get_daily_analyses(self, user_id: int, analysis_type: str, offset: int = 0, limit: int = 5) -> List[Dict]:
        """
        Recupera análises paginadas do banco.
        
        Args:
            user_id: ID do usuário
            analysis_type: Tipo de análise
            offset: Offset para paginação
            limit: Limite de resultados
            
        Returns:
            Lista de análises com seus dossiers
        """
        if not self.enabled:
            return []
        
        try:
            with self._get_connection() as conn:
                if not conn:
                    return []
                    
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                
                query = """
                    SELECT id, fixture_id, analysis_type, dossier_json, created_at
                    FROM daily_analyses
                    WHERE user_id = %s AND analysis_type = %s
                    AND created_at >= CURRENT_DATE
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                """
                
                cursor.execute(query, (user_id, analysis_type, limit, offset))
                resultados = cursor.fetchall()
                
                cursor.close()
                
                return [dict(r) for r in resultados]
            
        except Exception as e:
            print(f"❌ Erro ao buscar daily analyses: {e}")
            return []
    
    def count_daily_analyses(self, user_id: int, analysis_type: str) -> int:
        """
        Conta total de análises disponíveis para paginação.
        
        Args:
            user_id: ID do usuário
            analysis_type: Tipo de análise
            
        Returns:
            Total de análises
        """
        if not self.enabled:
            return 0
        
        try:
            with self._get_connection() as conn:
                if not conn:
                    return 0
                    
                cursor = conn.cursor()
                
                query = """
                    SELECT COUNT(*) as total
                    FROM daily_analyses
                    WHERE user_id = %s AND analysis_type = %s
                    AND created_at >= CURRENT_DATE
                """
                
                cursor.execute(query, (user_id, analysis_type))
                total = cursor.fetchone()[0]
                
                cursor.close()
                
                return total
            
        except Exception as e:
            print(f"❌ Erro ao contar daily analyses: {e}")
            return 0

    # ─── Métodos para rastreamento de resultados (result_tracker) ─────────

    def buscar_fixtures_sem_resultado(self, janela_horas: int = 48) -> List[int]:
        """
        Retorna fixture_ids que têm palpites pendentes e não têm resultado gravado.
        Filtra jogos cuja data_jogo está dentro da janela de horas (padrão: 48h atrás).

        Args:
            janela_horas: Quantas horas atrás buscar jogos encerrados

        Returns:
            Lista de fixture_ids sem resultado registrado
        """
        if not self.enabled:
            return []

        try:
            with self._get_connection() as conn:
                if not conn:
                    return []

                cursor = conn.cursor()
                limite = agora_brasilia() - timedelta(hours=janela_horas)

                query = """
                    SELECT DISTINCT aj.fixture_id
                    FROM analises_jogos aj
                    LEFT JOIN resultado_jogos rj ON rj.fixture_id = aj.fixture_id
                    WHERE rj.fixture_id IS NULL
                      AND aj.data_jogo >= %s
                      AND aj.data_jogo <= %s
                    ORDER BY aj.fixture_id
                """
                cursor.execute(query, (limite, agora_brasilia()))
                rows = cursor.fetchall()
                cursor.close()

                return [r[0] for r in rows]

        except Exception as e:
            print(f"❌ Erro ao buscar fixtures sem resultado: {e}")
            return []

    def salvar_resultado_jogo(
        self,
        fixture_id: int,
        placar_casa: Optional[int],
        placar_fora: Optional[int],
        status_final: str,
    ) -> bool:
        """
        Grava o resultado real de um jogo em resultado_jogos.
        Usa UPSERT para ser idempotente.

        Args:
            fixture_id: ID do jogo
            placar_casa: Gols do time da casa (None se jogo não encerrado)
            placar_fora: Gols do time visitante
            status_final: Status da API (FT, AET, PEN, etc.)

        Returns:
            True se salvo com sucesso
        """
        if not self.enabled:
            return False

        try:
            with self._get_connection() as conn:
                if not conn:
                    return False

                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO resultado_jogos
                        (fixture_id, placar_casa, placar_fora, status_final, buscado_em)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (fixture_id) DO UPDATE SET
                        placar_casa  = EXCLUDED.placar_casa,
                        placar_fora  = EXCLUDED.placar_fora,
                        status_final = EXCLUDED.status_final,
                        buscado_em   = EXCLUDED.buscado_em
                    """,
                    (fixture_id, placar_casa, placar_fora, status_final, agora_brasilia()),
                )
                conn.commit()
                cursor.close()
                return True

        except Exception as e:
            print(f"❌ Erro ao salvar resultado do jogo #{fixture_id}: {e}")
            return False

    def buscar_palpites_pendentes(self, fixture_id: int) -> List[Dict]:
        """
        Retorna palpites sem resultado (acertou IS NULL) para um fixture.

        Args:
            fixture_id: ID do jogo

        Returns:
            Lista de dicts com os palpites pendentes
        """
        if not self.enabled:
            return []

        try:
            with self._get_connection() as conn:
                if not conn:
                    return []

                cursor = conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute(
                    """
                    SELECT id, fixture_id, mercado, linha, time_aposta, confianca, odd,
                           resultado_esperado, periodo
                    FROM palpites_historico
                    WHERE fixture_id = %s AND acertou IS NULL
                    ORDER BY id
                    """,
                    (fixture_id,),
                )
                rows = cursor.fetchall()
                cursor.close()
                return [dict(r) for r in rows]

        except Exception as e:
            print(f"❌ Erro ao buscar palpites pendentes #{fixture_id}: {e}")
            return []

    def atualizar_palpite_resultado(
        self,
        palpite_id: int,
        acertou: bool,
        roi_unitario: float,
    ) -> bool:
        """
        Marca um palpite como acertado/errado e registra ROI unitário.

        ROI unitário:
          - Acertou → odd − 1  (lucro unitário)
          - Errou   → −1       (perda unitária)

        Args:
            palpite_id: PK da tabela palpites_historico
            acertou: True se o palpite foi correto
            roi_unitario: Lucro/prejuízo unitário calculado

        Returns:
            True se atualizado com sucesso
        """
        if not self.enabled:
            return False

        try:
            with self._get_connection() as conn:
                if not conn:
                    return False

                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE palpites_historico
                    SET acertou = %s, roi_unitario = %s
                    WHERE id = %s
                    """,
                    (acertou, roi_unitario, palpite_id),
                )
                conn.commit()
                cursor.close()
                return True

        except Exception as e:
            print(f"❌ Erro ao atualizar palpite #{palpite_id}: {e}")
            return False

    def get_market_confidence_adjustment(
        self,
        mercado: str,
        liga_id: int = 0,
        script: str = '',
    ) -> float:
        """
        Retorna um ajuste de confiança (+/-) baseado na performance histórica do mercado
        para uma combinação específica de mercado + liga + script.

        Damping por tamanho de amostra (n_amostras):
          < 30:   sem ajuste (0.0) — dados insuficientes
          30-99:  50% do ajuste calculado
          100+:   100% do ajuste calculado

        Fórmula do ajuste bruto (antes do damping):
          taxa >= 65%: +0.5 (bônus)
          taxa 50-65%: 0.0 (neutro)
          taxa 40-50%: -0.3 (penalidade leve)
          taxa < 40%:  -0.7 (penalidade severa)

        Fallback: se não há dados específicos de liga+script, usa dados do mercado global (liga_id=0, script='').

        Args:
            mercado:  Nome do mercado (ex: "Gols", "Cantos", "BTTS")
            liga_id:  ID da liga (0 = global)
            script:   Script tático ('' = global)

        Returns:
            float: Ajuste de confiança dampened entre -0.7 e +0.5
        """
        if not self.enabled:
            return 0.0

        def _calc_adj(taxa: float, n: int) -> float:
            if n < 30:
                return 0.0
            if taxa >= 65:
                raw = 0.5
            elif taxa >= 50:
                raw = 0.0
            elif taxa >= 40:
                raw = -0.3
            else:
                raw = -0.7
            damping = 0.5 if n < 100 else 1.0
            return round(raw * damping, 3)

        try:
            with self._get_connection() as conn:
                if not conn:
                    return 0.0

                cursor = conn.cursor(cursor_factory=RealDictCursor)

                # Tentar primeiro com contexto específico
                cursor.execute(
                    """
                    SELECT n_amostras, taxa_acerto
                    FROM performance_mercados
                    WHERE mercado = %s AND liga_id = %s AND script = %s
                    """,
                    (mercado, liga_id, script),
                )
                row = cursor.fetchone()

                if row and row["n_amostras"] >= 30:
                    cursor.close()
                    return _calc_adj(float(row["taxa_acerto"] or 0), int(row["n_amostras"]))

                # Fallback: dados globais do mercado (liga_id=0, script='')
                cursor.execute(
                    """
                    SELECT SUM(n_amostras) AS total, SUM(total_acertos) AS acertos
                    FROM performance_mercados
                    WHERE mercado = %s
                    """,
                    (mercado,),
                )
                agg = cursor.fetchone()
                cursor.close()

                if not agg or not agg["total"] or int(agg["total"]) < 30:
                    return 0.0

                taxa_global = float(agg["acertos"] or 0) / float(agg["total"]) * 100
                return _calc_adj(taxa_global, int(agg["total"]))

        except Exception as e:
            print(f"❌ Erro ao buscar performance do mercado '{mercado}': {e}")
            return 0.0

    def upsert_performance_mercado(
        self,
        mercado: str,
        acertou: bool,
        roi_unitario: float,
        liga_id: int = 0,
        script: str = '',
    ) -> bool:
        """
        Atualiza (ou cria) o registro de performance para (mercado, liga_id, script).

        Args:
            mercado:      Nome do mercado
            acertou:      True se o palpite acertou
            roi_unitario: Lucro/prejuízo unitário
            liga_id:      ID da liga (0 = desconhecido)
            script:       Script tático ('' = desconhecido)

        Returns:
            True se atualizado com sucesso
        """
        if not self.enabled:
            return False

        acertou_int = 1 if acertou else 0
        errou_int = 0 if acertou else 1

        try:
            with self._get_connection() as conn:
                if not conn:
                    return False

                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO performance_mercados
                        (mercado, liga_id, script, n_amostras, total_acertos, total_erros,
                         taxa_acerto, roi_total, atualizado_em)
                    VALUES (%s, %s, %s, 1, %s, %s, %s, %s, %s)
                    ON CONFLICT (mercado, liga_id, script) DO UPDATE SET
                        n_amostras    = performance_mercados.n_amostras + 1,
                        total_acertos = performance_mercados.total_acertos + %s,
                        total_erros   = performance_mercados.total_erros   + %s,
                        taxa_acerto   = ROUND(
                            (performance_mercados.total_acertos + %s)::DECIMAL
                            / (performance_mercados.n_amostras + 1) * 100,
                            2
                        ),
                        roi_total     = performance_mercados.roi_total + %s,
                        atualizado_em = %s
                    """,
                    (
                        mercado, liga_id, script,
                        acertou_int, errou_int,
                        100.0 if acertou else 0.0,
                        roi_unitario,
                        agora_brasilia(),
                        acertou_int, errou_int, acertou_int,
                        roi_unitario,
                        agora_brasilia(),
                    ),
                )
                conn.commit()
                cursor.close()
                return True

        except Exception as e:
            print(f"❌ Erro ao upsert performance do mercado '{mercado}': {e}")
            return False

    def buscar_performance_mercados(self) -> List[Dict]:
        """
        Retorna performance agregada por mercado (soma de todas as ligas/scripts).
        Ordenada por taxa de acerto DESC.

        Returns:
            Lista de dicts com mercado, n_amostras, total_acertos, taxa_acerto, roi_total
        """
        if not self.enabled:
            return []

        try:
            with self._get_connection() as conn:
                if not conn:
                    return []

                cursor = conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute(
                    """
                    SELECT
                        mercado,
                        SUM(n_amostras) AS total_palpites,
                        SUM(total_acertos) AS total_acertos,
                        SUM(total_erros) AS total_erros,
                        CASE WHEN SUM(n_amostras) > 0
                             THEN ROUND(SUM(total_acertos)::DECIMAL / SUM(n_amostras) * 100, 2)
                             ELSE 0 END AS taxa_acerto,
                        SUM(roi_total) AS roi_total,
                        MAX(atualizado_em) AS atualizado_em
                    FROM performance_mercados
                    WHERE n_amostras > 0
                    GROUP BY mercado
                    ORDER BY taxa_acerto DESC, total_palpites DESC
                    """
                )
                rows = cursor.fetchall()
                cursor.close()
                return [dict(r) for r in rows]

        except Exception as e:
            print(f"❌ Erro ao buscar performance de mercados: {e}")
            return []

    def buscar_performance_por_liga(self) -> List[Dict]:
        """
        Retorna performance detalhada por mercado + liga_id para breakdown no frontend.

        Returns:
            Lista de dicts com mercado, liga_id, n_amostras, taxa_acerto, roi_total
        """
        if not self.enabled:
            return []

        try:
            with self._get_connection() as conn:
                if not conn:
                    return []

                cursor = conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute(
                    """
                    SELECT mercado, liga_id,
                           SUM(n_amostras) AS n_amostras,
                           SUM(total_acertos) AS total_acertos,
                           CASE WHEN SUM(n_amostras) > 0
                                THEN ROUND(SUM(total_acertos)::DECIMAL / SUM(n_amostras) * 100, 2)
                                ELSE 0 END AS taxa_acerto,
                           SUM(roi_total) AS roi_total
                    FROM performance_mercados
                    WHERE n_amostras >= 5 AND liga_id > 0
                    GROUP BY mercado, liga_id
                    ORDER BY mercado, taxa_acerto DESC
                    """
                )
                rows = cursor.fetchall()
                cursor.close()
                return [dict(r) for r in rows]

        except Exception as e:
            print(f"❌ Erro ao buscar performance por liga: {e}")
            return []

    def buscar_evolucao_acerto(self, dias: int = 30) -> List[Dict]:
        """
        Retorna a taxa de acerto diária dos últimos N dias para gráfico de evolução.

        Args:
            dias: Janela de dias para calcular a evolução (padrão: 30)

        Returns:
            Lista de dicts com data, total, acertos, taxa_acerto ordenados por data
        """
        if not self.enabled:
            return []

        try:
            with self._get_connection() as conn:
                if not conn:
                    return []

                cursor = conn.cursor(cursor_factory=RealDictCursor)
                limite = agora_brasilia() - timedelta(days=dias)
                cursor.execute(
                    """
                    SELECT
                        DATE(ph.criado_em AT TIME ZONE 'America/Sao_Paulo') AS data,
                        COUNT(*) AS total,
                        SUM(CASE WHEN ph.acertou = TRUE THEN 1 ELSE 0 END) AS acertos,
                        ROUND(
                            SUM(CASE WHEN ph.acertou = TRUE THEN 1 ELSE 0 END)::DECIMAL
                            / COUNT(*) * 100,
                            1
                        ) AS taxa_acerto
                    FROM palpites_historico ph
                    WHERE ph.acertou IS NOT NULL
                      AND ph.criado_em >= %s
                    GROUP BY DATE(ph.criado_em AT TIME ZONE 'America/Sao_Paulo')
                    ORDER BY data ASC
                    """,
                    (limite,),
                )
                rows = cursor.fetchall()
                cursor.close()
                return [
                    {
                        "data": str(r["data"]),
                        "total": int(r["total"]),
                        "acertos": int(r["acertos"]),
                        "taxa_acerto": float(r["taxa_acerto"] or 0),
                    }
                    for r in rows
                ]

        except Exception as e:
            print(f"❌ Erro ao buscar evolução de acerto: {e}")
            return []

    def buscar_ultimos_palpites(self, limite: int = 20) -> List[Dict]:
        """
        Retorna os últimos N palpites avaliados (acertou IS NOT NULL) para o histórico.

        Args:
            limite: Quantidade máxima de registros

        Returns:
            Lista de dicts com palpite + resultado
        """
        if not self.enabled:
            return []

        try:
            with self._get_connection() as conn:
                if not conn:
                    return []

                cursor = conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute(
                    """
                    SELECT ph.id, ph.fixture_id, ph.mercado, ph.linha, ph.time_aposta,
                           ph.confianca, ph.odd, ph.periodo, ph.acertou, ph.roi_unitario,
                           ph.criado_em,
                           aj.time_casa, aj.time_fora, aj.liga, aj.data_jogo
                    FROM palpites_historico ph
                    LEFT JOIN analises_jogos aj ON aj.fixture_id = ph.fixture_id
                    WHERE ph.acertou IS NOT NULL
                    ORDER BY ph.criado_em DESC
                    LIMIT %s
                    """,
                    (limite,),
                )
                rows = cursor.fetchall()
                cursor.close()
                return [dict(r) for r in rows]

        except Exception as e:
            print(f"❌ Erro ao buscar últimos palpites: {e}")
            return []

    def salvar_estatisticas_jogador(
        self,
        jogador_id: int,
        fixture_id: int,
        time_id: int,
        nome: str,
        minutos: int,
        gols: int,
        assistencias: int,
        finalizacoes: int,
        finalizacoes_no_gol: int,
        cartao_amarelo: bool,
        cartao_vermelho: bool,
        eh_mandante: bool,
        foi_titular: bool,
    ) -> bool:
        """
        Insere ou ignora estatísticas de um jogador para uma partida.
        Usa ON CONFLICT DO NOTHING — idempotente.

        Returns:
            True se inserido ou já existia (sem erro)
        """
        if not self.enabled:
            return False

        try:
            with self._get_connection() as conn:
                if not conn:
                    return False

                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO estatisticas_jogadores
                        (jogador_id, fixture_id, time_id, minutos, gols, assistencias,
                         finalizacoes, finalizacoes_no_gol, cartao_amarelo, cartao_vermelho,
                         eh_mandante, foi_titular)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (jogador_id, fixture_id) DO NOTHING
                    """,
                    (
                        jogador_id, fixture_id, time_id, minutos, gols, assistencias,
                        finalizacoes, finalizacoes_no_gol, cartao_amarelo, cartao_vermelho,
                        eh_mandante, foi_titular,
                    ),
                )
                conn.commit()
                cursor.close()

                # Recalcular perfil acumulado do jogador
                self._recalcular_perfil_jogador(jogador_id, time_id, nome)
                return True

        except Exception as e:
            print(f"❌ Erro ao salvar stats do jogador #{jogador_id}: {e}")
            return False

    def _recalcular_perfil_jogador(self, jogador_id: int, time_id: int, nome: str) -> None:
        """
        Recalcula e faz upsert do perfil acumulado de um jogador em perfis_jogadores.
        Calcula médias e desvio padrão de gols e finalizações.
        """
        if not self.enabled:
            return

        try:
            with self._get_connection() as conn:
                if not conn:
                    return

                cursor = conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute(
                    """
                    SELECT
                        COUNT(*) AS n_total,
                        SUM(CASE WHEN eh_mandante THEN 1 ELSE 0 END) AS n_casa,
                        SUM(CASE WHEN NOT eh_mandante THEN 1 ELSE 0 END) AS n_fora,
                        SUM(CASE WHEN foi_titular THEN 1 ELSE 0 END) AS n_titular,
                        AVG(gols) AS media_gols,
                        AVG(assistencias) AS media_assistencias,
                        AVG(finalizacoes) AS media_finalizacoes,
                        STDDEV_POP(gols) AS stddev_gols,
                        STDDEV_POP(finalizacoes) AS stddev_finalizacoes
                    FROM estatisticas_jogadores
                    WHERE jogador_id = %s
                    """,
                    (jogador_id,),
                )
                row = cursor.fetchone()
                cursor.close()

                if not row or not row["n_total"]:
                    return

                cursor2 = conn.cursor()
                cursor2.execute(
                    """
                    INSERT INTO perfis_jogadores
                        (jogador_id, time_id, nome, n_jogos_total, n_jogos_casa, n_jogos_fora,
                         n_jogos_titular, media_gols, media_assistencias, media_finalizacoes,
                         stddev_gols, stddev_finalizacoes, atualizado_em)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (jogador_id) DO UPDATE SET
                        nome               = EXCLUDED.nome,
                        n_jogos_total      = EXCLUDED.n_jogos_total,
                        n_jogos_casa       = EXCLUDED.n_jogos_casa,
                        n_jogos_fora       = EXCLUDED.n_jogos_fora,
                        n_jogos_titular    = EXCLUDED.n_jogos_titular,
                        media_gols         = EXCLUDED.media_gols,
                        media_assistencias = EXCLUDED.media_assistencias,
                        media_finalizacoes = EXCLUDED.media_finalizacoes,
                        stddev_gols        = EXCLUDED.stddev_gols,
                        stddev_finalizacoes= EXCLUDED.stddev_finalizacoes,
                        atualizado_em      = EXCLUDED.atualizado_em
                    """,
                    (
                        jogador_id, time_id, nome,
                        int(row["n_total"]),
                        int(row["n_casa"] or 0),
                        int(row["n_fora"] or 0),
                        int(row["n_titular"] or 0),
                        float(row["media_gols"] or 0),
                        float(row["media_assistencias"] or 0),
                        float(row["media_finalizacoes"] or 0),
                        float(row["stddev_gols"] or 0),
                        float(row["stddev_finalizacoes"] or 0),
                        agora_brasilia(),
                    ),
                )
                conn.commit()
                cursor2.close()

        except Exception as e:
            print(f"⚠️ Erro ao recalcular perfil do jogador #{jogador_id}: {e}")

    def get_player_confidence_tier(
        self,
        jogador_id: int,
        contexto: str = 'total',
    ) -> Dict:
        """
        Retorna o nível de confiança e metadados do perfil de um jogador.

        Níveis baseados em n_jogos_total:
          < 3 jogos:  tier='none'     — sem mercados de jogador
          3-5 jogos:  tier='low'      — confiança reduzida (aviso de amostra pequena)
          6-9 jogos:  tier='medium'   — confiança moderada
          10+ jogos:  tier='high'     — confiança plena

        Alta inconstância (stddev > 1.5× média): reduz tier em um nível.

        Args:
            jogador_id: ID do jogador na API-Football
            contexto:   'total' | 'casa' | 'fora'

        Returns:
            Dict com {tier, n_jogos, media_gols, media_finalizacoes, stddev_gols,
                      stddev_finalizacoes, aviso}
        """
        default = {
            "tier": "none",
            "n_jogos": 0,
            "media_gols": 0.0,
            "media_finalizacoes": 0.0,
            "stddev_gols": 0.0,
            "stddev_finalizacoes": 0.0,
            "aviso": None,
        }

        if not self.enabled:
            return default

        try:
            with self._get_connection() as conn:
                if not conn:
                    return default

                cursor = conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute(
                    """
                    SELECT n_jogos_total, n_jogos_casa, n_jogos_fora,
                           media_gols, media_assistencias, media_finalizacoes,
                           stddev_gols, stddev_finalizacoes
                    FROM perfis_jogadores
                    WHERE jogador_id = %s
                    """,
                    (jogador_id,),
                )
                row = cursor.fetchone()
                cursor.close()

                if not row:
                    return default

                if contexto == 'casa':
                    n = int(row["n_jogos_casa"] or 0)
                elif contexto == 'fora':
                    n = int(row["n_jogos_fora"] or 0)
                else:
                    n = int(row["n_jogos_total"] or 0)

                media_gols = float(row["media_gols"] or 0)
                media_fin = float(row["media_finalizacoes"] or 0)
                stddev_gols = float(row["stddev_gols"] or 0)
                stddev_fin = float(row["stddev_finalizacoes"] or 0)

                # Determinar tier base
                if n < 3:
                    tier = "none"
                elif n < 6:
                    tier = "low"
                elif n < 10:
                    tier = "medium"
                else:
                    tier = "high"

                # Penalidade por alta inconstância: stddev > 1.5 × média
                aviso = None
                if tier != "none":
                    if media_gols > 0 and stddev_gols > 1.5 * media_gols:
                        tier = {"high": "medium", "medium": "low", "low": "none"}.get(tier, tier)
                        aviso = "Alta inconstância nos gols — confiança reduzida"
                    elif media_fin > 0 and stddev_fin > 1.5 * media_fin:
                        aviso = "Alta inconstância nas finalizações"

                return {
                    "tier": tier,
                    "n_jogos": n,
                    "media_gols": media_gols,
                    "media_finalizacoes": media_fin,
                    "stddev_gols": stddev_gols,
                    "stddev_finalizacoes": stddev_fin,
                    "aviso": aviso,
                }

        except Exception as e:
            print(f"❌ Erro ao buscar tier do jogador #{jogador_id}: {e}")
            return default
