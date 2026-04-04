"""
Analisador de Gols V3.0 - DEEP ANALYSIS PROTOCOL

BLUEPRINT IMPLEMENTATION:
- Retorna LISTA de múltiplas predições (~20 predições)
- Analisa submercados: Total Goals (FT), HT Goals, BTTS, Team Goals
- Cada predição tem confiança calculada via confidence_calculator
- Modificador tático centralizado em confidence_calculator.apply_tactical_script_modifier()
"""

from config import (MIN_CONFIANCA_GOLS_OVER_UNDER,
                    MIN_CONFIANCA_GOLS_OVER_1_5, MIN_CONFIANCA_GOLS_OVER_3_5)
from analysts.confidence_calculator import (
    calculate_final_confidence,
    calculate_statistical_probability_goals_over
)
import math
import time as _time

# --- Trivial market cache (TTL 1h) ---
# Stores set of bet types (tipo strings) that appeared in >70% of games in the last 7 days.
_trivial_market_cache: dict = {"ts": 0.0, "types": set()}
_TRIVIAL_CACHE_TTL = 3600  # 1 hour
_TRIVIAL_THRESHOLD = 0.70  # 70% frequency → trivial market
_TRIVIAL_PENALTY = 0.7     # confidence penalty for trivial markets


# Lazy singleton for trivial-market DB queries (avoids heavy import at module load)
_trivial_db_instance = None


def _get_trivial_db():
    """Return a lightweight DatabaseManager instance (1-2 connections)."""
    global _trivial_db_instance
    if _trivial_db_instance is None:
        import db_manager as _dbm
        _trivial_db_instance = _dbm.DatabaseManager(min_conn=1, max_conn=2)
    return _trivial_db_instance


def _get_trivial_market_types() -> set:
    """
    Query palpites_historico to find bet types that appeared in >70% of analyzed
    games in the last 7 days. Result is cached in memory for 1 hour.

    Returns an empty set when there are insufficient samples (<5 distinct fixtures).
    """
    now = _time.time()
    if now - _trivial_market_cache["ts"] < _TRIVIAL_CACHE_TTL:
        return _trivial_market_cache["types"]

    trivial: set = set()
    try:
        db = _get_trivial_db()
        with db._get_connection() as conn:
            if conn is None:
                return trivial
            with conn.cursor() as cur:
                cur.execute("""
                    WITH window_data AS (
                        SELECT linha, fixture_id
                        FROM palpites_historico
                        WHERE criado_em >= NOW() - INTERVAL '7 days'
                          AND mercado = 'Gols'
                    ),
                    total AS (
                        SELECT COUNT(DISTINCT fixture_id) AS n FROM window_data
                    ),
                    per_market AS (
                        SELECT linha,
                               COUNT(DISTINCT fixture_id) AS cnt
                        FROM window_data
                        GROUP BY linha
                    )
                    SELECT p.linha
                    FROM per_market p, total t
                    WHERE t.n >= 5
                      AND p.cnt::float / t.n > %s
                """, (_TRIVIAL_THRESHOLD,))
                rows = cur.fetchall()
                trivial = {row[0] for row in rows}
    except Exception:
        pass

    _trivial_market_cache["ts"] = now
    _trivial_market_cache["types"] = trivial
    if trivial:
        print(f"  📊 [TRIVIAL] Mercados triviais (>{int(_TRIVIAL_THRESHOLD*100)}% dos jogos/7d): {trivial}")
    return trivial


def analisar_mercado_gols(analysis_packet, odds):
    """
    FUNÇÃO PRINCIPAL - Análise profunda do mercado de gols.
    
    ACTION 1.1: Retorna LISTA de múltiplas predições (~20 predições) com submercados:
    - Total Goals FT: Over/Under 1.5, 2.5, 3.5
    - First Half Goals HT: Over/Under 0.5, 1.5
    - Both Teams To Score: Sim e Não
    - Team Goals: Home Over/Under 0.5, 1.5 / Away Over/Under 0.5, 1.5
    
    Args:
        analysis_packet: Pacote completo do Master Analyzer
        odds: Dicionário com odds disponíveis
    
    Returns:
        list: Lista de dicionários de predições (format compatível com sistema atual)
    """
    if 'error' in analysis_packet:
        return []
    
    probabilities = analysis_packet['calculated_probabilities']
    script = analysis_packet['analysis_summary']['selected_script']
    reasoning = analysis_packet['analysis_summary']['reasoning']

    # TASK 4: Extrair severidade e papel dos desfalques para modificador direcional
    _summary = analysis_packet.get('analysis_summary', {})
    _sev_home  = _summary.get('injury_severity_home', 'none')
    _sev_away  = _summary.get('injury_severity_away', 'none')
    _role_home = _summary.get('injury_role_home', 'mixed')
    _role_away = _summary.get('injury_role_away', 'mixed')
    
    # Extrair lambdas individuais calculados pelo master analyzer (FASE 2)
    lambda_data = probabilities.get('lambda_goals', {})
    lambda_home = lambda_data.get('lambda_home', 0.0)
    lambda_away = lambda_data.get('lambda_away', 0.0)
    lambda_total = lambda_data.get('lambda_total', 0.0)
    ht_ratio = lambda_data.get('ht_ratio', 0.43)
    clean_sheet_home_def = lambda_data.get('clean_sheet_rate_home_def', None)
    clean_sheet_away_def = lambda_data.get('clean_sheet_rate_away_def', None)

    # TASK 7: Ler ajustes de lambda por desfalques para incluir nas justificativas
    lambda_adjustments = lambda_data.get('lambda_adjustments', {})
    _lambda_adjusted = lambda_adjustments.get('adjusted', False)
    _lambda_adj_notes = lambda_adjustments.get('notes', [])

    # Fallback: se não há lambdas reais, usar over_2_5 do script como âncora
    _over_2_5_script = probabilities['goals_over_under_2_5']['over_2_5_prob']
    _has_real_lambdas = lambda_total > 0

    if _has_real_lambdas:
        # FASE 3: Blending H2H dinâmico quando houver 3+ confrontos históricos
        h2h_data = analysis_packet.get('h2h')
        if h2h_data and h2h_data.get('count', 0) >= 3:
            h2h_avg_goals = h2h_data.get('avg_goals', 0)
            if h2h_avg_goals > 0 and lambda_total > 0:
                count = h2h_data['count']
                # Base weight: 3→40%, 4→45%, 5+→50%
                base_w = 0.40 + min(count - 3, 2) * 0.05
                # Divergence bonus: +5% per 1.0 gol de divergência (max +10%)
                divergence = abs(lambda_total - h2h_avg_goals)
                div_bonus = min(divergence * 0.05, 0.10)
                h2h_weight = min(base_w + div_bonus, 0.55)
                model_weight = 1.0 - h2h_weight
                # Preservar proporção home/away, ajustar magnitude total
                ratio_home = lambda_home / lambda_total
                ratio_away = lambda_away / lambda_total
                lambda_total_blended = model_weight * lambda_total + h2h_weight * h2h_avg_goals
                # Floor: blended total never below h2h_avg * 0.75
                lambda_total_blended = max(lambda_total_blended, h2h_avg_goals * 0.75)
                lambda_home = lambda_total_blended * ratio_home
                lambda_away = lambda_total_blended * ratio_away
                lambda_total = lambda_total_blended

        # FASE 2: Calcular todas as linhas via Poisson com lambda real — sem offsets fixos
        lambda_ht = lambda_total * ht_ratio

        # FT total lines
        over_1_5_prob = calculate_statistical_probability_goals_over(lambda_total, 1.5)
        over_2_5_prob = calculate_statistical_probability_goals_over(lambda_total, 2.5)
        over_3_5_prob = calculate_statistical_probability_goals_over(lambda_total, 3.5)
        over_4_5_prob = calculate_statistical_probability_goals_over(lambda_total, 4.5)

        # HT lines (lambda do 1º tempo)
        over_0_5_ht_prob = calculate_statistical_probability_goals_over(lambda_ht, 0.5)
        over_1_5_ht_prob = calculate_statistical_probability_goals_over(lambda_ht, 1.5)

        # Team goals por lambda individual
        home_over_0_5_prob = calculate_statistical_probability_goals_over(lambda_home, 0.5)
        home_over_1_5_prob = calculate_statistical_probability_goals_over(lambda_home, 1.5)
        away_over_0_5_prob = calculate_statistical_probability_goals_over(lambda_away, 0.5)
        away_over_1_5_prob = calculate_statistical_probability_goals_over(lambda_away, 1.5)

        # BTTS via clean sheet rates: P(BTTS) = P(home marca) × P(away marca)
        # P(home marca) = 1 - P(away defense keeps CS) = 1 - clean_sheet_away_def
        # P(away marca) = 1 - P(home defense keeps CS) = 1 - clean_sheet_home_def
        if clean_sheet_home_def is not None and clean_sheet_away_def is not None:
            p_home_scores = 1 - clean_sheet_away_def
            p_away_scores = 1 - clean_sheet_home_def
        else:
            p_home_scores = 1 - math.exp(-lambda_home)
            p_away_scores = 1 - math.exp(-lambda_away)
        btts_sim_prob = round(p_home_scores * p_away_scores * 100, 1)

        # H2H BTTS frequency modifier: blend model BTTS with H2H empirical BTTS rate
        h2h_data = analysis_packet.get('h2h')
        if h2h_data and h2h_data.get('count', 0) >= 3:
            games = h2h_data.get('games', [])
            btts_count = sum(
                1 for g in games
                if (g.get('home_goals') or 0) > 0 and (g.get('away_goals') or 0) > 0
            )
            if games:
                h2h_btts_rate = btts_count / len(games) * 100
                count = h2h_data['count']
                h2h_w = 0.40 + min(count - 3, 2) * 0.05
                btts_sim_prob = round((1 - h2h_w) * btts_sim_prob + h2h_w * h2h_btts_rate, 1)

        print(f"  🧮 POISSON: λ_total={lambda_total:.2f} | λ_ht={lambda_ht:.2f} | λ_casa={lambda_home:.2f} | λ_fora={lambda_away:.2f}")
    else:
        # Fallback para comportamento anterior quando lambdas não disponíveis
        over_2_5_prob = _over_2_5_script
        over_1_5_prob = min(over_2_5_prob + 15, 95)
        over_3_5_prob = max(over_2_5_prob - 30, 10)
        over_4_5_prob = max(over_2_5_prob - 45, 5)
        over_0_5_ht_prob = min(over_1_5_prob * 0.75, 85)
        over_1_5_ht_prob = max(over_2_5_prob * 0.40, 25)
        home_over_0_5_prob = min(over_1_5_prob * 0.80, 85)
        home_over_1_5_prob = max(over_2_5_prob * 0.55, 30)
        away_over_0_5_prob = min(over_1_5_prob * 0.70, 80)
        away_over_1_5_prob = max(over_2_5_prob * 0.45, 25)
        btts_sim_prob = probabilities.get('btts', {}).get('btts_yes_prob', 50.0)

    # Calcular complementos (Under)
    under_1_5_prob = 100 - over_1_5_prob
    under_2_5_prob = 100 - over_2_5_prob
    under_3_5_prob = 100 - over_3_5_prob
    under_0_5_ht_prob = 100 - over_0_5_ht_prob
    under_1_5_ht_prob = 100 - over_1_5_ht_prob
    home_under_0_5_prob = 100 - home_over_0_5_prob
    home_under_1_5_prob = 100 - home_over_1_5_prob
    away_under_0_5_prob = 100 - away_over_0_5_prob
    away_under_1_5_prob = 100 - away_over_1_5_prob
    btts_nao_prob = 100 - btts_sim_prob
    
    all_predictions = []
    
    print(f"\n  📊 GOLS V3.0: Analisando ~20 mercados profundos...")
    print(f"  🎯 Script Tático: {script}")
    
    # ========== 1. TOTAL GOALS FULL TIME ==========
    
    # Over 1.5 FT
    if 'gols_ft_over_1.5' in odds:
        prob = over_1_5_prob
        confianca, breakdown = calculate_final_confidence(
            statistical_probability_pct=prob,
            bet_type="Over 1.5",
            tactical_script=script,
            injury_severity_home=_sev_home,
            injury_severity_away=_sev_away,
            injury_role_home=_role_home,
            injury_role_away=_role_away,
            odd=odds.get('gols_ft_over_1.5'),
        )
        if confianca >= MIN_CONFIANCA_GOLS_OVER_1_5:
            all_predictions.append({
                "mercado": "Gols",
                "tipo": "Over 1.5",
                "confianca": confianca,
                "odd": odds['gols_ft_over_1.5'],
                "periodo": "FT",
                "time": "Total",
                "probabilidade": prob,
                "confidence_breakdown": breakdown
            })
    
    # Under 1.5 FT
    if 'gols_ft_under_1.5' in odds:
        prob = under_1_5_prob
        confianca, breakdown = calculate_final_confidence(
            statistical_probability_pct=prob,
            bet_type="Under 1.5",
            tactical_script=script,
            injury_severity_home=_sev_home,
            injury_severity_away=_sev_away,
            injury_role_home=_role_home,
            injury_role_away=_role_away,
            odd=odds.get('gols_ft_under_1.5'),
        )
        if confianca >= 5.0:
            all_predictions.append({
                "mercado": "Gols",
                "tipo": "Under 1.5",
                "confianca": confianca,
                "odd": odds['gols_ft_under_1.5'],
                "periodo": "FT",
                "time": "Total",
                "probabilidade": prob,
                "confidence_breakdown": breakdown
            })
    
    # Over 2.5 FT
    if 'gols_ft_over_2.5' in odds:
        prob = over_2_5_prob
        confianca, breakdown = calculate_final_confidence(
            statistical_probability_pct=prob,
            bet_type="Over 2.5",
            tactical_script=script,
            injury_severity_home=_sev_home,
            injury_severity_away=_sev_away,
            injury_role_home=_role_home,
            injury_role_away=_role_away,
            odd=odds.get('gols_ft_over_2.5'),
        )
        if confianca >= 5.0:
            all_predictions.append({
                "mercado": "Gols",
                "tipo": "Over 2.5",
                "confianca": confianca,
                "odd": odds['gols_ft_over_2.5'],
                "periodo": "FT",
                "time": "Total",
                "probabilidade": prob,
                "confidence_breakdown": breakdown
            })
    
    # Under 2.5 FT
    if 'gols_ft_under_2.5' in odds:
        prob = under_2_5_prob
        confianca, breakdown = calculate_final_confidence(
            statistical_probability_pct=prob,
            bet_type="Under 2.5",
            tactical_script=script,
            injury_severity_home=_sev_home,
            injury_severity_away=_sev_away,
            injury_role_home=_role_home,
            injury_role_away=_role_away,
            odd=odds.get('gols_ft_under_2.5'),
        )
        if confianca >= 5.0:
            all_predictions.append({
                "mercado": "Gols",
                "tipo": "Under 2.5",
                "confianca": confianca,
                "odd": odds['gols_ft_under_2.5'],
                "periodo": "FT",
                "time": "Total",
                "probabilidade": prob,
                "confidence_breakdown": breakdown
            })
    
    # Over 3.5 FT
    if 'gols_ft_over_3.5' in odds:
        prob = over_3_5_prob
        confianca, breakdown = calculate_final_confidence(
            statistical_probability_pct=prob,
            bet_type="Over 3.5",
            tactical_script=script,
            injury_severity_home=_sev_home,
            injury_severity_away=_sev_away,
            injury_role_home=_role_home,
            injury_role_away=_role_away,
            odd=odds.get('gols_ft_over_3.5'),
        )
        if confianca >= 5.0:
            all_predictions.append({
                "mercado": "Gols",
                "tipo": "Over 3.5",
                "confianca": confianca,
                "odd": odds['gols_ft_over_3.5'],
                "periodo": "FT",
                "time": "Total",
                "probabilidade": prob,
                "confidence_breakdown": breakdown
            })
    
    # Under 3.5 FT
    if 'gols_ft_under_3.5' in odds:
        prob = under_3_5_prob
        confianca, breakdown = calculate_final_confidence(
            statistical_probability_pct=prob,
            bet_type="Under 3.5",
            tactical_script=script,
            injury_severity_home=_sev_home,
            injury_severity_away=_sev_away,
            injury_role_home=_role_home,
            injury_role_away=_role_away,
            odd=odds.get('gols_ft_under_3.5'),
        )
        if confianca >= 5.0:
            all_predictions.append({
                "mercado": "Gols",
                "tipo": "Under 3.5",
                "confianca": confianca,
                "odd": odds['gols_ft_under_3.5'],
                "periodo": "FT",
                "time": "Total",
                "probabilidade": prob,
                "confidence_breakdown": breakdown
            })

    # Over 4.5 FT
    if 'gols_ft_over_4.5' in odds:
        prob = over_4_5_prob
        confianca, breakdown = calculate_final_confidence(
            statistical_probability_pct=prob,
            bet_type="Over 4.5",
            tactical_script=script,
            injury_severity_home=_sev_home,
            injury_severity_away=_sev_away,
            injury_role_home=_role_home,
            injury_role_away=_role_away,
            odd=odds.get('gols_ft_over_4.5'),
        )
        if confianca >= 5.0:
            all_predictions.append({
                "mercado": "Gols",
                "tipo": "Over 4.5",
                "confianca": confianca,
                "odd": odds['gols_ft_over_4.5'],
                "periodo": "FT",
                "time": "Total",
                "probabilidade": prob,
                "confidence_breakdown": breakdown
            })

    # Under 4.5 FT
    if 'gols_ft_under_4.5' in odds:
        prob = 100 - over_4_5_prob
        confianca, breakdown = calculate_final_confidence(
            statistical_probability_pct=prob,
            bet_type="Under 4.5",
            tactical_script=script,
            injury_severity_home=_sev_home,
            injury_severity_away=_sev_away,
            injury_role_home=_role_home,
            injury_role_away=_role_away,
            odd=odds.get('gols_ft_under_4.5'),
        )
        if confianca >= 5.0:
            all_predictions.append({
                "mercado": "Gols",
                "tipo": "Under 4.5",
                "confianca": confianca,
                "odd": odds['gols_ft_under_4.5'],
                "periodo": "FT",
                "time": "Total",
                "probabilidade": prob,
                "confidence_breakdown": breakdown
            })

    # ========== 2. FIRST HALF GOALS ==========
    
    # Over 0.5 HT
    if 'gols_ht_over_0.5' in odds:
        prob = over_0_5_ht_prob
        confianca, breakdown = calculate_final_confidence(
            statistical_probability_pct=prob,
            bet_type="Over 0.5 HT",
            tactical_script=script,
            injury_severity_home=_sev_home,
            injury_severity_away=_sev_away,
            injury_role_home=_role_home,
            injury_role_away=_role_away,
            odd=odds.get('gols_ht_over_0.5'),
        )
        if confianca >= 5.0:
            all_predictions.append({
                "mercado": "Gols",
                "tipo": "Over 0.5 HT",
                "confianca": confianca,
                "odd": odds['gols_ht_over_0.5'],
                "periodo": "HT",
                "time": "Total",
                "probabilidade": prob,
                "confidence_breakdown": breakdown
            })
    
    # Under 0.5 HT
    if 'gols_ht_under_0.5' in odds:
        prob = under_0_5_ht_prob
        confianca, breakdown = calculate_final_confidence(
            statistical_probability_pct=prob,
            bet_type="Under 0.5 HT",
            tactical_script=script,
            injury_severity_home=_sev_home,
            injury_severity_away=_sev_away,
            injury_role_home=_role_home,
            injury_role_away=_role_away,
            odd=odds.get('gols_ht_under_0.5'),
        )
        if confianca >= 5.0:
            all_predictions.append({
                "mercado": "Gols",
                "tipo": "Under 0.5 HT",
                "confianca": confianca,
                "odd": odds['gols_ht_under_0.5'],
                "periodo": "HT",
                "time": "Total",
                "probabilidade": prob,
                "confidence_breakdown": breakdown
            })
    
    # Over 1.5 HT
    if 'gols_ht_over_1.5' in odds:
        prob = over_1_5_ht_prob
        confianca, breakdown = calculate_final_confidence(
            statistical_probability_pct=prob,
            bet_type="Over 1.5 HT",
            tactical_script=script,
            injury_severity_home=_sev_home,
            injury_severity_away=_sev_away,
            injury_role_home=_role_home,
            injury_role_away=_role_away,
            odd=odds.get('gols_ht_over_1.5'),
        )
        if confianca >= 5.0:
            all_predictions.append({
                "mercado": "Gols",
                "tipo": "Over 1.5 HT",
                "confianca": confianca,
                "odd": odds['gols_ht_over_1.5'],
                "periodo": "HT",
                "time": "Total",
                "probabilidade": prob,
                "confidence_breakdown": breakdown
            })
    
    # Under 1.5 HT
    if 'gols_ht_under_1.5' in odds:
        prob = under_1_5_ht_prob
        confianca, breakdown = calculate_final_confidence(
            statistical_probability_pct=prob,
            bet_type="Under 1.5 HT",
            tactical_script=script,
            injury_severity_home=_sev_home,
            injury_severity_away=_sev_away,
            injury_role_home=_role_home,
            injury_role_away=_role_away,
            odd=odds.get('gols_ht_under_1.5'),
        )
        if confianca >= 5.0:
            all_predictions.append({
                "mercado": "Gols",
                "tipo": "Under 1.5 HT",
                "confianca": confianca,
                "odd": odds['gols_ht_under_1.5'],
                "periodo": "HT",
                "time": "Total",
                "probabilidade": prob,
                "confidence_breakdown": breakdown
            })
    
    # ========== 3. BOTH TEAMS TO SCORE ==========
    
    # BTTS Sim
    if 'btts_sim' in odds or 'btts_yes' in odds:
        odd_key = 'btts_sim' if 'btts_sim' in odds else 'btts_yes'
        prob = btts_sim_prob
        confianca, breakdown = calculate_final_confidence(
            statistical_probability_pct=prob,
            bet_type="BTTS Sim",
            tactical_script=script,
            injury_severity_home=_sev_home,
            injury_severity_away=_sev_away,
            injury_role_home=_role_home,
            injury_role_away=_role_away,
            odd=odds.get(odd_key),
        )
        if confianca >= 5.0:
            all_predictions.append({
                "mercado": "BTTS",
                "tipo": "BTTS Sim",
                "confianca": confianca,
                "odd": odds[odd_key],
                "periodo": "FT",
                "time": "Ambos",
                "probabilidade": prob,
                "confidence_breakdown": breakdown
            })
    
    # BTTS Não
    if 'btts_nao' in odds or 'btts_no' in odds:
        odd_key = 'btts_nao' if 'btts_nao' in odds else 'btts_no'
        prob = btts_nao_prob
        confianca, breakdown = calculate_final_confidence(
            statistical_probability_pct=prob,
            bet_type="BTTS Não",
            tactical_script=script,
            injury_severity_home=_sev_home,
            injury_severity_away=_sev_away,
            injury_role_home=_role_home,
            injury_role_away=_role_away,
            odd=odds.get(odd_key),
        )
        if confianca >= 5.0:
            all_predictions.append({
                "mercado": "BTTS",
                "tipo": "BTTS Não",
                "confianca": confianca,
                "odd": odds[odd_key],
                "periodo": "FT",
                "time": "Ambos",
                "probabilidade": prob,
                "confidence_breakdown": breakdown
            })
    
    # ========== 4. TEAM GOALS - HOME ==========
    
    # Home Over 0.5
    if 'gols_casa_over_0.5' in odds:
        prob = home_over_0_5_prob
        confianca, breakdown = calculate_final_confidence(
            statistical_probability_pct=prob,
            bet_type="Casa Over 0.5",
            tactical_script=script,
            injury_severity_home=_sev_home,
            injury_severity_away=_sev_away,
            injury_role_home=_role_home,
            injury_role_away=_role_away,
            odd=odds.get('gols_casa_over_0.5'),
        )
        if confianca >= 5.0:
            all_predictions.append({
                "mercado": "Gols",
                "tipo": "Casa Over 0.5",
                "confianca": confianca,
                "odd": odds['gols_casa_over_0.5'],
                "periodo": "FT",
                "time": "Casa",
                "probabilidade": prob,
                "confidence_breakdown": breakdown
            })
    
    # Home Under 0.5
    if 'gols_casa_under_0.5' in odds:
        prob = home_under_0_5_prob
        confianca, breakdown = calculate_final_confidence(
            statistical_probability_pct=prob,
            bet_type="Casa Under 0.5",
            tactical_script=script,
            injury_severity_home=_sev_home,
            injury_severity_away=_sev_away,
            injury_role_home=_role_home,
            injury_role_away=_role_away,
            odd=odds.get('gols_casa_under_0.5'),
        )
        if confianca >= 5.0:
            all_predictions.append({
                "mercado": "Gols",
                "tipo": "Casa Under 0.5",
                "confianca": confianca,
                "odd": odds['gols_casa_under_0.5'],
                "periodo": "FT",
                "time": "Casa",
                "probabilidade": prob,
                "confidence_breakdown": breakdown
            })
    
    # Home Over 1.5
    if 'gols_casa_over_1.5' in odds:
        prob = home_over_1_5_prob
        confianca, breakdown = calculate_final_confidence(
            statistical_probability_pct=prob,
            bet_type="Casa Over 1.5",
            tactical_script=script,
            injury_severity_home=_sev_home,
            injury_severity_away=_sev_away,
            injury_role_home=_role_home,
            injury_role_away=_role_away,
            odd=odds.get('gols_casa_over_1.5'),
        )
        if confianca >= 5.0:
            all_predictions.append({
                "mercado": "Gols",
                "tipo": "Casa Over 1.5",
                "confianca": confianca,
                "odd": odds['gols_casa_over_1.5'],
                "periodo": "FT",
                "time": "Casa",
                "probabilidade": prob,
                "confidence_breakdown": breakdown
            })
    
    # Home Under 1.5
    if 'gols_casa_under_1.5' in odds:
        prob = home_under_1_5_prob
        confianca, breakdown = calculate_final_confidence(
            statistical_probability_pct=prob,
            bet_type="Casa Under 1.5",
            tactical_script=script,
            injury_severity_home=_sev_home,
            injury_severity_away=_sev_away,
            injury_role_home=_role_home,
            injury_role_away=_role_away,
            odd=odds.get('gols_casa_under_1.5'),
        )
        if confianca >= 5.0:
            all_predictions.append({
                "mercado": "Gols",
                "tipo": "Casa Under 1.5",
                "confianca": confianca,
                "odd": odds['gols_casa_under_1.5'],
                "periodo": "FT",
                "time": "Casa",
                "probabilidade": prob,
                "confidence_breakdown": breakdown
            })
    
    # ========== 5. TEAM GOALS - AWAY ==========
    
    # Away Over 0.5
    if 'gols_fora_over_0.5' in odds:
        prob = away_over_0_5_prob
        confianca, breakdown = calculate_final_confidence(
            statistical_probability_pct=prob,
            bet_type="Fora Over 0.5",
            tactical_script=script,
            injury_severity_home=_sev_home,
            injury_severity_away=_sev_away,
            injury_role_home=_role_home,
            injury_role_away=_role_away,
            odd=odds.get('gols_fora_over_0.5'),
        )
        if confianca >= 5.0:
            all_predictions.append({
                "mercado": "Gols",
                "tipo": "Fora Over 0.5",
                "confianca": confianca,
                "odd": odds['gols_fora_over_0.5'],
                "periodo": "FT",
                "time": "Fora",
                "probabilidade": prob,
                "confidence_breakdown": breakdown
            })
    
    # Away Under 0.5
    if 'gols_fora_under_0.5' in odds:
        prob = away_under_0_5_prob
        confianca, breakdown = calculate_final_confidence(
            statistical_probability_pct=prob,
            bet_type="Fora Under 0.5",
            tactical_script=script,
            injury_severity_home=_sev_home,
            injury_severity_away=_sev_away,
            injury_role_home=_role_home,
            injury_role_away=_role_away,
            odd=odds.get('gols_fora_under_0.5'),
        )
        if confianca >= 5.0:
            all_predictions.append({
                "mercado": "Gols",
                "tipo": "Fora Under 0.5",
                "confianca": confianca,
                "odd": odds['gols_fora_under_0.5'],
                "periodo": "FT",
                "time": "Fora",
                "probabilidade": prob,
                "confidence_breakdown": breakdown
            })
    
    # Away Over 1.5
    if 'gols_fora_over_1.5' in odds:
        prob = away_over_1_5_prob
        confianca, breakdown = calculate_final_confidence(
            statistical_probability_pct=prob,
            bet_type="Fora Over 1.5",
            tactical_script=script,
            injury_severity_home=_sev_home,
            injury_severity_away=_sev_away,
            injury_role_home=_role_home,
            injury_role_away=_role_away,
            odd=odds.get('gols_fora_over_1.5'),
        )
        if confianca >= 5.0:
            all_predictions.append({
                "mercado": "Gols",
                "tipo": "Fora Over 1.5",
                "confianca": confianca,
                "odd": odds['gols_fora_over_1.5'],
                "periodo": "FT",
                "time": "Fora",
                "probabilidade": prob,
                "confidence_breakdown": breakdown
            })
    
    # Away Under 1.5
    if 'gols_fora_under_1.5' in odds:
        prob = away_under_1_5_prob
        confianca, breakdown = calculate_final_confidence(
            statistical_probability_pct=prob,
            bet_type="Fora Under 1.5",
            tactical_script=script,
            injury_severity_home=_sev_home,
            injury_severity_away=_sev_away,
            injury_role_home=_role_home,
            injury_role_away=_role_away,
            odd=odds.get('gols_fora_under_1.5'),
        )
        if confianca >= 5.0:
            all_predictions.append({
                "mercado": "Gols",
                "tipo": "Fora Under 1.5",
                "confianca": confianca,
                "odd": odds['gols_fora_under_1.5'],
                "periodo": "FT",
                "time": "Fora",
                "probabilidade": prob,
                "confidence_breakdown": breakdown
            })
    
    # Aplicar penalidade de mercados triviais (>70% dos jogos na última semana)
    _trivial_types = _get_trivial_market_types()
    if _trivial_types:
        for _pred in all_predictions:
            if _pred.get('tipo') in _trivial_types:
                _pred['confianca'] = round(max(1.0, _pred['confianca'] - _TRIVIAL_PENALTY), 2)
                if 'confidence_breakdown' in _pred:
                    _pred['confidence_breakdown']['modificador_trivial'] = -_TRIVIAL_PENALTY
                    _pred['confidence_breakdown']['confianca_final'] = _pred['confianca']
        # Re-filter: drop predictions that fell below their market threshold after penalty
        _thresholds = {
            'Over 1.5': MIN_CONFIANCA_GOLS_OVER_1_5,
        }
        all_predictions = [
            p for p in all_predictions
            if p['confianca'] >= _thresholds.get(p.get('tipo'), 5.0)
        ]

    # Ordenar por confiança (descendente)
    all_predictions.sort(key=lambda x: x['confianca'], reverse=True)
    
    print(f"  ✅ GOLS V3.0: {len(all_predictions)} predições geradas (deep analysis)")
    
    # Retornar no formato compatível (wrapping lista em dict para compatibilidade)
    if all_predictions:
        # TASK 7: Adicionar notas de ajuste de lambda por desfalques ao suporte
        _suporte = f"💡 {reasoning}"
        if _lambda_adjusted and _lambda_adj_notes:
            _suporte += "\n\n⚠️ AJUSTE DE LAMBDA POR DESFALQUES:\n" + "\n".join(f"   • {n}" for n in _lambda_adj_notes)
            _suporte += f"\n   λ_casa={lambda_home:.2f} | λ_fora={lambda_away:.2f} (pós-ajuste)"
        return {
            "mercado": "Gols",
            "palpites": all_predictions,
            "dados_suporte": _suporte,
            "script": script
        }

    return None


def extract_goals_suggestions(analysis_packet, odds):
    """Wrapper para compatibilidade com código existente"""
    return analisar_mercado_gols(analysis_packet, odds)
