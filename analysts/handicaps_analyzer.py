# analysts/handicaps_analyzer.py
"""
PHOENIX V4.0 - HANDICAPS ANALYZER (ASIAN HANDICAP REAL)
========================================================
Suporte a linhas fracionadas (0.25, 0.75) com regras de push/half-win/half-loss.

ARQUITETURA:
1. Calcular probabilidades Poisson de vitória por margem para cada time
2. Para linhas inteiras (.0, .5): resultado simples win/push/loss
3. Para linhas de quarto-bola (.25, .75): dividir aposta em duas metades
   e calcular retorno esperado ponderado
4. Detectar value bets (nossa prob > prob implícita da odd + 5%)
5. Chamar calculate_final_confidence para confiança final

REGRAS DE ASIAN HANDICAP:
- Linha 0.0 (draw no bet): push se empate, win/loss se resultado decisivo
- Linha -0.5: vence se casa ganhar por 1+; perde se empatar ou perder
- Linha -0.25: meia aposta em 0.0, meia em -0.5
  → Casa vence por 1+: win total
  → Empate: perde meia aposta (push na 0.0, loss na -0.5)
  → Casa perde: loss total
- Linha -0.75: meia em -0.5, meia em -1.0
  → Casa vence por 2+: win total
  → Casa vence por 1: meia win (win na -0.5, push na -1.0)
  → Empate ou perde: loss total
"""

import math
from analysts.confidence_calculator import calculate_final_confidence, detect_value_bet


def _poisson_prob(lam: float, k: int) -> float:
    """P(X = k) para distribuição de Poisson com média lam."""
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def calcular_distribuicao_margem(lambda_home: float, lambda_away: float, max_gols: int = 8) -> dict:
    """
    Calcula probabilidades de cada margem de resultado via convolução de Poisson independentes.

    Returns:
        dict com chaves:
          'home_win_by_N' para N=1..max_gols
          'draw'
          'away_win_by_N' para N=1..max_gols
    """
    dist = {}
    p_draw = 0.0
    home_wins = {}
    away_wins = {}

    for gh in range(max_gols + 1):
        ph = _poisson_prob(lambda_home, gh)
        for ga in range(max_gols + 1):
            pa = _poisson_prob(lambda_away, ga)
            prob = ph * pa
            margin = gh - ga
            if margin == 0:
                p_draw += prob
            elif margin > 0:
                home_wins[margin] = home_wins.get(margin, 0) + prob
            else:
                away_wins[-margin] = away_wins.get(-margin, 0) + prob

    dist['draw'] = p_draw
    for n in range(1, max_gols + 1):
        dist[f'home_win_by_{n}'] = home_wins.get(n, 0)
        dist[f'away_win_by_{n}'] = away_wins.get(n, 0)

    # Probabilidades cumulativas acima de N
    dist['home_win_by_1_plus'] = sum(home_wins.get(n, 0) for n in range(1, max_gols + 1))
    dist['home_win_by_2_plus'] = sum(home_wins.get(n, 0) for n in range(2, max_gols + 1))
    dist['home_win_by_3_plus'] = sum(home_wins.get(n, 0) for n in range(3, max_gols + 1))
    dist['away_win_by_1_plus'] = sum(away_wins.get(n, 0) for n in range(1, max_gols + 1))
    dist['away_win_by_2_plus'] = sum(away_wins.get(n, 0) for n in range(2, max_gols + 1))

    return dist


def prob_asian_handicap_casa(linha: float, dist: dict) -> float:
    """
    Calcula a probabilidade de "ganhar" a aposta no Asian Handicap pelo time da casa.
    Retorna probabilidade em % (0-100), considerando half-win como 0.5 de lucro.

    Para linhas de quarto-bola (.25, .75), retorna probabilidade de lucro equivalente:
      P(win total) * 1.0 + P(half-win) * 0.5  (normalizado → % probabilidade efectiva de ganho)

    Args:
        linha: linha do handicap para a casa (ex: -1.0, -0.25, +0.5, -0.75)
        dist: dicionário de distribuição de margens

    Returns:
        float: probabilidade efectiva em % de ganhar a aposta
    """
    d = dist['draw']
    h1 = dist.get('home_win_by_1_plus', 0)
    h2 = dist.get('home_win_by_2_plus', 0)
    h3 = dist.get('home_win_by_3_plus', 0)
    hw1 = dist.get('home_win_by_1', 0)
    hw2 = dist.get('home_win_by_2', 0)
    a1 = dist.get('away_win_by_1_plus', 0)

    if linha == 0.0:
        # Draw no bet: push se empate
        # P(lucro) = P(casa vence) | P(push) = d | P(loss) = P(fora vence)
        # Para efeitos de probability efectiva: exclui push
        return h1 / (1.0 - d) * 100 if (1.0 - d) > 0 else 50.0

    elif linha == -0.25:
        # Meia aposta em 0.0, meia em -0.5
        # Win total se casa vence por 1+
        # Perda de metade se empate (push na 0.0, loss na -0.5)
        p_win = h1
        p_half_loss = d
        p_loss = a1
        return round((p_win + p_half_loss * 0.5) * 100, 2)

    elif linha == -0.5:
        return round(h1 * 100, 2)

    elif linha == -0.75:
        # Meia em -0.5, meia em -1.0
        # Win total se casa vence por 2+
        # Half-win se casa vence por exatamente 1 (win na -0.5, push na -1.0)
        p_win = h2
        p_half_win = hw1
        return round((p_win + p_half_win * 0.5) * 100, 2)

    elif linha == -1.0:
        return round(h2 * 100, 2)

    elif linha == -1.25:
        # Meia em -1.0, meia em -1.5
        # Win total se casa vence por 2+
        # Half-loss se casa vence por exatamente 1
        p_win = h2
        p_half_loss = hw1
        return round((p_win + p_half_loss * 0.5) * 100, 2)

    elif linha == -1.5:
        return round(h3 * 100, 2)

    elif linha == -1.75:
        p_win = h3
        p_half_win = hw2
        return round((p_win + p_half_win * 0.5) * 100, 2)

    elif linha == -2.0:
        return round(h3 * 100, 2)

    elif linha == 0.25:
        # Casa +0.25: win se empatar ou ganhar; half-win se fora vencer por 1
        p_win = h1 + d
        p_half_win = dist.get('away_win_by_1', 0)
        return round((p_win + p_half_win * 0.5) * 100, 2)

    elif linha == 0.5:
        return round((h1 + d) * 100, 2)

    elif linha == 0.75:
        # Casa +0.75: win se ganhar ou empatar ou fora vencer por 1; half-win se fora vencer por 2
        p_win = h1 + d + dist.get('away_win_by_1', 0)
        p_half_win = dist.get('away_win_by_2', 0)
        return round((p_win + p_half_win * 0.5) * 100, 2)

    elif linha == 1.0:
        return round((h1 + d + dist.get('away_win_by_1', 0)) * 100, 2)

    elif linha == 1.25:
        p_win = h1 + d + dist.get('away_win_by_1', 0)
        p_half_win = dist.get('away_win_by_2', 0)
        return round((p_win + p_half_win * 0.5) * 100, 2)

    elif linha == 1.5:
        return round((h1 + d + dist.get('away_win_by_1_plus', 0) - dist.get('away_win_by_2_plus', 0) + dist.get('away_win_by_1_plus', 0)) * 100, 2)

    else:
        # Fallback genérico
        if linha < 0:
            return round(h2 * 100, 2)
        else:
            return round((h1 + d) * 100, 2)


def calcular_superioridade(stats_casa, stats_fora, pos_casa="N/A", pos_fora="N/A"):
    """
    Calcula score de superioridade contextual (-10 a +10).
    > 0 = Casa superior; < 0 = Fora superior; ~0 = Equilibrado
    """
    gols_casa_marcados = stats_casa['casa'].get('gols_marcados', 0)
    gols_casa_sofridos = stats_casa['casa'].get('gols_sofridos', 0)
    gols_fora_marcados = stats_fora['fora'].get('gols_marcados', 0)
    gols_fora_sofridos = stats_fora['fora'].get('gols_sofridos', 0)

    forca_casa = gols_casa_marcados - gols_casa_sofridos
    forca_fora = gols_fora_marcados - gols_fora_sofridos
    diferenca_forca = forca_casa - forca_fora

    superioridade = 0.0

    if diferenca_forca >= 2.5:
        superioridade += 4.0
    elif diferenca_forca >= 1.5:
        superioridade += 3.0
    elif diferenca_forca >= 0.8:
        superioridade += 2.0
    elif diferenca_forca >= 0.3:
        superioridade += 1.0
    elif diferenca_forca <= -2.5:
        superioridade -= 4.0
    elif diferenca_forca <= -1.5:
        superioridade -= 3.0
    elif diferenca_forca <= -0.8:
        superioridade -= 2.0
    elif diferenca_forca <= -0.3:
        superioridade -= 1.0

    if pos_casa != "N/A" and pos_fora != "N/A":
        try:
            diferenca_posicao = int(pos_fora) - int(pos_casa)
            if diferenca_posicao >= 10:
                superioridade += 3.0
            elif diferenca_posicao >= 6:
                superioridade += 2.0
            elif diferenca_posicao >= 3:
                superioridade += 1.0
            elif diferenca_posicao <= -10:
                superioridade -= 3.0
            elif diferenca_posicao <= -6:
                superioridade -= 2.0
            elif diferenca_posicao <= -3:
                superioridade -= 1.0
        except (ValueError, TypeError):
            pass

    if gols_casa_marcados >= 2.0 and gols_fora_sofridos >= 1.5:
        superioridade += 1.5
    if gols_fora_marcados >= 2.0 and gols_casa_sofridos >= 1.5:
        superioridade -= 1.5

    cantos_casa = stats_casa['casa'].get('cantos_feitos', 0)
    cantos_fora = stats_fora['fora'].get('cantos_feitos', 0)
    diferenca_cantos = cantos_casa - cantos_fora

    if diferenca_cantos >= 3.0:
        superioridade += 0.5
    elif diferenca_cantos <= -3.0:
        superioridade -= 0.5

    return superioridade


def _linha_label(linha: float, team: str) -> str:
    """Formata a linha do handicap com sinal correto para o label."""
    if linha == 0.0:
        return f"AH {team} 0"
    sign = "+" if linha > 0 else ""
    frac = linha % 1
    if frac == 0:
        return f"AH {team} {sign}{int(linha)}"
    elif abs(frac) == 0.5:
        return f"AH {team} {sign}{linha:g}"
    elif abs(frac) == 0.25:
        base = int(linha)
        return f"AH {team} {sign}{base}/{'+' if linha > 0 else ''}{base + (1 if linha > 0 else -1)*1}".replace("+-", "-").replace("+0", "0")
    elif abs(frac) == 0.75:
        base = int(linha)
        alt = base + (1 if linha > 0 else -1)
        return f"AH {team} {sign}{base}/{sign}{alt}"
    return f"AH {team} {sign}{linha:g}"


def analisar_mercado_handicaps(stats_casa, stats_fora, odds, classificacao=None, pos_casa="N/A", pos_fora="N/A", script_name=None, analysis_packet=None):
    """
    Analisa handicaps asiáticos usando probabilidades Poisson reais com suporte a linhas fracionadas.

    TASK 7: Quando analysis_packet está disponível, usa lambdas já ajustados por desfalques
    confirmados do Master Analyzer, garantindo que o Handicap Asiático reflita ausências
    de jogadores-chave (e.g., artilheiro suspenso → menor superioridade de lambda).

    Args:
        stats_casa: Estatísticas do time da casa
        stats_fora: Estatísticas do time visitante
        odds: Dicionário de odds disponíveis
        classificacao: Tabela de classificação
        pos_casa: Posição do time da casa
        pos_fora: Posição do time visitante
        script_name: Nome do script tático
        analysis_packet: Pacote completo do Master Analyzer (com lambdas ajustados)

    Returns:
        dict: Análise de handicaps com palpites ou None
    """
    if not stats_casa or not stats_fora:
        return None

    lambda_adj_source = "estatísticas brutas"

    # TASK 7: Usar lambdas ajustados por desfalques quando disponíveis no analysis_packet
    if analysis_packet:
        lambda_data = analysis_packet.get('calculated_probabilities', {}).get('lambda_goals', {})
        lambda_home_adj = lambda_data.get('lambda_home')
        lambda_away_adj = lambda_data.get('lambda_away')
        adj_meta = lambda_data.get('lambda_adjustments', {})
        if lambda_home_adj and lambda_away_adj and lambda_home_adj > 0 and lambda_away_adj > 0:
            lambda_home = max(0.3, min(4.0, lambda_home_adj))
            lambda_away = max(0.3, min(4.0, lambda_away_adj))
            if adj_meta.get('adjusted'):
                lambda_adj_source = "master (ajustado por desfalques)"
            else:
                lambda_adj_source = "master (sem ajuste)"
            print(f"\n  🔗 HANDICAP: Usando lambdas do Master ({lambda_home:.2f}/{lambda_away:.2f}) — {lambda_adj_source}")

            superioridade = calcular_superioridade(stats_casa, stats_fora, pos_casa, pos_fora)
            dist = calcular_distribuicao_margem(lambda_home, lambda_away)
            print(f"  🎯 ASIAN HANDICAP — λ_casa={lambda_home:.2f} λ_fora={lambda_away:.2f} sup={superioridade:+.1f}")

            return _build_handicap_palpites(
                odds, script_name, lambda_home, lambda_away, superioridade, dist,
                adj_notes=adj_meta.get('notes', []) if adj_meta.get('adjusted') else []
            )

    # Fallback: cálculo clássico via estatísticas brutas
    lambda_home = stats_casa['casa'].get('gols_marcados', 1.2)
    lambda_away = stats_fora['fora'].get('gols_marcados', 1.0)

    # Ajuste defensivo: considerar gols sofridos do adversário
    lambda_home = (lambda_home + stats_fora['fora'].get('gols_sofridos', 1.1)) / 2.0
    lambda_away = (lambda_away + stats_casa['casa'].get('gols_sofridos', 1.1)) / 2.0

    lambda_home = max(0.3, min(4.0, lambda_home))
    lambda_away = max(0.3, min(4.0, lambda_away))

    # 2. Calcular superioridade para selecionar linhas
    superioridade = calcular_superioridade(stats_casa, stats_fora, pos_casa, pos_fora)

    # 3. Calcular distribuição de margens via Poisson
    dist = calcular_distribuicao_margem(lambda_home, lambda_away)

    print(f"\n  🎯 ASIAN HANDICAP — λ_casa={lambda_home:.2f} λ_fora={lambda_away:.2f} sup={superioridade:+.1f}")

    return _build_handicap_palpites(odds, script_name, lambda_home, lambda_away, superioridade, dist)


def _build_handicap_palpites(odds, script_name, lambda_home, lambda_away, superioridade, dist, adj_notes=None):
    """
    Constrói a lista de palpites de handicap asiático a partir dos lambdas e distribuição Poisson.
    Reutilizado tanto pelo caminho com lambdas ajustados (Task 7) quanto pelo fallback clássico.
    """
    palpites = []
    linhas_candidatas = []

    if superioridade >= 5.0:
        linhas_candidatas = [
            ("handicap_asia_casa_-1.75", -1.75, "Casa", 5.5),
            ("handicap_asia_casa_-1.5",  -1.5,  "Casa", 5.5),
            ("handicap_asia_casa_-1.25", -1.25, "Casa", 5.5),
            ("handicap_asia_casa_-1.0",  -1.0,  "Casa", 5.0),
            ("handicap_asia_casa_-0.75", -0.75, "Casa", 5.0),
        ]
    elif superioridade >= 2.5:
        linhas_candidatas = [
            ("handicap_asia_casa_-1.0",  -1.0,  "Casa", 5.0),
            ("handicap_asia_casa_-0.75", -0.75, "Casa", 5.0),
            ("handicap_asia_casa_-0.5",  -0.5,  "Casa", 5.0),
            ("handicap_asia_casa_-0.25", -0.25, "Casa", 5.0),
        ]
    elif superioridade >= 1.0:
        linhas_candidatas = [
            ("handicap_asia_casa_-0.5",  -0.5,  "Casa", 5.0),
            ("handicap_asia_casa_-0.25", -0.25, "Casa", 5.0),
            ("handicap_asia_casa_0.0",    0.0,  "Casa", 5.0),
        ]
    elif superioridade >= -1.0:
        linhas_candidatas = [
            ("handicap_asia_casa_0.0",    0.0,  "Casa", 5.0),
            ("handicap_asia_casa_+0.25", +0.25, "Casa", 5.0),
            ("handicap_asia_fora_0.0",    0.0,  "Fora", 5.0),
            ("handicap_asia_fora_+0.25", +0.25, "Fora", 5.0),
        ]
    elif superioridade >= -2.5:
        linhas_candidatas = [
            ("handicap_asia_fora_-0.5",  -0.5,  "Fora", 5.0),
            ("handicap_asia_fora_-0.25", -0.25, "Fora", 5.0),
            ("handicap_asia_fora_0.0",    0.0,  "Fora", 5.0),
        ]
    else:
        linhas_candidatas = [
            ("handicap_asia_fora_-1.0",  -1.0,  "Fora", 5.0),
            ("handicap_asia_fora_-0.75", -0.75, "Fora", 5.0),
            ("handicap_asia_fora_-0.5",  -0.5,  "Fora", 5.0),
        ]

    for odd_key, linha, team, min_conf in linhas_candidatas:
        odd_value = odds.get(odd_key) if odds else None

        if team == "Casa":
            prob_pct = prob_asian_handicap_casa(linha, dist)
        else:
            prob_pct = prob_asian_handicap_casa(-linha, _inverter_dist(dist))

        prob_pct = max(1.0, min(99.0, prob_pct))
        bet_label = _linha_label(linha, team)
        is_value, edge_pct, prob_implicita = detect_value_bet(prob_pct, odd_value) if odd_value else (False, 0.0, 0.0)

        conf_final, breakdown = calculate_final_confidence(
            statistical_probability_pct=prob_pct,
            bet_type=bet_label,
            tactical_script=script_name,
        )

        print(f"     {bet_label}: prob={prob_pct:.1f}% → conf={conf_final:.1f}"
              f" (odd={odd_value if odd_value else 'N/A'}"
              f"{' ★VALUE edge=+'+str(edge_pct)+'%' if is_value else ''})")

        if conf_final >= min_conf:
            palpites.append({
                "tipo": bet_label,
                "confianca": conf_final,
                "odd": odd_value,
                "periodo": "FT",
                "time": team,
                "mercado": "Handicaps",
                "probabilidade": prob_pct,
                "prob_implicita": prob_implicita,
                "edge": edge_pct,
                "is_value": is_value,
                "linha": linha,
                "breakdown": breakdown,
                "confidence_breakdown": breakdown,
                "superioridade": superioridade,
            })

    palpites.sort(key=lambda x: (x.get('is_value', False), x['confianca']), reverse=True)
    palpites = palpites[:3]
    print(f"  ✅ ASIAN HANDICAP: {len(palpites)} palpites gerados")

    if palpites:
        value_count = sum(1 for p in palpites if p.get('is_value'))
        adj_line = ""
        if adj_notes:
            adj_line = "   - ⚠️ " + " | ".join(adj_notes[:2]) + "\n"
        suporte = (
            f"   - <b>λ Casa:</b> {lambda_home:.2f} | <b>λ Fora:</b> {lambda_away:.2f}\n"
            f"   - <b>Superioridade Casa:</b> {superioridade:+.1f}/10\n"
            f"   - <b>Value bets detectados:</b> {value_count}/{len(palpites)}\n"
            f"{adj_line}"
            f"   - <i>💡 Probabilidades calculadas via distribuição de Poisson com regras AH reais</i>\n"
        )
        return {"mercado": "Handicaps", "palpites": palpites, "dados_suporte": suporte}

    print(f"  ❌ ASIAN HANDICAP: Nenhum palpite passou nos filtros de qualidade")
    return None


def _inverter_dist(dist: dict) -> dict:
    """Inverte a perspectiva da distribuição: home ↔ away."""
    inv = {'draw': dist['draw']}
    for n in range(1, 9):
        inv[f'home_win_by_{n}'] = dist.get(f'away_win_by_{n}', 0)
        inv[f'away_win_by_{n}'] = dist.get(f'home_win_by_{n}', 0)
    inv['home_win_by_1_plus'] = dist.get('away_win_by_1_plus', 0)
    inv['home_win_by_2_plus'] = dist.get('away_win_by_2_plus', 0)
    inv['home_win_by_3_plus'] = dist.get('away_win_by_3_plus', 0)
    inv['away_win_by_1_plus'] = dist.get('home_win_by_1_plus', 0)
    inv['away_win_by_2_plus'] = dist.get('home_win_by_2_plus', 0)
    return inv
