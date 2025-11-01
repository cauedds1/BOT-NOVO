# analysts/justification_generator.py
"""
Gerador de justificativas persuasivas e dinâmicas para apostas esportivas.
Explica o "porquê" de cada sugestão de forma convincente e não-genérica.

PHOENIX V3.0: Evidence-Based Analysis Protocol
"""


def generate_evidence_based_justification(mercado, tipo, evidencias_home, evidencias_away, home_team_name, away_team_name):
    """
    EVIDENCE-BASED: Gera justificativa específica baseada nos dados reais dos últimos jogos.
    
    Conforme especificação do protocolo Evidence-Based Analysis, as justificativas devem ser:
    - Específicas (mencionando médias reais)
    - Factuais (baseadas em dados concretos)
    - Não-genéricas (únicas para este jogo)
    
    Args:
        mercado: Tipo de mercado ('Gols', 'Cantos', 'Cartões', etc.)
        tipo: Tipo específico da análise
        evidencias_home: Dict com evidências dos últimos jogos do time casa
        evidencias_away: Dict com evidências dos últimos jogos do time fora
        home_team_name: Nome do time casa
        away_team_name: Nome do time fora
    
    Returns:
        str: Justificativa baseada em evidências
    
    Exemplo Output:
        "A média de gols nos jogos do Coritiba em casa é de apenas 1.0, enquanto a do CRB
        como visitante é a mesma, reforçando a tendência de um jogo com poucos gols."
    """
    
    if mercado == "Gols":
        return _justificar_gols_evidence_based(tipo, evidencias_home, evidencias_away, home_team_name, away_team_name)
    elif mercado == "Cantos":
        return _justificar_cantos_evidence_based(tipo, evidencias_home, evidencias_away, home_team_name, away_team_name)
    elif mercado == "Cartões":
        return _justificar_cartoes_evidence_based(tipo, evidencias_home, evidencias_away, home_team_name, away_team_name)
    elif mercado == "Finalizações":
        return _justificar_finalizacoes_evidence_based(tipo, evidencias_home, evidencias_away, home_team_name, away_team_name)
    else:
        return f"Análise baseada nos dados recentes favorece {tipo}."


def _justificar_gols_evidence_based(tipo, evidencias_home, evidencias_away, home_team_name, away_team_name):
    """Gera justificativa para Gols baseada em evidências reais"""
    gols_home = evidencias_home.get('gols', [])
    gols_away = evidencias_away.get('gols', [])
    
    if not gols_home or not gols_away:
        return f"Análise estatística favorece {tipo} baseado no perfil das equipes."
    
    # Calcular média de gols totais nos últimos jogos
    media_total_home = sum(g['total_goals'] for g in gols_home) / len(gols_home) if gols_home else 0
    media_total_away = sum(g['total_goals'] for g in gols_away) / len(gols_away) if gols_away else 0
    media_combinada = (media_total_home + media_total_away) / 2
    
    # Calcular média de gols marcados
    media_marcados_home = sum(g['team_goals'] for g in gols_home) / len(gols_home) if gols_home else 0
    media_marcados_away = sum(g['team_goals'] for g in gols_away) / len(gols_away) if gols_away else 0
    
    if "Over" in tipo or "Mais" in tipo:
        return (
            f"A média de gols totais nos jogos do {home_team_name} em casa é de {media_total_home:.1f}, "
            f"enquanto a do {away_team_name} como visitante é de {media_total_away:.1f}, "
            f"resultando em uma média combinada de {media_combinada:.1f} gols, "
            f"favorecendo {tipo}."
        )
    elif "Under" in tipo or "Menos" in tipo:
        return (
            f"A média de gols nos jogos do {home_team_name} em casa é de apenas {media_total_home:.1f}, "
            f"enquanto a do {away_team_name} como visitante é de {media_total_away:.1f}, "
            f"reforçando a tendência de um jogo com poucos gols."
        )
    else:
        return (
            f"{home_team_name} marca {media_marcados_home:.1f} gols em casa, "
            f"enquanto {away_team_name} marca {media_marcados_away:.1f} fora, "
            f"favorecendo {tipo}."
        )


def _justificar_cantos_evidence_based(tipo, evidencias_home, evidencias_away, home_team_name, away_team_name):
    """Gera justificativa para Cantos baseada em evidências reais"""
    cantos_home = evidencias_home.get('cantos', [])
    cantos_away = evidencias_away.get('cantos', [])
    
    if not cantos_home or not cantos_away:
        return f"Análise de volume de jogo favorece {tipo}."
    
    # Calcular médias
    media_total_home = sum(c['total_corners'] for c in cantos_home) / len(cantos_home) if cantos_home else 0
    media_total_away = sum(c['total_corners'] for c in cantos_away) / len(cantos_away) if cantos_away else 0
    media_forcados_home = sum(c['corners_for'] for c in cantos_home) / len(cantos_home) if cantos_home else 0
    media_forcados_away = sum(c['corners_for'] for c in cantos_away) / len(cantos_away) if cantos_away else 0
    
    media_combinada = (media_total_home + media_total_away) / 2
    
    if "Over" in tipo or "Mais" in tipo:
        return (
            f"{home_team_name} força {media_forcados_home:.1f} escanteios em casa (total médio de {media_total_home:.1f} por jogo), "
            f"enquanto {away_team_name} força {media_forcados_away:.1f} fora (total médio de {media_total_away:.1f}). "
            f"A média combinada de {media_combinada:.1f} escanteios favorece {tipo}."
        )
    elif "Under" in tipo or "Menos" in tipo:
        return (
            f"Nos últimos jogos, a média de escanteios foi de apenas {media_total_home:.1f} para {home_team_name} em casa "
            f"e {media_total_away:.1f} para {away_team_name} fora, "
            f"indicando baixo volume de jogo e favorecendo {tipo}."
        )
    else:
        return f"Análise de escanteios favorece {tipo} com base nas médias recentes."


def _justificar_cartoes_evidence_based(tipo, evidencias_home, evidencias_away, home_team_name, away_team_name):
    """Gera justificativa para Cartões baseada em evidências reais"""
    cartoes_home = evidencias_home.get('cartoes', [])
    cartoes_away = evidencias_away.get('cartoes', [])
    
    if not cartoes_home or not cartoes_away:
        return f"Análise de disciplina favorece {tipo}."
    
    # Calcular médias
    media_cartoes_home = sum(c['total_cards'] for c in cartoes_home) / len(cartoes_home) if cartoes_home else 0
    media_cartoes_away = sum(c['total_cards'] for c in cartoes_away) / len(cartoes_away) if cartoes_away else 0
    media_combinada = media_cartoes_home + media_cartoes_away
    
    if "Over" in tipo or "Mais" in tipo:
        return (
            f"{home_team_name} recebe uma média de {media_cartoes_home:.1f} cartões em casa, "
            f"enquanto {away_team_name} recebe {media_cartoes_away:.1f} fora. "
            f"A média combinada de {media_combinada:.1f} cartões indica jogo físico, favorecendo {tipo}."
        )
    elif "Under" in tipo or "Menos" in tipo:
        return (
            f"Ambos os times têm baixa média de cartões recentemente "
            f"({home_team_name}: {media_cartoes_home:.1f}, {away_team_name}: {media_cartoes_away:.1f}), "
            f"indicando jogo mais técnico e favorecendo {tipo}."
        )
    else:
        return f"Análise de disciplina favorece {tipo}."


def _justificar_finalizacoes_evidence_based(tipo, evidencias_home, evidencias_away, home_team_name, away_team_name):
    """Gera justificativa para Finalizações baseada em evidências reais"""
    shots_home = evidencias_home.get('finalizacoes', [])
    shots_away = evidencias_away.get('finalizacoes', [])
    
    if not shots_home or not shots_away:
        return f"Análise de volume ofensivo favorece {tipo}."
    
    # Calcular médias
    media_shots_home = sum(s['shots_for'] for s in shots_home) / len(shots_home) if shots_home else 0
    media_shots_away = sum(s['shots_for'] for s in shots_away) / len(shots_away) if shots_away else 0
    media_total_home = sum(s['total_shots'] for s in shots_home) / len(shots_home) if shots_home else 0
    media_total_away = sum(s['total_shots'] for s in shots_away) / len(shots_away) if shots_away else 0
    
    media_combinada = (media_total_home + media_total_away) / 2
    
    if "Over" in tipo or "Mais" in tipo:
        return (
            f"{home_team_name} finaliza {media_shots_home:.1f} vezes por jogo em casa "
            f"({media_total_home:.1f} total), "
            f"enquanto {away_team_name} finaliza {media_shots_away:.1f} fora "
            f"({media_total_away:.1f} total). "
            f"Alto volume ofensivo favorece {tipo}."
        )
    else:
        return f"Análise de finalizações favorece {tipo} baseado no volume ofensivo recente."

def generate_persuasive_justification(mercado, tipo, value_score, game_script=None, expectativa_gols=None, 
                                       quality_home=None, quality_away=None, odd=None, **kwargs):
    """
    Gera justificativa persuasiva e dinâmica para uma sugestão de aposta.
    
    Args:
        mercado (str): Tipo de mercado ('Gols', 'Cantos', 'Cartões', etc.)
        tipo (str): Tipo específico ('Over 2.5', 'BTTS Sim', etc.)
        value_score (float): Value Score calculado
        game_script (str): Roteiro do jogo (DOMINIO_CASA, EQUILIBRADO, etc.)
        expectativa_gols (float): Expectativa total de gols
        quality_home (int): Qualidade técnica do time da casa
        quality_away (int): Qualidade técnica do time visitante
        odd (float): Odd da aposta
        **kwargs: Outros dados contextuais
    
    Returns:
        str: Justificativa persuasiva formatada
    """
    
    # --- MERCADO DE GOLS ---
    if mercado == "Gols":
        return _justificar_gols(tipo, value_score, game_script, expectativa_gols, 
                                quality_home, quality_away, odd, **kwargs)
    
    # --- MERCADO DE CANTOS ---
    elif mercado == "Cantos":
        return _justificar_cantos(tipo, value_score, game_script, **kwargs)
    
    # --- MERCADO DE CARTÕES ---
    elif mercado == "Cartões":
        return _justificar_cartoes(tipo, value_score, game_script, **kwargs)
    
    # --- MERCADO BTTS ---
    elif mercado == "BTTS":
        return _justificar_btts(tipo, value_score, expectativa_gols, **kwargs)
    
    # --- FALLBACK GENÉRICO ---
    else:
        return _justificar_generica(tipo, value_score, odd)


def _justificar_gols(tipo, value_score, game_script, expectativa_gols, quality_home, quality_away, odd, **kwargs):
    """Justificativa específica para mercado de Gols"""
    
    # Calcular diferença de qualidade
    quality_diff = abs(quality_home - quality_away) if quality_home and quality_away else 0
    value_pct = f"{value_score*100:+.1f}%"
    
    # --- CENÁRIO 1: DOMÍNIO TÉCNICO + OVER ---
    if game_script and "DOMINIO" in game_script and "Over" in tipo:
        time_dominante = "casa" if "CASA" in game_script else "visitante"
        qual_forte = quality_home if "CASA" in game_script else quality_away
        qual_fraco = quality_away if "CASA" in game_script else quality_home
        
        justificativa = (
            f"📊 <b>Análise Técnica:</b> Domínio claro do time <b>{time_dominante}</b> "
            f"(Qualidade <b>{qual_forte}</b> vs <b>{qual_fraco}</b>). "
        )
        
        if expectativa_gols:
            justificativa += f"Nossa projeção indica <b>{expectativa_gols:.1f} gols</b> no jogo. "
        
        if odd and odd > 0:
            justificativa += (
                f"\n\n💡 <b>Oportunidade de Valor:</b> A odd de <b>@{odd:.2f}</b> para {tipo} "
                f"implica uma probabilidade menor do que nossa análise sugere, "
                f"gerando um valor positivo de <b>{value_pct}</b>."
            )
        else:
            justificativa += (
                f"\n\n💡 <b>Oportunidade de Valor:</b> Nossa análise sugere "
                f"um valor positivo de <b>{value_pct}</b> para {tipo}."
            )
        
        return justificativa
    
    # --- CENÁRIO 2: FAVORITISMO + OVER ---
    elif game_script and "FAVORITISMO" in game_script and "Over" in tipo:
        time_favorito = "casa" if "CASA" in game_script else "visitante"
        
        justificativa = (
            f"📊 <b>Análise Técnica:</b> Favoritismo moderado do time <b>{time_favorito}</b> "
            f"(Diferença de qualidade: <b>{quality_diff} pontos</b>). "
        )
        
        if expectativa_gols:
            justificativa += f"Expectativa de <b>{expectativa_gols:.1f} gols</b> baseada no confronto ofensivo/defensivo. "
        
        if odd and odd > 0:
            justificativa += (
                f"\n\n💰 <b>Valor Matemático:</b> O mercado subprecificou esta linha. "
                f"A odd @{odd:.2f} oferece <b>{value_pct}</b> de valor sobre nossa estimativa."
            )
        else:
            justificativa += (
                f"\n\n💰 <b>Valor Matemático:</b> Nossa análise identifica "
                f"<b>{value_pct}</b> de valor sobre a estimativa de mercado."
            )
        
        return justificativa
    
    # --- CENÁRIO 3: EQUILIBRADO + OVER (Baseado em Estatísticas) ---
    elif game_script == "EQUILIBRADO" and "Over" in tipo and expectativa_gols:
        justificativa = (
            f"⚖️ <b>Jogo Equilibrado:</b> Sem disparidade técnica clara "
            f"(Qualidade: <b>{quality_home}</b> vs <b>{quality_away}</b>). "
            f"A análise se baseia no confronto estatístico entre <b>ataque e defesa</b>.\n\n"
        )
        
        if odd and odd > 0:
            justificativa += (
                f"📈 <b>Projeção:</b> Com <b>{expectativa_gols:.1f} gols</b> esperados, "
                f"a linha {tipo} a <b>@{odd:.2f}</b> apresenta valor matemático interessante. "
                f"O mercado parece ter subestimado o potencial ofensivo (<b>{value_pct}</b> de valor)."
            )
        else:
            justificativa += (
                f"📈 <b>Projeção:</b> Com <b>{expectativa_gols:.1f} gols</b> esperados, "
                f"a linha {tipo} apresenta valor matemático interessante. "
                f"Nossa análise identifica <b>{value_pct}</b> de valor positivo."
            )
        
        return justificativa
    
    # --- CENÁRIO 4: EQUILIBRADO + UNDER (Defesas Fortes) ---
    elif game_script == "EQUILIBRADO" and "Under" in tipo and expectativa_gols:
        odd_text = f" a <b>@{odd:.2f}</b>" if odd and odd > 0 else ""
        justificativa = (
            f"🛡️ <b>Confronto Equilibrado:</b> O ponto-chave é a <b>força defensiva</b> de ambas as equipes. "
            f"Com expectativa de apenas <b>{expectativa_gols:.1f} gols</b>, "
            f"a linha {tipo}{odd_text} tem valor matemático.\n\n"
        )
        
        justificativa += (
            f"💡 <b>Insight:</b> O mercado parece superestimar o potencial ofensivo desta partida. "
            f"Nossa análise identifica <b>{value_pct}</b> de valor positivo nesta aposta."
        )
        
        return justificativa
    
    # --- CENÁRIO 5: FALLBACK COM EXPECTATIVA ---
    elif expectativa_gols:
        over_under = "Over" if "Over" in tipo else "Under"
        trend = "ofensiva" if over_under == "Over" else "defensiva"
        
        justificativa = (
            f"📊 <b>Análise Estatística:</b> Expectativa de <b>{expectativa_gols:.1f} gols</b> "
            f"baseada no histórico recente e tendência <b>{trend}</b> das equipes.\n\n"
        )
        
        if odd and odd > 0:
            justificativa += (
                f"💰 <b>Valor Identificado:</b> A odd @{odd:.2f} oferece <b>{value_pct}</b> "
                f"de valor sobre nossa projeção matemática."
            )
        else:
            justificativa += (
                f"💰 <b>Valor Identificado:</b> Nossa análise oferece <b>{value_pct}</b> "
                f"de valor sobre a projeção matemática."
            )
        
        return justificativa
    
    # --- FALLBACK GENÉRICO ---
    else:
        return _justificar_generica(tipo, value_score, odd)


def _justificar_cantos(tipo, value_score, game_script, **kwargs):
    """Justificativa específica para mercado de Cantos"""
    
    projecao_cantos = kwargs.get('projecao_cantos')
    estilo_jogo = kwargs.get('estilo_jogo', 'padrão')
    odd = kwargs.get('odd', 0)
    value_pct = f"{value_score*100:+.1f}%"
    
    if game_script and "DOMINIO" in game_script:
        time_dominante = "casa" if "CASA" in game_script else "visitante"
        
        justificativa = (
            f"🚩 <b>Domínio Técnico:</b> O time <b>{time_dominante}</b> tende a dominar a posse "
            f"e pressionar constantemente, gerando <b>muitas finalizações e escanteios</b>.\n\n"
        )
        
        if projecao_cantos:
            justificativa += f"📈 Nossa projeção: <b>{projecao_cantos:.1f} cantos</b>. "
        
        if odd and odd > 0:
            justificativa += (
                f"A odd @{odd:.2f} para {tipo} oferece <b>{value_pct}</b> "
                f"de valor, pois o mercado subestimou o volume de ataques esperado."
            )
        else:
            justificativa += (
                f"Nossa análise identifica <b>{value_pct}</b> de valor, "
                f"pois o mercado subestimou o volume de ataques esperado."
            )
        
        return justificativa
    
    elif estilo_jogo == "vertical" or estilo_jogo == "ataque_contra_ataque":
        justificativa = (
            f"⚡ <b>Estilo de Jogo:</b> Partida com estilo <b>{estilo_jogo.replace('_', ' ')}</b>, "
            f"favorecendo transições rápidas e muitas finalizações.\n\n"
        )
        
        if projecao_cantos:
            justificativa += f"Nossa projeção de <b>{projecao_cantos:.1f} cantos</b> "
        
        if odd and odd > 0:
            justificativa += (
                f"sugere que {tipo} a <b>@{odd:.2f}</b> está mal precificado "
                f"(<b>{value_pct}</b> de valor positivo)."
            )
        else:
            justificativa += (
                f"sugere que {tipo} está mal precificado "
                f"(<b>{value_pct}</b> de valor positivo)."
            )
        
        return justificativa
    
    else:
        return _justificar_generica(tipo, value_score, odd)


def _justificar_cartoes(tipo, value_score, game_script, **kwargs):
    """Justificativa específica para mercado de Cartões"""
    
    intensidade = kwargs.get('intensidade', 'média')
    classico = kwargs.get('classico', False)
    odd = kwargs.get('odd', 0)
    value_pct = f"{value_score*100:+.1f}%"
    
    if classico:
        justificativa = (
            f"🔥 <b>Clássico/Derby:</b> Rivalidade histórica eleva a <b>intensidade emocional</b> "
            f"do confronto. Estatisticamente, clássicos têm <b>50% mais cartões</b> que jogos normais.\n\n"
        )
        
        if odd and odd > 0:
            justificativa += (
                f"💡 A linha {tipo} a <b>@{odd:.2f}</b> não precificou adequadamente este fator, "
                f"gerando <b>{value_pct}</b> de valor."
            )
        else:
            justificativa += (
                f"💡 A linha {tipo} não precificou adequadamente este fator, "
                f"gerando <b>{value_pct}</b> de valor."
            )
        
        return justificativa
    
    elif intensidade == "alta":
        justificativa = (
            f"⚠️ <b>Jogo de Alta Intensidade:</b> Ambas as equipes têm estilo físico e histórico "
            f"de muitas faltas. Expectativa de <b>arbitragem rigorosa</b>.\n\n"
        )
        
        if odd and odd > 0:
            justificativa += (
                f"📊 Nossa análise indica que {tipo} a <b>@{odd:.2f}</b> "
                f"oferece <b>{value_pct}</b> de valor matemático."
            )
        else:
            justificativa += (
                f"📊 Nossa análise indica que {tipo} "
                f"oferece <b>{value_pct}</b> de valor matemático."
            )
        
        return justificativa
    
    else:
        return _justificar_generica(tipo, value_score, odd)


def _justificar_btts(tipo, value_score, expectativa_gols, **kwargs):
    """Justificativa específica para mercado BTTS"""
    
    odd = kwargs.get('odd', 0)
    value_pct = f"{value_score*100:+.1f}%"
    defesas_fracas = kwargs.get('defesas_fracas', False)
    
    if "Sim" in tipo and defesas_fracas:
        justificativa = (
            f"🎯 <b>Defesas Vulneráveis:</b> Ambos os times têm <b>defesas frágeis</b> "
            f"e concedem gols regularmente em casa/fora.\n\n"
        )
        
        if expectativa_gols:
            justificativa += f"Com expectativa de <b>{expectativa_gols:.1f} gols</b>, "
        
        if odd and odd > 0:
            justificativa += (
                f"BTTS Sim a <b>@{odd:.2f}</b> oferece <b>{value_pct}</b> "
                f"de valor, já que ambos têm alto poder ofensivo."
            )
        else:
            justificativa += (
                f"BTTS Sim oferece <b>{value_pct}</b> "
                f"de valor, já que ambos têm alto poder ofensivo."
            )
        
        return justificativa
    
    elif "Não" in tipo:
        justificativa = (
            f"🛡️ <b>Solidez Defensiva:</b> Pelo menos um dos times possui <b>defesa consistente</b>, "
            f"reduzindo a probabilidade de ambos marcarem.\n\n"
        )
        
        if odd and odd > 0:
            justificativa += (
                f"💰 A odd @{odd:.2f} para BTTS Não está subvalorizada, "
                f"oferecendo <b>{value_pct}</b> de valor matemático."
            )
        else:
            justificativa += (
                f"💰 BTTS Não oferece <b>{value_pct}</b> de valor matemático."
            )
        
        return justificativa
    
    else:
        return _justificar_generica(tipo, value_score, odd)


def _justificar_generica(tipo, value_score, odd):
    """Justificativa genérica de fallback"""
    
    value_pct = f"{value_score*100:+.1f}%"
    
    if value_score >= 0.10:
        intensidade = "excelente"
    elif value_score >= 0.05:
        intensidade = "boa"
    else:
        intensidade = "razoável"
    
    justificativa = (
        f"📊 <b>Análise Matemática:</b> Nossa avaliação técnica identificou "
        f"uma <b>{intensidade} oportunidade de valor</b> nesta linha.\n\n"
    )
    
    if odd and odd > 0:
        justificativa += (
            f"💰 A odd @{odd:.2f} para {tipo} oferece <b>{value_pct}</b> "
            f"de valor positivo sobre nossa estimativa de probabilidade."
        )
    else:
        justificativa += (
            f"💰 A linha {tipo} oferece <b>{value_pct}</b> "
            f"de valor positivo sobre nossa estimativa de probabilidade."
        )
    
    return justificativa
