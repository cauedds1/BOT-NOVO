"""
Analisador de Primeiro a Marcar (First Goal - Team) - Phoenix V4.0

Mercado: qual EQUIPE marcará o primeiro gol do jogo, ou se terminará sem gols.
Três desfechos: Casa / Fora / Nenhum (No Goal)

Matemática:
  λ_home, λ_away = gols esperados do master_analyzer
  P(nenhum) = P(0 gols no jogo) = e^(-λ_total)
  P(casa marca primeiro) ≈ λ_home / (λ_home + λ_away) × (1 - P(nenhum))
  P(fora marca primeiro) ≈ λ_away / (λ_home + λ_away) × (1 - P(nenhum))

  Em jogos Poisson, o processo de chegada de gols é memoryless. Dado que um gol
  ocorre, a probabilidade de ser do mandante é proporcional a λ_home / (λ_home + λ_away).
  Esse resultado é exato sob o modelo de Poisson independente.

Ajustes aplicados:
  • Vantagem de jogar em casa (+5% em P(casa)) — campo, torcida, rotina
  • Momento ofensivo (form_string dos últimos 5 jogos) — time em chamas > time em crise
  • Perfil tático do script selecionado:
      DOMINIO_CASA / TIME_EM_CHAMAS_CASA → bônus casa
      DOMINIO_VISITANTE / TIME_EM_CHAMAS_FORA → bônus fora
      GIANT_VS_MINNOW → casa domina (se casa for favorita) ou fora (se visitante for favorita)
      CAGEY / TIGHT_LOW_SCORING / JOGO_DE_COMPADRES → aumenta P(nenhum)

Odds keys normalizadas (pelo api_client):
  primeiro_marcador_casa, primeiro_marcador_fora, primeiro_marcador_nenhum

Invariante:
  P(casa) + P(fora) + P(nenhum) ≈ 100% (verificado por validação interna)
"""

import math
from analysts.confidence_calculator import (
    convert_probability_to_base_confidence,
    apply_tactical_script_modifier,
    apply_injury_confidence_modifier,
)

THRESHOLD_CONF = 5.5
HOME_FIELD_BONUS = 0.05


def _poisson_zero(lam: float) -> float:
    """P(X = 0) para X ~ Poisson(λ)."""
    if lam <= 0:
        return 1.0
    return math.exp(-lam)


def _calcular_probs_primeiro_marcador(
    lambda_home: float,
    lambda_away: float,
    momento_home: float = 50.0,
    momento_away: float = 50.0,
    tactical_script: str = None,
) -> dict:
    """
    Calcula as probabilidades brutas de Primeiro a Marcar para cada desfecho.

    Args:
        lambda_home: λ esperado do mandante
        lambda_away: λ esperado do visitante
        momento_home: Momento score do mandante (0-100)
        momento_away: Momento score do visitante (0-100)
        tactical_script: Script tático selecionado pelo master_analyzer

    Returns:
        {
            'prob_casa': float (%),
            'prob_fora': float (%),
            'prob_nenhum': float (%),
        }
    """
    lambda_total = lambda_home + lambda_away

    # Probabilidade de nenhum gol (jogo termina 0-0)
    prob_nenhum = _poisson_zero(lambda_total) * 100.0

    # Probabilidade de um gol ocorrer
    prob_algum_gol = 100.0 - prob_nenhum

    # Dado que há gol, fracionar entre casa e fora por proporção λ
    if lambda_total > 0:
        frac_casa = lambda_home / lambda_total
        frac_fora = lambda_away / lambda_total
    else:
        frac_casa = 0.5
        frac_fora = 0.5

    prob_casa_raw = frac_casa * prob_algum_gol
    prob_fora_raw = frac_fora * prob_algum_gol

    # Ajuste 1: Vantagem de campo (mandante)
    home_bonus = HOME_FIELD_BONUS * prob_algum_gol
    prob_casa_raw += home_bonus
    prob_fora_raw -= home_bonus

    # Ajuste 2: Momento ofensivo relativo
    momento_diff = (momento_home - momento_away) / 100.0
    momento_adj = momento_diff * 0.03 * prob_algum_gol
    prob_casa_raw += momento_adj
    prob_fora_raw -= momento_adj

    # Ajuste 3: Script tático
    script_adj = 0.0
    nenhum_adj = 0.0
    if tactical_script:
        OFFENSIVO_CASA = {"SCRIPT_DOMINIO_CASA", "SCRIPT_TIME_EM_CHAMAS_CASA"}
        OFFENSIVO_FORA = {"SCRIPT_DOMINIO_VISITANTE", "SCRIPT_TIME_EM_CHAMAS_FORA"}
        BAIXO_GOL = {
            "SCRIPT_CAGEY_TACTICAL_AFFAIR",
            "SCRIPT_TIGHT_LOW_SCORING",
            "SCRIPT_JOGO_DE_COMPADRES",
            "SCRIPT_RELEGATION_BATTLE",
        }
        if tactical_script in OFFENSIVO_CASA:
            script_adj = 0.04 * prob_algum_gol
            prob_casa_raw += script_adj
            prob_fora_raw -= script_adj
        elif tactical_script in OFFENSIVO_FORA:
            script_adj = 0.04 * prob_algum_gol
            prob_fora_raw += script_adj
            prob_casa_raw -= script_adj
        elif tactical_script in BAIXO_GOL:
            nenhum_adj = 3.0
            prob_nenhum = min(prob_nenhum + nenhum_adj, 50.0)
            prob_algum_gol_adj = 100.0 - prob_nenhum
            scale = prob_algum_gol_adj / max(prob_algum_gol, 0.001)
            prob_casa_raw *= scale
            prob_fora_raw *= scale

    # Garantir não-negatividade
    prob_casa_raw = max(prob_casa_raw, 0.0)
    prob_fora_raw = max(prob_fora_raw, 0.0)
    prob_nenhum = max(prob_nenhum, 0.0)

    # Re-normalizar para soma = 100%
    total = prob_casa_raw + prob_fora_raw + prob_nenhum
    if total > 0:
        scale = 100.0 / total
        prob_casa_raw *= scale
        prob_fora_raw *= scale
        prob_nenhum *= scale

    return {
        'prob_casa': round(prob_casa_raw, 2),
        'prob_fora': round(prob_fora_raw, 2),
        'prob_nenhum': round(prob_nenhum, 2),
    }


def analisar_mercado_primeiro_a_marcar(analysis_packet: dict, odds: dict):
    """
    Analisador de Primeiro a Marcar (Equipe) — Phoenix V4.0.

    Args:
        analysis_packet: Pacote completo gerado pelo master_analyzer
        odds: Dicionário normalizado com odds do jogo

    Returns:
        dict: {'mercado', 'palpites', 'dados_suporte'} ou None
    """
    if not analysis_packet or 'error' in analysis_packet:
        return None

    # Extrair lambdas do master_analyzer
    calc_probs = analysis_packet.get('calculated_probabilities', {})
    lambda_goals_data = calc_probs.get('lambda_goals', {})

    if isinstance(lambda_goals_data, dict):
        lambda_home = lambda_goals_data.get('lambda_home', 0.0)
        lambda_away = lambda_goals_data.get('lambda_away', 0.0)
    else:
        lambda_home = lambda_away = 0.0

    if lambda_home <= 0 or lambda_away <= 0:
        print("  ⚠️  Primeiro a Marcar: lambdas inválidos, abortando")
        return None

    # Verificar se há pelo menos uma odd disponível
    odd_casa = odds.get('primeiro_marcador_casa', 0)
    odd_fora = odds.get('primeiro_marcador_fora', 0)
    odd_nenhum = odds.get('primeiro_marcador_nenhum', 0)

    if not (odd_casa or odd_fora or odd_nenhum):
        print("  ℹ️  Primeiro a Marcar: sem odds disponíveis — pulando")
        return None

    # Extrair contexto do summary
    summary = analysis_packet.get('analysis_summary', {})
    tactical_script = summary.get('selected_script', None)
    injury_sev_home = summary.get('injury_severity_home', 'none')
    injury_sev_away = summary.get('injury_severity_away', 'none')
    momento_home = summary.get('moment_score_home', 50.0)
    momento_away = summary.get('moment_score_away', 50.0)

    # Calcular probabilidades brutas
    probs = _calcular_probs_primeiro_marcador(
        lambda_home=lambda_home,
        lambda_away=lambda_away,
        momento_home=float(momento_home),
        momento_away=float(momento_away),
        tactical_script=tactical_script,
    )
    prob_casa = probs['prob_casa']
    prob_fora = probs['prob_fora']
    prob_nenhum = probs['prob_nenhum']

    # Validação: soma deve ser ≈ 100%
    prob_sum = prob_casa + prob_fora + prob_nenhum
    if prob_sum > 100.5:
        print(
            f"  ❌ PM: BUG — soma {prob_sum:.2f}% > 100% "
            f"(λ_home={lambda_home:.2f}, λ_away={lambda_away:.2f}) — verifique o modelo"
        )
    elif prob_sum < 98.0:
        print(
            f"  ⚠️  PM: Cobertura baixa {prob_sum:.2f}% — verifique o ajuste de momento/script"
        )
    else:
        print(
            f"  ✅ PM: Cobertura {prob_sum:.2f}% OK "
            f"P(casa)={prob_casa:.1f}% P(fora)={prob_fora:.1f}% P(nenhum)={prob_nenhum:.1f}%"
        )

    print(
        f"  📐 Primeiro Marcador: λ_home={lambda_home:.2f} λ_away={lambda_away:.2f} "
        f"script={tactical_script}"
    )

    candidatos = []

    desfechos = [
        ("Primeiro a Marcar — Casa", prob_casa, odd_casa, 'casa'),
        ("Primeiro a Marcar — Fora", prob_fora, odd_fora, 'fora'),
        ("Nenhum (Sem Gols)", prob_nenhum, odd_nenhum, 'nenhum'),
    ]

    for nome, prob, odd, lado in desfechos:
        if not odd or odd <= 1.0:
            continue

        # Gate obrigatório: edge = prob - 100/odd > 0
        prob_implicita = 100.0 / odd
        edge = prob - prob_implicita
        if edge <= 0:
            print(f"    ⛔ {nome}: sem valor (edge={edge:.2f}%)")
            continue

        print(f"    ✅ {nome}: edge=+{edge:.2f}% (prob={prob:.1f}% vs impl={prob_implicita:.1f}%)")

        # Confiança
        base_conf = convert_probability_to_base_confidence(prob)
        mod_script = apply_tactical_script_modifier(base_conf, f"primeiro_marcador_{lado}", tactical_script)
        mod_injury = apply_injury_confidence_modifier(f"primeiro_marcador_{lado}", injury_sev_home, injury_sev_away)
        confianca = max(1.0, min(10.0, base_conf + mod_script + mod_injury))

        if confianca < THRESHOLD_CONF:
            print(f"    ⛔ {nome}: confiança insuficiente ({confianca:.1f} < {THRESHOLD_CONF})")
            continue

        candidatos.append({
            'mercado': 'Primeiro a Marcar',
            'tipo': nome,
            'confianca': round(confianca, 1),
            'odd': odd,
            'probabilidade': round(prob, 2),
            'prob_implicita': round(prob_implicita, 2),
            'edge': round(edge, 2),
            'lambda_home': round(lambda_home, 3),
            'lambda_away': round(lambda_away, 3),
        })

    if not candidatos:
        print("  ℹ️  Primeiro a Marcar: sem candidatos com valor e confiança suficientes")
        return None

    candidatos.sort(key=lambda x: x['confianca'], reverse=True)

    lambda_total = lambda_home + lambda_away
    dados_suporte = (
        f"λ_casa={lambda_home:.2f} | λ_fora={lambda_away:.2f} | λ_total={lambda_total:.2f} | "
        f"P(casa)={prob_casa:.1f}% | P(fora)={prob_fora:.1f}% | P(nenhum)={prob_nenhum:.1f}%"
    )

    print(f"  🎯 Primeiro a Marcar: {len(candidatos)} picks com valor e confiança suficientes")

    return {
        'mercado': 'Primeiro a Marcar',
        'palpites': candidatos,
        'dados_suporte': dados_suporte,
        'script': tactical_script,
    }
