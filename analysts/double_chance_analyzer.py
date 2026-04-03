"""
Analisador de Dupla Chance (Double Chance) - Phoenix V4.0

Mercado Dupla Chance cobre duas das três possibilidades de resultado:
  - 1X: Casa Vence OU Empate  (P = home_win + draw)
  - X2: Empate OU Fora Vence  (P = draw + away_win)
  - 12: Casa Vence OU Fora Vence  (P = home_win + away_win)

Consome o pacote do Master Analyzer para obter probabilidades já calculadas
pelo motor Poisson+H2H. Usa as odds normalizadas dupla_1x, dupla_x2, dupla_12.

Threshold elevado (6.0) porque probabilidades de DC são naturalmente altas;
usar o mesmo threshold de 1X2 geraria palpites de baixo valor.
"""


def _prob_to_confianca(prob_pct: float) -> float:
    """
    Converte probabilidade percentual para escala de confiança 0-10.

    Escala ajustada para DC (probabilidades naturalmente altas):
      >= 85% → 9.5
      >= 80% → 9.0
      >= 75% → 8.5
      >= 70% → 8.0
      >= 65% → 7.5
      >= 60% → 7.0
      >= 55% → 6.5
      >= 50% → 6.0
      <  50% → 5.0 (abaixo do threshold)
    """
    if prob_pct >= 85:
        return 9.5
    elif prob_pct >= 80:
        return 9.0
    elif prob_pct >= 75:
        return 8.5
    elif prob_pct >= 70:
        return 8.0
    elif prob_pct >= 65:
        return 7.5
    elif prob_pct >= 60:
        return 7.0
    elif prob_pct >= 55:
        return 6.5
    elif prob_pct >= 50:
        return 6.0
    return 5.0


def analisar_mercado_dupla_chance(analysis_packet: dict, odds: dict) -> dict | None:
    """
    Analisa o mercado de Dupla Chance (Double Chance).

    Args:
        analysis_packet: Pacote completo gerado pelo master_analyzer.
        odds: Dicionário de odds normalizado pelo api_client (keys: dupla_1x, dupla_x2, dupla_12).

    Returns:
        dict com 'mercado', 'palpites' e 'dados_suporte', ou None se sem dados.
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

    reasoning = analysis_packet.get('analysis_summary', {}).get('reasoning', '')
    power_home = analysis_packet.get('analysis_summary', {}).get('power_score_home', 0)
    power_away = analysis_packet.get('analysis_summary', {}).get('power_score_away', 0)

    palpites = []
    THRESHOLD = 6.0

    dc_options = [
        {
            'tipo': 'Dupla Chance 1X (Casa ou Empate)',
            'prob': home_win_prob + draw_prob,
            'odd_key': 'dupla_1x',
        },
        {
            'tipo': 'Dupla Chance X2 (Empate ou Fora)',
            'prob': draw_prob + away_win_prob,
            'odd_key': 'dupla_x2',
        },
        {
            'tipo': 'Dupla Chance 12 (Casa ou Fora)',
            'prob': home_win_prob + away_win_prob,
            'odd_key': 'dupla_12',
        },
    ]

    for opt in dc_options:
        prob = round(opt['prob'], 2)
        confianca = _prob_to_confianca(prob)

        if confianca < THRESHOLD:
            print(f"  ℹ️  Dupla Chance: {opt['tipo']} → prob={prob}% confiança={confianca} (abaixo do threshold)")
            continue

        odd_value = odds.get(opt['odd_key'], 0)

        palpites.append({
            'mercado': 'Dupla Chance',
            'tipo': opt['tipo'],
            'confianca': confianca,
            'odd': odd_value,
            'probabilidade': prob,
        })

        print(f"  ✅ Dupla Chance: {opt['tipo']} → prob={prob}% confiança={confianca} odd={odd_value}")

    if not palpites:
        print("  ℹ️  Dupla Chance: nenhum palpite acima do threshold")
        return None

    palpites_sorted = sorted(palpites, key=lambda x: x['confianca'], reverse=True)

    suporte = (
        f"💡 {reasoning}\n\n"
        f"   - <b>Power Score Casa:</b> {power_home}\n"
        f"   - <b>Power Score Fora:</b> {power_away}\n"
        f"   - <b>Probabilidades 1X2:</b> Casa {home_win_prob}% | Empate {draw_prob}% | Fora {away_win_prob}%"
    )

    return {
        'mercado': 'Dupla Chance',
        'palpites': palpites_sorted,
        'dados_suporte': suporte,
    }
