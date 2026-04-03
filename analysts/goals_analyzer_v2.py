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
from analysts.confidence_calculator import calculate_final_confidence
import math


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
    
    # Extrair probabilidades base do master analyzer
    over_2_5_prob = probabilities['goals_over_under_2_5']['over_2_5_prob']
    under_2_5_prob = probabilities['goals_over_under_2_5']['under_2_5_prob']
    btts_sim_prob = probabilities.get('btts', {}).get('btts_yes_prob', 50.0)
    btts_nao_prob = probabilities.get('btts', {}).get('btts_no_prob', 50.0)
    
    # Calcular probabilidades para outras linhas
    over_1_5_prob = min(over_2_5_prob + 15, 95)
    under_1_5_prob = 100 - over_1_5_prob
    over_3_5_prob = max(over_2_5_prob - 20, 15) if script == 'SCRIPT_OPEN_HIGH_SCORING_GAME' else max(over_2_5_prob - 30, 10)
    under_3_5_prob = 100 - over_3_5_prob
    
    # HT probabilities (aproximadamente 50% dos gols no HT)
    over_0_5_ht_prob = min(over_1_5_prob * 0.75, 85)
    under_0_5_ht_prob = 100 - over_0_5_ht_prob
    over_1_5_ht_prob = max(over_2_5_prob * 0.40, 25)
    under_1_5_ht_prob = 100 - over_1_5_ht_prob
    
    # Team goals (estimativa baseada em distribuição)
    home_over_0_5_prob = min(over_1_5_prob * 0.80, 85)
    home_under_0_5_prob = 100 - home_over_0_5_prob
    home_over_1_5_prob = max(over_2_5_prob * 0.55, 30)
    home_under_1_5_prob = 100 - home_over_1_5_prob
    
    away_over_0_5_prob = min(over_1_5_prob * 0.70, 80)
    away_under_0_5_prob = 100 - away_over_0_5_prob
    away_over_1_5_prob = max(over_2_5_prob * 0.45, 25)
    away_under_1_5_prob = 100 - away_over_1_5_prob
    
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
            tactical_script=script
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
            tactical_script=script
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
            tactical_script=script
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
            tactical_script=script
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
            tactical_script=script
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
            tactical_script=script
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
    
    # ========== 2. FIRST HALF GOALS ==========
    
    # Over 0.5 HT
    if 'gols_ht_over_0.5' in odds:
        prob = over_0_5_ht_prob
        confianca, breakdown = calculate_final_confidence(
            statistical_probability_pct=prob,
            bet_type="Over 0.5 HT",
            tactical_script=script
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
            tactical_script=script
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
            tactical_script=script
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
            tactical_script=script
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
            tactical_script=script
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
            tactical_script=script
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
            tactical_script=script
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
            tactical_script=script
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
            tactical_script=script
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
            tactical_script=script
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
            tactical_script=script
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
            tactical_script=script
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
            tactical_script=script
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
            tactical_script=script
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
    
    # Ordenar por confiança (descendente)
    all_predictions.sort(key=lambda x: x['confianca'], reverse=True)
    
    print(f"  ✅ GOLS V3.0: {len(all_predictions)} predições geradas (deep analysis)")
    
    # Retornar no formato compatível (wrapping lista em dict para compatibilidade)
    if all_predictions:
        return {
            "mercado": "Gols",
            "palpites": all_predictions,
            "dados_suporte": f"💡 {reasoning}",
            "script": script
        }
    
    return None


def extract_goals_suggestions(analysis_packet, odds):
    """Wrapper para compatibilidade com código existente"""
    return analisar_mercado_gols(analysis_packet, odds)
