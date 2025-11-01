# analysts/handicaps_analyzer.py
"""
PHOENIX V3.0 - HANDICAPS ANALYZER (REFATORADO - SIMPLIFICADO)
=============================================================
UNIFIED CONFIDENCE SYSTEM: Usa exclusivamente confidence_calculator.py
para todos os cálculos de confiança.

ARQUITETURA:
1. Calcular superioridade contextual baseada em múltiplos fatores
2. Converter superioridade em probabilidade estatística
3. Chamar calculate_final_confidence para obter confiança final
4. Usar breakdown para evidências e transparência

NOTA: Handicaps são complexos e requerem análise contextual profunda.
Esta versão simplificada mantém a essência do sistema unificado.
"""

from analysts.confidence_calculator import calculate_final_confidence


def calcular_superioridade(stats_casa, stats_fora, pos_casa="N/A", pos_fora="N/A"):
    """
    Calcula score de superioridade contextual (0-10) baseado em múltiplos fatores.
    
    Returns:
        float: Score de superioridade (-10 a +10)
            > 0 = Casa superior
            < 0 = Fora superior
            ~0 = Equilibrado
    """
    # 1. FORÇA OFENSIVA/DEFENSIVA (Gols) - 40% peso
    gols_casa_marcados = stats_casa['casa'].get('gols_marcados', 0)
    gols_casa_sofridos = stats_casa['casa'].get('gols_sofridos', 0)
    gols_fora_marcados = stats_fora['fora'].get('gols_marcados', 0)
    gols_fora_sofridos = stats_fora['fora'].get('gols_sofridos', 0)

    forca_casa = gols_casa_marcados - gols_casa_sofridos
    forca_fora = gols_fora_marcados - gols_fora_sofridos
    diferenca_forca = forca_casa - forca_fora

    superioridade = 0.0
    
    # Força
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
    
    # 2. POSIÇÃO NA TABELA - 30% peso
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
    
    # 3. ATAQUE VS DEFESA - 20% peso
    if gols_casa_marcados >= 2.0 and gols_fora_sofridos >= 1.5:
        superioridade += 1.5
    if gols_fora_marcados >= 2.0 and gols_casa_sofridos >= 1.5:
        superioridade -= 1.5
    
    # 4. ESCANTEIOS - 10% peso
    cantos_casa = stats_casa['casa'].get('cantos_feitos', 0)
    cantos_fora = stats_fora['fora'].get('cantos_feitos', 0)
    diferenca_cantos = cantos_casa - cantos_fora
    
    if diferenca_cantos >= 3.0:
        superioridade += 0.5
    elif diferenca_cantos <= -3.0:
        superioridade -= 0.5
    
    return superioridade


def superioridade_to_probability(superioridade, handicap_line):
    """
    Converte score de superioridade em probabilidade de cobrir o handicap.
    
    Args:
        superioridade: Score -10 a +10
        handicap_line: Linha do handicap (ex: -1.5, -2.0, +0.5)
    
    Returns:
        float: Probabilidade em % (0-100)
    """
    # Superioridade muito alta (>6) = ~75-85% probabilidade de handicaps altos
    # Superioridade média (3-6) = ~60-70% probabilidade de handicaps médios
    # Superioridade baixa (<3) = ~50-60% probabilidade de handicaps baixos
    
    abs_line = abs(handicap_line)
    
    if superioridade >= 6.0:
        # Muito superior
        if abs_line >= 2.0:
            return 70.0  # Alta dificuldade, mas favorito forte
        elif abs_line >= 1.0:
            return 75.0
        else:
            return 80.0
    elif superioridade >= 3.5:
        # Superior
        if abs_line >= 2.0:
            return 55.0
        elif abs_line >= 1.0:
            return 65.0
        else:
            return 70.0
    elif superioridade >= 1.5:
        # Ligeiramente superior
        if abs_line >= 1.0:
            return 50.0
        else:
            return 60.0
    else:
        # Não superior o suficiente
        return 45.0


def analisar_mercado_handicaps(stats_casa, stats_fora, odds, classificacao=None, pos_casa="N/A", pos_fora="N/A", script_name=None):
    """
    Analisa handicaps usando o sistema unificado de confiança.
    
    PHOENIX V3.0 REFACTORING:
    - ✅ USA confidence_calculator.py para TODOS os cálculos
    - ✅ Calcula superioridade contextual primeiro
    - ✅ Converte superioridade em probabilidade
    - ✅ Aplica modificadores via calculate_final_confidence
    - ✅ Retorna breakdown para transparência
    
    Args:
        stats_casa: Estatísticas do time da casa
        stats_fora: Estatísticas do time visitante
        odds: Dicionário de odds disponíveis
        classificacao: Tabela de classificação
        pos_casa: Posição do time da casa
        pos_fora: Posição do time visitante
        script_name: Nome do script tático
    
    Returns:
        dict: Análise de handicaps com palpites ou None
    """
    if not stats_casa or not stats_fora or not odds:
        return None

    # ✅ STEP 1: CALCULAR SUPERIORIDADE CONTEXTUAL
    superioridade_casa = calcular_superioridade(stats_casa, stats_fora, pos_casa, pos_fora)
    
    print(f"\n  🎯 HANDICAPS - Superioridade Casa: {superioridade_casa:+.1f}/10")

    palpites = []

    # ✅ STEP 2: ANALISAR HANDICAPS BASEADOS EM SUPERIORIDADE
    
    # Definir handicaps a analisar baseado em superioridade
    handicaps_to_check = []
    
    if superioridade_casa >= 6.0:
        print(f"     ✅ CASA MUITO SUPERIOR - Analisando handicaps altos")
        handicaps_to_check.extend([
            ("handicap_asia_casa_-2.5", -2.5, "Handicap Asiático -2.5 (Casa)", 6.5),
            ("handicap_asia_casa_-2.0", -2.0, "Handicap Asiático -2.0 (Casa)", 6.2),
            ("handicap_euro_casa_-2", -2.0, "Handicap Europeu -2 (Casa)", 6.5),
        ])
    
    if superioridade_casa >= 3.5:
        print(f"     ✅ CASA SUPERIOR - Analisando handicaps médios")
        handicaps_to_check.extend([
            ("handicap_asia_casa_-1.5", -1.5, "Handicap Asiático -1.5 (Casa)", 5.5),
            ("handicap_asia_casa_-1.0", -1.0, "Handicap Asiático -1.0 (Casa)", 5.5),
            ("handicap_euro_casa_-1", -1.0, "Handicap Europeu -1 (Casa)", 5.5),
        ])
    
    if superioridade_casa >= 1.5:
        print(f"     ✅ CASA LIGEIRAMENTE SUPERIOR - Analisando handicaps baixos")
        handicaps_to_check.extend([
            ("handicap_asia_casa_-0.5", -0.5, "Handicap Asiático -0.5 (Casa)", 5.0),
            ("handicap_asia_casa_0.0", 0.0, "Handicap Asiático 0.0 (Casa)", 5.0),
        ])
    
    # Fora superior
    if superioridade_casa <= -1.5:
        print(f"     ✅ FORA SUPERIOR - Analisando handicaps fora")
        handicaps_to_check.extend([
            ("handicap_asia_fora_-0.5", -0.5, "Handicap Asiático -0.5 (Fora)", 5.0),
            ("handicap_asia_fora_-1.0", -1.0, "Handicap Asiático -1.0 (Fora)", 5.5),
        ])

    # ✅ STEP 3: PROCESSAR CADA HANDICAP
    for odd_key, handicap_line, bet_type, min_conf in handicaps_to_check:
        if odd_key in odds:
            odd_value = odds[odd_key]
            
            if False:  # PURE ANALYST: No odd filtering
                continue
            
            # ✅ REFATORADO: Converter superioridade em probabilidade
            # Para handicaps da fora, inverter a superioridade
            if "fora" in odd_key.lower():
                prob_pct = superioridade_to_probability(-superioridade_casa, handicap_line)
            else:
                prob_pct = superioridade_to_probability(superioridade_casa, handicap_line)
            
            # ✅ PURE ANALYST: Calculate confidence based purely on statistical probability
            conf_final, breakdown = calculate_final_confidence(
                statistical_probability_pct=prob_pct,
                bet_type=bet_type,
                tactical_script=script_name
            )
            
            print(f"     {bet_type}: Prob={prob_pct:.1f}% → Conf={conf_final:.1f} (odd={odd_value:.2f})")
            
            # ✅ Filtro de qualidade
            if conf_final >= min_conf:
                palpites.append({
                    "tipo": bet_type,
                    "confianca": conf_final,
                    "odd": odd_value,
                    "periodo": "FT",
                    "time": "Casa" if "casa" in odd_key else "Fora",
                    "breakdown": breakdown,
                    "probabilidade_estatistica": prob_pct,
                    "superioridade": superioridade_casa
                })

    # ✅ RETORNO FINAL
    print(f"  ✅ HANDICAPS: {len(palpites)} palpites gerados")
    
    if palpites:
        gols_casa_marcados = stats_casa['casa'].get('gols_marcados', 0)
        gols_fora_marcados = stats_fora['fora'].get('gols_marcados', 0)
        
        suporte = (f"   - <b>Superioridade Casa:</b> {superioridade_casa:+.1f}/10\n"
                   f"   - <b>Gols Casa:</b> {gols_casa_marcados:.1f} marcados/jogo\n"
                   f"   - <b>Gols Fora:</b> {gols_fora_marcados:.1f} marcados/jogo\n"
                   f"   - <i>💡 Análise contextual baseada em força, posição, ataque e defesa</i>\n")
        
        return {"mercado": "Handicaps", "palpites": palpites, "dados_suporte": suporte}
    
    print(f"  ❌ HANDICAPS: Nenhum palpite passou nos filtros de qualidade")
    return None
