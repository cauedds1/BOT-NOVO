"""
Analisador de Placar Exato (Correct Score) - Phoenix V4.0

Mercado Placar Exato: prever o resultado exato do jogo (ex: 1-0, 2-1, 0-0).

Matemática (Poisson bivariada independente):
  λ_home = gols esperados do mandante (lambda_effective_home do master_analyzer)
  λ_away = gols esperados do visitante (lambda_effective_away do master_analyzer)

  P(Casa=i, Fora=j) = [e^(-λ_home) * λ_home^i / i!] × [e^(-λ_away) * λ_away^j / j!]

Critério de valor (gate obrigatório):
  Para cada placar com odd disponível:
    edge (%) = prob_calculada - 100/odd
  Só avança palpites com edge > 0.  Ordena por edge desc.  Top-3.

Categoria "Outros":
  Massa Poisson fora da grade 0-4×0-4 = prob residual.
  Distribuída proporcionalmente por resultado (Casa/Empate/Fora).
  API lines como "Any Other Home Win/Draw/Away Win" são detectadas e avaliadas.

Calibração de confiança (escala relativa):
  Placares individuais: base_conf = 5.0 + (prob/4.0 - 1) * 2  (baseline 4% = 1/25)
  Categoria "Outros":   base_conf = 5.0 + (prob/10.0 - 1) * 2 (baseline agregada)

λ_home e λ_away do modelo são incluídos em cada palpite para uso em justificativas.
"""

import math
import re
from analysts.confidence_calculator import (
    apply_tactical_script_modifier,
    apply_injury_confidence_modifier,
)

MAX_GOALS = 4
THRESHOLD_CONF = 5.5
MAX_PALPITES = 3
UNIFORM_BASE_PCT = 4.0   # 1/25 placares = 4%
OUTROS_BASE_PCT = 10.0   # baseline para categoria "Outros" (agregada)
POISSON_MASS_MIN = 0.90  # 90% de cobertura mínima esperada


def _poisson_pmf(lam: float, k: int) -> float:
    """P(X = k) onde X ~ Poisson(lam)."""
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def _calcular_matriz_placares(lambda_home: float, lambda_away: float) -> dict:
    """
    Calcula probabilidade (%) de cada placar (home, away) para 0-MAX_GOALS.
    Returns: {(home, away): prob_pct, ...}
    """
    matriz = {}
    for i in range(MAX_GOALS + 1):
        for j in range(MAX_GOALS + 1):
            prob = _poisson_pmf(lambda_home, i) * _poisson_pmf(lambda_away, j)
            matriz[(i, j)] = round(prob * 100, 4)
    return matriz


def _validar_cobertura_poisson(matriz: dict, lambda_home: float, lambda_away: float) -> float:
    """
    Valida que a grade 0-MAX_GOALS cobre >= POISSON_MASS_MIN da massa total.
    Returns: fração de cobertura (0-1)
    """
    total_mass = sum(matriz.values()) / 100.0
    if total_mass < POISSON_MASS_MIN:
        print(
            f"  ⚠️  Placar Exato: Cobertura Poisson {total_mass:.1%} "
            f"< {POISSON_MASS_MIN:.0%} (λ_home={lambda_home:.2f}, λ_away={lambda_away:.2f}) "
            f"— alta expectativa de gols; considere aumentar MAX_GOALS"
        )
    else:
        print(f"  ✅ Placar Exato: Cobertura Poisson {total_mass:.1%} (OK)")
    return total_mass


def _normalizar_chave_placar(raw: str):
    """
    Converte string de placar da API para tupla (home, away).
    Aceita: "1:0", "1-0", "1 0", "Home 1-0", etc.
    Retorna None se não parseable ou se conter 'other'.
    """
    if 'other' in raw.lower():
        return None
    nums = re.findall(r'\d+', raw)
    if len(nums) >= 2:
        return int(nums[0]), int(nums[1])
    return None


def _detectar_categoria_outros(raw: str) -> str | None:
    """
    Detecta se a chave da API é uma linha de "Any Other Score".
    Retorna: 'outros_casa' / 'outros_empate' / 'outros_fora' / 'outros' / None.
    """
    raw_lower = raw.lower()
    if 'other' not in raw_lower and 'outro' not in raw_lower:
        return None
    if 'home' in raw_lower or 'casa' in raw_lower or 'win' in raw_lower and 'away' not in raw_lower:
        return 'outros_casa'
    if 'draw' in raw_lower or 'empate' in raw_lower:
        return 'outros_empate'
    if 'away' in raw_lower or 'fora' in raw_lower or 'visitant' in raw_lower:
        return 'outros_fora'
    return 'outros'


def _calcular_confianca_placar_exato(
    prob_pct: float,
    bet_type: str,
    tactical_script,
    injury_sev_home: str,
    injury_sev_away: str,
    is_outros: bool = False,
) -> tuple:
    """
    Calcula confiança específica para Placar Exato (escala relativa ao baseline).
    Returns: (confianca_final, breakdown_dict)
    """
    base_pct = OUTROS_BASE_PCT if is_outros else UNIFORM_BASE_PCT
    ratio = prob_pct / base_pct
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


def _criar_palpite(
    tipo: str,
    prob_pct: float,
    odd_val: float,
    edge: float,
    final_conf: float,
    breakdown: dict,
    lambda_home: float,
    lambda_away: float,
    home_g=None,
    away_g=None,
) -> dict:
    """Cria um dict de palpite padronizado com λ do modelo incluídos."""
    return {
        'mercado': 'Placar Exato',
        'tipo': tipo,
        'confianca': round(final_conf, 1),
        'odd': odd_val,
        'probabilidade': prob_pct,
        'prob_implicita': round(100.0 / odd_val, 2),
        'edge': round(edge, 2),
        'lambda_home': lambda_home,   # λ real do master_analyzer
        'lambda_away': lambda_away,   # λ real do master_analyzer
        'confidence_breakdown': breakdown,
        'home_goals': home_g,
        'away_goals': away_g,
    }


def analisar_mercado_placar_exato(analysis_packet: dict, odds: dict) -> dict | None:
    """
    Analisa o mercado Placar Exato (Correct Score).

    Fluxo:
      1. Ler λ_home e λ_away do master_analyzer (via lambda_goals dict).
      2. Calcular matriz Poisson 5×5 e validar cobertura.
      3. Calcular prob residual "Outros" para grades 0-4 × 0-4.
      4. Para cada placar/categoria com odd disponível, aplicar gates de valor e confiança.
      5. Retornar top-3 ordenados por edge descendente.

    Args:
        analysis_packet: Pacote completo gerado pelo master_analyzer.
        odds: Dicionário de odds normalizado pelo api_client.

    Returns:
        dict com 'mercado', 'palpites' e 'dados_suporte', ou None se sem dados.
        Cada palpite inclui 'lambda_home' e 'lambda_away' do modelo Poisson.
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

    # --- Coletar odds ---
    # Formato 1: {'placar_exato': {'1:0': 5.5, ...}}   (dict aninhado)
    # Formato 2: {'placar_1_0': 5.5, ...}               (chaves normalizadas)
    odds_placar_dict = odds.get('placar_exato', {})
    odds_por_placar = {}   # {(home, away): odd_float}
    odds_outros = {}       # {'outros_casa': float, ...}

    if odds_placar_dict and isinstance(odds_placar_dict, dict):
        for raw_str, odd_val in odds_placar_dict.items():
            outros_cat = _detectar_categoria_outros(raw_str)
            if outros_cat:
                odds_outros[outros_cat] = odd_val
                continue
            parsed = _normalizar_chave_placar(raw_str)
            if parsed is not None:
                odds_por_placar[parsed] = odd_val
    else:
        for key, val in odds.items():
            m = re.match(r'^placar_(\d+)_(\d+)$', key)
            if m:
                odds_por_placar[(int(m.group(1)), int(m.group(2)))] = val

    if not odds_por_placar and not odds_outros:
        print("  ℹ️  Placar Exato: sem odds de placar exato disponíveis, abortando")
        return None

    print(
        f"  🔢 Placar Exato: λ_home={lambda_home:.2f} | λ_away={lambda_away:.2f} | "
        f"{len(odds_por_placar)} placares + {len(odds_outros)} categorias 'outros'"
    )

    # --- Matriz Poisson ---
    matriz = _calcular_matriz_placares(lambda_home, lambda_away)
    cobertura = _validar_cobertura_poisson(matriz, lambda_home, lambda_away)

    # Prob residual total
    prob_total_grid = sum(matriz.values())
    prob_residual_pct = max(0.0, round(100.0 - prob_total_grid, 4))

    # Proporções por resultado para distribuir residual entre categorias "outros"
    prob_casa_grid = sum(v for (h, a), v in matriz.items() if h > a)
    prob_emp_grid = sum(v for (h, a), v in matriz.items() if h == a)
    prob_fora_grid = sum(v for (h, a), v in matriz.items() if h < a)

    if prob_total_grid > 0:
        ratio_c = prob_casa_grid / prob_total_grid
        ratio_e = prob_emp_grid / prob_total_grid
        ratio_f = prob_fora_grid / prob_total_grid
    else:
        ratio_c = ratio_e = ratio_f = 1 / 3

    outros_probs = {
        'outros_casa': round(prob_residual_pct * ratio_c, 4),
        'outros_empate': round(prob_residual_pct * ratio_e, 4),
        'outros_fora': round(prob_residual_pct * ratio_f, 4),
        'outros': round(prob_residual_pct, 4),
    }

    cat_labels = {
        'outros_casa': 'Qualquer Outro Placar (Casa Vence)',
        'outros_empate': 'Qualquer Outro Placar (Empate)',
        'outros_fora': 'Qualquer Outro Placar (Fora Vence)',
        'outros': 'Qualquer Outro Placar',
    }

    candidatos = []

    # --- Placares individuais ---
    for (home_g, away_g), odd_val in odds_por_placar.items():
        prob_pct = matriz.get((home_g, away_g), 0.0)
        if prob_pct <= 0 or odd_val <= 0:
            continue

        prob_implicita = 100.0 / odd_val
        edge = prob_pct - prob_implicita

        if edge <= 0:
            continue

        if home_g > away_g:
            tipo = f"Placar Exato {home_g}-{away_g} (Casa Vence)"
        elif home_g < away_g:
            tipo = f"Placar Exato {home_g}-{away_g} (Fora Vence)"
        else:
            tipo = f"Placar Exato {home_g}-{away_g} (Empate)"

        final_conf, breakdown = _calcular_confianca_placar_exato(
            prob_pct, tipo, tactical_script, injury_sev_home, injury_sev_away, is_outros=False
        )

        if final_conf < THRESHOLD_CONF:
            print(
                f"  ℹ️  Placar Exato: {tipo} → edge={edge:+.2f}% conf={final_conf:.1f} "
                f"(abaixo do threshold {THRESHOLD_CONF})"
            )
            continue

        candidatos.append(_criar_palpite(
            tipo, prob_pct, odd_val, edge, final_conf, breakdown,
            lambda_home, lambda_away, home_g, away_g
        ))

    # --- Categoria "Outros" ---
    for cat, odd_val in odds_outros.items():
        if odd_val <= 0:
            continue
        prob_pct = outros_probs.get(cat, 0.0)
        if prob_pct <= 0:
            continue

        prob_implicita = 100.0 / odd_val
        edge = prob_pct - prob_implicita

        if edge <= 0:
            continue

        tipo = cat_labels.get(cat, 'Qualquer Outro Placar')
        final_conf, breakdown = _calcular_confianca_placar_exato(
            prob_pct, tipo, tactical_script, injury_sev_home, injury_sev_away, is_outros=True
        )

        if final_conf < THRESHOLD_CONF:
            continue

        candidatos.append(_criar_palpite(
            tipo, prob_pct, odd_val, edge, final_conf, breakdown,
            lambda_home, lambda_away
        ))

    if not candidatos:
        print(f"  ℹ️  Placar Exato: nenhum placar com edge positivo e conf >= {THRESHOLD_CONF}")
        return None

    # Ordenar por edge desc, confiança desc; retornar top-3
    candidatos.sort(key=lambda x: (x['edge'], x['confianca']), reverse=True)
    palpites = candidatos[:MAX_PALPITES]

    for p in palpites:
        print(
            f"  ✅ Placar Exato: {p['tipo']} → prob={p['probabilidade']:.2f}% "
            f"impl={p['prob_implicita']:.2f}% edge={p['edge']:+.2f}% "
            f"conf={p['confianca']:.1f} odd={p['odd']}"
        )

    suporte = (
        f"💡 {reasoning}\n\n"
        f"   - <b>λ Casa (Poisson):</b> {lambda_home:.2f} gols/jogo\n"
        f"   - <b>λ Fora (Poisson):</b> {lambda_away:.2f} gols/jogo\n"
        f"   - <b>Prob. Casa Vence:</b> {prob_casa_grid:.1f}% | "
        f"<b>Empate:</b> {prob_emp_grid:.1f}% | <b>Fora Vence:</b> {prob_fora_grid:.1f}%\n"
        f"   - <b>Outros Placares (residual):</b> {prob_residual_pct:.1f}%\n"
        f"   - <b>Power Score Casa:</b> {power_home} | <b>Power Score Fora:</b> {power_away}\n"
        f"   - <b>Critério:</b> Apenas placares com valor real (prob > prob implícita da odd)"
    )

    return {
        'mercado': 'Placar Exato',
        'palpites': palpites,
        'dados_suporte': suporte,
    }
