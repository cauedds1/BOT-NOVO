"""
Analisador Win to Nil (Vitória sem sofrer gol) — Phoenix V4.0

Calcula a probabilidade de cada time vencer sem sofrer gols usando
distribuição de Poisson independente para os lambdas de cada time.

P(Win to Nil - Casa) = P(away goals = 0) × P(home goals >= 1)
                     = exp(-λ_away) × (1 - exp(-λ_home))

P(Win to Nil - Fora) = P(home goals = 0) × P(away goals >= 1)
                     = exp(-λ_home) × (1 - exp(-λ_away))

Threshold: 5.5 (mercado exigente — clean sheet + vitória)
"""

import math
from analysts.confidence_calculator import (
    convert_probability_to_base_confidence,
    apply_tactical_script_modifier,
    apply_injury_confidence_modifier,
)


def analisar_mercado_win_to_nil(analysis_packet: dict, odds: dict) -> dict | None:
    """
    Analisa o mercado Win to Nil para ambos os times.

    Args:
        analysis_packet: Pacote completo do master_analyzer.
        odds: Dicionário de odds normalizado (chaves win_to_nil_casa, win_to_nil_fora — opcionais).

    Returns:
        dict com 'mercado', 'palpites' e 'dados_suporte', ou None.
    """
    if not analysis_packet or 'error' in analysis_packet:
        return None

    probabilities = analysis_packet.get('calculated_probabilities', {})
    lambda_data = probabilities.get('lambda_goals', {})
    lambda_home = lambda_data.get('lambda_home', 0.0)
    lambda_away = lambda_data.get('lambda_away', 0.0)

    # Fallback: derivar lambdas das probabilidades de resultado se necessário
    if lambda_home == 0.0 and lambda_away == 0.0:
        match_result = probabilities.get('match_result', {})
        home_win_prob = match_result.get('home_win_prob', 33.3)
        away_win_prob = match_result.get('away_win_prob', 33.3)
        lambda_home = 1.3 if home_win_prob > 45 else (0.85 if home_win_prob < 25 else 1.1)
        lambda_away = 1.3 if away_win_prob > 45 else (0.85 if away_win_prob < 25 else 1.1)
        print(f"  ⚠️  Win to Nil: usando lambdas estimados λ_casa={lambda_home:.2f} λ_fora={lambda_away:.2f}")

    summary = analysis_packet.get('analysis_summary', {})
    script = summary.get('selected_script')
    reasoning = summary.get('reasoning', '')
    power_home = summary.get('power_score_home', 0)
    power_away = summary.get('power_score_away', 0)
    sev_home = summary.get('injury_severity_home', 'none')
    sev_away = summary.get('injury_severity_away', 'none')
    role_home = summary.get('injury_role_home', 'mixed')
    role_away = summary.get('injury_role_away', 'mixed')

    # P(Win to Nil - Casa) = P(away = 0) * P(home >= 1)
    p_away_zero = math.exp(-lambda_away)
    p_home_scores = 1.0 - math.exp(-lambda_home)
    prob_casa = round(p_away_zero * p_home_scores * 100, 2)

    # P(Win to Nil - Fora) = P(home = 0) * P(away >= 1)
    p_home_zero = math.exp(-lambda_home)
    p_away_scores = 1.0 - math.exp(-lambda_away)
    prob_fora = round(p_home_zero * p_away_scores * 100, 2)

    print(f"  🔒 Win to Nil: λ_casa={lambda_home:.2f} λ_fora={lambda_away:.2f}")
    print(f"       Casa sem sofrer: {prob_casa:.1f}% | Fora sem sofrer: {prob_fora:.1f}%")

    THRESHOLD = 5.5

    palpites = []

    options = [
        {
            'tipo': 'Win to Nil - Casa',
            'prob': prob_casa,
            'odd_key': 'win_to_nil_casa',
            'bet_type': 'Win to Nil Casa',
        },
        {
            'tipo': 'Win to Nil - Fora',
            'prob': prob_fora,
            'odd_key': 'win_to_nil_fora',
            'bet_type': 'Win to Nil Fora',
        },
    ]

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
                f"  ℹ️  Win to Nil: {opt['tipo']} prob={prob:.1f}% confiança={confianca:.1f} "
                f"(abaixo do threshold {THRESHOLD})"
            )
            continue

        palpites.append({
            'mercado': 'Win to Nil',
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
        print(f"  ✅ Win to Nil: {opt['tipo']} prob={prob:.1f}% confiança={confianca:.1f}")

    if not palpites:
        print("  ℹ️  Win to Nil: nenhum palpite acima do threshold")
        return None

    palpites_sorted = sorted(palpites, key=lambda x: x['confianca'], reverse=True)

    dados_suporte = (
        f"💡 {reasoning}\n\n"
        f"   - <b>Power Score Casa:</b> {power_home}\n"
        f"   - <b>Power Score Fora:</b> {power_away}\n"
        f"   - <b>λ Casa:</b> {lambda_home:.2f} | <b>λ Fora:</b> {lambda_away:.2f}\n"
        f"   - <b>P(Clean Sheet Casa):</b> {round(p_home_zero * 100, 1)}% | "
        f"<b>P(Clean Sheet Fora):</b> {round(p_away_zero * 100, 1)}%"
    )

    return {
        'mercado': 'Win to Nil',
        'palpites': palpites_sorted,
        'dados_suporte': dados_suporte,
    }
