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
from config import ODD_MINIMA_PALPITE, ODD_PENALIDADE_BAIXA, ODD_PENALIDADE_MEDIA


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
    TASK 14: Probabilidade de Over X.5 finalizações via interpolação linear contínua.
    Substitui o sistema de buckets por uma curva suave de 25% a 80%.
    Âncoras calibradas empiricamente (finalizações seguem distribuição aproximadamente normal):
      delta = weighted_shots_avg - line
      delta <= -5 → 20%   (média muito abaixo da linha)
      delta = 0   → 52%   (média igual à linha: ligeira vantagem Over)
      delta >= +6 → 80%   (média muito acima da linha)
    """
    delta = weighted_shots_avg - line
    anchors = [
        (-5.0, 20.0),
        (-3.0, 30.0),
        (-1.5, 42.0),
        (0.0,  52.0),
        (1.5,  62.0),
        (3.0,  72.0),
        (6.0,  80.0),
    ]
    # Abaixo do menor âncora
    if delta <= anchors[0][0]:
        return anchors[0][1]
    # Acima do maior âncora
    if delta >= anchors[-1][0]:
        return anchors[-1][1]
    # Interpolação linear entre os dois âncoras mais próximos
    for i in range(len(anchors) - 1):
        x0, y0 = anchors[i]
        x1, y1 = anchors[i + 1]
        if x0 <= delta <= x1:
            t = (delta - x0) / (x1 - x0)
            return round(y0 + t * (y1 - y0), 1)
    return 52.0  # fallback


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
    STEP 3a: Único ponto de aplicação do modificador tático — cobre TODOS os mercados.

    Consolida gols, cantos e cartões para eliminar double-counting: os analisadores
    individuais passam probabilidades puras, sem pré-modificação por script.

    Args:
        base_confidence: Confiança base (já calculada)
        bet_type: Tipo da aposta (ex: "Over 2.5", "Over 9.5 Cantos", "Over 4.5 Cartões")
        tactical_script: Script tático do jogo

    Returns:
        float: Modificador de confiança (negativo = penalidade, positivo = bônus)
    """
    if not tactical_script:
        return 0.0

    bet_lower = bet_type.lower()
    script = tactical_script

    OFFENSIVE_SCRIPTS = {
        "SCRIPT_OPEN_HIGH_SCORING_GAME", "SCRIPT_DOMINIO_CASA", "SCRIPT_DOMINIO_VISITANTE",
        "SCRIPT_TIME_EM_CHAMAS_CASA", "SCRIPT_TIME_EM_CHAMAS_FORA", "SCRIPT_GIANT_VS_MINNOW"
    }
    DEFENSIVE_SCRIPTS = {
        "SCRIPT_CAGEY_TACTICAL_AFFAIR", "SCRIPT_RELEGATION_BATTLE", "SCRIPT_JOGO_DE_COMPADRES",
        "SCRIPT_TIGHT_LOW_SCORING", "SCRIPT_BALANCED_TACTICAL_BATTLE"
    }
    HIGH_INTENSITY_SCRIPTS = {
        "SCRIPT_RELEGATION_BATTLE", "SCRIPT_BALANCED_RIVALRY_CLASH", "SCRIPT_MATA_MATA_VOLTA",
        "SCRIPT_TIME_EM_CHAMAS_CASA", "SCRIPT_TIME_EM_CHAMAS_FORA"
    }
    LOW_INTENSITY_SCRIPTS = {
        "SCRIPT_JOGO_DE_COMPADRES", "SCRIPT_GIANT_VS_MINNOW", "SCRIPT_DOMINIO_CASA", "SCRIPT_DOMINIO_VISITANTE"
    }

    # ========== MERCADOS DE CANTOS ==========
    if "canto" in bet_lower:
        if "over" in bet_lower:
            if script in OFFENSIVE_SCRIPTS:
                if ("casa" in bet_lower and script in {"SCRIPT_DOMINIO_CASA", "SCRIPT_TIME_EM_CHAMAS_CASA"}):
                    return 1.5
                if ("fora" in bet_lower and script in {"SCRIPT_DOMINIO_VISITANTE", "SCRIPT_TIME_EM_CHAMAS_FORA"}):
                    return 1.5
                return 1.2
            if script in DEFENSIVE_SCRIPTS:
                return -1.5
        elif "under" in bet_lower:
            if script in DEFENSIVE_SCRIPTS:
                if ("casa" in bet_lower and script in {"SCRIPT_DOMINIO_CASA", "SCRIPT_TIME_EM_CHAMAS_CASA"}):
                    return -1.5
                if ("fora" in bet_lower and script in {"SCRIPT_DOMINIO_VISITANTE", "SCRIPT_TIME_EM_CHAMAS_FORA"}):
                    return -1.5
                return 1.2
            if script in OFFENSIVE_SCRIPTS:
                return -1.5
        return 0.0

    # ========== MERCADOS DE CARTÕES ==========
    if "cartõ" in bet_lower or "cartao" in bet_lower or "card" in bet_lower:
        if "over" in bet_lower:
            if script in HIGH_INTENSITY_SCRIPTS:
                return 1.0
            if script in LOW_INTENSITY_SCRIPTS:
                return -1.0
        elif "under" in bet_lower:
            if script in LOW_INTENSITY_SCRIPTS:
                return 1.0
            if script in HIGH_INTENSITY_SCRIPTS:
                return -1.0
        return 0.0

    # ========== MERCADOS DE GOLS ==========

    # BTTS
    if "btts" in bet_lower:
        if "sim" in bet_lower or "yes" in bet_lower:
            if script in {"SCRIPT_BALANCED_RIVALRY_CLASH", "SCRIPT_OPEN_HIGH_SCORING_GAME"}:
                return 1.5
            if script in {"SCRIPT_GIANT_VS_MINNOW", "SCRIPT_DOMINIO_CASA", "SCRIPT_DOMINIO_VISITANTE"}:
                return -2.5
        else:
            if script in {"SCRIPT_GIANT_VS_MINNOW", "SCRIPT_DOMINIO_CASA", "SCRIPT_DOMINIO_VISITANTE"}:
                return 1.5
            if script in {"SCRIPT_BALANCED_RIVALRY_CLASH", "SCRIPT_OPEN_HIGH_SCORING_GAME"}:
                return -2.5
        return 0.0

    # Over goals (todos os sub-mercados: FT, HT, casa, fora)
    if "over" in bet_lower:
        if script in OFFENSIVE_SCRIPTS:
            if "2.5" in bet_lower:
                return 1.5
            if "1.5" in bet_lower:
                return 1.2
            return 1.0
        if script in DEFENSIVE_SCRIPTS:
            if "CAGEY" in script or "LOW_SCORING" in script or "JOGO_DE_COMPADRES" in script:
                return -2.5
            return -1.5
        return 0.0

    # Under goals (todos os sub-mercados)
    if "under" in bet_lower:
        if script in DEFENSIVE_SCRIPTS:
            if "2.5" in bet_lower:
                return 1.5
            return 1.2
        if script in OFFENSIVE_SCRIPTS:
            if "OPEN_HIGH_SCORING" in script or "TIME_EM_CHAMAS" in script:
                return -2.5
            return -1.5
        return 0.0

    return 0.0


# PURE ANALYST PROTOCOL: Value and odd modifiers removed
# Analysis is now independent of market odds


def apply_injury_confidence_modifier(
    bet_type: str,
    injury_severity_home: str = "none",
    injury_severity_away: str = "none",
    injury_role_home: str = "mixed",
    injury_role_away: str = "mixed",
) -> float:
    """
    PHOENIX V4.0 — Modificador de confiança baseado em desfalques DIRECIONAL.

    A direção do modificador depende do PAPEL do jogador ausente e do TIPO de aposta:

      injury_role = 'offensive' (atacante/meia lesionado):
        - Apostas de OVER / ataque → penalidade (menos gols esperados)
        - Apostas de UNDER / defensivas → bônus (menos gols = Under mais provável)
        - BTTS Sim → penalidade

      injury_role = 'defensive' (defensor/goleiro lesionado):
        - Apostas de OVER / ataque → bônus (defesa fragilizada = mais gols)
        - Apostas de UNDER / defensivas → penalidade
        - BTTS Sim → bônus

      injury_role = 'mixed' (papel desconhecido):
        - Comportamento simétrico: apenas penalidade moderada em qualquer direção

    Severidade → magnitude:
      - "none"     → 0.0
      - "minor"    → 0.3
      - "moderate" → 0.6
      - "severe"   → 1.0

    Args:
        bet_type:            Tipo de aposta
        injury_severity_home: Severidade de desfalques do mandante
        injury_severity_away: Severidade de desfalques do visitante
        injury_role_home:    Papel dos lesionados do mandante ('offensive'/'defensive'/'mixed')
        injury_role_away:    Papel dos lesionados do visitante ('offensive'/'defensive'/'mixed')

    Returns:
        float: Modificador de confiança (pode ser positivo ou negativo)
    """
    SEVERITY_MAP = {"none": 0.0, "minor": 0.3, "moderate": 0.6, "severe": 1.0}

    bet_lower = bet_type.lower()

    # Detectar direção da aposta
    is_over = "over" in bet_lower or "btts sim" in bet_lower or "sim" in bet_lower
    is_under = "under" in bet_lower or "btts não" in bet_lower or "não" in bet_lower
    is_home_bet = "casa" in bet_lower or "home" in bet_lower
    is_away_bet = "fora" in bet_lower or "away" in bet_lower or "visitante" in bet_lower

    def _directional_mod(magnitude: float, role: str, is_attack_favored: bool) -> float:
        """
        Calcula o modificador direcional baseado no papel do lesionado.
        is_attack_favored=True → aposta favorece mais gols (Over/BTTS Sim/Resultado fora)
        """
        if magnitude == 0.0:
            return 0.0
        if role == "offensive":
            # Atacante lesionado → menos gols → Over perde, Under ganha
            return -magnitude if is_attack_favored else +magnitude * 0.7
        elif role == "defensive":
            # Defensor lesionado → mais gols → Over ganha, Under perde
            return +magnitude * 0.7 if is_attack_favored else -magnitude
        else:
            # Papel desconhecido: penalidade simétrica reduzida.
            # 0.3 (menor que 0.5 anterior) pois a falta de posição é ambiguidade,
            # não evidência de impacto real em nenhuma direção.
            return -magnitude * 0.3

    mod = 0.0

    if is_home_bet:
        mag = SEVERITY_MAP.get(injury_severity_home, 0.0)
        mod = _directional_mod(mag, injury_role_home, is_attack_favored=is_over)
    elif is_away_bet:
        mag = SEVERITY_MAP.get(injury_severity_away, 0.0)
        mod = _directional_mod(mag, injury_role_away, is_attack_favored=is_over)
    else:
        # Mercado total → combinar ambos os times
        mag_h = SEVERITY_MAP.get(injury_severity_home, 0.0)
        mag_a = SEVERITY_MAP.get(injury_severity_away, 0.0)
        mod_h = _directional_mod(mag_h, injury_role_home, is_attack_favored=is_over)
        mod_a = _directional_mod(mag_a, injury_role_away, is_attack_favored=is_over)
        # Para mercados totais, ambos os times influenciam na mesma direção
        mod = mod_h + mod_a

    return round(mod, 2)


def calculate_final_confidence(
    statistical_probability_pct: float,
    bet_type: str,
    tactical_script: Optional[str] = None,
    injury_severity_home: str = "none",
    injury_severity_away: str = "none",
    injury_role_home: str = "mixed",
    injury_role_away: str = "mixed",
    market_history_adjustment: float = 0.0,
    odd: Optional[float] = None,
) -> Tuple[float, Dict[str, float]]:
    """
    PURE ANALYST PROTOCOL - STEP 4: Calcula Confiança Final.

    PHOENIX V4.0: Modificador de desfalques DIRECIONAL — lesões ofensivas aumentam
    confiança em Under, lesões defensivas aumentam confiança em Over/BTTS.

    TASK #17 — Aprendizado: Aceita ajuste histórico por mercado (dampened via
    get_market_confidence_adjustment): 0.0 se amostras insuficientes, ±valor se
    o mercado tem histórico de acerto acima/abaixo do esperado.

    TASK #16 — ODD_MINIMA_PENALIDADE reativada:
      odd < 1.35          → confiança 0.0  (palpite não gerado pelo chamador)
      1.35 ≤ odd < 1.50   → -1.5 na confiança
      1.50 ≤ odd < 1.70   → -0.5 na confiança
      odd ≥ 1.70          → sem penalidade
      odd = None          → sem penalidade (mercado sem cobertura de odds)

    Args:
        statistical_probability_pct:  Probabilidade estatística base (0-100%)
        bet_type:                     Tipo da aposta
        tactical_script:              Script tático (opcional)
        injury_severity_home:         Severidade de desfalques do mandante
        injury_severity_away:         Severidade de desfalques do visitante
        injury_role_home:             Papel dos lesionados do mandante
        injury_role_away:             Papel dos lesionados do visitante
        market_history_adjustment:    Ajuste histórico dampened do mercado (de
                                      db.get_market_confidence_adjustment)
        odd:                          Odd disponível para esta aposta (None = sem odds)

    Returns:
        tuple: (confianca_final, breakdown_dict)
               confianca_final = 0.0 indica que o palpite deve ser descartado
               (odd abaixo do mínimo aceitável)
    """
    # STEP 0: Filtro de odd mínima — sem valor para o usuário abaixo de ODD_MINIMA_PALPITE.
    # Thresholds lidos de config.py: ODD_MINIMA_PALPITE=1.35, ODD_PENALIDADE_BAIXA=1.50,
    # ODD_PENALIDADE_MEDIA=1.70
    mod_odd = 0.0
    if odd is not None:
        if odd < ODD_MINIMA_PALPITE:
            # Descartado imediatamente — sem valor real para o apostador
            _bd = {
                "probabilidade_base": statistical_probability_pct,
                "confianca_base": 0.0,
                "modificador_script": 0.0,
                "modificador_lesoes": 0.0,
                "modificador_historico": 0.0,
                "modificador_odd": -99.0,
                "confianca_final": 0.0,
            }
            return 0.0, _bd
        elif odd < ODD_PENALIDADE_BAIXA:
            mod_odd = -1.5
        elif odd < ODD_PENALIDADE_MEDIA:
            mod_odd = -0.5

    # STEP 2: Base confidence
    base_conf = convert_probability_to_base_confidence(statistical_probability_pct)

    # STEP 3: Tactical script modifier
    mod_script = apply_tactical_script_modifier(base_conf, bet_type, tactical_script)

    # STEP 3b: Injury modifier — direcional por papel do lesionado
    mod_injury = apply_injury_confidence_modifier(
        bet_type,
        injury_severity_home, injury_severity_away,
        injury_role_home, injury_role_away,
    )

    # STEP 3c: Historical market adjustment (learning layer)
    mod_historico = float(market_history_adjustment)

    # STEP 4: Final (inclui penalidade de odd)
    final_conf = base_conf + mod_script + mod_injury + mod_historico + mod_odd

    # Cap entre 1.0 e 10.0
    final_conf = max(1.0, min(10.0, final_conf))

    breakdown = {
        "probabilidade_base": statistical_probability_pct,
        "confianca_base": base_conf,
        "modificador_script": mod_script,
        "modificador_lesoes": mod_injury,
        "modificador_historico": mod_historico,
        "modificador_odd": mod_odd,
        "confianca_final": final_conf
    }

    return final_conf, breakdown


def detect_value_bet(probabilidade_pct: float, odd: float, threshold_pct: float = 5.0) -> tuple:
    """
    VALUE BET DETECTOR: Compara probabilidade do modelo com a probabilidade implícita da odd.

    A aposta tem "value" quando nossa probabilidade calculada supera a probabilidade implícita
    da odd de mercado em pelo menos `threshold_pct` pontos percentuais.

    Args:
        probabilidade_pct: Probabilidade calculada pelo modelo (0-100%).
        odd: Odd de mercado decimal (ex: 1.90).
        threshold_pct: Mínimo de edge para sinalizar value (padrão: 5%).

    Returns:
        tuple: (is_value: bool, edge_pct: float, prob_implicita_pct: float)
            is_value      — True se edge >= threshold_pct
            edge_pct      — Diferença signed: nossa prob − prob implícita (pode ser negativo)
            prob_implicita_pct — Probabilidade implícita da odd (1/odd * 100)
    """
    if not odd or odd <= 1.0:
        return False, 0.0, 0.0

    prob_implicita = (1.0 / odd) * 100.0
    edge = probabilidade_pct - prob_implicita
    is_value = edge >= threshold_pct

    return is_value, round(edge, 2), round(prob_implicita, 2)
