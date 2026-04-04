"""
PHOENIX V3.0 - EVIDENCE-BASED ANALYSIS PROTOCOL
================================================

Formatador de mensagens implementando o protocolo Evidence-Based Analysis.

ESTRUTURA OBRIGATÓRIA DO OUTPUT:
1. 🏆 Header: Liga, Times (Posições), Data/Hora
2. 💎 ANÁLISE PRINCIPAL: Melhor palpite com evidências dos últimos 4 jogos
3. 🧠 SUGESTÕES TÁTICAS: Outras análises de valor (com ou sem odds)
4. ⚠️ AVISOS: Mercados sem odds ou análises indisponíveis
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from analysts.justification_generator import generate_evidence_based_justification


def format_evidence_based_dossier(
    jogo: Dict,
    todos_palpites: List[Dict],
    master_analysis: Dict
) -> str:
    """
    EVIDENCE-BASED PROTOCOL: Formata mensagem seguindo especificação exata.
    
    Args:
        jogo: Dados do jogo
        todos_palpites: TODOS os palpites (com e sem odd), ordenados por confiança desc
        master_analysis: Análise completa do Master Analyzer (com evidências)
    
    Returns:
        str: Mensagem formatada em Plain Text seguindo protocolo Evidence-Based
    """
    if not todos_palpites or len(todos_palpites) == 0:
        return _format_header_evidence_based(jogo) + "\n⚠️ Nenhuma análise de valor identificada para este jogo.\n"
    
    # Extrair dados
    time_casa = jogo['teams']['home']['name']
    time_fora = jogo['teams']['away']['name']
    evidence = master_analysis.get('evidence', {})
    evidencias_home = evidence.get('home', {})
    evidencias_away = evidence.get('away', {})
    home_team_name = evidence.get('home_team_name', time_casa)
    away_team_name = evidence.get('away_team_name', time_fora)

    # TASK 7: Extrair ajustes de lambda por desfalques para contexto das justificativas
    _lambda_data = master_analysis.get('calculated_probabilities', {}).get('lambda_goals', {})
    _lambda_adj = _lambda_data.get('lambda_adjustments', {})
    _lambda_adj_notes = _lambda_adj.get('notes', []) if _lambda_adj.get('adjusted') else []
    _lambda_home = _lambda_data.get('lambda_home')
    _lambda_away = _lambda_data.get('lambda_away')
    _extra_gols = {
        'lambda_adj_notes': _lambda_adj_notes,
        'lambda_home': _lambda_home,
        'lambda_away': _lambda_away,
    }
    
    # === SECTION 1: HEADER ===
    msg = _format_header_evidence_based(jogo)

    # Separar palpites de seções dedicadas dos demais
    palpites_dc = [p for p in todos_palpites if p.get('mercado') == 'Dupla Chance']
    palpites_gabt = [p for p in todos_palpites if p.get('mercado') == 'Gols Ambos Tempos']
    palpites_placar_exato = [p for p in todos_palpites if p.get('mercado') == 'Placar Exato']
    palpites_he = [p for p in todos_palpites if p.get('mercado') == 'Handicap Europeu']
    palpites_pm = [p for p in todos_palpites if p.get('mercado') == 'Primeiro a Marcar']
    palpites_htft = [p for p in todos_palpites if p.get('mercado') == 'HT/FT']
    palpites_wtn = [p for p in todos_palpites if p.get('mercado') == 'Win to Nil']
    palpites_dnb = [p for p in todos_palpites if p.get('mercado') == 'Draw No Bet']
    _MERCADOS_DEDICADOS = (
        'Dupla Chance', 'Gols Ambos Tempos', 'Placar Exato', 'Handicap Europeu',
        'Primeiro a Marcar', 'HT/FT', 'Win to Nil', 'Draw No Bet',
    )
    palpites_outros = [p for p in todos_palpites if p.get('mercado') not in _MERCADOS_DEDICADOS]

    # === SECTION 2: VALUE BETS (todos os mercados) ===
    todos_value_bets = [p for p in todos_palpites if p.get('is_value')]
    if todos_value_bets:
        msg += _format_value_bets_section(todos_value_bets)

    # === SECTION 3: ANÁLISE PRINCIPAL ===
    if palpites_outros:
        palpite_principal = palpites_outros[0]  # Maior confiança (excluindo DC)
        _extra_principal = _extra_gols if palpite_principal.get('mercado') == 'Gols' else None
        msg += _format_analise_principal_evidence_based(
            palpite_principal,
            evidencias_home,
            evidencias_away,
            home_team_name,
            away_team_name,
            extra=_extra_principal
        )

        # === SECTION 4: SUGESTÕES TÁTICAS (restante dos palpites, exceto DC) ===
        if len(palpites_outros) > 1:
            msg += _format_sugestoes_taticas_evidence_based(
                palpites_outros[1:],
                evidencias_home,
                evidencias_away,
                home_team_name,
                away_team_name
            )
    else:
        # Sem palpites de outros mercados — a seção dedicada de DC abaixo já cobre tudo
        pass

    # === SECTION 4: DUPLA CHANCE (seção dedicada - sempre visível quando há picks) ===
    if palpites_dc:
        msg += _format_dupla_chance_section(
            palpites_dc,
            evidencias_home,
            evidencias_away,
            home_team_name,
            away_team_name
        )

    # === SECTION 5: GOLS EM AMBOS OS TEMPOS (seção dedicada) ===
    if palpites_gabt:
        msg += _format_gabt_section(
            palpites_gabt,
            evidencias_home,
            evidencias_away,
            home_team_name,
            away_team_name
        )

    # === SECTION 6: PLACAR EXATO (seção dedicada) ===
    if palpites_placar_exato:
        msg += _format_placar_exato_section(
            palpites_placar_exato,
            evidencias_home,
            evidencias_away,
            home_team_name,
            away_team_name
        )

    # === SECTION 7: HANDICAP EUROPEU (seção dedicada) ===
    if palpites_he:
        msg += _format_handicap_europeu_section(
            palpites_he,
            evidencias_home,
            evidencias_away,
            home_team_name,
            away_team_name
        )

    # === SECTION 8: PRIMEIRO A MARCAR (seção dedicada) ===
    if palpites_pm:
        msg += _format_primeiro_marcador_section(
            palpites_pm,
            evidencias_home,
            evidencias_away,
            home_team_name,
            away_team_name
        )

    # === SECTION 9: HT/FT (seção dedicada) ===
    if palpites_htft:
        msg += _format_htft_section(
            palpites_htft,
            evidencias_home,
            evidencias_away,
            home_team_name,
            away_team_name
        )

    # === SECTION 10: WIN TO NIL (seção dedicada) ===
    if palpites_wtn:
        msg += _format_win_to_nil_section(
            palpites_wtn,
            evidencias_home,
            evidencias_away,
            home_team_name,
            away_team_name
        )

    # === SECTION 11: DRAW NO BET (seção dedicada) ===
    if palpites_dnb:
        msg += _format_draw_no_bet_section(
            palpites_dnb,
            evidencias_home,
            evidencias_away,
            home_team_name,
            away_team_name
        )

    # === SECTION 12: AVISOS (se houver) ===
    avisos = _collect_warnings(todos_palpites)
    if avisos:
        msg += _format_avisos(avisos)

    return msg


def _format_header_evidence_based(jogo: Dict) -> str:
    """Formata header conforme especificação Evidence-Based"""
    liga_nome = jogo['league']['name']
    time_casa = jogo['teams']['home']['name']
    time_fora = jogo['teams']['away']['name']
    
    # Converter horário UTC para Brasília
    data_utc = datetime.strptime(jogo['fixture']['date'], '%Y-%m-%dT%H:%M:%S%z')
    data_brasilia = data_utc - timedelta(hours=3)
    data_formatada = data_brasilia.strftime('%d/%m/%Y')
    horario_formatado = data_brasilia.strftime('%H:%M')
    
    msg = f"🏆 {liga_nome}\n"
    msg += f"⚽ {time_casa} vs {time_fora}\n"
    msg += f"⏰ {data_formatada} às {horario_formatado} (Brasília)\n"
    msg += f"---\n\n"
    
    return msg


def _format_value_bets_section(value_bets: List[Dict]) -> str:
    """Formata seção de VALUE BETS detectados — palpites onde nossa probabilidade
    supera a probabilidade implícita da odd em pelo menos 5%."""
    if not value_bets:
        return ""

    msg = "🔥 VALUE BETS DETECTADOS\n"
    for p in value_bets[:5]:  # Máximo 5 value bets na seção
        mercado = p.get('mercado', '')
        tipo = p.get('tipo', '')
        odd = p.get('odd')
        prob = p.get('probabilidade', 0)
        edge = p.get('edge', 0)
        confianca = p.get('confianca', 0)

        odd_str = f"@{odd:.2f}" if odd else ""
        msg += f"   ⚡ [{mercado}] {tipo} {odd_str}\n"
        msg += f"      Prob. Modelo: {prob:.1f}% | Edge: +{edge:.1f}% | Confiança: {confianca:.1f}/10\n"
    msg += "\n"
    return msg


def _format_analise_principal_evidence_based(
    palpite: Dict,
    evidencias_home: Dict,
    evidencias_away: Dict,
    home_team_name: str,
    away_team_name: str,
    extra: Dict = None
) -> str:
    """Formata ANÁLISE PRINCIPAL com evidências dos últimos 4 jogos"""
    mercado = palpite.get('mercado', 'Gols')
    tipo = palpite.get('tipo', '')
    confianca = palpite.get('confianca', 0)

    msg = f"💎 ANÁLISE PRINCIPAL\n"
    msg += f"   Mercado: {mercado}\n"

    # PHOENIX V4.0 - ALVO #3: PURE ANALYST PROTOCOL - Sem exibição de odds
    msg += f"   Palpite: {tipo}\n"
    msg += f"   Confiança: {confianca:.1f} / 10\n"

    # Justificativa baseada em evidências
    msg += f"   Justificativa: "
    justificativa = generate_evidence_based_justification(
        mercado, tipo, evidencias_home, evidencias_away, home_team_name, away_team_name, extra=extra
    )
    msg += justificativa + "\n\n"
    
    # === EVIDÊNCIAS DOS ÚLTIMOS 4 JOGOS ===
    msg += f"   📊 EVIDÊNCIAS (ÚLTIMOS 4 JOGOS):\n"
    msg += _format_evidence_section(mercado, evidencias_home, evidencias_away, home_team_name, away_team_name)
    
    msg += f"---\n\n"
    return msg


def _format_evidence_section(
    mercado: str,
    evidencias_home: Dict,
    evidencias_away: Dict,
    home_team_name: str,
    away_team_name: str
) -> str:
    """Formata seção de evidências conforme o mercado"""
    msg = ""
    
    if mercado == "Gols":
        msg += _format_gols_evidence(evidencias_home, evidencias_away, home_team_name, away_team_name)
    elif mercado == "Cantos":
        msg += _format_cantos_evidence(evidencias_home, evidencias_away, home_team_name, away_team_name)
    elif mercado == "Cartões":
        msg += _format_cartoes_evidence(evidencias_home, evidencias_away, home_team_name, away_team_name)
    elif mercado == "Finalizações":
        msg += _format_finalizacoes_evidence(evidencias_home, evidencias_away, home_team_name, away_team_name)
    elif mercado == "Dupla Chance":
        msg += _format_dupla_chance_evidence(evidencias_home, evidencias_away, home_team_name, away_team_name)
    elif mercado == "Gols Ambos Tempos":
        msg += _format_gabt_evidence(evidencias_home, evidencias_away, home_team_name, away_team_name)
    elif mercado == "Placar Exato":
        msg += _format_placar_exato_evidence(evidencias_home, evidencias_away, home_team_name, away_team_name)
    elif mercado == "Handicap Europeu":
        msg += _format_handicap_europeu_evidence(evidencias_home, evidencias_away, home_team_name, away_team_name)
    elif mercado == "Primeiro a Marcar":
        msg += _format_primeiro_marcador_evidence(evidencias_home, evidencias_away, home_team_name, away_team_name)
    elif mercado in ("HT/FT", "Win to Nil", "Draw No Bet"):
        msg += _format_gols_evidence(evidencias_home, evidencias_away, home_team_name, away_team_name)
    else:
        msg += f"      (Evidências não disponíveis para este mercado)\n"
    
    return msg


def _format_gols_evidence(evidencias_home, evidencias_away, home_team_name, away_team_name):
    """Formata evidências de GOLS dos últimos 4 jogos"""
    msg = f"      {home_team_name} (Casa):\n"
    
    gols_home = evidencias_home.get('gols', [])
    if gols_home:
        for jogo in gols_home[:4]:
            opponent = jogo.get('opponent', 'Adversário')
            result = jogo.get('result', '0-0')
            total = jogo.get('total_goals', 0)
            msg += f"         vs {opponent}: {result} (Total: {total})\n"
        
        # Calcular média
        media = sum(j['total_goals'] for j in gols_home) / len(gols_home)
        msg += f"         📈 Média Gols (Jogos): {media:.1f}\n"
    else:
        msg += f"         (Dados não disponíveis)\n"
    
    msg += f"\n      {away_team_name} (Fora):\n"
    
    gols_away = evidencias_away.get('gols', [])
    if gols_away:
        for jogo in gols_away[:4]:
            opponent = jogo.get('opponent', 'Adversário')
            result = jogo.get('result', '0-0')
            total = jogo.get('total_goals', 0)
            msg += f"         vs {opponent}: {result} (Total: {total})\n"
        
        # Calcular média
        media = sum(j['total_goals'] for j in gols_away) / len(gols_away)
        msg += f"         📉 Média Gols (Jogos): {media:.1f}\n"
    else:
        msg += f"         (Dados não disponíveis)\n"
    
    return msg


def _format_cantos_evidence(evidencias_home, evidencias_away, home_team_name, away_team_name):
    """Formata evidências de CANTOS dos últimos 4 jogos"""
    msg = f"      {home_team_name} (Casa):\n"
    
    cantos_home = evidencias_home.get('cantos', [])
    if cantos_home:
        for jogo in cantos_home[:4]:
            opponent = jogo.get('opponent', 'Adversário')
            corners_for = jogo.get('corners_for', 0)
            total = jogo.get('total_corners', 0)
            msg += f"         vs {opponent}: {corners_for} (Total Jogo: {total})\n"
        
        # Calcular média
        media = sum(j['corners_for'] for j in cantos_home) / len(cantos_home)
        msg += f"         📈 Média Cantos (Próprios): {media:.1f}\n"
    else:
        msg += f"         (Dados não disponíveis)\n"
    
    msg += f"\n      {away_team_name} (Fora):\n"
    
    cantos_away = evidencias_away.get('cantos', [])
    if cantos_away:
        for jogo in cantos_away[:4]:
            opponent = jogo.get('opponent', 'Adversário')
            corners_for = jogo.get('corners_for', 0)
            total = jogo.get('total_corners', 0)
            msg += f"         vs {opponent}: {corners_for} (Total Jogo: {total})\n"
        
        # Calcular média
        media = sum(j['corners_for'] for j in cantos_away) / len(cantos_away)
        msg += f"         📈 Média Cantos (Próprios): {media:.1f}\n"
    else:
        msg += f"         (Dados não disponíveis)\n"
    
    return msg


def _format_cartoes_evidence(evidencias_home, evidencias_away, home_team_name, away_team_name):
    """Formata evidências de CARTÕES dos últimos 4 jogos"""
    msg = f"      {home_team_name} (Casa):\n"
    
    cartoes_home = evidencias_home.get('cartoes', [])
    if cartoes_home:
        for jogo in cartoes_home[:4]:
            opponent = jogo.get('opponent', 'Adversário')
            total_cards = jogo.get('total_cards', 0)
            msg += f"         vs {opponent}: {total_cards} cartões\n"
        
        # Calcular média
        media = sum(j['total_cards'] for j in cartoes_home) / len(cartoes_home)
        msg += f"         📈 Média Cartões: {media:.1f}\n"
    else:
        msg += f"         (Dados não disponíveis)\n"
    
    msg += f"\n      {away_team_name} (Fora):\n"
    
    cartoes_away = evidencias_away.get('cartoes', [])
    if cartoes_away:
        for jogo in cartoes_away[:4]:
            opponent = jogo.get('opponent', 'Adversário')
            total_cards = jogo.get('total_cards', 0)
            msg += f"         vs {opponent}: {total_cards} cartões\n"
        
        # Calcular média
        media = sum(j['total_cards'] for j in cartoes_away) / len(cartoes_away)
        msg += f"         📈 Média Cartões: {media:.1f}\n"
    else:
        msg += f"         (Dados não disponíveis)\n"
    
    return msg


def _format_finalizacoes_evidence(evidencias_home, evidencias_away, home_team_name, away_team_name):
    """Formata evidências de FINALIZAÇÕES dos últimos 4 jogos"""
    msg = f"      {home_team_name} (Casa):\n"
    
    shots_home = evidencias_home.get('finalizacoes', [])
    if shots_home:
        for jogo in shots_home[:4]:
            opponent = jogo.get('opponent', 'Adversário')
            shots_for = jogo.get('shots_for', 0)
            total = jogo.get('total_shots', 0)
            msg += f"         vs {opponent}: {shots_for} (Total Jogo: {total})\n"
        
        # Calcular média
        media = sum(j['shots_for'] for j in shots_home) / len(shots_home)
        msg += f"         📈 Média Finalizações: {media:.1f}\n"
    else:
        msg += f"         (Dados não disponíveis)\n"
    
    msg += f"\n      {away_team_name} (Fora):\n"
    
    shots_away = evidencias_away.get('finalizacoes', [])
    if shots_away:
        for jogo in shots_away[:4]:
            opponent = jogo.get('opponent', 'Adversário')
            shots_for = jogo.get('shots_for', 0)
            total = jogo.get('total_shots', 0)
            msg += f"         vs {opponent}: {shots_for} (Total Jogo: {total})\n"
        
        # Calcular média
        media = sum(j['shots_for'] for j in shots_away) / len(shots_away)
        msg += f"         📈 Média Finalizações: {media:.1f}\n"
    else:
        msg += f"         (Dados não disponíveis)\n"
    
    return msg


def _format_dupla_chance_evidence(evidencias_home, evidencias_away, home_team_name, away_team_name):
    """Formata evidências de DUPLA CHANCE usando dados de gols dos últimos 4 jogos"""
    msg = f"      {home_team_name} (Casa) - Resultados Recentes:\n"

    gols_home = evidencias_home.get('gols', [])
    if gols_home:
        for jogo in gols_home[:4]:
            opponent = jogo.get('opponent', 'Adversário')
            result = jogo.get('result', '?-?')
            team_goals = jogo.get('team_goals', 0)
            msg += f"         vs {opponent}: {result} ({team_goals} gols marcados)\n"

        media = sum(j['team_goals'] for j in gols_home) / len(gols_home)
        msg += f"         📈 Média Gols Marcados (Casa): {media:.1f}\n"
    else:
        msg += f"         (Dados não disponíveis)\n"

    msg += f"\n      {away_team_name} (Fora) - Resultados Recentes:\n"

    gols_away = evidencias_away.get('gols', [])
    if gols_away:
        for jogo in gols_away[:4]:
            opponent = jogo.get('opponent', 'Adversário')
            result = jogo.get('result', '?-?')
            team_goals = jogo.get('team_goals', 0)
            msg += f"         vs {opponent}: {result} ({team_goals} gols marcados)\n"

        media = sum(j['team_goals'] for j in gols_away) / len(gols_away)
        msg += f"         📉 Média Gols Marcados (Fora): {media:.1f}\n"
    else:
        msg += f"         (Dados não disponíveis)\n"

    return msg


def _format_dupla_chance_section(
    palpites_dc: List[Dict],
    evidencias_home: Dict,
    evidencias_away: Dict,
    home_team_name: str,
    away_team_name: str
) -> str:
    """
    Seção DEDICADA de Dupla Chance — sempre renderizada quando há picks aprovados.
    Exibe odds explicitamente, pois o valor comparativo (odd vs prob) é central neste mercado.
    """
    msg = f"🔀 DUPLA CHANCE\n\n"

    for palpite in palpites_dc:
        tipo = palpite.get('tipo', '')
        confianca = palpite.get('confianca', 0)
        probabilidade = palpite.get('probabilidade', 0)
        odd = palpite.get('odd', 0)

        msg += f"   Análise: {tipo}\n"
        msg += f"   Confiança: {confianca:.1f} / 10\n"
        msg += f"   Probabilidade Calculada: {probabilidade:.1f}%\n"
        if odd and odd > 0:
            msg += f"   Odd Disponível: @{odd:.2f}\n"
        else:
            msg += f"   Odd: Não disponível\n"

        justificativa = generate_evidence_based_justification(
            'Dupla Chance', tipo, evidencias_home, evidencias_away, home_team_name, away_team_name
        )
        msg += f"   Justificativa: {justificativa}\n\n"

    # Evidências resumidas
    msg += f"   📊 EVIDÊNCIAS:\n"
    msg += _format_dupla_chance_evidence(evidencias_home, evidencias_away, home_team_name, away_team_name)
    msg += f"\n---\n\n"

    return msg


def _format_gabt_evidence(evidencias_home, evidencias_away, home_team_name, away_team_name):
    """Formata evidências de GABT usando dados de gols dos últimos 4 jogos (placar por tempo)."""
    msg = f"      {home_team_name} (Casa) - Gols por Tempo:\n"

    gols_home = evidencias_home.get('gols', [])
    if gols_home:
        for jogo in gols_home[:4]:
            opponent = jogo.get('opponent', 'Adversário')
            result = jogo.get('result', '?-?')
            total = jogo.get('total_goals', 0)
            msg += f"         vs {opponent}: {result} ({total} gols no jogo)\n"

        media = sum(j['total_goals'] for j in gols_home) / len(gols_home)
        msg += f"         📈 Média Gols/Jogo (Casa): {media:.1f}\n"
    else:
        msg += f"         (Dados não disponíveis)\n"

    msg += f"\n      {away_team_name} (Fora) - Gols por Tempo:\n"

    gols_away = evidencias_away.get('gols', [])
    if gols_away:
        for jogo in gols_away[:4]:
            opponent = jogo.get('opponent', 'Adversário')
            result = jogo.get('result', '?-?')
            total = jogo.get('total_goals', 0)
            msg += f"         vs {opponent}: {result} ({total} gols no jogo)\n"

        media = sum(j['total_goals'] for j in gols_away) / len(gols_away)
        msg += f"         📉 Média Gols/Jogo (Fora): {media:.1f}\n"
    else:
        msg += f"         (Dados não disponíveis)\n"

    return msg


def _format_placar_exato_evidence(evidencias_home, evidencias_away, home_team_name, away_team_name):
    """Formata evidências de PLACAR EXATO usando dados de gols dos últimos 4 jogos."""
    msg = f"      {home_team_name} (Casa) - Resultados Recentes:\n"

    gols_home = evidencias_home.get('gols', [])
    if gols_home:
        for jogo in gols_home[:4]:
            opponent = jogo.get('opponent', 'Adversário')
            result = jogo.get('result', '?-?')
            msg += f"         vs {opponent}: {result}\n"
        media = sum(j['total_goals'] for j in gols_home) / len(gols_home)
        msg += f"         📈 Média Gols/Jogo (Casa): {media:.1f}\n"
    else:
        msg += f"         (Dados não disponíveis)\n"

    msg += f"\n      {away_team_name} (Fora) - Resultados Recentes:\n"

    gols_away = evidencias_away.get('gols', [])
    if gols_away:
        for jogo in gols_away[:4]:
            opponent = jogo.get('opponent', 'Adversário')
            result = jogo.get('result', '?-?')
            msg += f"         vs {opponent}: {result}\n"
        media = sum(j['total_goals'] for j in gols_away) / len(gols_away)
        msg += f"         📉 Média Gols/Jogo (Fora): {media:.1f}\n"
    else:
        msg += f"         (Dados não disponíveis)\n"

    return msg


def _format_placar_exato_section(
    palpites_placar: List[Dict],
    evidencias_home: Dict,
    evidencias_away: Dict,
    home_team_name: str,
    away_team_name: str
) -> str:
    """
    Seção DEDICADA de Placar Exato — renderizada quando há picks aprovados.
    Exibe os placares mais prováveis com probabilidades e odds.
    """
    msg = f"🎯 PLACAR EXATO\n\n"

    for palpite in palpites_placar:
        tipo = palpite.get('tipo', '')
        confianca = palpite.get('confianca', 0)
        probabilidade = palpite.get('probabilidade', 0)
        prob_implicita = palpite.get('prob_implicita', 0.0)
        edge = palpite.get('edge', 0.0)
        odd = palpite.get('odd', 0)

        msg += f"   Análise: {tipo}\n"
        msg += f"   Confiança: {confianca:.1f} / 10\n"
        msg += f"   Probabilidade Calculada: {probabilidade:.2f}% | Prob. Implícita: {prob_implicita:.2f}%\n"
        if edge > 0:
            msg += f"   Edge de Valor: +{edge:.2f}%\n"
        if odd and odd > 0:
            msg += f"   Odd Disponível: @{odd:.2f}\n"
        else:
            msg += f"   Odd: Não disponível\n"

        from analysts.justification_generator import generate_evidence_based_justification
        justificativa = generate_evidence_based_justification(
            'Placar Exato', tipo, evidencias_home, evidencias_away, home_team_name, away_team_name,
            extra={
                'lambda_home': palpite.get('lambda_home'),
                'lambda_away': palpite.get('lambda_away'),
                'edge': edge,
                'probabilidade': probabilidade,
            }
        )
        msg += f"   Justificativa: {justificativa}\n\n"

    msg += f"   📊 EVIDÊNCIAS:\n"
    msg += _format_placar_exato_evidence(evidencias_home, evidencias_away, home_team_name, away_team_name)
    msg += f"\n---\n\n"

    return msg


def _format_handicap_europeu_section(
    palpites_he: List[Dict],
    evidencias_home: Dict,
    evidencias_away: Dict,
    home_team_name: str,
    away_team_name: str
) -> str:
    """
    Seção DEDICADA de Handicap Europeu — 3 desfechos por linha (Casa/Empate/Fora).
    Exibe odds, probabilidade, edge e confiança para cada desfecho com valor real.
    Visualmente distinto do Handicap Asiático.
    """
    msg = f"🏷️ HANDICAP EUROPEU\n\n"
    msg += (
        f"   ℹ️  Handicap Europeu: mercado de 3 desfechos (Casa/Empate/Fora) com ajuste\n"
        f"   de gols aplicado antes do jogo. Sem push — há sempre um vencedor.\n\n"
    )

    for palpite in palpites_he:
        tipo = palpite.get('tipo', '')
        confianca = palpite.get('confianca', 0)
        probabilidade = palpite.get('probabilidade', 0)
        prob_implicita = palpite.get('prob_implicita', 0.0)
        edge = palpite.get('edge', 0.0)
        odd = palpite.get('odd', 0)
        lambda_home = palpite.get('lambda_home')
        lambda_away = palpite.get('lambda_away')

        msg += f"   Análise: {tipo}\n"
        msg += f"   Confiança: {confianca:.1f} / 10\n"
        msg += f"   Probabilidade Calculada: {probabilidade:.2f}% | Prob. Implícita: {prob_implicita:.2f}%\n"
        if edge > 0:
            msg += f"   Edge de Valor: +{edge:.2f}%\n"
        if odd and odd > 0:
            msg += f"   Odd Disponível: @{odd:.2f}\n"
        else:
            msg += f"   Odd: Não disponível\n"

        from analysts.justification_generator import generate_evidence_based_justification
        justificativa = generate_evidence_based_justification(
            'Handicap Europeu', tipo, evidencias_home, evidencias_away, home_team_name, away_team_name,
            extra={
                'lambda_home': lambda_home,
                'lambda_away': lambda_away,
                'edge': edge,
                'probabilidade': probabilidade,
            }
        )
        msg += f"   Justificativa: {justificativa}\n\n"

    msg += f"   📊 EVIDÊNCIAS:\n"
    msg += _format_handicap_europeu_evidence(evidencias_home, evidencias_away, home_team_name, away_team_name)
    msg += f"\n---\n\n"

    return msg


def _format_handicap_europeu_evidence(evidencias_home, evidencias_away, home_team_name, away_team_name):
    """Formata evidências para Handicap Europeu (resultados recentes para contexto de margem)."""
    msg = f"      {home_team_name} (Casa) - Resultados Recentes:\n"

    gols_home = evidencias_home.get('gols', [])
    if gols_home:
        for jogo in gols_home[:4]:
            opponent = jogo.get('opponent', 'Adversário')
            result = jogo.get('result', '?-?')
            msg += f"         vs {opponent}: {result}\n"
        media = sum(j['total_goals'] for j in gols_home) / len(gols_home)
        msg += f"         📈 Média Gols/Jogo (Casa): {media:.1f}\n"
    else:
        msg += f"         (Dados não disponíveis)\n"

    msg += f"\n      {away_team_name} (Fora) - Resultados Recentes:\n"

    gols_away = evidencias_away.get('gols', [])
    if gols_away:
        for jogo in gols_away[:4]:
            opponent = jogo.get('opponent', 'Adversário')
            result = jogo.get('result', '?-?')
            msg += f"         vs {opponent}: {result}\n"
        media = sum(j['total_goals'] for j in gols_away) / len(gols_away)
        msg += f"         📉 Média Gols/Jogo (Fora): {media:.1f}\n"
    else:
        msg += f"         (Dados não disponíveis)\n"

    return msg


def _format_gabt_section(
    palpites_gabt: List[Dict],
    evidencias_home: Dict,
    evidencias_away: Dict,
    home_team_name: str,
    away_team_name: str
) -> str:
    """
    Seção DEDICADA de Gols em Ambos os Tempos — renderizada quando há picks aprovados.
    Exibe odds, probabilidade e confiança para cada opção (Sim / Não).
    """
    msg = f"⏱️ GOLS EM AMBOS OS TEMPOS\n\n"

    for palpite in palpites_gabt:
        tipo = palpite.get('tipo', '')
        confianca = palpite.get('confianca', 0)
        probabilidade = palpite.get('probabilidade', 0)
        odd = palpite.get('odd', 0)

        msg += f"   Análise: {tipo}\n"
        msg += f"   Confiança: {confianca:.1f} / 10\n"
        msg += f"   Probabilidade Calculada: {probabilidade:.1f}%\n"
        if odd and odd > 0:
            msg += f"   Odd Disponível: @{odd:.2f}\n"
        else:
            msg += f"   Odd: Não disponível\n"

        justificativa = generate_evidence_based_justification(
            'Gols Ambos Tempos', tipo, evidencias_home, evidencias_away, home_team_name, away_team_name
        )
        msg += f"   Justificativa: {justificativa}\n\n"

    msg += f"   📊 EVIDÊNCIAS:\n"
    msg += _format_gabt_evidence(evidencias_home, evidencias_away, home_team_name, away_team_name)
    msg += f"\n---\n\n"

    return msg


def _format_primeiro_marcador_evidence(evidencias_home, evidencias_away, home_team_name, away_team_name):
    """Formata evidências de Primeiro a Marcar usando média de gols marcados (ataque)."""
    msg = f"      {home_team_name} (Casa) - Poder Ofensivo Recente:\n"

    gols_home = evidencias_home.get('gols', [])
    if gols_home:
        for jogo in gols_home[:4]:
            opponent = jogo.get('opponent', 'Adversário')
            result = jogo.get('result', '?-?')
            team_goals = jogo.get('team_goals', 0)
            msg += f"         vs {opponent}: {result} ({team_goals} gols marcados)\n"
        media = sum(j['team_goals'] for j in gols_home) / len(gols_home)
        msg += f"         📈 Média Gols Marcados (Casa): {media:.1f}/jogo\n"
    else:
        msg += f"         (Dados não disponíveis)\n"

    msg += f"\n      {away_team_name} (Fora) - Poder Ofensivo Recente:\n"

    gols_away = evidencias_away.get('gols', [])
    if gols_away:
        for jogo in gols_away[:4]:
            opponent = jogo.get('opponent', 'Adversário')
            result = jogo.get('result', '?-?')
            team_goals = jogo.get('team_goals', 0)
            msg += f"         vs {opponent}: {result} ({team_goals} gols marcados)\n"
        media = sum(j['team_goals'] for j in gols_away) / len(gols_away)
        msg += f"         📉 Média Gols Marcados (Fora): {media:.1f}/jogo\n"
    else:
        msg += f"         (Dados não disponíveis)\n"

    return msg


def _format_primeiro_marcador_section(
    palpites_pm: List[Dict],
    evidencias_home: Dict,
    evidencias_away: Dict,
    home_team_name: str,
    away_team_name: str
) -> str:
    """
    Seção DEDICADA de Primeiro a Marcar — renderizada quando há picks aprovados.
    Exibe probabilidades calculadas, odds e edge para cada desfecho: Casa / Fora / Nenhum.
    """
    msg = f"🥇 PRIMEIRO A MARCAR\n\n"
    msg += (
        f"   ℹ️  Qual equipe marcará o primeiro gol? Calculado via modelo de Poisson:\n"
        f"   P(casa) ∝ λ_casa / λ_total; P(nenhum) = e^(-λ_total).\n\n"
    )

    for palpite in palpites_pm:
        tipo = palpite.get('tipo', '')
        confianca = palpite.get('confianca', 0)
        probabilidade = palpite.get('probabilidade', 0)
        prob_implicita = palpite.get('prob_implicita', 0.0)
        edge = palpite.get('edge', 0.0)
        odd = palpite.get('odd', 0)
        lambda_home = palpite.get('lambda_home')
        lambda_away = palpite.get('lambda_away')

        msg += f"   Análise: {tipo}\n"
        msg += f"   Confiança: {confianca:.1f} / 10\n"
        msg += f"   Probabilidade Calculada: {probabilidade:.2f}% | Prob. Implícita: {prob_implicita:.2f}%\n"
        if edge > 0:
            msg += f"   Edge de Valor: +{edge:.2f}%\n"
        if lambda_home is not None and lambda_away is not None:
            msg += f"   λ_casa={lambda_home:.3f} | λ_fora={lambda_away:.3f}\n"
        if odd and odd > 0:
            msg += f"   Odd Disponível: @{odd:.2f}\n"
        else:
            msg += f"   Odd: Não disponível\n"

        from analysts.justification_generator import generate_evidence_based_justification
        justificativa = generate_evidence_based_justification(
            'Primeiro a Marcar', tipo, evidencias_home, evidencias_away, home_team_name, away_team_name,
            extra={
                'lambda_home': lambda_home,
                'lambda_away': lambda_away,
                'edge': edge,
                'probabilidade': probabilidade,
            }
        )
        msg += f"   Justificativa: {justificativa}\n\n"

    msg += f"   📊 EVIDÊNCIAS:\n"
    msg += _format_primeiro_marcador_evidence(evidencias_home, evidencias_away, home_team_name, away_team_name)
    msg += f"\n---\n\n"

    return msg


def _select_diverse_predictions(palpites: List[Dict], max_predictions: int = 5) -> List[Dict]:
    """
    ACTION 2.2 - DIVERSITY LOGIC: Seleciona predições garantindo variedade de mercados.
    
    Se as top 5 predições são todas do mesmo mercado (ex: "Finalizações"),
    selecionamos a melhor predição de cada mercado diferente para apresentar
    um relatório variado e útil.
    
    Args:
        palpites: Lista de predições ordenadas por confiança (desc)
        max_predictions: Número máximo de predições a retornar
    
    Returns:
        Lista de predições com máxima diversidade de mercados
    """
    if not palpites:
        return []
    
    diverse_predictions = []
    mercados_usados = set()
    
    # Primeira passagem: selecionar a melhor predição de cada mercado
    for palpite in palpites:
        mercado = palpite.get('mercado', 'Gols')
        
        if mercado not in mercados_usados:
            diverse_predictions.append(palpite)
            mercados_usados.add(mercado)
            
            if len(diverse_predictions) >= max_predictions:
                break
    
    # Segunda passagem: se ainda temos espaço, adicionar segundas melhores de cada mercado
    if len(diverse_predictions) < max_predictions:
        mercados_segunda_rodada = set()
        
        for palpite in palpites:
            if len(diverse_predictions) >= max_predictions:
                break
                
            mercado = palpite.get('mercado', 'Gols')
            
            # Já adicionamos este palpite na primeira passagem?
            if palpite in diverse_predictions:
                continue
            
            # Podemos adicionar uma segunda predição deste mercado?
            if mercado not in mercados_segunda_rodada:
                diverse_predictions.append(palpite)
                mercados_segunda_rodada.add(mercado)
    
    return diverse_predictions


def _format_sugestoes_taticas_evidence_based(
    palpites: List[Dict],
    evidencias_home: Dict,
    evidencias_away: Dict,
    home_team_name: str,
    away_team_name: str
) -> str:
    """
    Formata SUGESTÕES TÁTICAS com evidências (todas as outras análises).
    
    IMPLEMENTA DIVERSITY LOGIC: Garante variedade de mercados nas sugestões.
    """
    if not palpites:
        return ""
    
    # ACTION 2.2: Aplicar lógica de diversidade
    diverse_palpites = _select_diverse_predictions(palpites, max_predictions=5)
    
    msg = f"🧠 OUTRAS TENDÊNCIAS DE ALTA CONFIANÇA\n\n"
    
    for palpite in diverse_palpites:
        mercado = palpite.get('mercado', 'Gols')
        tipo = palpite.get('tipo', '')
        confianca = palpite.get('confianca', 0)
        
        msg += f"   Mercado: {mercado}\n"
        
        # PHOENIX V4.0 - ALVO #3: PURE ANALYST PROTOCOL - Sem exibição de odds
        msg += f"   Análise: {tipo}\n"
        msg += f"   Confiança: {confianca:.1f} / 10\n"
        
        # Justificativa
        justificativa = generate_evidence_based_justification(
            mercado, tipo, evidencias_home, evidencias_away, home_team_name, away_team_name
        )
        msg += f"   Justificativa: {justificativa}\n\n"
        
        # Evidências resumidas (apenas médias)
        msg += f"   📊 EVIDÊNCIAS:\n"
        msg += _format_evidence_summary(mercado, evidencias_home, evidencias_away, home_team_name, away_team_name)
        msg += f"\n---\n\n"
    
    return msg


def _format_evidence_summary(mercado, evidencias_home, evidencias_away, home_team_name, away_team_name):
    """Formata resumo de evidências (apenas médias)"""
    msg = ""
    
    if mercado == "Gols":
        gols_home = evidencias_home.get('gols', [])
        gols_away = evidencias_away.get('gols', [])
        if gols_home and gols_away:
            media_home = sum(j['total_goals'] for j in gols_home) / len(gols_home)
            media_away = sum(j['total_goals'] for j in gols_away) / len(gols_away)
            msg += f"      {home_team_name}: {media_home:.1f} gols/jogo (casa)\n"
            msg += f"      {away_team_name}: {media_away:.1f} gols/jogo (fora)\n"
    
    elif mercado == "Cantos":
        cantos_home = evidencias_home.get('cantos', [])
        cantos_away = evidencias_away.get('cantos', [])
        if cantos_home and cantos_away:
            media_home = sum(j['corners_for'] for j in cantos_home) / len(cantos_home)
            media_away = sum(j['corners_for'] for j in cantos_away) / len(cantos_away)
            msg += f"      {home_team_name}: {media_home:.1f} cantos/jogo (casa)\n"
            msg += f"      {away_team_name}: {media_away:.1f} cantos/jogo (fora)\n"
    
    elif mercado == "Cartões":
        cartoes_home = evidencias_home.get('cartoes', [])
        cartoes_away = evidencias_away.get('cartoes', [])
        if cartoes_home and cartoes_away:
            media_home = sum(j['total_cards'] for j in cartoes_home) / len(cartoes_home)
            media_away = sum(j['total_cards'] for j in cartoes_away) / len(cartoes_away)
            msg += f"      {home_team_name}: {media_home:.1f} cartões/jogo (casa)\n"
            msg += f"      {away_team_name}: {media_away:.1f} cartões/jogo (fora)\n"
    
    elif mercado == "Finalizações":
        shots_home = evidencias_home.get('finalizacoes', [])
        shots_away = evidencias_away.get('finalizacoes', [])
        if shots_home and shots_away:
            media_home = sum(j['shots_for'] for j in shots_home) / len(shots_home)
            media_away = sum(j['shots_for'] for j in shots_away) / len(shots_away)
            msg += f"      {home_team_name}: {media_home:.1f} finalizações/jogo (casa)\n"
            msg += f"      {away_team_name}: {media_away:.1f} finalizações/jogo (fora)\n"

    elif mercado == "Dupla Chance":
        gols_home = evidencias_home.get('gols', [])
        gols_away = evidencias_away.get('gols', [])
        if gols_home:
            media_home = sum(j['team_goals'] for j in gols_home) / len(gols_home)
            msg += f"      {home_team_name}: {media_home:.1f} gols marcados/jogo (casa)\n"
        if gols_away:
            media_away = sum(j['team_goals'] for j in gols_away) / len(gols_away)
            msg += f"      {away_team_name}: {media_away:.1f} gols marcados/jogo (fora)\n"

    elif mercado == "Gols Ambos Tempos":
        gols_home = evidencias_home.get('gols', [])
        gols_away = evidencias_away.get('gols', [])
        if gols_home:
            media_home = sum(j['total_goals'] for j in gols_home) / len(gols_home)
            msg += f"      {home_team_name}: {media_home:.1f} gols/jogo (casa)\n"
        if gols_away:
            media_away = sum(j['total_goals'] for j in gols_away) / len(gols_away)
            msg += f"      {away_team_name}: {media_away:.1f} gols/jogo (fora)\n"

    elif mercado == "Placar Exato":
        gols_home = evidencias_home.get('gols', [])
        gols_away = evidencias_away.get('gols', [])
        if gols_home:
            media_home = sum(j['total_goals'] for j in gols_home) / len(gols_home)
            msg += f"      {home_team_name}: {media_home:.1f} gols/jogo (casa)\n"
        if gols_away:
            media_away = sum(j['total_goals'] for j in gols_away) / len(gols_away)
            msg += f"      {away_team_name}: {media_away:.1f} gols/jogo (fora)\n"

    elif mercado == "Handicap Europeu":
        gols_home = evidencias_home.get('gols', [])
        gols_away = evidencias_away.get('gols', [])
        if gols_home:
            media_home = sum(j['total_goals'] for j in gols_home) / len(gols_home)
            msg += f"      {home_team_name}: {media_home:.1f} gols/jogo (casa)\n"
        if gols_away:
            media_away = sum(j['total_goals'] for j in gols_away) / len(gols_away)
            msg += f"      {away_team_name}: {media_away:.1f} gols/jogo (fora)\n"

    return msg


def _collect_warnings(palpites: List[Dict]) -> List[str]:
    """Coleta avisos sobre mercados sem odds ou análises indisponíveis"""
    avisos = []
    
    # Verificar se há palpites sem odd
    palpites_sem_odd = [p for p in palpites if not p.get('odd') or p.get('odd') == 0]
    if palpites_sem_odd:
        mercados_sem_odd = list(set(p.get('mercado', 'Desconhecido') for p in palpites_sem_odd))
        for mercado in mercados_sem_odd:
            avisos.append(f"⚠️ Nenhuma odd encontrada na API para o mercado de {mercado}.")
    
    return avisos


def _format_avisos(avisos: List[str]) -> str:
    """Formata seção de avisos"""
    if not avisos:
        return ""
    
    msg = f"⚠️ AVISOS E OBSERVAÇÕES\n"
    for aviso in avisos:
        msg += f"   {aviso}\n"
    msg += "\n"
    
    return msg


def format_confidence_debug_report(
    jogo: Dict,
    all_predictions: Dict,
    master_analysis: Dict,
    threshold: float = 7.0
) -> str:
    """
    MODO VERBOSO: Relatório de depuração de confiança.
    Mostra TODOS os palpites (aprovados e reprovados) com detalhamento completo do cálculo de confiança.
    
    Args:
        jogo: Dados do jogo
        all_predictions: Dicionário com TODOS os palpites de todos os mercados
        master_analysis: Análise completa do Master Analyzer
        threshold: Threshold de confiança para aprovação (padrão: 7.0)
    
    Returns:
        str: Relatório de depuração formatado
    """
    time_casa = jogo['teams']['home']['name']
    time_fora = jogo['teams']['away']['name']
    liga_nome = jogo['league']['name']
    script_name = master_analysis.get('analysis_summary', {}).get('selected_script', 'N/A')
    
    # Header
    msg = "--- 🕵️‍♂️ RELATÓRIO DE DEPURAÇÃO DE CONFIANÇA 🕵️‍♂️ ---\n\n"
    msg += f"JOGO: {time_casa} vs {time_fora}\n"
    msg += f"LIGA: {liga_nome}\n"
    msg += f"SCRIPT TÁTICO: {script_name}\n"
    msg += f"THRESHOLD DE APROVAÇÃO: {threshold:.1f}\n\n"
    
    # Processar cada mercado
    mercados_ordem = ['Gols', 'Resultado', 'Cantos', 'BTTS', 'Cartões', 'Finalizações', 'Handicaps', 'Dupla Chance', 'Gols Ambos Tempos', 'Placar Exato', 'Handicap Europeu']
    
    for mercado_nome in mercados_ordem:
        if mercado_nome not in all_predictions or not all_predictions[mercado_nome]:
            continue
        
        mercado_data = all_predictions[mercado_nome]
        palpites = mercado_data.get('palpites', [])
        
        if not palpites:
            continue
        
        msg += f"--- MERCADO: {mercado_nome.upper()} ---\n"
        
        for palpite in palpites:
            tipo = palpite.get('tipo', 'N/A')
            confianca = palpite.get('confianca', 0.0)
            odd = palpite.get('odd')
            breakdown = palpite.get('confidence_breakdown', {})
            
            msg += f"Palpite: {tipo}\n"
            
            # Mostrar breakdown se disponível
            if breakdown:
                # Formatar probabilidade base
                prob_base = breakdown.get('probabilidade_base')
                if isinstance(prob_base, (int, float)):
                    msg += f"- Probabilidade Base: {prob_base:.1f}%\n"
                else:
                    msg += f"- Probabilidade Base: N/A\n"
                
                # Formatar confiança base
                conf_base = breakdown.get('confianca_base')
                if isinstance(conf_base, (int, float)):
                    msg += f"- Base Score: {conf_base:.1f}\n"
                else:
                    msg += f"- Base Score: N/A\n"
                
                # Formatar modificadores com verificação de tipo
                mod_script = breakdown.get('modificador_script', 0)
                mod_value = breakdown.get('modificador_value', 0)
                mod_odd = breakdown.get('modificador_odd', 0)
                
                if isinstance(mod_script, (int, float)):
                    msg += f"- Modificador Script: {mod_script:+.1f}\n"
                else:
                    msg += f"- Modificador Script: N/A\n"
                
                if isinstance(mod_value, (int, float)):
                    msg += f"- Modificador Value: {mod_value:+.1f}\n"
                else:
                    msg += f"- Modificador Value: N/A\n"
                
                if isinstance(mod_odd, (int, float)):
                    msg += f"- Modificador Odd: {mod_odd:+.1f}\n"
                else:
                    msg += f"- Modificador Odd: N/A\n"
            else:
                msg += f"- Confiança Calculada: {confianca:.1f}\n"
                msg += f"- (Breakdown não disponível para este mercado)\n"
            
            msg += f"- FINAL SCORE: {confianca:.1f}\n"
            
            if odd:
                msg += f"- ODD: @{odd:.2f}\n"
            else:
                msg += f"- ODD: Não disponível\n"
            
            # Status
            if confianca >= threshold:
                msg += f"- STATUS: ✅ APROVADO (Acima do threshold {threshold:.1f})\n"
            else:
                msg += f"- STATUS: ❌ REPROVADO (Abaixo do threshold {threshold:.1f})\n"
            
            msg += "\n"
        
        msg += "\n"
    
    msg += "--- FIM DO RELATÓRIO ---\n"
    
    return msg


def _format_htft_section(
    palpites_htft: List[Dict],
    evidencias_home: Dict,
    evidencias_away: Dict,
    home_team_name: str,
    away_team_name: str,
) -> str:
    """Seção dedicada HT/FT — mostra as top combinações intervalo+final."""
    msg = "⏱️ HALF-TIME / FULL-TIME\n\n"
    msg += (
        "   ℹ️  Resultado ao intervalo e ao final calculados via Poisson bivariado.\n"
        "   Apenas combinações com probabilidade suficiente são exibidas.\n\n"
    )

    for palpite in palpites_htft:
        tipo = palpite.get('tipo', '')
        confianca = palpite.get('confianca', 0)
        probabilidade = palpite.get('probabilidade', 0)
        odd = palpite.get('odd')

        msg += f"   Cenário: {tipo}\n"
        msg += f"   Confiança: {confianca:.1f} / 10\n"
        msg += f"   Probabilidade Calculada: {probabilidade:.1f}%\n"
        if odd:
            msg += f"   Odd Disponível: @{odd:.2f}\n"
        else:
            msg += "   Odd: Não disponível\n"

        justificativa = generate_evidence_based_justification(
            'HT/FT', tipo, evidencias_home, evidencias_away,
            home_team_name, away_team_name,
            extra={'probabilidade': probabilidade},
        )
        msg += f"   Justificativa: {justificativa}\n\n"

    msg += "   📊 EVIDÊNCIAS (GOLS):\n"
    msg += _format_gols_evidence(evidencias_home, evidencias_away, home_team_name, away_team_name)
    msg += "\n---\n\n"
    return msg


def _format_win_to_nil_section(
    palpites_wtn: List[Dict],
    evidencias_home: Dict,
    evidencias_away: Dict,
    home_team_name: str,
    away_team_name: str,
) -> str:
    """Seção dedicada Win to Nil — vitória sem sofrer gol."""
    msg = "🔒 WIN TO NIL\n\n"
    msg += (
        "   ℹ️  Probabilidade de vencer sem sofrer gol: P(vitória) × P(clean sheet).\n"
        "   Calculado via Poisson: P(clean sheet) = e^(-λ_adversário).\n\n"
    )

    for palpite in palpites_wtn:
        tipo = palpite.get('tipo', '')
        confianca = palpite.get('confianca', 0)
        probabilidade = palpite.get('probabilidade', 0)
        odd = palpite.get('odd')

        msg += f"   Análise: {tipo}\n"
        msg += f"   Confiança: {confianca:.1f} / 10\n"
        msg += f"   Probabilidade Calculada: {probabilidade:.1f}%\n"
        if odd:
            msg += f"   Odd Disponível: @{odd:.2f}\n"
        else:
            msg += "   Odd: Não disponível\n"

        justificativa = generate_evidence_based_justification(
            'Win to Nil', tipo, evidencias_home, evidencias_away,
            home_team_name, away_team_name,
            extra={'probabilidade': probabilidade},
        )
        msg += f"   Justificativa: {justificativa}\n\n"

    msg += "   📊 EVIDÊNCIAS (GOLS):\n"
    msg += _format_gols_evidence(evidencias_home, evidencias_away, home_team_name, away_team_name)
    msg += "\n---\n\n"
    return msg


def _format_draw_no_bet_section(
    palpites_dnb: List[Dict],
    evidencias_home: Dict,
    evidencias_away: Dict,
    home_team_name: str,
    away_team_name: str,
) -> str:
    """Seção dedicada Draw No Bet — exclui empate, aposta retornada se empatar."""
    msg = "🔄 DRAW NO BET\n\n"
    msg += (
        "   ℹ️  Aposta excluindo o empate: se o jogo terminar empatado, a aposta é devolvida.\n"
        "   P(DNB Casa) = P(Vitória Casa) / (P(V.Casa) + P(V.Fora))\n\n"
    )

    for palpite in palpites_dnb:
        tipo = palpite.get('tipo', '')
        confianca = palpite.get('confianca', 0)
        probabilidade = palpite.get('probabilidade', 0)
        odd = palpite.get('odd')

        msg += f"   Análise: {tipo}\n"
        msg += f"   Confiança: {confianca:.1f} / 10\n"
        msg += f"   Probabilidade Condicional: {probabilidade:.1f}%\n"
        if odd:
            msg += f"   Odd Disponível: @{odd:.2f}\n"
        else:
            msg += "   Odd: Não disponível\n"

        justificativa = generate_evidence_based_justification(
            'Draw No Bet', tipo, evidencias_home, evidencias_away,
            home_team_name, away_team_name,
            extra={'probabilidade': probabilidade},
        )
        msg += f"   Justificativa: {justificativa}\n\n"

    msg += "   📊 EVIDÊNCIAS (GOLS):\n"
    msg += _format_gols_evidence(evidencias_home, evidencias_away, home_team_name, away_team_name)
    msg += "\n---\n\n"
    return msg


# Manter compatibilidade com código existente
def format_phoenix_dossier(*args, **kwargs):
    """Wrapper para compatibilidade"""
    return format_evidence_based_dossier(*args, **kwargs)


def format_dossier_message(*args, **kwargs):
    """Wrapper para compatibilidade"""
    return format_evidence_based_dossier(*args, **kwargs)
