"""
Analisador de Placar Exato (Correct Score) - Phoenix V4.0

Mercado Placar Exato: prever o resultado exato do jogo (ex: 1-0, 2-1, 0-0).

Matemática (Poisson bivariada independente):
  λ_home = gols esperados do mandante (lambda_effective_home do master_analyzer)
  λ_away = gols esperados do visitante (lambda_effective_away do master_analyzer)

  P(Casa=i, Fora=j) = [e^(-λ_home) * λ_home^i / i!] × [e^(-λ_away) * λ_away^j / j!]

Critério de valor (gate obrigatório):
  Para cada placar com odd disponível calcula:
    prob_calculada (%) via Poisson
    prob_implícita (%) = 100 / odd
    edge (%) = prob_calculada - prob_implícita

  Só avança palpites com edge > 0 (valor real identificado pelo modelo).
  Palpites são ordenados por edge descendente; retorna top-3.

Calibração de confiança:
  Probs individuais de Placar Exato são naturalmente baixas (4-20%).
  Usar escala relativa ao baseline uniforme de 25 placares (1/25 = 4%).
    ratio = prob_calculada / 4.0
    base_conf = 5.0 + (ratio - 1.0) * 2.0    [capped 1–10]
  Modificadores: tactical_script + injury (via confidence_calculator).

Validação do modelo Poisson:
  Massa truncada em {0..MAX_GOALS}×{0..MAX_GOALS} deve cobrir >= 90% da probabilidade total.
  Se cobertura < 90% → aviso de log (modelo pode subestimar placares altos).

Placares analisados: todos i,j em {0..4} (25 placares)
Limite de output: top-3 palpites com valor real (edge > 0).
Odds obrigatórias — sem odds não há palpite.
"""

import math
from analysts.confidence_calculator import (
    apply_tactical_script_modifier,
    apply_injury_confidence_modifier,
)

MAX_GOALS = 4
THRESHOLD_CONF = 5.5
MAX_PALPITES = 3
UNIFORM_BASE_PCT = 4.0  # 1/25 placares = 4%
POISSON_MASS_MIN = 0.90  # 90% de cobertura mínima esperada


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
            matriz[(i, j)] = round(prob * 100, 4)
    return matriz


def _validar_cobertura_poisson(matriz: dict, lambda_home: float, lambda_away: float):
    """Valida que a grade 0-MAX_GOALS cobre >= POISSON_MASS_MIN da massa total."""
    total_mass = sum(matriz.values()) / 100.0
    if total_mass < POISSON_MASS_MIN:
        print(
            f"  ⚠️  Placar Exato: Cobertura Poisson {total_mass:.1%} "
            f"< {POISSON_MASS_MIN:.0%} (λ_home={lambda_home:.2f}, λ_away={lambda_away:.2f}) "
            f"— considere aumentar MAX_GOALS para jogos de alta expectativa de gols"
        )
    else:
        print(f"  ✅ Placar Exato: Cobertura Poisson {total_mass:.1%} (OK)")


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
    tactical_script,
    injury_sev_home: str,
    injury_sev_away: str,
) -> tuple:
    """
    Calcula confiança específica para Placar Exato (escala relativa).

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

    Fluxo:
      1. Ler λ_home e λ_away do master_analyzer.
      2. Calcular matriz Poisson 5×5.
      3. Validar cobertura (>= 90%).
      4. Para cada placar com odd disponível:
           a. Calcular prob_calculada (Poisson)
           b. Calcular prob_implícita = 100/odd
           c. Calcular edge = prob_calculada - prob_implícita
           d. Gate de valor: só avança se edge > 0
           e. Calcular confiança via escala relativa
           f. Gate de confiança: só avança se >= THRESHOLD_CONF
      5. Ordenar por edge descendente.
      6. Retornar top-3 picks.

    Args:
        analysis_packet: Pacote completo gerado pelo master_analyzer.
        odds: Dicionário de odds normalizado pelo api_client
              (chave 'placar_exato' → dict {str_placar: float}
               OU chaves individuais 'placar_X_Y').

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

    # Suporte a dois formatos:
    # 1. {'placar_exato': {'1:0': 5.5, ...}}  (dict aninhado)
    # 2. {'placar_1_0': 5.5, ...}             (chaves individuais normalizadas)
    odds_placar_dict = odds.get('placar_exato', {})
    odds_por_placar = {}  # {(home, away): odd_float}

    if odds_placar_dict and isinstance(odds_placar_dict, dict):
        for raw_str, odd_val in odds_placar_dict.items():
            parsed = _normalizar_chave_placar(raw_str)
            if parsed is not None:
                odds_por_placar[parsed] = odd_val
    else:
        # Tentar chaves individuais placar_X_Y
        import re
        for key, val in odds.items():
            m = re.match(r'^placar_(\d+)_(\d+)$', key)
            if m:
                odds_por_placar[(int(m.group(1)), int(m.group(2)))] = val

    if not odds_por_placar:
        print("  ℹ️  Placar Exato: sem odds de placar exato disponíveis, abortando")
        return None

    print(f"  🔢 Placar Exato: λ_home={lambda_home:.2f} | λ_away={lambda_away:.2f} | {len(odds_por_placar)} placares com odds")

    # Calcular matriz Poisson
    matriz = _calcular_matriz_placares(lambda_home, lambda_away)

    # Validar cobertura
    _validar_cobertura_poisson(matriz, lambda_home, lambda_away)

    # Calcular candidatos com gate de valor
    candidatos = []
    for (home_g, away_g), odd_val in odds_por_placar.items():
        prob_pct = matriz.get((home_g, away_g), 0.0)
        if prob_pct <= 0 or odd_val <= 0:
            continue

        # Gate de valor: prob calculada > prob implícita
        prob_implicita = 100.0 / odd_val
        edge = prob_pct - prob_implicita

        if edge <= 0:
            continue  # Sem valor identificado pelo modelo

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

        # Gate de confiança
        if final_conf < THRESHOLD_CONF:
            print(
                f"  ℹ️  Placar Exato: {tipo} → prob={prob_pct:.2f}% edge={edge:+.2f}% "
                f"conf={final_conf:.1f} (abaixo do threshold {THRESHOLD_CONF})"
            )
            continue

        candidatos.append({
            'mercado': 'Placar Exato',
            'tipo': tipo,
            'confianca': round(final_conf, 1),
            'odd': odd_val,
            'probabilidade': prob_pct,
            'prob_implicita': round(prob_implicita, 2),
            'edge': round(edge, 2),
            'confidence_breakdown': breakdown,
            'home_goals': home_g,
            'away_goals': away_g,
        })

    if not candidatos:
        print(f"  ℹ️  Placar Exato: nenhum placar com edge positivo e conf >= {THRESHOLD_CONF}")
        return None

    # Ordenar por edge descendente (maior valor primeiro), depois confiança
    candidatos.sort(key=lambda x: (x['edge'], x['confianca']), reverse=True)

    # Limitar a top-3
    palpites = candidatos[:MAX_PALPITES]

    for p in palpites:
        print(
            f"  ✅ Placar Exato: {p['tipo']} → prob={p['probabilidade']:.2f}% "
            f"impl={p['prob_implicita']:.2f}% edge={p['edge']:+.2f}% "
            f"conf={p['confianca']:.1f} odd={p['odd']}"
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
        f"   - <b>Power Score Casa:</b> {power_home} | <b>Power Score Fora:</b> {power_away}\n"
        f"   - <b>Critério:</b> Apenas placares com valor real (prob > prob implícita da odd)"
    )

    return {
        'mercado': 'Placar Exato',
        'palpites': palpites,
        'dados_suporte': suporte,
    }
