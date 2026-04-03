"""
Analisador de Gols em Ambos os Tempos (GABT) - Phoenix V4.0

Mercado GABT (Goals Both Halves): o jogo deve ter pelo menos 1 gol no 1º tempo
e pelo menos 1 gol no 2º tempo.

Matemática:
  lambda_goals = calculated_probabilities['lambda_goals'] (dict do master_analyzer)
  λ_total  = lambda_goals['lambda_total']
  ht_ratio = lambda_goals.get('ht_ratio', HT_RATIO_DEFAULT)
  λ_1T     = λ_total × ht_ratio
  λ_2T     = λ_total × (1 - ht_ratio)
  P(≥1 gol em T) = 1 - e^(-λ_T)   [distribuição Poisson]
  P(GABT Sim) = P(≥1 no 1T) × P(≥1 no 2T)   [independência dos tempos]

Calibração:
  - Confiança calculada via calculate_final_confidence (pipeline compartilhado)
  - Threshold: 6.5 (GABT é mais difícil de atingir que BTTS; probs típicas 22-75%)
  - Odds obrigatórias (gabt_sim / gabt_nao) — sem odds não há palpite
"""

import math
from analysts.confidence_calculator import calculate_final_confidence

HT_RATIO_DEFAULT = 0.43
THRESHOLD = 6.5


def _poisson_prob_at_least_one(lam: float) -> float:
    """P(X >= 1) onde X ~ Poisson(lam). Retorna probabilidade em fração (0-1)."""
    if lam <= 0:
        return 0.0
    return 1.0 - math.exp(-lam)


def analisar_mercado_gabt(analysis_packet: dict, odds: dict) -> dict | None:
    """
    Analisa o mercado Gols em Ambos os Tempos (GABT).

    Args:
        analysis_packet: Pacote completo gerado pelo master_analyzer.
        odds: Dicionário de odds normalizado pelo api_client
              (chaves esperadas: gabt_sim, gabt_nao).

    Returns:
        dict com 'mercado', 'palpites' e 'dados_suporte', ou None se sem dados.
    """
    if not analysis_packet or 'error' in analysis_packet:
        return None

    probabilities = analysis_packet.get('calculated_probabilities', {})
    lambda_goals_data = probabilities.get('lambda_goals', None)

    if not lambda_goals_data:
        print("  ⚠️  GABT: lambda_goals não disponível no pacote, abortando")
        return None

    if isinstance(lambda_goals_data, dict):
        lambda_total = lambda_goals_data.get('lambda_total', 0)
        ht_ratio = lambda_goals_data.get('ht_ratio', HT_RATIO_DEFAULT)
    elif isinstance(lambda_goals_data, (int, float)):
        lambda_total = float(lambda_goals_data)
        ht_ratio = HT_RATIO_DEFAULT
    else:
        print(f"  ⚠️  GABT: lambda_goals tipo inesperado ({type(lambda_goals_data)}), abortando")
        return None

    if not lambda_total or lambda_total <= 0:
        print("  ⚠️  GABT: lambda_total zero ou inválido, abortando")
        return None

    summary = analysis_packet.get('analysis_summary', {})
    tactical_script = summary.get('selected_script', None)
    injury_sev_home = summary.get('injury_severity_home', 'none')
    injury_sev_away = summary.get('injury_severity_away', 'none')
    reasoning = summary.get('reasoning', '')
    power_home = summary.get('power_score_home', 0)
    power_away = summary.get('power_score_away', 0)

    lam_1t = lambda_total * ht_ratio
    lam_2t = lambda_total * (1.0 - ht_ratio)

    prob_gol_1t = _poisson_prob_at_least_one(lam_1t)
    prob_gol_2t = _poisson_prob_at_least_one(lam_2t)

    prob_gabt_sim = prob_gol_1t * prob_gol_2t
    prob_gabt_nao = 1.0 - prob_gabt_sim

    prob_gabt_sim_pct = round(prob_gabt_sim * 100, 1)
    prob_gabt_nao_pct = round(prob_gabt_nao * 100, 1)

    print(
        f"  🔢 GABT: λ_total={lambda_total:.2f} | ht_ratio={ht_ratio:.2f} "
        f"| λ_1T={lam_1t:.2f} | λ_2T={lam_2t:.2f} "
        f"| P(≥1 1T)={prob_gol_1t:.1%} | P(≥1 2T)={prob_gol_2t:.1%} "
        f"| P(GABT Sim)={prob_gabt_sim_pct}%"
    )

    opcoes = [
        {
            'tipo': 'GABT - Sim (Gol em Ambos os Tempos)',
            'prob': prob_gabt_sim_pct,
            'odd_key': 'gabt_sim',
        },
        {
            'tipo': 'GABT - Não (Sem Gol em Um dos Tempos)',
            'prob': prob_gabt_nao_pct,
            'odd_key': 'gabt_nao',
        },
    ]

    palpites = []

    for opt in opcoes:
        odd_value = odds.get(opt['odd_key'], 0)

        if not odd_value or odd_value == 0:
            print(f"  ℹ️  GABT: {opt['tipo']} → sem odds disponíveis, ignorando")
            continue

        prob = opt['prob']

        final_conf, breakdown = calculate_final_confidence(
            statistical_probability_pct=prob,
            bet_type=opt['tipo'],
            tactical_script=tactical_script,
            injury_severity_home=injury_sev_home,
            injury_severity_away=injury_sev_away,
        )

        if final_conf < THRESHOLD:
            print(
                f"  ℹ️  GABT: {opt['tipo']} → prob={prob}% "
                f"confiança={final_conf:.1f} (abaixo do threshold {THRESHOLD})"
            )
            continue

        palpites.append({
            'mercado': 'Gols Ambos Tempos',
            'tipo': opt['tipo'],
            'confianca': round(final_conf, 1),
            'odd': odd_value,
            'probabilidade': prob,
            'confidence_breakdown': breakdown,
        })

        print(
            f"  ✅ GABT: {opt['tipo']} → prob={prob}% "
            f"confiança={final_conf:.1f} odd={odd_value}"
        )

    if not palpites:
        print("  ℹ️  GABT: nenhum palpite acima do threshold")
        return None

    palpites_sorted = sorted(palpites, key=lambda x: x['confianca'], reverse=True)

    suporte = (
        f"💡 {reasoning}\n\n"
        f"   - <b>λ Gols (Poisson):</b> {lambda_total:.2f}\n"
        f"   - <b>P(≥1 gol 1T):</b> {prob_gol_1t:.1%}\n"
        f"   - <b>P(≥1 gol 2T):</b> {prob_gol_2t:.1%}\n"
        f"   - <b>P(GABT Sim):</b> {prob_gabt_sim_pct}% | <b>P(GABT Não):</b> {prob_gabt_nao_pct}%\n"
        f"   - <b>Power Score Casa:</b> {power_home} | <b>Power Score Fora:</b> {power_away}"
    )

    return {
        'mercado': 'Gols Ambos Tempos',
        'palpites': palpites_sorted,
        'dados_suporte': suporte,
    }
