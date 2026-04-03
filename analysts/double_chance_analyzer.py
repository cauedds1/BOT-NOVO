"""
Analisador de Dupla Chance (Double Chance) - Phoenix V4.0

Mercado Dupla Chance cobre duas das três possibilidades de resultado:
  - 1X: Casa Vence OU Empate  (P = home_win + draw)
  - X2: Empate OU Fora Vence  (P = draw + away_win)
  - 12: Casa Vence OU Fora Vence  (P = home_win + away_win)

Consome o pacote do Master Analyzer para obter probabilidades já calculadas
pelo motor Poisson+H2H. Usa as odds normalizadas dupla_1x, dupla_x2, dupla_12.

Calibração:
  - Confiança calculada via calculate_final_confidence (pipeline compartilhado)
  - Threshold final: 7.0 (mais exigente que 1X2 pois probs são naturalmente altas)
  - Odds ausentes/zero → opção filtrada (sem mercado = sem valor)
"""

from analysts.confidence_calculator import calculate_final_confidence


def analisar_mercado_dupla_chance(analysis_packet: dict, odds: dict) -> dict | None:
    """
    Analisa o mercado de Dupla Chance (Double Chance).

    Args:
        analysis_packet: Pacote completo gerado pelo master_analyzer.
        odds: Dicionário de odds normalizado pelo api_client
              (chaves esperadas: dupla_1x, dupla_x2, dupla_12).

    Returns:
        dict com 'mercado', 'palpites' e 'dados_suporte', ou None se sem dados suficientes.
    """
    if not analysis_packet or 'error' in analysis_packet:
        return None

    probabilities = analysis_packet.get('calculated_probabilities', {})
    match_result = probabilities.get('match_result', {})

    home_win_prob = match_result.get('home_win_prob', 0.0)
    draw_prob = match_result.get('draw_prob', 0.0)
    away_win_prob = match_result.get('away_win_prob', 0.0)

    if not (home_win_prob or draw_prob or away_win_prob):
        print("  ⚠️  Dupla Chance: probabilidades 1X2 não disponíveis no pacote")
        return None

    summary = analysis_packet.get('analysis_summary', {})
    reasoning = summary.get('reasoning', '')
    power_home = summary.get('power_score_home', 0)
    power_away = summary.get('power_score_away', 0)
    tactical_script = summary.get('selected_script', None)
    injury_sev_home = summary.get('injury_severity_home', 'none')
    injury_sev_away = summary.get('injury_severity_away', 'none')

    THRESHOLD = 7.0

    dc_options = [
        {
            'tipo': 'Dupla Chance 1X (Casa ou Empate)',
            'prob': round(home_win_prob + draw_prob, 2),
            'odd_key': 'dupla_1x',
        },
        {
            'tipo': 'Dupla Chance X2 (Empate ou Fora)',
            'prob': round(draw_prob + away_win_prob, 2),
            'odd_key': 'dupla_x2',
        },
        {
            'tipo': 'Dupla Chance 12 (Casa ou Fora)',
            'prob': round(home_win_prob + away_win_prob, 2),
            'odd_key': 'dupla_12',
        },
    ]

    palpites = []

    for opt in dc_options:
        odd_value = odds.get(opt['odd_key'], 0)

        # Gate 1: Odds devem estar disponíveis — sem mercado não há valor
        if not odd_value or odd_value == 0:
            print(f"  ℹ️  Dupla Chance: {opt['tipo']} → sem odds disponíveis, ignorando")
            continue

        prob = opt['prob']

        # Gate 2: Calcular confiança via pipeline compartilhado (com script + desfalques)
        final_conf, breakdown = calculate_final_confidence(
            statistical_probability_pct=prob,
            bet_type=opt['tipo'],
            tactical_script=tactical_script,
            injury_severity_home=injury_sev_home,
            injury_severity_away=injury_sev_away,
        )

        # Gate 3: Threshold calibrado (mais exigente para DC pois probs são naturalmente altas)
        if final_conf < THRESHOLD:
            print(
                f"  ℹ️  Dupla Chance: {opt['tipo']} → prob={prob}% "
                f"confiança={final_conf:.1f} (abaixo do threshold {THRESHOLD})"
            )
            continue

        palpites.append({
            'mercado': 'Dupla Chance',
            'tipo': opt['tipo'],
            'confianca': round(final_conf, 1),
            'odd': odd_value,
            'probabilidade': prob,
            'confidence_breakdown': breakdown,
        })

        print(
            f"  ✅ Dupla Chance: {opt['tipo']} → prob={prob}% "
            f"confiança={final_conf:.1f} odd={odd_value}"
        )

    if not palpites:
        print("  ℹ️  Dupla Chance: nenhum palpite acima do threshold")
        return None

    palpites_sorted = sorted(palpites, key=lambda x: x['confianca'], reverse=True)

    suporte = (
        f"💡 {reasoning}\n\n"
        f"   - <b>Power Score Casa:</b> {power_home}\n"
        f"   - <b>Power Score Fora:</b> {power_away}\n"
        f"   - <b>Probabilidades 1X2:</b> Casa {home_win_prob}% | "
        f"Empate {draw_prob}% | Fora {away_win_prob}%"
    )

    return {
        'mercado': 'Dupla Chance',
        'palpites': palpites_sorted,
        'dados_suporte': suporte,
    }
