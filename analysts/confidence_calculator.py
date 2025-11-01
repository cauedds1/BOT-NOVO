"""
PHOENIX V2.0 - CONFIDENCE CALCULATOR
====================================

Novo modelo de cálculo de confiança baseado em Probabilidades Estatísticas Reais.

ARQUITETURA EM 4 PASSOS:
1. Calcular Probabilidade Estatística Base (0-100%) a partir de dados históricos
2. Converter Probabilidade para Confiança Base (0-10)
3. Aplicar Modificadores Contextuais (Roteiro Tático, Value, Odd)
4. Retornar Confiança Final calibrada

Este modelo garante que a confiança está sempre ancorada na realidade estatística.
"""

import math
from typing import Dict, List, Tuple, Optional


def calculate_statistical_probability_goals_over(
    weighted_goals_avg: float,
    line: float,
    historical_frequency: Optional[float] = None
) -> float:
    """
    STEP 1: Calcula probabilidade estatística de Over X.5 gols.
    
    Args:
        weighted_goals_avg: Média ponderada de gols esperados no jogo
        line: Linha do over (ex: 2.5)
        historical_frequency: % histórica de jogos que bateram essa linha (opcional)
    
    Returns:
        float: Probabilidade em % (0-100)
    """
    # Se temos frequência histórica real, usar isso (mais preciso)
    if historical_frequency is not None:
        return historical_frequency
    
    # Caso contrário, usar distribuição de Poisson
    # P(X > line) = 1 - P(X <= line)
    prob_under = 0.0
    for k in range(int(line) + 1):
        prob_under += (math.exp(-weighted_goals_avg) * (weighted_goals_avg ** k)) / math.factorial(k)
    
    prob_over = (1 - prob_under) * 100  # Converter para %
    
    return min(max(prob_over, 0), 100)  # Garantir 0-100%


def calculate_statistical_probability_corners_over(
    weighted_corners_avg: float,
    line: float,
    historical_frequency: Optional[float] = None
) -> float:
    """
    STEP 1: Calcula probabilidade estatística de Over X.5 escanteios.
    """
    if historical_frequency is not None:
        return historical_frequency
    
    # Usar Poisson (escanteios seguem distribuição similar a gols)
    prob_under = 0.0
    for k in range(int(line) + 1):
        prob_under += (math.exp(-weighted_corners_avg) * (weighted_corners_avg ** k)) / math.factorial(k)
    
    prob_over = (1 - prob_under) * 100
    return min(max(prob_over, 0), 100)


def calculate_statistical_probability_btts(
    home_scoring_rate: float,
    away_scoring_rate: float
) -> float:
    """
    STEP 1: Calcula probabilidade de BTTS (Both Teams To Score).
    
    Args:
        home_scoring_rate: Taxa de jogos onde casa marcou (0-1)
        away_scoring_rate: Taxa de jogos onde fora marcou (0-1)
    
    Returns:
        float: Probabilidade em % (0-100)
    """
    # Probabilidade independente: P(A e B) = P(A) * P(B)
    prob_btts = home_scoring_rate * away_scoring_rate * 100
    return min(max(prob_btts, 0), 100)


def calculate_statistical_probability_cards_over(
    weighted_cards_avg: float,
    line: float
) -> float:
    """
    STEP 1: Calcula probabilidade estatística de Over X.5 cartões.
    """
    # Usar Poisson para cartões (distribuição similar a gols/cantos)
    prob_under = 0.0
    for k in range(int(line) + 1):
        prob_under += (math.exp(-weighted_cards_avg) * (weighted_cards_avg ** k)) / math.factorial(k)
    
    prob_over = (1 - prob_under) * 100
    return min(max(prob_over, 0), 100)


def calculate_statistical_probability_shots_over(
    weighted_shots_avg: float,
    line: float
) -> float:
    """
    STEP 1: Calcula probabilidade estatística de Over X.5 finalizações.
    """
    # Usar distribuição normal para finalizações (valores mais altos)
    # Como aproximação, usar % baseado na média
    if weighted_shots_avg >= line + 3:
        return 75.0
    elif weighted_shots_avg >= line + 1:
        return 65.0
    elif weighted_shots_avg >= line:
        return 55.0
    elif weighted_shots_avg >= line - 1:
        return 45.0
    elif weighted_shots_avg >= line - 3:
        return 35.0
    else:
        return 25.0


def calculate_historical_frequency_from_games(
    last_games_home: List[Dict],
    last_games_away: List[Dict],
    metric: str,
    threshold: float,
    operator: str = "over"
) -> Optional[float]:
    """
    Calcula frequência histórica real de um evento nos últimos jogos.
    
    Args:
        last_games_home: Últimos jogos do time casa
        last_games_away: Últimos jogos do time fora
        metric: Métrica a analisar ('goals', 'corners', 'cards')
        threshold: Linha (ex: 2.5)
        operator: 'over' ou 'under'
    
    Returns:
        Optional[float]: Frequência em % (0-100) ou None se sem dados
    """
    all_games = last_games_home + last_games_away
    if not all_games:
        return None
    
    count_success = 0
    for game in all_games:
        value = game.get(metric, 0)
        
        if operator == "over":
            if value > threshold:
                count_success += 1
        else:  # under
            if value < threshold:
                count_success += 1
    
    frequency = (count_success / len(all_games)) * 100
    return frequency


def convert_probability_to_base_confidence(probability_pct: float) -> float:
    """
    STEP 2: Converte Probabilidade (0-100%) em Confiança Base (0-10).
    
    NOVA ESCALA CALIBRADA:
    - 85%+ -> 9.5-10.0 (Quase certeza)
    - 75-84% -> 8.5-9.4 (Muito provável)
    - 65-74% -> 7.5-8.4 (Provável)
    - 55-64% -> 6.5-7.4 (Mais provável que não)
    - 45-54% -> 5.5-6.4 (Equilibrado)
    - 35-44% -> 4.5-5.4 (Improvável)
    - <35% -> 0-4.4 (Muito improvável)
    """
    if probability_pct >= 85:
        return 9.0 + (probability_pct - 85) / 15  # 9.0-10.0
    elif probability_pct >= 75:
        return 8.0 + (probability_pct - 75) / 10  # 8.0-9.0
    elif probability_pct >= 65:
        return 7.0 + (probability_pct - 65) / 10  # 7.0-8.0
    elif probability_pct >= 55:
        return 6.0 + (probability_pct - 55) / 10  # 6.0-7.0
    elif probability_pct >= 45:
        return 5.0 + (probability_pct - 45) / 10  # 5.0-6.0
    elif probability_pct >= 35:
        return 4.0 + (probability_pct - 35) / 10  # 4.0-5.0
    else:
        return max(probability_pct / 10, 1.0)  # 1.0-4.0


def apply_tactical_script_modifier(
    base_confidence: float,
    bet_type: str,
    tactical_script: Optional[str] = None
) -> float:
    """
    STEP 3a: Aplica modificador baseado em coerência com Roteiro Tático.
    
    Args:
        base_confidence: Confiança base (já calculada)
        bet_type: Tipo da aposta (ex: "Over 2.5", "BTTS Sim")
        tactical_script: Script tático do jogo
    
    Returns:
        float: Modificador (-2.0 a +1.5)
    """
    if not tactical_script:
        return 0.0
    
    # PHOENIX V3.0: SKEPTICAL CONTEXTUALIZATION
    # O contexto tático deve ter POWERFUL IMPACT na confiança
    # Coherence Bonus aumentado para garantir que o script DOMINA sobre stats brutas
    
    coherence_map = {
        "Over 2.5": {
            "coherent": ["SCRIPT_OPEN_HIGH_SCORING_GAME", "SCRIPT_DOMINIO_CASA", "SCRIPT_DOMINIO_VISITANTE", 
                        "SCRIPT_TIME_EM_CHAMAS_CASA", "SCRIPT_TIME_EM_CHAMAS_FORA"],
            "bonus": 1.5  # Aumentado de 1.0 para garantir impacto forte
        },
        "Under 2.5": {
            "coherent": ["SCRIPT_CAGEY_TACTICAL_AFFAIR", "SCRIPT_RELEGATION_BATTLE", "SCRIPT_JOGO_DE_COMPADRES",
                        "SCRIPT_TIGHT_LOW_SCORING", "SCRIPT_BALANCED_TACTICAL_BATTLE"],
            "bonus": 1.5  # Aumentado de 1.0
        },
        "Over 1.5": {
            "coherent": ["SCRIPT_OPEN_HIGH_SCORING_GAME", "SCRIPT_TIME_EM_CHAMAS_CASA", "SCRIPT_TIME_EM_CHAMAS_FORA"],
            "bonus": 1.2  # Aumentado de 0.8
        },
        "BTTS Sim": {
            "coherent": ["SCRIPT_BALANCED_RIVALRY_CLASH", "SCRIPT_OPEN_HIGH_SCORING_GAME"],
            "bonus": 1.5  # Aumentado de 1.0
        },
        "BTTS Não": {
            "coherent": ["SCRIPT_GIANT_VS_MINNOW", "SCRIPT_DOMINIO_CASA", "SCRIPT_DOMINIO_VISITANTE"],
            "bonus": 1.5  # Aumentado de 1.0
        }
    }
    
    # Encontrar mapeamento
    bet_key = None
    for key in coherence_map.keys():
        if key.lower() in bet_type.lower():
            bet_key = key
            break
    
    if not bet_key:
        return 0.0
    
    # Verificar coerência PERFEITA
    if tactical_script in coherence_map[bet_key]["coherent"]:
        return coherence_map[bet_key]["bonus"]
    
    # PHOENIX V3.0: PENALIDADE SEVERA para incoerência
    # "Each Game is a Game" - contexto sobrepõe probabilidade
    # Aumentado de -1.5 para -2.5 para garantir impacto FORTE
    if "over" in bet_type.lower() and ("CAGEY" in tactical_script or "LOW_SCORING" in tactical_script or "JOGO_DE_COMPADRES" in tactical_script):
        return -2.5  # SEVERE penalty - stat pode dizer Over mas contexto diz Under
    if "under" in bet_type.lower() and ("OPEN_HIGH_SCORING" in tactical_script or "TIME_EM_CHAMAS" in tactical_script):
        return -2.5  # SEVERE penalty - stat pode dizer Under mas contexto diz Over
    
    return 0.0


# PURE ANALYST PROTOCOL: Value and odd modifiers removed
# Analysis is now independent of market odds


def calculate_final_confidence(
    statistical_probability_pct: float,
    bet_type: str,
    tactical_script: Optional[str] = None
) -> Tuple[float, Dict[str, float]]:
    """
    PURE ANALYST PROTOCOL - STEP 4: Calcula Confiança Final (sem dependência de odds).
    
    Args:
        statistical_probability_pct: Probabilidade estatística base (0-100%)
        bet_type: Tipo da aposta
        tactical_script: Script tático (opcional)
    
    Returns:
        tuple: (confianca_final, breakdown_dict)
    """
    # STEP 2: Base confidence
    base_conf = convert_probability_to_base_confidence(statistical_probability_pct)
    
    # STEP 3: Tactical script modifier only
    mod_script = apply_tactical_script_modifier(base_conf, bet_type, tactical_script)
    
    # STEP 4: Final (simplified - no value/odd modifiers)
    final_conf = base_conf + mod_script
    
    # Cap entre 1.0 e 10.0
    final_conf = max(1.0, min(10.0, final_conf))
    
    breakdown = {
        "probabilidade_base": statistical_probability_pct,
        "confianca_base": base_conf,
        "modificador_script": mod_script,
        "confianca_final": final_conf
    }
    
    return final_conf, breakdown
