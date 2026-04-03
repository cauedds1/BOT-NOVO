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
        """
        
        try:
            with self._get_connection() as conn:
                if not conn:
                    print("❌ Não foi possível obter conexão para inicializar banco")
                    return False
                
                cursor = conn.cursor()
                
                # Executar todo o schema
                cursor.execute(schema_sql)
                
                conn.commit()
                cursor.close()
                
                print("✅ Database schema inicializado com sucesso!")
                print("   📋 Tabelas criadas: analises_jogos, daily_analyses, palpites_historico, resultado_jogos")
                return True
                
        except Exception as e:
            print(f"❌ Erro ao inicializar database schema: {e}")
            return False
    
    def close_pool(self):
        """Fecha o connection pool ao desligar a aplicação"""
        if self.pool:
            self.pool.closeall()
            print("✅ Connection pool fechado")

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
                             palpites_totais, confianca_media, data_analise, atualizado_em)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
