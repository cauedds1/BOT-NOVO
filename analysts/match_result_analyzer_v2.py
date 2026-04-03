"""
Analisador de Resultado Final V2 - Consome output do Master Analyzer

Extrai probabilidades de 1X2 calculadas pelo Master Analyzer e formata sugestões.

PHOENIX V4.0: Aplica modificadores de script tático na confiança final,
consistente com todos os demais analisadores especializados.
"""

from analysts.confidence_calculator import (
    apply_tactical_script_modifier,
    convert_probability_to_base_confidence,
    apply_injury_confidence_modifier,
)


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
    summary = analysis_packet['analysis_summary']
    script = summary.get('selected_script')
    reasoning = summary.get('reasoning', '')

    home_win_prob = probabilities['match_result']['home_win_prob']
    draw_prob = probabilities['match_result']['draw_prob']
    away_win_prob = probabilities['match_result']['away_win_prob']

    # Extrair desfalques para modificador direcional
    sev_home  = summary.get('injury_severity_home', 'none')
    sev_away  = summary.get('injury_severity_away', 'none')
    role_home = summary.get('injury_role_home', 'mixed')
    role_away = summary.get('injury_role_away', 'mixed')

    palpites = []

    if 'home_win' in odds:
        confianca = _build_confidence("Vitória Casa", home_win_prob, script,
                                      sev_home, sev_away, role_home, role_away)
        if confianca >= 5.5:
            palpites.append({
                "tipo": "Vitória Casa (1)",
                "confianca": confianca,
                "odd": odds['home_win'],
                "probabilidade": home_win_prob
            })

    if 'draw' in odds:
        confianca = _build_confidence("Empate", draw_prob, script,
                                      sev_home, sev_away, role_home, role_away)
        if confianca >= 5.5:
            palpites.append({
                "tipo": "Empate (X)",
                "confianca": confianca,
                "odd": odds['draw'],
                "probabilidade": draw_prob
            })

    if 'away_win' in odds:
        confianca = _build_confidence("Vitória Fora", away_win_prob, script,
                                      sev_home, sev_away, role_home, role_away)
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

    power_home = summary.get('power_score_home', '?')
    power_away = summary.get('power_score_away', '?')

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


def _build_confidence(bet_type, probability_pct, tactical_script,
                      sev_home, sev_away, role_home, role_away):
    """
    Calcula confiança final para um palpite de resultado:
      1. Converte probabilidade → confiança base
      2. Aplica modificador de script tático
      3. Aplica modificador de desfalques direcional
      4. Clampa entre 1.0 e 10.0
    """
    base = convert_probability_to_base_confidence(probability_pct)
    mod_script = apply_tactical_script_modifier(base, bet_type, tactical_script)
    mod_injury = apply_injury_confidence_modifier(
        bet_type,
        sev_home, sev_away,
        role_home, role_away,
    )
    return round(max(1.0, min(10.0, base + mod_script + mod_injury)), 1)


def analisar_mercado_resultado_final(analysis_packet, odds):
    """
    Função principal compatível com interface antiga.
    Wrapper para extract_match_result_suggestions().
    """
    return extract_match_result_suggestions(analysis_packet, odds)
