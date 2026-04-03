"""
Analisador de Handicap Europeu (European Handicap) - Phoenix V4.0

Handicap Europeu (HE): mercado de 3 resultados (Casa / Empate / Fora) com uma
vantagem/desvantagem de gols adicionada ANTES do jogo.  Diferente do Handicap
Asiático, NÃO há "push" — há sempre um vencedor entre os três desfechos.

Linhas suportadas: -2, -1, 0, +1, +2
  • HE -1 para casa:  casa precisa vencer por ≥2 (net +1+), empate = 1 gol, fora = menos
  • HE +1 para casa:  casa pode empatar ou perder por 1 (net), empate com handicap = vitória fora por 1 gol

Matemática (Poisson bivariada):
  λ_home, λ_away = gols esperados do master_analyzer
  P(casa=i, fora=j) = Poisson(λ_home, i) × Poisson(λ_away, j)

  Para handicap L (linha, e.g. -1):
    result_net = (i + L) - j   ← i gols casa + L ajuste vs j gols fora
    P(casa HE)  = sum_{(i,j): result_net > 0}  P(i,j)
    P(empate HE)= sum_{(i,j): result_net == 0} P(i,j)
    P(fora HE)  = sum_{(i,j): result_net < 0}  P(i,j)

Critério de valor (gate obrigatório):
  edge (%) = prob_calculada - 100/odd  >  0

Odds keys normalizadas (pelo api_client):
  he_casa_{line}, he_empate_{line}, he_fora_{line}
  Exemplos: he_casa_-1, he_empate_0, he_fora_+1
"""

import math
from analysts.confidence_calculator import (
    calculate_final_confidence,
    apply_tactical_script_modifier,
    apply_injury_confidence_modifier,
)

MAX_GOALS = 8
THRESHOLD_CONF = 5.5
SUPPORTED_LINES = [-2, -1, 0, 1, 2]
LINE_LABELS = {
    -2: "HE -2",
    -1: "HE -1",
     0: "HE 0",
     1: "HE +1",
     2: "HE +2",
}


def _poisson_pmf(lam: float, k: int) -> float:
    """P(X = k) onde X ~ Poisson(lam)."""
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def _calcular_probs_he(lambda_home: float, lambda_away: float, linha: int) -> dict:
    """
    Calcula probabilidades (%) para os 3 desfechos do Handicap Europeu.

    Args:
        lambda_home: λ esperado do mandante
        lambda_away: λ esperado do visitante
        linha: ajuste do handicap (−2, −1, 0, +1, +2)
               Positivo = vantagem para o mandante.
               Negativo = o mandante precisa compensar.

    Returns:
        {prob_casa, prob_empate, prob_fora}  — em percentagem (não normalizadas para 100,
        pois a soma Poisson sobre o grid ≤ 100%).
    """
    prob_casa = 0.0
    prob_empate = 0.0
    prob_fora = 0.0

    for i in range(MAX_GOALS + 1):
        p_home = _poisson_pmf(lambda_home, i)
        for j in range(MAX_GOALS + 1):
            p_joint = p_home * _poisson_pmf(lambda_away, j)
            net = (i + linha) - j
            if net > 0:
                prob_casa += p_joint
            elif net == 0:
                prob_empate += p_joint
            else:
                prob_fora += p_joint

    return {
        'prob_casa': round(prob_casa * 100, 4),
        'prob_empate': round(prob_empate * 100, 4),
        'prob_fora': round(prob_fora * 100, 4),
    }


def _linha_to_key(linha: int) -> str:
    """Converte linha inteira para sufixo de chave. e.g. -1 → '-1', 1 → '+1'."""
    if linha > 0:
        return f"+{linha}"
    return str(linha)


def _calcular_confianca_he(
    prob_pct: float,
    bet_type: str,
    tactical_script,
    injury_sev_home: str,
    injury_sev_away: str,
) -> tuple:
    """
    Calcula confiança para Handicap Europeu.

    Usa a pipeline compartilhada (confidence_calculator), com base_conf derivada
    da probabilidade relativa a um baseline uniforme de 33% (3 desfechos iguais).

    Returns:
        (confianca_final, breakdown_dict)
    """
    UNIFORM_BASE_PCT = 33.33
    ratio = prob_pct / UNIFORM_BASE_PCT
    base_conf = 5.0 + (ratio - 1.0) * 3.0
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


def _criar_palpite_he(
    tipo: str,
    prob_pct: float,
    odd_val: float,
    edge: float,
    final_conf: float,
    breakdown: dict,
    lambda_home: float,
    lambda_away: float,
    linha: int,
    desfecho: str,
) -> dict:
    """Cria palpite padronizado para Handicap Europeu."""
    return {
        'mercado': 'Handicap Europeu',
        'tipo': tipo,
        'confianca': round(final_conf, 1),
        'odd': odd_val,
        'probabilidade': prob_pct,
        'prob_implicita': round(100.0 / odd_val, 2),
        'edge': round(edge, 2),
        'lambda_home': lambda_home,
        'lambda_away': lambda_away,
        'linha': linha,
        'desfecho': desfecho,
        'confidence_breakdown': breakdown,
    }


def analisar_mercado_handicap_europeu(analysis_packet: dict, odds: dict) -> dict | None:
    """
    Analisa o mercado Handicap Europeu.

    Fluxo:
      1. Ler λ_home e λ_away do master_analyzer (lambda_goals dict).
      2. Para cada linha suportada com odds disponíveis:
         a. Calcular P(casa HE), P(empate HE), P(fora HE) via Poisson bivariada.
         b. Aplicar gate de valor (edge > 0).
         c. Calcular confiança específica.
      3. Retornar todos os desfechos com valor real (edge > 0 e conf >= THRESHOLD_CONF).

    Args:
        analysis_packet: Pacote completo gerado pelo master_analyzer.
        odds: Dicionário de odds normalizado pelo api_client.

    Returns:
        dict com 'mercado', 'palpites' e 'dados_suporte', ou None se sem dados.
    """
    if not analysis_packet or 'error' in analysis_packet:
        return None

    probabilities = analysis_packet.get('calculated_probabilities', {})
    lambda_goals_data = probabilities.get('lambda_goals', None)

    if not lambda_goals_data or not isinstance(lambda_goals_data, dict):
        print("  ⚠️  Handicap Europeu: lambda_goals não disponível, abortando")
        return None

    lambda_home = lambda_goals_data.get('lambda_home', 0.0)
    lambda_away = lambda_goals_data.get('lambda_away', 0.0)

    if lambda_home <= 0 or lambda_away <= 0:
        print("  ⚠️  Handicap Europeu: lambdas inválidos, abortando")
        return None

    summary = analysis_packet.get('analysis_summary', {})
    tactical_script = summary.get('selected_script', None)
    injury_sev_home = summary.get('injury_severity_home', 'none')
    injury_sev_away = summary.get('injury_severity_away', 'none')
    reasoning = summary.get('reasoning', '')
    power_home = summary.get('power_score_home', 0)
    power_away = summary.get('power_score_away', 0)

    candidatos = []
    linhas_avaliadas = []

    for linha in SUPPORTED_LINES:
        key_suffix = _linha_to_key(linha)
        key_casa = f"he_casa_{key_suffix}"
        key_emp = f"he_empate_{key_suffix}"
        key_fora = f"he_fora_{key_suffix}"

        odd_casa = odds.get(key_casa, 0)
        odd_emp = odds.get(key_emp, 0)
        odd_fora = odds.get(key_fora, 0)

        if not (odd_casa or odd_emp or odd_fora):
            continue

        probs = _calcular_probs_he(lambda_home, lambda_away, linha)
        prob_casa = probs['prob_casa']
        prob_emp = probs['prob_empate']
        prob_fora = probs['prob_fora']

        linhas_avaliadas.append(linha)
        label = LINE_LABELS[linha]

        print(
            f"  📐 HE {label}: P(casa)={prob_casa:.1f}% P(emp)={prob_emp:.1f}% P(fora)={prob_fora:.1f}%"
        )

        desfechos = [
            (f"Handicap Europeu {label} — Casa", prob_casa, odd_casa, 'casa'),
            (f"Handicap Europeu {label} — Empate", prob_emp, odd_emp, 'empate'),
            (f"Handicap Europeu {label} — Fora", prob_fora, odd_fora, 'fora'),
        ]

        for tipo, prob_pct, odd_val, desfecho in desfechos:
            if odd_val <= 0 or prob_pct <= 0:
                continue

            prob_implicita = 100.0 / odd_val
            edge = prob_pct - prob_implicita

            if edge <= 0:
                continue

            final_conf, breakdown = _calcular_confianca_he(
                prob_pct, tipo, tactical_script, injury_sev_home, injury_sev_away
            )

            if final_conf < THRESHOLD_CONF:
                print(
                    f"  ℹ️  HE: {tipo} → edge={edge:+.2f}% conf={final_conf:.1f} "
                    f"(abaixo do threshold {THRESHOLD_CONF})"
                )
                continue

            candidatos.append(_criar_palpite_he(
                tipo, prob_pct, odd_val, edge, final_conf, breakdown,
                lambda_home, lambda_away, linha, desfecho
            ))

    if not candidatos:
        print("  ℹ️  Handicap Europeu: nenhum desfecho com edge positivo e conf >= threshold")
        return None

    candidatos.sort(key=lambda x: (x['edge'], x['confianca']), reverse=True)

    for p in candidatos:
        print(
            f"  ✅ HE: {p['tipo']} → prob={p['probabilidade']:.2f}% "
            f"impl={p['prob_implicita']:.2f}% edge={p['edge']:+.2f}% "
            f"conf={p['confianca']:.1f} odd={p['odd']}"
        )

    linhas_str = ", ".join(LINE_LABELS[l] for l in linhas_avaliadas) if linhas_avaliadas else "nenhuma"
    suporte = (
        f"💡 {reasoning}\n\n"
        f"   - <b>λ Casa (Poisson):</b> {lambda_home:.2f} gols/jogo\n"
        f"   - <b>λ Fora (Poisson):</b> {lambda_away:.2f} gols/jogo\n"
        f"   - <b>Linhas avaliadas:</b> {linhas_str}\n"
        f"   - <b>Power Score Casa:</b> {power_home} | <b>Power Score Fora:</b> {power_away}\n"
        f"   - <b>Critério:</b> Apenas desfechos com valor real (prob > prob implícita da odd)\n"
        f"   - <b>Nota:</b> Handicap Europeu tem 3 desfechos (Casa/Empate/Fora), sem push."
    )

    return {
        'mercado': 'Handicap Europeu',
        'palpites': candidatos,
        'dados_suporte': suporte,
    }
