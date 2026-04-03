"""
Analisador de Resultado Final V2 - Consome output do Master Analyzer

Extrai probabilidades de 1X2 calculadas pelo Master Analyzer e formata sugestões.

PHOENIX V2.0: Agora com sistema de VETO e ajuste de confiança por script.
"""

# PURE ANALYST: No odd filtering - only confidence-based selection
# DEPRECATED: from analysts.context_analyzer import verificar_veto_mercado, ajustar_confianca_por_script


def extract_match_result_suggestions(analysis_packet, odds):
    """
    Extrai sugestões de resultado final do pacote do Master Analyzer.
    
    Args:
        analysis_packet: Pacote completo gerado por master_analyzer
        odds: Dicionário com odds disponíveis
    
    Returns:
        dict: Sugestões formatadas para resultado final
    """
    if 'error' in analysis_packet:
        return None
    
    probabilities = analysis_packet['calculated_probabilities']
    script = analysis_packet['analysis_summary']['selected_script']
    reasoning = analysis_packet['analysis_summary']['reasoning']
    
    home_win_prob = probabilities['match_result']['home_win_prob']
    draw_prob = probabilities['match_result']['draw_prob']
    away_win_prob = probabilities['match_result']['away_win_prob']
    
    palpites = []
    
    # LAYER 3: Verificar VETO antes de adicionar cada palpite
    # LAYER 4: Ajustar confiança baseado em coerência com script
    
    if 'home_win' in odds:
        tipo = "Vitória Casa"
        confianca = _convert_probability_to_confidence(home_win_prob)
        if confianca >= 5.5:
            palpites.append({
                "tipo": "Vitória Casa (1)",
                "confianca": confianca,
                "odd": odds['home_win'],
                "probabilidade": home_win_prob
            })
    
    if 'draw' in odds:
        tipo = "Draw"
        confianca = _convert_probability_to_confidence(draw_prob)
        if confianca >= 5.5:
            palpites.append({
                "tipo": "Empate (X)",
                "confianca": confianca,
                "odd": odds['draw'],
                "probabilidade": draw_prob
            })
    
    if 'away_win' in odds:
        tipo = "Vitória Fora"
        confianca = _convert_probability_to_confidence(away_win_prob)
        if confianca >= 5.5:
            palpites.append({
                "tipo": "Vitória Fora (2)",
                "confianca": confianca,
                "odd": odds['away_win'],
                "probabilidade": away_win_prob
            })
    
    if not palpites:
        return None
    
    palpites_sorted = sorted(palpites, key=lambda x: x['confianca'], reverse=True)
    
    power_home = analysis_packet['analysis_summary']['power_score_home']
    power_away = analysis_packet['analysis_summary']['power_score_away']
    
    contexto = (f"💡 {reasoning}\n\n"
               f"   - <b>Power Score Casa:</b> {power_home}\n"
               f"   - <b>Power Score Fora:</b> {power_away}\n"
               f"   - <b>Probabilidades:</b> Casa {home_win_prob}% | Empate {draw_prob}% | Fora {away_win_prob}%")
    
    return {
        "mercado": "Resultado",
        "palpites": palpites_sorted,
        "dados_suporte": contexto,
        "script": script
    }


def _convert_probability_to_confidence(probability_pct):
    """
    Converte probabilidade (%) para escala de confiança (0-10).
    """
    if probability_pct >= 70:
        return 9.0
    elif probability_pct >= 65:
        return 8.5
    elif probability_pct >= 60:
        return 8.0
    elif probability_pct >= 55:
        return 7.5
    elif probability_pct >= 50:
        return 7.0
    elif probability_pct >= 45:
        return 6.5
    elif probability_pct >= 40:
        return 6.0
    elif probability_pct >= 35:
        return 5.5
        return 5.0


def analisar_mercado_resultado_final(analysis_packet, odds):
    """
    Função principal compatível com interface antiga.
    Wrapper para extract_match_result_suggestions().
    """
    return extract_match_result_suggestions(analysis_packet, odds)
