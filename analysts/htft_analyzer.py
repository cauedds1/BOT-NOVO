"""
Analisador HT/FT (Resultado Intervalo + Resultado Final) — Phoenix V4.0

Calcula probabilidades para todas as 9 combinações de resultado ao intervalo
e resultado final usando distribuição de Poisson bivariada independente.

Os lambdas são divididos por tempo (HT e 2H) com base no ht_ratio configurado
no master_analyzer. As probabilidades de cada cenário (home goals, away goals)
são acumuladas diretamente via Poisson para dar as probabilidades conjuntas.

Threshold padrão: 5.5 (este mercado é de nicho; exige alta confiança)
Máximo de picks por partida: 3 (as 3 combinações mais prováveis acima do threshold)
"""

import math
from analysts.confidence_calculator import (
    convert_probability_to_base_confidence,
    apply_tactical_script_modifier,
    apply_injury_confidence_modifier,
)

_MAX_GOLS = 6  # teto para iteração Poisson (probabilidade restante é negligenciável)


def _poisson_prob(lam: float, k: int) -> float:
    """P(X = k) para Poisson(lambda)."""
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def _htft_probs(lambda_home: float, lambda_away: float, ht_ratio: float) -> dict:
    """
    Calcula P(HT result, FT result) para todas as 9 combinações.

    Modelo:
      - Goals HT ~ Poisson(lambda_home * ht_ratio) × Poisson(lambda_away * ht_ratio)
      - Goals 2H ~ Poisson(lambda_home * 2h_ratio) × Poisson(lambda_away * 2h_ratio)
      - Goals FT = Goals HT + Goals 2H
      - Assume independência entre HT e 2H (boa aproximação)

    Returns:
        dict com chaves "H/H", "H/D", "H/A", "D/H", "D/D", "D/A", "A/H", "A/D", "A/A"
        e valores em percentagem (0–100).
    """
    ht_ratio = max(0.35, min(0.55, ht_ratio))  # sanidade
    second_ratio = 1.0 - ht_ratio

    lam_h_ht = lambda_home * ht_ratio
    lam_a_ht = lambda_away * ht_ratio
    lam_h_2h = lambda_home * second_ratio
    lam_a_2h = lambda_away * second_ratio

    probs = {
        "H/H": 0.0, "H/D": 0.0, "H/A": 0.0,
        "D/H": 0.0, "D/D": 0.0, "D/A": 0.0,
        "A/H": 0.0, "A/D": 0.0, "A/A": 0.0,
    }

    for ht_h in range(_MAX_GOLS + 1):
        p_hth = _poisson_prob(lam_h_ht, ht_h)
        for ht_a in range(_MAX_GOLS + 1):
            p_hta = _poisson_prob(lam_a_ht, ht_a)
            p_ht = p_hth * p_hta

            if ht_h > ht_a:
                ht_result = "H"
            elif ht_h == ht_a:
                ht_result = "D"
            else:
                ht_result = "A"

            for h2h in range(_MAX_GOLS + 1):
                p_2hh = _poisson_prob(lam_h_2h, h2h)
                for h2a in range(_MAX_GOLS + 1):
                    p_2ha = _poisson_prob(lam_a_2h, h2a)
                    p_joint = p_ht * p_2hh * p_2ha

                    ft_h = ht_h + h2h
                    ft_a = ht_a + h2a

                    if ft_h > ft_a:
                        ft_result = "H"
                    elif ft_h == ft_a:
                        ft_result = "D"
                    else:
                        ft_result = "A"

                    key = f"{ht_result}/{ft_result}"
                    probs[key] += p_joint

    # Converter para percentagem e normalizar
    total = sum(probs.values())
    if total > 0:
        probs = {k: round(v / total * 100, 2) for k, v in probs.items()}

    return probs


_LABEL_MAP = {
    "H/H": "Casa/Casa (1/1)",
    "H/D": "Casa/Empate (1/X)",
    "H/A": "Casa/Fora (1/2)",
    "D/H": "Empate/Casa (X/1)",
    "D/D": "Empate/Empate (X/X)",
    "D/A": "Empate/Fora (X/2)",
    "A/H": "Fora/Casa (2/1)",
    "A/D": "Fora/Empate (2/X)",
    "A/A": "Fora/Fora (2/2)",
}


def analisar_mercado_htft(analysis_packet: dict, odds: dict) -> dict | None:
    """
    Analisa o mercado HT/FT (Half-Time / Full-Time).

    Retorna as 3 combinações mais prováveis acima do threshold de confiança.

    Args:
        analysis_packet: Pacote completo do master_analyzer.
        odds: Dicionário de odds normalizado (chaves htft_* — opcionais).

    Returns:
        dict com 'mercado', 'palpites' e 'dados_suporte', ou None.
    """
    if not analysis_packet or 'error' in analysis_packet:
        return None

    probabilities = analysis_packet.get('calculated_probabilities', {})
    lambda_data = probabilities.get('lambda_goals', {})
    lambda_home = lambda_data.get('lambda_home', 0.0)
    lambda_away = lambda_data.get('lambda_away', 0.0)
    ht_ratio = lambda_data.get('ht_ratio', 0.43)

    if lambda_home == 0.0 and lambda_away == 0.0:
        print("  ⚠️  HT/FT: lambdas não disponíveis, usando probabilidades de resultado")
        match_result = probabilities.get('match_result', {})
        home_win_prob = match_result.get('home_win_prob', 33.3)
        draw_prob = match_result.get('draw_prob', 33.3)
        away_win_prob = match_result.get('away_win_prob', 33.3)
        # Estimativa grosseira com lambdas derivados das probabilidades
        # Usar lambda médio como proxy
        lambda_home = 1.3 if home_win_prob > 40 else (0.9 if home_win_prob < 25 else 1.1)
        lambda_away = 0.9 if away_win_prob < 30 else (1.3 if away_win_prob > 40 else 1.1)

    summary = analysis_packet.get('analysis_summary', {})
    script = summary.get('selected_script')
    reasoning = summary.get('reasoning', '')
    power_home = summary.get('power_score_home', 0)
    power_away = summary.get('power_score_away', 0)
    sev_home = summary.get('injury_severity_home', 'none')
    sev_away = summary.get('injury_severity_away', 'none')
    role_home = summary.get('injury_role_home', 'mixed')
    role_away = summary.get('injury_role_away', 'mixed')

    htft_probs = _htft_probs(lambda_home, lambda_away, ht_ratio)

    print(f"  🕐 HT/FT: λ_casa={lambda_home:.2f} λ_fora={lambda_away:.2f} ht_ratio={ht_ratio:.2f}")
    for k, v in sorted(htft_probs.items(), key=lambda x: -x[1])[:5]:
        print(f"         {k}: {v:.1f}%")

    THRESHOLD = 5.5
    MAX_PICKS = 3

    palpites = []
    for key, prob in sorted(htft_probs.items(), key=lambda x: -x[1]):
        tipo = _LABEL_MAP[key]
        odd_key = f"htft_{key.replace('/', '_').lower()}"
        odd_value = odds.get(odd_key, 0)

        base = convert_probability_to_base_confidence(prob)
        mod_script = apply_tactical_script_modifier(base, f"HT/FT {key}", script)
        mod_injury = apply_injury_confidence_modifier(
            f"HT/FT {key}", sev_home, sev_away, role_home, role_away
        )
        confianca = round(max(1.0, min(10.0, base + mod_script + mod_injury)), 1)

        if confianca < THRESHOLD:
            continue

        palpites.append({
            'mercado': 'HT/FT',
            'tipo': tipo,
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
        print(f"  ✅ HT/FT {key}: prob={prob:.1f}% confiança={confianca:.1f}")

        if len(palpites) >= MAX_PICKS:
            break

    if not palpites:
        print("  ℹ️  HT/FT: nenhum palpite acima do threshold")
        return None

    palpites_sorted = sorted(palpites, key=lambda x: x['confianca'], reverse=True)

    dados_suporte = (
        f"💡 {reasoning}\n\n"
        f"   - <b>Power Score Casa:</b> {power_home}\n"
        f"   - <b>Power Score Fora:</b> {power_away}\n"
        f"   - <b>λ Casa:</b> {lambda_home:.2f} | <b>λ Fora:</b> {lambda_away:.2f}\n"
        f"   - <b>Top 3 combinações HT/FT:</b> "
        + " | ".join(
            f"{_LABEL_MAP[k]}: {v:.1f}%"
            for k, v in sorted(htft_probs.items(), key=lambda x: -x[1])[:3]
        )
    )

    return {
        'mercado': 'HT/FT',
        'palpites': palpites_sorted,
        'dados_suporte': dados_suporte,
    }
