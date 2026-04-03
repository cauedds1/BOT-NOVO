"""
Analisador de Placar Exato (Correct Score) - Phoenix V4.0

Mercado Placar Exato: prever o resultado exato do jogo (ex: 1-0, 2-1, 0-0).

Matemática (Poisson bivariada independente):
  λ_home = gols esperados do mandante (lambda_effective_home do master_analyzer)
  λ_away = gols esperados do visitante (lambda_effective_away do master_analyzer)

  P(Casa=i, Fora=j) = [e^(-λ_home) * λ_home^i / i!] × [e^(-λ_away) * λ_away^j / j!]

Calibração de confiança para Placar Exato:
  Probabilidades individuais típicas: 4-20% (muito menores que outros mercados).
  Usar escala relativa: comparar cada placar ao valor uniforme equivalente.
  Valor de referência "uniforme" em {0..4}x{0..4} = 1/25 = 4%.

  Fórmula:
    ratio = prob_placar / 4.0           (quanto melhor que aleatório)
    base_conf = 5.0 + (ratio - 1) * 2  (escala 1-10)

  Modificadores:
    + tactical_script  (via apply_tactical_script_modifier com 'over'/'under' adaptado)
    + injury modifier  (via apply_injury_confidence_modifier)

  Threshold: 5.5 — garante que apenas placares com prob >= ~6% aparecem.
  Odds obrigatórias — sem odds não há palpite.

Placares analisados: todos i,j em {0..4} (25 placares)
"""

import math
from analysts.confidence_calculator import (
    apply_tactical_script_modifier,
    apply_injury_confidence_modifier,
)

MAX_GOALS = 4
THRESHOLD = 5.5
UNIFORM_BASE_PCT = 4.0  # 1/25 placares = 4% de referência


def _poisson_pmf(lam: float, k: int) -> float:
    """P(X = k) onde X ~ Poisson(lam)."""
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def _calcular_matriz_placares(lambda_home: float, lambda_away: float) -> dict:
    """
    Calcula probabilidade de cada placar (home_goals, away_goals) para 0-MAX_GOALS.

    Returns:
        dict: {(home, away): prob_pct, ...}
    """
    matriz = {}
    for i in range(MAX_GOALS + 1):
        for j in range(MAX_GOALS + 1):
            prob = _poisson_pmf(lambda_home, i) * _poisson_pmf(lambda_away, j)
            matriz[(i, j)] = round(prob * 100, 2)
    return matriz


def _normalizar_chave_placar(raw: str):
    """
    Converte string de placar da API para tupla (home, away).
    Aceita formatos: "1:0", "1-0", "1 0", "Home 1-0", etc.
    """
    import re
    nums = re.findall(r'\d+', raw)
    if len(nums) >= 2:
        return int(nums[0]), int(nums[1])
    return None


def _calcular_confianca_placar_exato(
    prob_pct: float,
    bet_type: str,
    tactical_script: str | None,
    injury_sev_home: str,
    injury_sev_away: str,
) -> tuple:
    """
    Calcula confiança específica para Placar Exato.

    A escala de confiança é relativa ao baseline uniforme (4% por placar).

    Returns:
        (confianca_final, breakdown_dict)
    """
    ratio = prob_pct / UNIFORM_BASE_PCT
    base_conf = 5.0 + (ratio - 1.0) * 2.0
    base_conf = max(1.0, min(10.0, base_conf))

    mod_script = apply_tactical_script_modifier(base_conf, bet_type, tactical_script)
    mod_injury = apply_injury_confidence_modifier(bet_type, injury_sev_home, injury_sev_away)

    final_conf = max(1.0, min(10.0, base_conf + mod_script + mod_injury))

    breakdown = {
        "probabilidade_base": prob_pct,
        "confianca_base": base_conf,
        "modificador_script": mod_script,
        "modificador_lesoes": mod_injury,
        "confianca_final": final_conf,
    }
    return final_conf, breakdown


def analisar_mercado_placar_exato(analysis_packet: dict, odds: dict) -> dict | None:
    """
    Analisa o mercado Placar Exato (Correct Score).

    Args:
        analysis_packet: Pacote completo gerado pelo master_analyzer.
        odds: Dicionário de odds normalizado pelo api_client
              (chave esperada: 'placar_exato' → dict {str_placar: float}).

    Returns:
        dict com 'mercado', 'palpites' e 'dados_suporte', ou None se sem dados.
    """
    if not analysis_packet or 'error' in analysis_packet:
        return None

    probabilities = analysis_packet.get('calculated_probabilities', {})
    lambda_goals_data = probabilities.get('lambda_goals', None)

    if not lambda_goals_data or not isinstance(lambda_goals_data, dict):
        print("  ⚠️  Placar Exato: lambda_goals não disponível, abortando")
        return None

    lambda_home = lambda_goals_data.get('lambda_home', 0.0)
    lambda_away = lambda_goals_data.get('lambda_away', 0.0)

    if lambda_home <= 0 or lambda_away <= 0:
        print("  ⚠️  Placar Exato: lambdas inválidos, abortando")
        return None

    summary = analysis_packet.get('analysis_summary', {})
    tactical_script = summary.get('selected_script', None)
    injury_sev_home = summary.get('injury_severity_home', 'none')
    injury_sev_away = summary.get('injury_severity_away', 'none')
    reasoning = summary.get('reasoning', '')
    power_home = summary.get('power_score_home', 0)
    power_away = summary.get('power_score_away', 0)

    odds_placar = odds.get('placar_exato', {})
    if not odds_placar:
        print("  ℹ️  Placar Exato: sem odds disponíveis, abortando")
        return None

    print(f"  🔢 Placar Exato: λ_home={lambda_home:.2f} | λ_away={lambda_away:.2f}")

    matriz = _calcular_matriz_placares(lambda_home, lambda_away)

    odds_por_placar = {}
    for raw_str, odd_val in odds_placar.items():
        parsed = _normalizar_chave_placar(raw_str)
        if parsed is not None:
            odds_por_placar[parsed] = (odd_val, raw_str)

    if not odds_por_placar:
        print("  ℹ️  Placar Exato: odds encontradas mas nenhuma parseable, abortando")
        return None

    candidatos = []
    for (home_g, away_g), (odd_val, raw_str) in odds_por_placar.items():
        prob_pct = matriz.get((home_g, away_g), 0.0)
        if prob_pct <= 0:
            continue

        if home_g > away_g:
            tipo = f"Placar Exato {home_g}-{away_g} (Casa Vence)"
        elif home_g < away_g:
            tipo = f"Placar Exato {home_g}-{away_g} (Fora Vence)"
        else:
            tipo = f"Placar Exato {home_g}-{away_g} (Empate)"

        final_conf, breakdown = _calcular_confianca_placar_exato(
            prob_pct=prob_pct,
            bet_type=tipo,
            tactical_script=tactical_script,
            injury_sev_home=injury_sev_home,
            injury_sev_away=injury_sev_away,
        )

        candidatos.append({
            'mercado': 'Placar Exato',
            'tipo': tipo,
            'confianca': round(final_conf, 1),
            'odd': odd_val,
            'probabilidade': prob_pct,
            'confidence_breakdown': breakdown,
            'home_goals': home_g,
            'away_goals': away_g,
        })

    if not candidatos:
        print("  ℹ️  Placar Exato: nenhum candidato com odds e prob calculáveis")
        return None

    candidatos.sort(key=lambda x: x['confianca'], reverse=True)

    aprovados = [c for c in candidatos if c['confianca'] >= THRESHOLD]

    if not aprovados:
        print(f"  ℹ️  Placar Exato: nenhum placar acima do threshold {THRESHOLD}")
        return None

    palpites = aprovados[:5]

    for p in palpites:
        print(
            f"  ✅ Placar Exato: {p['tipo']} → prob={p['probabilidade']}% "
            f"confiança={p['confianca']:.1f} odd={p['odd']}"
        )

    prob_casa = sum(v for (h, a), v in matriz.items() if h > a)
    prob_empate = sum(v for (h, a), v in matriz.items() if h == a)
    prob_fora = sum(v for (h, a), v in matriz.items() if h < a)

    suporte = (
        f"💡 {reasoning}\n\n"
        f"   - <b>λ Casa (Poisson):</b> {lambda_home:.2f} gols/jogo\n"
        f"   - <b>λ Fora (Poisson):</b> {lambda_away:.2f} gols/jogo\n"
        f"   - <b>Prob. Casa Vence:</b> {prob_casa:.1f}% | "
        f"<b>Empate:</b> {prob_empate:.1f}% | <b>Fora Vence:</b> {prob_fora:.1f}%\n"
        f"   - <b>Power Score Casa:</b> {power_home} | <b>Power Score Fora:</b> {power_away}"
    )

    return {
        'mercado': 'Placar Exato',
        'palpites': palpites,
        'dados_suporte': suporte,
    }
