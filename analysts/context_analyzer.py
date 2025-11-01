# analysts/context_analyzer.py

from config import QUALITY_SCORES, LEAGUE_WEIGHTING_FACTOR, MERCADOS_VETADOS_POR_SCRIPT


def calculate_dynamic_qsc(team_stats, team_id, classificacao=None, team_name=None, league_id=None, rodada_atual=0):
    """
    LAYER 1 - PHOENIX V2.0: Calcula Quality Score Composto e Dinâmico (QSC).
    
    O QSC é uma média ponderada de 4 componentes:
    1. Base QS (Reputation) - 25% peso - do dicionário QUALITY_SCORES
    2. Position QS (Table) - 30% peso - posição na tabela
    3. Goal Difference QS - 25% peso - saldo de gols
    4. Recent Form QS - 20% peso - últimos 5 jogos
    
    NOVIDADES PHOENIX V2.0:
    - League Weighting Factor: Multiplica QSC final pelo peso da liga
    - Season Start Adjustment: Primeiras 5 rodadas usam blend 50/50 entre table-based e reputation
    
    Args:
        team_stats: Estatísticas gerais do time
        team_id: ID do time
        classificacao: Tabela de classificação da liga
        team_name: Nome do time (para buscar na classificação)
        league_id: ID da liga (para League Weighting Factor)
        rodada_atual: Rodada atual da liga (para Season Start Adjustment)
    
    Returns:
        int: QSC Dynamic (0-100)
    """
    DEFAULT_BASE_QS = 70
    DEFAULT_LEAGUE_WEIGHT = 0.70
    
    # 1. BASE QS (REPUTATION) - 25% peso
    base_qs = QUALITY_SCORES.get(team_id, DEFAULT_BASE_QS)
    
    # 2. POSITION QS (TABLE) - 30% peso
    position_qs = 50  # Neutro
    if classificacao and team_name:
        for team_info in classificacao:
            if team_info['team']['name'] == team_name:
                rank = team_info['rank']
                total_teams = len(classificacao)
                # 1º lugar = 100, Último = 50
                position_qs = 100 - ((rank - 1) / (total_teams - 1)) * 50 if total_teams > 1 else 75
                break
    
    # 3. GOAL DIFFERENCE QS - 25% peso
    goal_diff_qs = 50  # Neutro
    goals = team_stats.get('goals', {})
    goals_for = goals.get('for', {}).get('total', {}).get('total', 0)
    goals_against = goals.get('against', {}).get('total', {}).get('total', 0)
    goal_diff = goals_for - goals_against
    
    # Saldo >= +20 = 100, Saldo <= -20 = 0
    if goal_diff >= 20:
        goal_diff_qs = 100
    elif goal_diff <= -20:
        goal_diff_qs = 0
    else:
        goal_diff_qs = 50 + (goal_diff / 20) * 50
    
    # 4. RECENT FORM QS - 20% peso
    form_qs = 50  # Neutro
    form_string = team_stats.get('form', '')
    if form_string:
        recent_form = form_string[-5:]  # Últimos 5 jogos
        wins = recent_form.count('W')
        draws = recent_form.count('D')
        losses = recent_form.count('L')
        
        # 5W = 100, 5L = 0
        if wins == 5:
            form_qs = 100
        elif wins == 4:
            form_qs = 85
        elif wins == 3:
            form_qs = 70
        elif wins == 2:
            form_qs = 60
        elif wins == 1:
            form_qs = 52
        elif losses == 5:
            form_qs = 0
        elif losses == 4:
            form_qs = 15
        elif losses == 3:
            form_qs = 30
        else:
            form_qs = 50
    
    # --- SEASON START ADJUSTMENT (PRIMEIRAS 5 RODADAS) ---
    # Nas primeiras 5 rodadas, a tabela não é confiável
    # Usar blend 50/50 entre Position QS e Base QS (reputation)
    if rodada_atual > 0 and rodada_atual <= 5:
        position_qs_original = position_qs
        position_qs = (position_qs * 0.5) + (base_qs * 0.5)
        print(f"    🔄 SEASON START ADJUSTMENT (Rodada {rodada_atual}): Position QS ajustado de {int(position_qs_original)} para {int(position_qs)}")
    
    # MÉDIA PONDERADA
    qsc = (
        base_qs * 0.25 +
        position_qs * 0.30 +
        goal_diff_qs * 0.25 +
        form_qs * 0.20
    )
    
    # --- LEAGUE WEIGHTING FACTOR ---
    # Multiplicar QSC pelo peso da liga
    league_weight = LEAGUE_WEIGHTING_FACTOR.get(league_id, DEFAULT_LEAGUE_WEIGHT) if league_id else DEFAULT_LEAGUE_WEIGHT
    qsc_before_league_weight = qsc
    qsc = qsc * league_weight
    
    qsc_final = int(round(qsc))
    
    print(f"    🧠 QSC DINÂMICO ({team_name}): {qsc_final}/100")
    print(f"       Base QS: {base_qs} | Position QS: {int(position_qs)} | Goal Diff QS: {int(goal_diff_qs)} | Form QS: {int(form_qs)}")
    if league_id:
        print(f"       ⚖️ League Weight: {league_weight:.2f} (QSC antes: {int(qsc_before_league_weight)}, depois: {qsc_final})")
    
    return qsc_final


def analisar_compatibilidade_ofensiva_defensiva(stats_casa, stats_fora):
    """
    Analisa se o ataque de um time se encaixa bem contra a defesa do outro.
    Retorna insights sobre a dinâmica do confronto.
    """
    insights = []

    # Gols: Casa ataca muito E Fora defende mal?
    if stats_casa['casa']['gols_marcados'] >= 1.8 and stats_fora['fora']['gols_sofridos'] >= 1.5:
        insights.append({
            'tipo': 'gols_casa_favoravel',
            'descricao': f"⚔️ ATAQUE CASA vs DEFESA FRÁGIL FORA! Casa marca {stats_casa['casa']['gols_marcados']:.1f} gols/jogo enquanto Fora sofre {stats_fora['fora']['gols_sofridos']:.1f}. Cenário IDEAL para gols da casa!",
            'fator_multiplicador': 1.3
        })

    # Gols: Fora ataca muito E Casa defende mal?
    if stats_fora['fora']['gols_marcados'] >= 1.3 and stats_casa['casa']['gols_sofridos'] >= 1.3:
        insights.append({
            'tipo': 'gols_fora_favoravel',
            'descricao': f"💥 VISITANTE OFENSIVO vs CASA VULNERÁVEL! Fora marca {stats_fora['fora']['gols_marcados']:.1f} quando visita e Casa sofre {stats_casa['casa']['gols_sofridos']:.1f} em casa. Gols do visitante PROVÁVEIS!",
            'fator_multiplicador': 1.25
        })

    # Ambos ataques fortes E ambas defesas fracas = Festival de gols
    if (stats_casa['casa']['gols_marcados'] >= 1.5 and stats_fora['fora']['gols_marcados'] >= 1.2 and
        stats_casa['casa']['gols_sofridos'] >= 1.2 and stats_fora['fora']['gols_sofridos'] >= 1.2):
        insights.append({
            'tipo': 'festival_gols',
            'descricao': f"🎆 EXPLOSÃO DE GOLS ESPERADA! Ambos atacam bem (Casa {stats_casa['casa']['gols_marcados']:.1f}, Fora {stats_fora['fora']['gols_marcados']:.1f}) E ambos defendem mal. Prepare a pipoca!",
            'fator_multiplicador': 1.4
        })

    # Ambas defesas SÓLIDAS = Jogo truncado
    if stats_casa['casa']['gols_sofridos'] <= 0.8 and stats_fora['fora']['gols_sofridos'] <= 0.8:
        insights.append({
            'tipo': 'jogo_truncado',
            'descricao': f"🛡️ BATALHA DE MURALHAS! Casa sofre apenas {stats_casa['casa']['gols_sofridos']:.1f} gols/jogo e Fora {stats_fora['fora']['gols_sofridos']:.1f}. Jogo TRAVADO esperado!",
            'fator_multiplicador': 0.7
        })

    # Cantos: Casa força muito E Fora sofre muitos cantos
    cantos_casa = stats_casa['casa'].get('cantos_feitos', 0)
    cantos_fora_sofre = stats_fora['fora'].get('cantos_sofridos', 0)

    if cantos_casa >= 5.5 and cantos_fora_sofre >= 5.0:
        insights.append({
            'tipo': 'cantos_casa_favoravel',
            'descricao': f"🚩 PRESSÃO OFENSIVA DA CASA! Time da casa força {cantos_casa:.1f} cantos/jogo e visitante costuma ceder {cantos_fora_sofre:.1f}. MUITOS escanteios para a casa!",
            'fator_multiplicador': 1.25
        })

    return insights


def analisar_importancia_jogo(classificacao, pos_casa, pos_fora, rodada_atual, total_rodadas=38):
    """
    Avalia a importância e motivação do jogo baseado em contexto da temporada.
    """
    if not classificacao or pos_casa == "N/A" or pos_fora == "N/A":
        return None

    total_times = len(classificacao)
    progresso_temporada = rodada_atual / total_rodadas

    # Reta final da temporada (últimas 25% das rodadas)
    reta_final = progresso_temporada >= 0.75

    contextos = []

    # Derby/Clássico (times próximos na tabela e posições altas)
    if abs(pos_casa - pos_fora) <= 3 and pos_casa <= 6 and pos_fora <= 6:
        contextos.append({
            'tipo': 'confronto_direto_topo',
            'descricao': f"⭐ CONFRONTO DIRETO NO TOPO! {pos_casa}º vs {pos_fora}º - Pontos diretos na briga por classificação!",
            'intensidade': 'ALTA',
            'efeito': 'Jogo mais ABERTO e AGRESSIVO. Ambos vão buscar a vitória.'
        })

    # Luta contra rebaixamento
    zona_rebaixamento = total_times - 3
    if pos_casa >= zona_rebaixamento or pos_fora >= zona_rebaixamento:
        if reta_final:
            contextos.append({
                'tipo': 'batalha_sobrevivencia',
                'descricao': f"🆘 JOGO DE SEIS PONTOS! Reta final e pelo menos um time na zona de rebaixamento. DECISIVO!",
                'intensidade': 'EXTREMA',
                'efeito': 'Jogo TRUNCADO e NERVOSO. Equipes podem se FECHAR mais.'
            })
        else:
            contextos.append({
                'tipo': 'preocupacao_rebaixamento',
                'descricao': f"⚠️ Time(s) em posição delicada na tabela. Necessidade de pontuar URGENTE!",
                'intensidade': 'MÉDIA-ALTA',
                'efeito': 'Time mandante pode pressionar mais, visitante pode se FECHAR.'
            })

    # Time pequeno vs gigante (diferença > 10 posições)
    if abs(pos_casa - pos_fora) >= 10:
        if pos_casa < pos_fora:
            contextos.append({
                'tipo': 'favorito_claro_casa',
                'descricao': f"🏠 FAVORITO ABSOLUTO em casa! Diferença de {abs(pos_casa - pos_fora)} posições na tabela.",
                'intensidade': 'MÉDIA',
                'efeito': 'Casa deve DOMINAR. Visitante pode se FECHAR e jogar no contra-ataque.'
            })
        else:
            contextos.append({
                'tipo': 'zebra_possivel',
                'descricao': f"🎲 Time menor recebe gigante! Casa jogando em seus domínios pode SURPREENDER.",
                'intensidade': 'MÉDIA',
                'efeito': 'Casa MOTIVADA pelo desafio. Jogo pode ser mais EQUILIBRADO do que parece.'
            })

    # Meio de tabela tranquilo (nenhum objetivo claro)
    if (8 <= pos_casa <= total_times - 5 and 8 <= pos_fora <= total_times - 5 and 
        not reta_final):
        contextos.append({
            'tipo': 'jogo_morno',
            'descricao': f"😴 Times no meio da tabela sem objetivos claros. Jogo pode ser BUROCRÁTICO.",
            'intensidade': 'BAIXA',
            'efeito': 'Ritmo MODERADO. Menos intensidade que jogos decisivos.'
        })

    return contextos if contextos else None


def analisar_estilo_jogo(stats_casa, stats_fora):
    """
    Identifica estilos de jogo e dinâmicas de confronto.
    """
    estilos = []

    # Time que começa devagar (poucos gols no 1º tempo)
    # Estimativa: se marca poucos gols no geral, provavelmente começa devagar
    if stats_casa['casa']['gols_marcados'] <= 1.0:
        estilos.append({
            'time': 'casa',
            'estilo': 'COMEÇA DEVAGAR',
            'descricao': f"🐌 Casa é time que ESQUENTA aos poucos (apenas {stats_casa['casa']['gols_marcados']:.1f} gols/jogo). Primeiro tempo pode ser MORNO."
        })

    if stats_fora['fora']['gols_marcados'] <= 0.8:
        estilos.append({
            'time': 'fora',
            'estilo': 'POUCO OFENSIVO FORA',
            'descricao': f"🔒 Visitante muito CAUTELOSO quando joga fora ({stats_fora['fora']['gols_marcados']:.1f} gols/jogo). Tende a se FECHAR."
        })

    # Time agressivo (muitos gols e cantos)
    cantos_casa = stats_casa['casa'].get('cantos_feitos', 0)
    if stats_casa['casa']['gols_marcados'] >= 2.0 and cantos_casa >= 6.0:
        estilos.append({
            'time': 'casa',
            'estilo': 'ULTRA OFENSIVO',
            'descricao': f"⚡ Casa é MÁQUINA OFENSIVA! {stats_casa['casa']['gols_marcados']:.1f} gols e {cantos_casa:.1f} cantos por jogo. Pressão CONSTANTE!"
        })

    # Time equilibrado (defende e ataca bem)
    if (1.3 <= stats_casa['casa']['gols_marcados'] <= 1.8 and 
        stats_casa['casa']['gols_sofridos'] <= 1.0):
        estilos.append({
            'time': 'casa',
            'estilo': 'EQUILIBRADO',
            'descricao': f"⚖️ Casa é time SÓLIDO e EQUILIBRADO. Marca {stats_casa['casa']['gols_marcados']:.1f} e sofre apenas {stats_casa['casa']['gols_sofridos']:.1f}."
        })

    return estilos if estilos else None


def gerar_analise_contextual_completa(stats_casa, stats_fora, classificacao, pos_casa, pos_fora, rodada_atual):
    """
    Combina todas as análises contextuais em um relatório completo.
    """
    relatorio = {
        'compatibilidade': analisar_compatibilidade_ofensiva_defensiva(stats_casa, stats_fora),
        'importancia': analisar_importancia_jogo(classificacao, pos_casa, pos_fora, rodada_atual),
        'estilos': analisar_estilo_jogo(stats_casa, stats_fora)
    }

    return relatorio


# ========================================
# PHOENIX V3.0 - DEPRECATED FUNCTIONS PURGED
# ========================================
# As seguintes funções foram DELETADAS durante a refatoração V3.0:
#
# 1. get_quality_scores() -> Deprecada, use calculate_dynamic_qsc()
# 2. definir_perfil_partida() -> Removida, lógica de perfil movida para master_analyzer
# 3. filtrar_mercados_por_contexto() -> Removida, filtragem agora é responsabilidade do dossier_formatter
# 4. ajustar_confianca_por_script() -> Integrado em confidence_calculator.apply_tactical_script_modifier()
# 5. verificar_veto_mercado() -> Integrado em confidence_calculator.calculate_final_confidence()
#
# ARQUIVO SIMPLIFICADO: context_analyzer.py agora contém APENAS funções de análise contextual:
# - calculate_dynamic_qsc()
# - analisar_compatibilidade_ofensiva_defensiva()
# - analisar_importancia_jogo()
# - analisar_estilo_jogo()
# - gerar_analise_contextual_completa()
# ========================================
