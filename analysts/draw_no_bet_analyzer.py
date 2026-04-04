"""
Analisador Draw No Bet (DNB) — Phoenix V4.0

Draw No Bet elimina o empate da equação e redistribui as probabilidades
de forma condicional:

  P(DNB - Casa) = P(Home wins) / (P(Home wins) + P(Away wins))
  P(DNB - Fora) = P(Away wins) / (P(Home wins) + P(Away wins))

Só são gerados palpites quando há desequilíbrio claro entre os times
(evitar DNB em jogos equilibrados onde a probabilidade condicional
não difere muito de 50%).

Threshold: 6.5 (exigente — pois P(DNB) sempre é artificialmente alta
              por excluir o empate; requer convicção real na vitória)
"""

from analysts.confidence_calculator import (
    convert_probability_to_base_confidence,
    apply_tactical_script_modifier,
    apply_injury_confidence_modifier,
)


def analisar_mercado_draw_no_bet(analysis_packet: dict, odds: dict) -> dict | None:
    """
    Analisa o mercado Draw No Bet para ambos os times.

    Args:
        analysis_packet: Pacote completo do master_analyzer.
        odds: Dicionário de odds normalizado (chaves dnb_casa, dnb_fora — opcionais).

    Returns:
        dict com 'mercado', 'palpites' e 'dados_suporte', ou None.
    """
    if not analysis_packet or 'error' in analysis_packet:
        return None

    probabilities = analysis_packet.get('calculated_probabilities', {})
    match_result = probabilities.get('match_result', {})

    home_win_prob = match_result.get('home_win_prob', 0.0)
    draw_prob = match_result.get('draw_prob', 0.0)
    away_win_prob = match_result.get('away_win_prob', 0.0)

    if not (home_win_prob or away_win_prob):
        print("  ⚠️  Draw No Bet: probabilidades 1X2 não disponíveis")
        return None

    # Normalizar escala: suporte tanto 0-1 quanto 0-100
    _total_raw = home_win_prob + draw_prob + away_win_prob
    if _total_raw > 1.5:
        # Escala percentual (0-100) — converter para 0-1
        home_win_prob /= 100.0
        draw_prob /= 100.0
        away_win_prob /= 100.0

    decisive_prob = home_win_prob + away_win_prob
    if decisive_prob < 0.01:
        print("  ⚠️  Draw No Bet: probabilidade decisiva muito baixa")
        return None

    # Probabilidades condicionais excluindo empate (saída em escala percentual)
    dnb_home_prob = round(home_win_prob / decisive_prob * 100, 2)
    dnb_away_prob = round(away_win_prob / decisive_prob * 100, 2)

    summary = analysis_packet.get('analysis_summary', {})
    script = summary.get('selected_script')
    reasoning = summary.get('reasoning', '')
    power_home = summary.get('power_score_home', 0)
    power_away = summary.get('power_score_away', 0)
    sev_home = summary.get('injury_severity_home', 'none')
    sev_away = summary.get('injury_severity_away', 'none')
    role_home = summary.get('injury_role_home', 'mixed')
    role_away = summary.get('injury_role_away', 'mixed')

    print(
        f"  🔄 Draw No Bet: home_win={home_win_prob}% draw={draw_prob}% away_win={away_win_prob}%"
    )
    print(f"       DNB Casa: {dnb_home_prob:.1f}% | DNB Fora: {dnb_away_prob:.1f}%")

    THRESHOLD = 6.5

    options = [
        {
            'tipo': 'Draw No Bet - Casa',
            'prob': dnb_home_prob,
            'odd_key': 'dnb_casa',
            'bet_type': 'Draw No Bet Casa',
        },
        {
            'tipo': 'Draw No Bet - Fora',
            'prob': dnb_away_prob,
            'odd_key': 'dnb_fora',
            'bet_type': 'Draw No Bet Fora',
        },
    ]

    palpites = []

    for opt in options:
        prob = opt['prob']
        odd_value = odds.get(opt['odd_key'], 0)

        base = convert_probability_to_base_confidence(prob)
        mod_script = apply_tactical_script_modifier(base, opt['bet_type'], script)
        mod_injury = apply_injury_confidence_modifier(
            opt['bet_type'], sev_home, sev_away, role_home, role_away
        )
        confianca = round(max(1.0, min(10.0, base + mod_script + mod_injury)), 1)

        if confianca < THRESHOLD:
            print(
                f"  ℹ️  Draw No Bet: {opt['tipo']} prob={prob:.1f}% "
                f"confiança={confianca:.1f} (abaixo do threshold {THRESHOLD})"
            )
            continue

        palpites.append({
            'mercado': 'Draw No Bet',
            'tipo': opt['tipo'],
            'confianca': confianca,
            'odd': odd_value if odd_value else None,
            'probabilidade': prob,
            'confidence_breakdown': {
                'base': base,
                'mod_script': mod_script,
                'mod_injury': mod_injury,
                'confianca_final': confianca,
            },
        })
        print(
            f"  ✅ Draw No Bet: {opt['tipo']} prob={prob:.1f}% confiança={confianca:.1f}"
        )

    if not palpites:
        print("  ℹ️  Draw No Bet: nenhum palpite acima do threshold")
        return None

    palpites_sorted = sorted(palpites, key=lambda x: x['confianca'], reverse=True)

    dados_suporte = (
        f"💡 {reasoning}\n\n"
        f"   - <b>Power Score Casa:</b> {power_home}\n"
        f"   - <b>Power Score Fora:</b> {power_away}\n"
        f"   - <b>Probabilidades 1X2:</b> Casa {home_win_prob}% | "
        f"Empate {draw_prob}% | Fora {away_win_prob}%\n"
        f"   - <b>DNB Casa:</b> {dnb_home_prob:.1f}% | <b>DNB Fora:</b> {dnb_away_prob:.1f}%"
    )

    return {
        'mercado': 'Draw No Bet',
        'palpites': palpites_sorted,
        'dados_suporte': dados_suporte,
    }
