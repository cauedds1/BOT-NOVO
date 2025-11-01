# analysts/corners_analyzer.py
"""
CORNERS ANALYZER V3.0 - DEEP ANALYSIS PROTOCOL

BLUEPRINT IMPLEMENTATION:
- Retorna LISTA de múltiplas predições (~12 predições)
- Analisa submercados: Total Corners (FT), HT Corners, Team Corners
- Cada predição tem confiança calculada via confidence_calculator
- Implementa Script-Based Probability Modifier
"""

from config import MIN_CONFIANCA_CANTOS, MIN_CONFIANCA_CANTOS_UNDER
from analysts.context_analyzer import analisar_compatibilidade_ofensiva_defensiva
from analysts.confidence_calculator import (
    calculate_statistical_probability_corners_over,
    calculate_final_confidence
)


def apply_script_modifier_to_probability_corners(base_prob_pct, bet_type, tactical_script):
    """
    Script-Based Probability Modifier para CANTOS
    
    Aplica modificador de probabilidade baseado no script tático.
    
    Args:
        base_prob_pct: Probabilidade base em % (0-100)
        bet_type: Tipo da aposta (ex: "Over 9.5 Cantos")
        tactical_script: Script tático selecionado
    
    Returns:
        float: Probabilidade modificada (0-100%)
    """
    if not tactical_script:
        return base_prob_pct
    
    modifier = 1.0
    
    # Jogos ofensivos/dominantes geram mais cantos
    if "Over" in bet_type or "over" in bet_type:
        if tactical_script in ["SCRIPT_OPEN_HIGH_SCORING_GAME", "SCRIPT_DOMINIO_CASA", 
                               "SCRIPT_DOMINIO_VISITANTE", "SCRIPT_TIME_EM_CHAMAS_CASA", 
                               "SCRIPT_TIME_EM_CHAMAS_FORA"]:
            modifier = 1.20  # +20% na probabilidade
        elif tactical_script in ["SCRIPT_CAGEY_TACTICAL_AFFAIR", "SCRIPT_TIGHT_LOW_SCORING"]:
            modifier = 0.80  # -20% na probabilidade
    
    elif "Under" in bet_type or "under" in bet_type:
        if tactical_script in ["SCRIPT_CAGEY_TACTICAL_AFFAIR", "SCRIPT_TIGHT_LOW_SCORING", 
                               "SCRIPT_JOGO_DE_COMPADRES"]:
            modifier = 1.20
        elif tactical_script in ["SCRIPT_OPEN_HIGH_SCORING_GAME", "SCRIPT_DOMINIO_CASA", 
                                 "SCRIPT_DOMINIO_VISITANTE"]:
            modifier = 0.80
    
    # Casa dominante gera mais cantos para casa
    if "Casa" in bet_type and "Over" in bet_type:
        if tactical_script in ["SCRIPT_DOMINIO_CASA", "SCRIPT_TIME_EM_CHAMAS_CASA"]:
            modifier = 1.25
    
    # Fora dominante gera mais cantos para visitante
    if "Fora" in bet_type and "Over" in bet_type:
        if tactical_script in ["SCRIPT_DOMINIO_VISITANTE", "SCRIPT_TIME_EM_CHAMAS_FORA"]:
            modifier = 1.25
    
    modified_prob = base_prob_pct * modifier
    return min(max(modified_prob, 0.0), 100.0)


def analisar_mercado_cantos(analysis_packet, odds):
    """
    FUNÇÃO PRINCIPAL - Análise profunda do mercado de cantos.
    
    ACTION 1.2: Retorna LISTA de múltiplas predições (~12 predições) com submercados:
    - Total Corners FT: Over/Under 8.5, 9.5, 10.5
    - First Half Corners HT: Over/Under 4.5
    - Team Corners: Home Over/Under 4.5, 5.5 / Away Over/Under 3.5, 4.5
    
    Args:
        analysis_packet: Pacote completo do Master Analyzer
        odds: Dicionário de odds disponíveis
    
    Returns:
        list: Lista de dicionários de predições ou lista vazia
    """
    # Verificar se há erro no packet
    if 'error' in analysis_packet:
        return []
    
    # Extrair dados do analysis_packet
    stats_casa = analysis_packet.get('raw_data', {}).get('home_stats', {})
    stats_fora = analysis_packet.get('raw_data', {}).get('away_stats', {})
    script_name = analysis_packet.get('analysis_summary', {}).get('selected_script', None)
    classificacao = analysis_packet.get('league_standings', None)
    pos_casa = analysis_packet.get('home_position', 'N/A')
    pos_fora = analysis_packet.get('away_position', 'N/A')
    
    if not stats_casa or not stats_fora:
        return []

    # STEP 1: EXTRAIR MÉTRICAS DE CANTOS
    cantos_casa_feitos = 0.0
    cantos_casa_sofridos = 0.0
    cantos_fora_feitos = 0.0
    cantos_fora_sofridos = 0.0

    use_weighted = False
    if 'analysis_summary' in analysis_packet:
        weighted_home = analysis_packet['analysis_summary'].get('weighted_metrics_home', {})
        weighted_away = analysis_packet['analysis_summary'].get('weighted_metrics_away', {})
        
        if weighted_home and weighted_away:
            use_weighted = True
            cantos_casa_feitos = weighted_home.get('weighted_corners_for', 0.0)
            cantos_casa_sofridos = weighted_home.get('weighted_corners_against', 0.0)
            cantos_fora_feitos = weighted_away.get('weighted_corners_for', 0.0)
            cantos_fora_sofridos = weighted_away.get('weighted_corners_against', 0.0)
            print(f"\n  ⚖️ CANTOS V3.0: Usando WEIGHTED METRICS (ponderado por SoS)")
    
    if not use_weighted:
        cantos_casa_feitos = stats_casa.get('casa', {}).get('cantos_feitos', 0.0)
        cantos_casa_sofridos = stats_casa.get('casa', {}).get('cantos_sofridos', 0.0)
        cantos_fora_feitos = stats_fora.get('fora', {}).get('cantos_feitos', 0.0)
        cantos_fora_sofridos = stats_fora.get('fora', {}).get('cantos_sofridos', 0.0)
        print(f"\n  📊 CANTOS V3.0: Usando médias simples")
    
    print(f"     Casa: {cantos_casa_feitos:.1f} feitos / {cantos_casa_sofridos:.1f} sofridos")
    print(f"     Fora: {cantos_fora_feitos:.1f} feitos / {cantos_fora_sofridos:.1f} sofridos")
    print(f"     Script Tático: {script_name}")

    if (cantos_casa_feitos == 0.0 and cantos_casa_sofridos == 0.0 and 
        cantos_fora_feitos == 0.0 and cantos_fora_sofridos == 0.0):
        print(f"  ❌ CANTOS BLOQUEADO: Dados insuficientes")
        return None

    # STEP 2: ANÁLISE CONTEXTUAL
    insights = analisar_compatibilidade_ofensiva_defensiva(stats_casa, stats_fora)
    fator_cantos = 1.0
    contexto_insights = []

    for insight in insights:
        if insight['tipo'] == 'cantos_casa_favoravel':
            fator_cantos *= insight['fator_multiplicador']
            contexto_insights.append(insight['descricao'])
        elif insight['tipo'] == 'festival_gols':
            fator_cantos *= 1.2
            contexto_insights.append("⚡ Jogo ofensivo tende a gerar MAIS cantos!")

    # STEP 3: CALCULAR MÉDIAS ESPERADAS
    media_exp_ft = (cantos_casa_feitos + cantos_fora_sofridos + 
                    cantos_fora_feitos + cantos_casa_sofridos) / 2
    media_exp_ft_ajustada = media_exp_ft * fator_cantos
    media_exp_ht = media_exp_ft_ajustada * 0.48  # HT = ~48% dos cantos
    media_casa = cantos_casa_feitos * (fator_cantos if fator_cantos > 1.0 else 1.0)
    media_fora = cantos_fora_feitos

    print(f"  📊 Médias: FT={media_exp_ft_ajustada:.1f}, HT={media_exp_ht:.1f}, Casa={media_casa:.1f}, Fora={media_fora:.1f}")

    all_predictions = []

    if not odds:
        print(f"  ⚠️ CANTOS: Sem odds disponíveis")
        return None

    # ========== 1. TOTAL CORNERS FULL TIME ==========
    
    linhas_ft_over = [8.5, 9.5, 10.5, 11.5]
    for linha in linhas_ft_over:
        odd_key = f"cantos_ft_over_{linha}"
        if odd_key in odds:
            prob_pct = calculate_statistical_probability_corners_over(
                weighted_corners_avg=media_exp_ft_ajustada,
                line=linha,
                historical_frequency=None
            )
            
            prob_pct = apply_script_modifier_to_probability_corners(
                prob_pct, f"Over {linha} Cantos", script_name
            )
            
            bet_type = f"Over {linha} Cantos"
            conf_final, breakdown = calculate_final_confidence(
                statistical_probability_pct=prob_pct,
                bet_type=bet_type,
                tactical_script=script_name,
            )
            
            if conf_final >= MIN_CONFIANCA_CANTOS:
                all_predictions.append({
                    "mercado": "Cantos",
                    "tipo": bet_type,
                    "confianca": conf_final,
                    "odd": odds[odd_key],
                    "periodo": "FT",
                    "time": "Total",
                    "breakdown": breakdown,
                    "probabilidade_estatistica": prob_pct
                })
    
    linhas_ft_under = [8.5, 9.5, 10.5, 11.5]
    for linha in linhas_ft_under:
        odd_key = f"cantos_ft_under_{linha}"
        if odd_key in odds:
            prob_over = calculate_statistical_probability_corners_over(
                weighted_corners_avg=media_exp_ft_ajustada,
                line=linha,
                historical_frequency=None
            )
            prob_under = 100.0 - prob_over
            
            prob_under = apply_script_modifier_to_probability_corners(
                prob_under, f"Under {linha} Cantos", script_name
            )
            
            bet_type = f"Under {linha} Cantos"
            conf_final, breakdown = calculate_final_confidence(
                statistical_probability_pct=prob_under,
                bet_type=bet_type,
                tactical_script=script_name,
            )
            
            if conf_final >= MIN_CONFIANCA_CANTOS_UNDER:
                all_predictions.append({
                    "mercado": "Cantos",
                    "tipo": bet_type,
                    "confianca": conf_final,
                    "odd": odds[odd_key],
                    "periodo": "FT",
                    "time": "Total",
                    "breakdown": breakdown,
                    "probabilidade_estatistica": prob_under
                })
    
    # ========== 2. FIRST HALF CORNERS ==========
    
    linhas_ht = [4.5, 5.5]
    for linha in linhas_ht:
        # Over HT
        odd_key_over = f"cantos_ht_over_{linha}"
        if odd_key_over in odds:
            prob_pct = calculate_statistical_probability_corners_over(
                weighted_corners_avg=media_exp_ht,
                line=linha,
                historical_frequency=None
            )
            
            prob_pct = apply_script_modifier_to_probability_corners(
                prob_pct, f"Over {linha} Cantos HT", script_name
            )
            
            bet_type = f"Over {linha} HT"
            conf_final, breakdown = calculate_final_confidence(
                statistical_probability_pct=prob_pct,
                bet_type=bet_type,
                tactical_script=script_name,
            )
            
            if conf_final >= MIN_CONFIANCA_CANTOS:
                all_predictions.append({
                    "mercado": "Cantos",
                    "tipo": bet_type,
                    "confianca": conf_final,
                    "odd": odds[odd_key_over],
                    "periodo": "HT",
                    "time": "Total",
                    "breakdown": breakdown,
                    "probabilidade_estatistica": prob_pct
                })
        
        # Under HT
        odd_key_under = f"cantos_ht_under_{linha}"
        if odd_key_under in odds:
            prob_over = calculate_statistical_probability_corners_over(
                weighted_corners_avg=media_exp_ht,
                line=linha,
                historical_frequency=None
            )
            prob_under = 100.0 - prob_over
            
            prob_under = apply_script_modifier_to_probability_corners(
                prob_under, f"Under {linha} Cantos HT", script_name
            )
            
            bet_type = f"Under {linha} HT"
            conf_final, breakdown = calculate_final_confidence(
                statistical_probability_pct=prob_under,
                bet_type=bet_type,
                tactical_script=script_name,
            )
            
            if conf_final >= MIN_CONFIANCA_CANTOS_UNDER:
                all_predictions.append({
                    "mercado": "Cantos",
                    "tipo": bet_type,
                    "confianca": conf_final,
                    "odd": odds[odd_key_under],
                    "periodo": "HT",
                    "time": "Total",
                    "breakdown": breakdown,
                    "probabilidade_estatistica": prob_under
                })
    
    # ========== 3. HOME TEAM CORNERS ==========
    
    linhas_casa = [4.5, 5.5, 6.5]
    for linha in linhas_casa:
        # Over Casa
        odd_key_over = f"cantos_casa_over_{linha}"
        if odd_key_over in odds:
            prob_pct = calculate_statistical_probability_corners_over(
                weighted_corners_avg=media_casa,
                line=linha,
                historical_frequency=None
            )
            
            prob_pct = apply_script_modifier_to_probability_corners(
                prob_pct, f"Casa Over {linha} Cantos", script_name
            )
            
            bet_type = f"Casa Over {linha}"
            conf_final, breakdown = calculate_final_confidence(
                statistical_probability_pct=prob_pct,
                bet_type=bet_type,
                tactical_script=script_name,
            )
            
            if conf_final >= MIN_CONFIANCA_CANTOS:
                all_predictions.append({
                    "mercado": "Cantos",
                    "tipo": bet_type,
                    "confianca": conf_final,
                    "odd": odds[odd_key_over],
                    "periodo": "FT",
                    "time": "Casa",
                    "breakdown": breakdown,
                    "probabilidade_estatistica": prob_pct
                })
        
        # Under Casa
        odd_key_under = f"cantos_casa_under_{linha}"
        if odd_key_under in odds:
            prob_over = calculate_statistical_probability_corners_over(
                weighted_corners_avg=media_casa,
                line=linha,
                historical_frequency=None
            )
            prob_under = 100.0 - prob_over
            
            prob_under = apply_script_modifier_to_probability_corners(
                prob_under, f"Casa Under {linha} Cantos", script_name
            )
            
            bet_type = f"Casa Under {linha}"
            conf_final, breakdown = calculate_final_confidence(
                statistical_probability_pct=prob_under,
                bet_type=bet_type,
                tactical_script=script_name,
            )
            
            if conf_final >= MIN_CONFIANCA_CANTOS_UNDER:
                all_predictions.append({
                    "mercado": "Cantos",
                    "tipo": bet_type,
                    "confianca": conf_final,
                    "odd": odds[odd_key_under],
                    "periodo": "FT",
                    "time": "Casa",
                    "breakdown": breakdown,
                    "probabilidade_estatistica": prob_under
                })
    
    # ========== 4. AWAY TEAM CORNERS ==========
    
    linhas_fora = [3.5, 4.5, 5.5]
    for linha in linhas_fora:
        # Over Fora
        odd_key_over = f"cantos_fora_over_{linha}"
        if odd_key_over in odds:
            prob_pct = calculate_statistical_probability_corners_over(
                weighted_corners_avg=media_fora,
                line=linha,
                historical_frequency=None
            )
            
            prob_pct = apply_script_modifier_to_probability_corners(
                prob_pct, f"Fora Over {linha} Cantos", script_name
            )
            
            bet_type = f"Fora Over {linha}"
            conf_final, breakdown = calculate_final_confidence(
                statistical_probability_pct=prob_pct,
                bet_type=bet_type,
                tactical_script=script_name,
            )
            
            if conf_final >= MIN_CONFIANCA_CANTOS:
                all_predictions.append({
                    "mercado": "Cantos",
                    "tipo": bet_type,
                    "confianca": conf_final,
                    "odd": odds[odd_key_over],
                    "periodo": "FT",
                    "time": "Fora",
                    "breakdown": breakdown,
                    "probabilidade_estatistica": prob_pct
                })
        
        # Under Fora
        odd_key_under = f"cantos_fora_under_{linha}"
        if odd_key_under in odds:
            prob_over = calculate_statistical_probability_corners_over(
                weighted_corners_avg=media_fora,
                line=linha,
                historical_frequency=None
            )
            prob_under = 100.0 - prob_over
            
            prob_under = apply_script_modifier_to_probability_corners(
                prob_under, f"Fora Under {linha} Cantos", script_name
            )
            
            bet_type = f"Fora Under {linha}"
            conf_final, breakdown = calculate_final_confidence(
                statistical_probability_pct=prob_under,
                bet_type=bet_type,
                tactical_script=script_name,
            )
            
            if conf_final >= MIN_CONFIANCA_CANTOS_UNDER:
                all_predictions.append({
                    "mercado": "Cantos",
                    "tipo": bet_type,
                    "confianca": conf_final,
                    "odd": odds[odd_key_under],
                    "periodo": "FT",
                    "time": "Fora",
                    "breakdown": breakdown,
                    "probabilidade_estatistica": prob_under
                })
    
    print(f"  ✅ CANTOS V3.0: {len(all_predictions)} predições geradas (deep analysis)")
    
    if all_predictions:
        contexto_str = ""
        if contexto_insights:
            contexto_str = f"💡 Contexto: {contexto_insights[0]}\n"

        suporte = (f"Expectativa Total: {media_exp_ft:.1f} → {media_exp_ft_ajustada:.1f} (ajustada)\n"
                   f"Casa: {cantos_casa_feitos:.1f} cantos/jogo\n"
                   f"Fora: {cantos_fora_feitos:.1f} cantos/jogo\n"
                   f"{contexto_str}")
        
        return {"mercado": "Cantos", "palpites": all_predictions, "dados_suporte": suporte}
    
    print(f"  ❌ CANTOS: Nenhuma predição passou nos filtros")
    return None
