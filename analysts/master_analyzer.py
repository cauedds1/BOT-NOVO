import sys
import os
import math
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_client import (
    buscar_estatisticas_gerais_time,
    buscar_estatisticas_jogo,
    buscar_h2h,
    buscar_lesoes_jogo
)


HIGH_ALTITUDE_CITIES = ['La Paz', 'Quito', 'Bogotá', 'Cusco', 'Sucre', 'Cochabamba']


def _calculate_moment_score(team_stats):
    """
    🔥 NOVO: Calcula MOMENTO ATUAL (últimos 5 jogos) - separado da reputação histórica.
    
    Um time "pequeno" em sequência de vitórias (Mirassol) pode ter momento 90+.
    Um time "grande" em crise pode ter momento 30.
    
    Args:
        team_stats: Dicionário com estatísticas do time
    
    Returns:
        int: Momento Score (0-100) baseado APENAS em forma recente
    """
    moment = 50  # Neutro
    
    form_string = team_stats.get('form', '')
    if not form_string:
        return moment
    
    recent_form = form_string[-5:]  # Últimos 5 jogos
    
    # Contar resultados recentes
    wins = recent_form.count('W')
    draws = recent_form.count('D')
    losses = recent_form.count('L')
    
    # 🔥 TIME EM CHAMAS (4-5 vitórias recentes)
    if wins >= 4:
        moment = 95
        print(f"    🔥 TIME EM CHAMAS detectado! ({wins}W nos últimos 5)")
    elif wins >= 3:
        moment = 80  # Momento excelente
    elif wins >= 2:
        moment = 65  # Momento bom
    elif wins == 1:
        moment = 55  # Levemente positivo
    elif losses >= 4:
        moment = 20  # Crise total
    elif losses >= 3:
        moment = 35  # Momento ruim
    
    # Ajuste por gols recentes
    goals = team_stats.get('goals', {})
    goals_avg = goals.get('for', {}).get('average', {}).get('total', 0)
    goals_avg = float(goals_avg) if goals_avg else 0.0
    
    if goals_avg > 2.5:
        moment = min(moment + 10, 100)  # Ataque potente
    elif goals_avg < 0.8:
        moment = max(moment - 10, 0)  # Ataque fraco
    
    return moment


# Razões que indicam lesão grave → ausência quase certa de titular
_SERIOUS_INJURY_KEYWORDS = frozenset({
    'acl', 'knee', 'hamstring', 'ligament', 'muscle', 'fracture',
    'broken', 'torn', 'surgery', 'rupture', 'thigh', 'ankle', 'calf',
    'groin', 'shoulder', 'tendon', 'meniscus', 'foot', 'quadricep'
})


def _injury_weight(injury):
    """
    TASK 4 - PHOENIX V4.0: Peso de impacto de uma ausência individual.

    Classifica cada ausência com base no TIPO (garantido vs questionável) e
    na RAZÃO (lesão grave vs leve), funcionando como proxy de importância do
    jogador quando ratings não estão disponíveis no endpoint /injuries.

    Pesos:
      2.0 — Suspenso OU "Missing Fixture" (ausência confirmada, geralmente titular)
      1.0 — Lesão grave (ACL, hamstring, cirurgia, fratura, etc.) — provável titular
      0.5 — "Questionable" / lesão leve / razão desconhecida (pode jogar)

    Args:
        injury: Dict com {name, type, reason, team_id}

    Returns:
        float: Peso do impacto desta ausência (0.5, 1.0 ou 2.0)
    """
    injury_type = (injury.get('type') or '').lower()
    reason = (injury.get('reason') or '').lower()

    # Confirmados ausentes = maior peso (suspensão ou confirmação explícita)
    if 'suspend' in injury_type or 'missing' in injury_type:
        return 2.0

    # Lesão grave com palavra-chave reconhecida = titular provavelmente fora
    if any(kw in reason for kw in _SERIOUS_INJURY_KEYWORDS):
        return 1.0

    # Questionável ou razão desconhecida = baixo impacto (pode recuperar)
    return 0.5


def _calculate_injury_impact(injuries):
    """
    TASK 4 - PHOENIX V4.0: Calcula penalidade no Momento baseada em ausências ponderadas.

    Usa _injury_weight() para distinguir ausências críticas (suspensos, lesões graves)
    de ausências menores (questionáveis, lesões leves), evitando penalizar o Momento
    de forma igual para jogadores chave e atletas de backup.

    Escala de penalidade por peso efetivo total:
      < 1.0  → -0 pts  (impacto negligível)
      ≥ 1.0  → -5 pts
      ≥ 2.5  → -10 pts
      ≥ 5.0  → -15 pts

    Args:
        injuries: Lista de dicts com jogadores ausentes [{name, type, reason, team_id}]

    Returns:
        int: Pontos de penalidade a subtrair do Momento Score (0, 5, 10 ou 15)
    """
    if not injuries:
        return 0
    effective_weight = sum(_injury_weight(p) for p in injuries)
    if effective_weight >= 5.0:
        return 15
    elif effective_weight >= 2.5:
        return 10
    elif effective_weight >= 1.0:
        return 5
    return 0


def _get_injury_role_label(injuries):
    """
    Infere o papel predominante dos jogadores lesionados com base em palavras-chave
    na razão/tipo da lesão e em keywords de posição quando disponíveis.

    A API /injuries nem sempre retorna posição diretamente; usamos heurística:
      - Palavras-chave de goleiro  → 'defensive'
      - Palavras-chave de atacante → 'offensive'
      - Sem evidência clara        → 'mixed'

    Returns:
        str: 'offensive' | 'defensive' | 'mixed'
    """
    if not injuries:
        return "mixed"

    _GOALKEEPER_KW = frozenset({'goalkeeper', 'keeper', 'portero', 'goleiro', 'gk'})
    _FORWARD_KW    = frozenset({'forward', 'striker', 'attacker', 'winger', 'atacante',
                                'centroavante', 'ponta', 'delantero'})
    _DEFENDER_KW   = frozenset({'defender', 'centre-back', 'center-back', 'fullback',
                                'back', 'defensor', 'zagueiro', 'lateral'})

    offense_score = 0
    defense_score = 0

    for p in injuries:
        name_lower    = (p.get('name') or '').lower()
        reason_lower  = (p.get('reason') or '').lower()
        pos_lower     = (p.get('position') or '').lower()  # presente se API retornar
        combined      = f"{name_lower} {reason_lower} {pos_lower}"

        if any(kw in combined for kw in _GOALKEEPER_KW | _DEFENDER_KW):
            defense_score += 1
        if any(kw in combined for kw in _FORWARD_KW):
            offense_score += 1

    if offense_score > defense_score:
        return "offensive"
    elif defense_score > offense_score:
        return "defensive"
    return "mixed"


def _get_injury_severity_label(injuries):
    """
    TASK 4 - PHOENIX V4.0: Mapeia ausências ponderadas para rótulo de severidade.

    Usa _injury_weight() para classificar apenas ausências de impacto real
    (suspensos, lesões graves) — "questionáveis" têm peso reduzido e raramente
    atingem os limiares superiores sozinhos.

    Limiar por peso efetivo total:
      < 1.0  → "none"
      ≥ 1.0  → "minor"
      ≥ 2.5  → "moderate"
      ≥ 5.0  → "severe"

    Args:
        injuries: Lista de dicts com jogadores ausentes [{name, type, reason, team_id}]

    Returns:
        str: "none" | "minor" | "moderate" | "severe"
    """
    if not injuries:
        return "none"
    effective_weight = sum(_injury_weight(p) for p in injuries)
    if effective_weight >= 5.0:
        return "severe"
    elif effective_weight >= 2.5:
        return "moderate"
    elif effective_weight >= 1.0:
        return "minor"
    return "none"


def _calculate_power_score(team_stats):
    """
    Calcula Power Score HISTÓRICO (0-100) baseado em win rate e saldo de gols da temporada.
    NOTA: Agora separado do MOMENTO (forma recente).
    
    Args:
        team_stats: Dicionário com estatísticas do time
    
    Returns:
        int: Power Score entre 0 e 100 (reputação histórica)
    """
    score = 50
    
    # Win rate da temporada (peso moderado)
    fixtures = team_stats.get('fixtures', {})
    played = fixtures.get('played', {}).get('total', 0)
    wins_total = fixtures.get('wins', {}).get('total', 0)
    
    if played > 0:
        win_rate = wins_total / played
        score += int(win_rate * 25)  # Máx +25
    
    # Saldo de gols da temporada
    goals = team_stats.get('goals', {})
    goals_for = goals.get('for', {}).get('total', {}).get('total', 0)
    goals_against = goals.get('against', {}).get('total', {}).get('total', 0)
    goal_diff = goals_for - goals_against
    
    if goal_diff > 15:
        score += 20
    elif goal_diff > 10:
        score += 15
    elif goal_diff > 5:
        score += 10
    elif goal_diff > 0:
        score += 5
    elif goal_diff < -15:
        score -= 20
    elif goal_diff < -10:
        score -= 15
    elif goal_diff < -5:
        score -= 10
    elif goal_diff < 0:
        score -= 5
    
    return max(0, min(100, score))


def _calculate_tactical_profile(team_stats, context='total'):
    """
    🧠 NOVO: Calcula perfil tático do time - como ele JOGA (volume de jogo).
    
    Usa dados REAIS de cantos e finalizações quando disponíveis na API.
    
    Args:
        team_stats: Estatísticas completas do time (dict com chaves 'casa'/'fora')
        context: 'casa' para time mandante, 'fora' para visitante, 'total' para média
    
    Returns:
        dict: Perfil tático com médias de volume de jogo
    """
    profile = {
        'corners_for_avg': 0,
        'corners_against_avg': 0,
        'shots_for_avg': 0,
        'shots_against_avg': 0,
        'offensive_style': 'neutro',
        'volume_intensity': 'medio'
    }

    # Análise de estilo ofensivo baseado em gols (para classificação)
    goals_for_avg = team_stats.get('goals', {}).get('for', {}).get('average', {}).get('total', 0)
    goals_for_avg = float(goals_for_avg) if goals_for_avg else 0.0
    goals_against_avg = team_stats.get('goals', {}).get('against', {}).get('average', {}).get('total', 0)
    goals_against_avg = float(goals_against_avg) if goals_against_avg else 0.0

    # Ler dados REAIS de cantos e finalizações da estrutura stats
    ctx_data = team_stats.get(context, {}) if context in ('casa', 'fora') else {}
    if not ctx_data and context == 'total':
        # Tentar média entre casa e fora quando context='total'
        casa = team_stats.get('casa', {})
        fora = team_stats.get('fora', {})
        cantos_feitos_real = (float(casa.get('cantos_feitos', 0) or 0) +
                              float(fora.get('cantos_feitos', 0) or 0)) / 2
        cantos_sofridos_real = (float(casa.get('cantos_sofridos', 0) or 0) +
                                float(fora.get('cantos_sofridos', 0) or 0)) / 2
        finalizacoes_real = (float(casa.get('finalizacoes', 0) or 0) +
                             float(fora.get('finalizacoes', 0) or 0)) / 2
    else:
        cantos_feitos_real = float(ctx_data.get('cantos_feitos', 0) or 0)
        cantos_sofridos_real = float(ctx_data.get('cantos_sofridos', 0) or 0)
        finalizacoes_real = float(ctx_data.get('finalizacoes', 0) or 0)

    # Classificar estilo ofensivo baseado em gols
    if goals_for_avg > 1.8:
        profile['offensive_style'] = 'ofensivo'
        _corners_est = 6.5
        _shots_est = 15.0
    elif goals_for_avg > 1.2:
        profile['offensive_style'] = 'neutro'
        _corners_est = 5.0
        _shots_est = 12.0
    else:
        profile['offensive_style'] = 'defensivo'
        _corners_est = 3.5
        _shots_est = 9.0

    # Usar dados reais se disponíveis, caso contrário usar estimativa
    profile['corners_for_avg'] = cantos_feitos_real if cantos_feitos_real > 0 else _corners_est
    profile['shots_for_avg'] = finalizacoes_real if finalizacoes_real > 0 else _shots_est

    # Dados reais de cantos cedidos / estimativa baseada em gols sofridos
    if cantos_sofridos_real > 0:
        profile['corners_against_avg'] = cantos_sofridos_real
    elif goals_against_avg > 1.5:
        profile['corners_against_avg'] = 6.0
    elif goals_against_avg > 1.0:
        profile['corners_against_avg'] = 4.5
    else:
        profile['corners_against_avg'] = 3.0

    # shots_against: sem dado real direto — estimar por gols sofridos
    if goals_against_avg > 1.5:
        profile['shots_against_avg'] = 14.0
    elif goals_against_avg > 1.0:
        profile['shots_against_avg'] = 11.0
    else:
        profile['shots_against_avg'] = 8.0

    # Volume de jogo total
    total_volume = profile['corners_for_avg'] + profile['shots_for_avg']
    if total_volume > 20:
        profile['volume_intensity'] = 'alto'
    elif total_volume > 15:
        profile['volume_intensity'] = 'medio'
    else:
        profile['volume_intensity'] = 'baixo'

    return profile


def _adjust_volume_by_opponent(my_profile, opponent_moment, opponent_power):
    """
    🧠 RACIOCÍNIO TÁTICO: Ajusta volume de jogo esperado baseado NO ADVERSÁRIO.
    
    LÓGICA:
    - Contra time fraco (momento<40, power<50): Muito mais volume ofensivo
    - Contra time médio: Volume normal
    - Contra time forte (momento>70, power>70): Muito menos volume ofensivo
    
    Args:
        my_profile: Meu perfil tático
        opponent_moment: Momento do adversário (0-100)
        opponent_power: Poder do adversário (0-100)
    
    Returns:
        dict: Volume ajustado contextualizado
    """
    adjusted = {
        'corners_expected': my_profile['corners_for_avg'],
        'corners_conceded_expected': my_profile['corners_against_avg'],
        'shots_expected': my_profile['shots_for_avg'],
        'shots_conceded_expected': my_profile['shots_against_avg']
    }
    
    # Classificar força do adversário
    opponent_strength = (opponent_moment + opponent_power) / 2
    
    # 🎯 AJUSTE CONTEXTUAL
    if opponent_strength < 40:  # Adversário FRACO
        print(f"    💡 Adversário FRACO detectado (força {opponent_strength:.0f}) → Aumentando volume ofensivo")
        adjusted['corners_expected'] *= 1.35  # +35% escanteios a favor
        adjusted['shots_expected'] *= 1.30    # +30% finalizações
        adjusted['corners_conceded_expected'] *= 0.60  # -40% escanteios contra
        adjusted['shots_conceded_expected'] *= 0.65    # -35% finalizações contra
        
    elif opponent_strength > 70:  # Adversário FORTE
        print(f"    💡 Adversário FORTE detectado (força {opponent_strength:.0f}) → Reduzindo volume ofensivo")
        adjusted['corners_expected'] *= 0.65  # -35% escanteios a favor
        adjusted['shots_expected'] *= 0.70    # -30% finalizações
        adjusted['corners_conceded_expected'] *= 1.40  # +40% escanteios contra
        adjusted['shots_conceded_expected'] *= 1.35    # +35% finalizações contra
        
    else:  # Adversário MÉDIO
        adjusted['corners_expected'] *= 1.0   # Mantém
        adjusted['shots_expected'] *= 1.0
    
    return adjusted


async def _process_h2h_data(h2h_list):
    """
    Processa lista de confrontos H2H e calcula médias de gols e cantos.

    Busca estatísticas de cantos por fixture quando disponível.

    Args:
        h2h_list: Lista de confrontos retornada por buscar_h2h()

    Returns:
        dict ou None: {count, avg_goals, avg_corners, games} quando há 3+ jogos válidos
    """
    if not h2h_list:
        return None

    valid = [c for c in h2h_list
             if c.get('home_goals') is not None and c.get('away_goals') is not None]

    if len(valid) < 3:
        return None

    total_goals = sum((c['home_goals'] or 0) + (c['away_goals'] or 0) for c in valid)
    avg_goals = total_goals / len(valid)

    # Enriquecer cada jogo com total_goals e tentar buscar total_corners via fixture stats
    enriched_games = []
    corner_totals = []
    for confronto in valid[:5]:
        fid = confronto.get('fixture_id')
        total_goals = (confronto.get('home_goals') or 0) + (confronto.get('away_goals') or 0)
        total_corners = None
        if fid:
            try:
                stats = await buscar_estatisticas_jogo(fid)
                if stats:
                    home_c = int(stats.get('home', {}).get('Corner Kicks', 0) or 0)
                    away_c = int(stats.get('away', {}).get('Corner Kicks', 0) or 0)
                    total_corners = home_c + away_c
                    corner_totals.append(total_corners)
            except Exception:
                pass
        enriched_games.append({
            **confronto,
            'total_goals': total_goals,
            'total_corners': total_corners
        })

    avg_corners = sum(corner_totals) / len(corner_totals) if corner_totals else None

    print(f"  🔗 H2H processado: {len(valid)} jogos | avg_goals={avg_goals:.2f} | avg_corners={avg_corners}")

    return {
        'count': len(valid),
        'avg_goals': round(avg_goals, 2),
        'avg_corners': round(avg_corners, 1) if avg_corners is not None else None,
        'games': enriched_games
    }


def _identify_contextual_factors(venue_info):
    """
    Identifica fatores contextuais críticos (altitude, campo sintético).
    
    Args:
        venue_info: Dicionário com informações do estádio
    
    Returns:
        dict: Fatores contextuais identificados
    """
    factors = {
        'high_altitude': False,
        'synthetic_pitch': False,
        'dominant_factor': None
    }
    
    city = venue_info.get('city', '')
    surface = venue_info.get('surface', '')
    
    if city in HIGH_ALTITUDE_CITIES:
        factors['high_altitude'] = True
        factors['dominant_factor'] = 'High Altitude'
    
    if surface and 'synthetic' in surface.lower():
        factors['synthetic_pitch'] = True
        if not factors['dominant_factor']:
            factors['dominant_factor'] = 'Synthetic Pitch'
    
    return factors


def _create_match_scenario(analysis_data):
    """
    🧠 CÉREBRO TÁTICO: Cria CENÁRIO COMPLETO da partida baseado em análise cruzada.
    
    Analisa:
    1. ATAQUE Casa vs DEFESA Fora
    2. DEFESA Casa vs ATAQUE Fora
    3. Momento atual de ambos
    4. Necessidade tática (mata-mata, rebaixamento)
    5. Fatores ambientais (altitude, campo)
    
    Returns:
        dict: Cenário tático completo com expectativas
    """
    # Extrair dados
    moment_home = analysis_data['moment_home']
    moment_away = analysis_data['moment_away']
    power_home = analysis_data['power_score_home']
    power_away = analysis_data['power_score_away']
    profile_home = analysis_data['profile_home']
    profile_away = analysis_data['profile_away']
    contextual = analysis_data['contextual_factors']
    
    # 🎯 ANÁLISE CRUZADA: Ataque vs Defesa
    # MEU ATAQUE (casa) vs DEFESA DELES (fora)
    home_offensive_power = (moment_home * 0.6) + (power_home * 0.4)  # Momento pesa mais
    away_defensive_power = (moment_away * 0.4) + (power_away * 0.6)  # Poder histórico pesa mais na defesa
    
    home_attack_advantage = home_offensive_power - away_defensive_power
    
    # ATAQUE DELES (fora) vs MINHA DEFESA (casa)
    away_offensive_power = (moment_away * 0.6) + (power_away * 0.4)
    home_defensive_power = (moment_home * 0.4) + (power_home * 0.6)
    
    away_attack_advantage = away_offensive_power - home_defensive_power
    
    # 🎬 Criar cenário tático
    scenario = {
        'home_will_dominate': home_attack_advantage > 20,
        'away_will_dominate': away_attack_advantage > 20,
        'balanced_game': abs(home_attack_advantage) < 15 and abs(away_attack_advantage) < 15,
        'home_attack_strong': home_attack_advantage > 10,
        'away_attack_strong': away_attack_advantage > 10,
        'home_defense_weak': away_attack_advantage > 15,
        'away_defense_weak': home_attack_advantage > 15,
        'volume_expected': {
            'home_corners': profile_home['corners_for_avg'],
            'away_corners': profile_away['corners_for_avg'],
            'home_shots': profile_home['shots_for_avg'],
            'away_shots': profile_away['shots_for_avg']
        },
        'tactical_narrative': ""
    }
    
    # 📖 CRIAR NARRATIVA TÁTICA
    if contextual['high_altitude']:
        scenario['tactical_narrative'] = (
            f"🏔️ ALTITUDE EXTREMA ({contextual.get('venue_city')}): Casa tem vantagem física brutal. "
            f"Visitante sofrerá nos primeiros 60 minutos. Espere pressão intensa do mandante."
        )
    elif moment_home >= 90:  # TIME EM CHAMAS
        scenario['tactical_narrative'] = (
            f"🔥 CASA EM CHAMAS: Momento absurdo ({moment_home}/100) em sequência de vitórias. "
            f"Confiança nas alturas, vai IMPOR o jogo mesmo contra adversário teoricamente superior. "
            f"Espere volume ofensivo alto e muita pressão."
        )
    elif moment_away >= 90:
        scenario['tactical_narrative'] = (
            f"🔥 VISITANTE EM CHAMAS: Momento excepcional ({moment_away}/100). "
            f"Não vai respeitar o mando adversário. Jogo equilibrado ou até domínio visitante possível."
        )
    elif scenario['home_will_dominate']:
        scenario['tactical_narrative'] = (
            f"💪 DOMÍNIO CASA ESPERADO: Ataque casa ({home_offensive_power:.0f}) >> Defesa fora ({away_defensive_power:.0f}). "
            f"Casa vai criar MUITO volume (escanteios, finalizações). Visitante defensivo."
        )
    elif scenario['away_will_dominate']:
        scenario['tactical_narrative'] = (
            f"⚠️ VISITANTE SUPERIOR: Ataque fora ({away_offensive_power:.0f}) >> Defesa casa ({home_defensive_power:.0f}). "
            f"Visitante vai controlar o jogo. Casa sofrerá defensivamente."
        )
    elif scenario['balanced_game']:
        if profile_home['offensive_style'] == 'ofensivo' and profile_away['offensive_style'] == 'ofensivo':
            scenario['tactical_narrative'] = (
                f"⚔️ DUELO DE ATACANTES: Ambos times ofensivos e equilibrados. "
                f"Jogo ABERTO com chances para os dois lados. Defesas podem sofrer."
            )
        else:
            scenario['tactical_narrative'] = (
                f"🔐 JOGO TÁTICO EQUILIBRADO: Times de força similar, jogo fechado. "
                f"Poucos espaços, decisão por detalhes."
            )
    else:
        scenario['tactical_narrative'] = (
            f"📊 Análise técnica: Casa ({home_offensive_power:.0f}) vs Fora ({away_offensive_power:.0f}). "
            f"Jogo com características mistas."
        )
    
    return scenario


def _select_match_script(analysis_data):
    """
    🎬 ROTEIRISTA: Seleciona Match Script baseado em CENÁRIO TÁTICO completo.
    
    PHOENIX V3.0: Knockout scenarios podem fazer OVERRIDE do script base.
    
    Args:
        analysis_data: Todos os dados incluindo momento, perfil tático, cenário
    
    Returns:
        tuple: (script_name, reasoning)
    """
    # === PRIORIDADE MÁXIMA: KNOCKOUT SCENARIO OVERRIDE ===
    # Jogos de mata-mata têm lógica própria que SOBREPÕE análises normais
    knockout_scenario = analysis_data.get('knockout_scenario')
    
    if knockout_scenario and knockout_scenario.get('is_knockout') and knockout_scenario.get('script_modifier'):
        script_modifier = knockout_scenario['script_modifier']
        description = knockout_scenario.get('description', '')
        tactical_impl = knockout_scenario.get('tactical_implications', {})
        
        # Gerar reasoning detalhado baseado no cenário de knockout
        reasoning = f"🏆 KNOCKOUT SCENARIO: {description}\n"
        
        if 'first_leg_result' in knockout_scenario:
            reasoning += f"   📊 Jogo de Ida: {knockout_scenario['first_leg_result']}\n"
            reasoning += f"   📈 Situação Agregada: {knockout_scenario.get('aggregate_situation', 'N/A')}\n"
        
        if tactical_impl:
            reasoning += f"   💥 Intensidade: {tactical_impl.get('expected_intensity', 'N/A')}\n"
            reasoning += f"   🏠 Casa: {tactical_impl.get('home_approach', 'N/A')}\n"
            reasoning += f"   ✈️ Fora: {tactical_impl.get('away_approach', 'N/A')}"
        
        print(f"\n  🎯 KNOCKOUT OVERRIDE: Script base sobreposto por {script_modifier}")
        return (script_modifier, reasoning)
    
    # Criar cenário tático primeiro
    scenario = _create_match_scenario(analysis_data)
    
    moment_home = analysis_data['moment_home']
    moment_away = analysis_data['moment_away']
    power_home = analysis_data['power_score_home']
    power_away = analysis_data['power_score_away']
    qsc_home = analysis_data.get('qsc_home', power_home)
    qsc_away = analysis_data.get('qsc_away', power_away)
    contextual = analysis_data['contextual_factors']
    league_round = analysis_data.get('league_round', '')
    
    # PRIORIDADE 1: Fatores ambientais extremos
    if contextual['high_altitude']:
        return (
            'SCRIPT_HOST_DOMINATION',
            scenario['tactical_narrative']
        )
    
    # PRIORIDADE 2: Times EM CHAMAS (momento absurdo)
    if moment_home >= 90:  # Casa em chamas
        return (
            'SCRIPT_TIME_EM_CHAMAS_CASA',
            scenario['tactical_narrative']
        )
    
    if moment_away >= 90:  # Visitante em chamas
        return (
            'SCRIPT_TIME_EM_CHAMAS_FORA',
            scenario['tactical_narrative']
        )
    
    # PRIORIDADE 3: Mata-mata (necessidade tática)
    if 'Round of 16' in league_round or 'Eighth' in league_round:
        if 'Leg 1' in league_round or '1st Leg' in league_round:
            return (
                'SCRIPT_MATA_MATA_IDA',
                f"🎯 MATA-MATA IDA: Casa PRECISA construir vantagem para jogo de volta. "
                f"Espere pressão intensa nos primeiros 60 minutos. Volume ofensivo alto esperado."
            )
        elif 'Leg 2' in league_round or '2nd Leg' in league_round:
            return (
                'SCRIPT_MATA_MATA_VOLTA',
                f"🔥 MATA-MATA VOLTA: Time que precisa reverter vai para TUDO. "
                f"Jogo aberto, chances para ambos, muito volume."
            )
    
    # PRIORIDADE 4: Cenários baseados em MOMENTO e análise cruzada
    qsc_diff = qsc_home - qsc_away  # Usar QSC (Quality Score Composto) como medida de gap de qualidade

    # PRIORIDADE 4.1: GIANT vs MINNOW — diferença de QSC abissal (>= 25 pontos)
    # QSC mede reputação + posição na tabela + saldo de gols + forma recente
    # Uma diferença de 25+ pontos é um fosso de qualidade real e persistente
    if qsc_diff >= 25 and scenario['home_will_dominate']:
        return (
            'SCRIPT_GIANT_VS_MINNOW',
            f"👑 GIGANTE vs MINNOW (Casa): Gap de qualidade real de {int(qsc_diff)} pontos de QSC. "
            f"Casa é estruturalmente MUITO superior. Espere domínio total, posse esmagadora e pressão constante. "
            f"BTTS Não e Vitória da Casa são as apostas mais lógicas."
        )

    if qsc_diff <= -25 and scenario['away_will_dominate']:
        return (
            'SCRIPT_GIANT_VS_MINNOW',
            f"👑 GIGANTE vs MINNOW (Fora): Visitante é estruturalmente MUITO superior, gap de QSC de {int(abs(qsc_diff))} pontos. "
            f"Espere domínio do visitante mesmo jogando fora. "
            f"BTTS Não e Vitória Fora são as apostas mais lógicas."
        )

    if scenario['home_will_dominate']:
        return (
            'SCRIPT_DOMINIO_CASA',
            scenario['tactical_narrative']
        )
    
    if scenario['away_will_dominate']:
        return (
            'SCRIPT_DOMINIO_VISITANTE',
            scenario['tactical_narrative']
        )
    
    # PRIORIDADE 5: Rebaixamento
    if 'Relegation' in league_round or analysis_data.get('relegation_battle'):
        return (
            'SCRIPT_RELEGATION_BATTLE',
            f"😰 LUTA CONTRA REBAIXAMENTO: Jogo tenso, times priorizando NÃO PERDER. "
            f"Poucos riscos, jogo travado, muitas faltas e cartões."
        )
    
    # PRIORIDADE 6: Jogo equilibrado - analisar estilos
    if scenario['balanced_game']:
        power_diff = abs(power_home - power_away)
        
        if 'Final' in league_round or 'Semi' in league_round:
            return (
                'SCRIPT_BALANCED_RIVALRY_CLASH',
                scenario['tactical_narrative']
            )
        
        profile_home = analysis_data['profile_home']
        profile_away = analysis_data['profile_away']
        
        if profile_home['offensive_style'] == 'ofensivo' and profile_away['offensive_style'] == 'ofensivo':
            return (
                'SCRIPT_OPEN_HIGH_SCORING_GAME',
                scenario['tactical_narrative']
            )
        else:
            return (
                'SCRIPT_CAGEY_TACTICAL_AFFAIR',
                scenario['tactical_narrative']
            )
    
    # PRIORIDADE 7: Favorito moderado mas não absoluto
    moment_diff = abs(moment_home - moment_away)
    if moment_diff >= 25 or abs(power_home - power_away) >= 15:
        return (
            'SCRIPT_UNSTABLE_FAVORITE',
            f"⚠️ Favorito existe mas cenário instável. Diferença de momento: {moment_diff}. "
            f"Resultado não é garantido."
        )
    
    # DEFAULT: Jogo de compadres ou sem motivação clara
    if moment_home < 50 and moment_away < 50:
        return (
            'SCRIPT_JOGO_DE_COMPADRES',
            f"😴 JOGO SEM MOTIVAÇÃO: Ambos times em momento fraco. "
            f"Ritmo lento esperado, poucos gols, baixa intensidade."
        )
    
    # Fallback
    return (
        'SCRIPT_CAGEY_TACTICAL_AFFAIR',
        scenario['tactical_narrative']
    )


def _calculate_probabilities_from_script(script_name, power_home, power_away):
    """
    Calcula probabilidades para mercados principais baseado EXCLUSIVAMENTE no script selecionado.
    
    Args:
        script_name: Nome do script selecionado
        power_home: Power Score do mandante
        power_away: Power Score do visitante
    
    Returns:
        dict: Probabilidades para 1X2, Over/Under 2.5, BTTS
    """
    probabilities = {
        'match_result': {
            'home_win_prob': 33,
            'draw_prob': 33,
            'away_win_prob': 33
        },
        'goals_over_under_2_5': {
            'over_2_5_prob': 50,
            'under_2_5_prob': 50
        },
        'btts': {
            'btts_yes_prob': 50,
            'btts_no_prob': 50
        }
    }
    
    if script_name == 'SCRIPT_HOST_DOMINATION':
        probabilities['match_result'] = {
            'home_win_prob': 60,
            'draw_prob': 25,
            'away_win_prob': 15
        }
        probabilities['goals_over_under_2_5'] = {
            'over_2_5_prob': 68,
            'under_2_5_prob': 32
        }
        probabilities['btts'] = {
            'btts_yes_prob': 45,
            'btts_no_prob': 55
        }
    
    elif script_name == 'SCRIPT_GIANT_VS_MINNOW':
        probabilities['match_result'] = {
            'home_win_prob': 70,
            'draw_prob': 20,
            'away_win_prob': 10
        }
        probabilities['goals_over_under_2_5'] = {
            'over_2_5_prob': 65,
            'under_2_5_prob': 35
        }
        probabilities['btts'] = {
            'btts_yes_prob': 35,
            'btts_no_prob': 65
        }
    
    elif script_name == 'SCRIPT_BALANCED_RIVALRY_CLASH':
        probabilities['match_result'] = {
            'home_win_prob': 35,
            'draw_prob': 35,
            'away_win_prob': 30
        }
        probabilities['goals_over_under_2_5'] = {
            'over_2_5_prob': 55,
            'under_2_5_prob': 45
        }
        probabilities['btts'] = {
            'btts_yes_prob': 58,
            'btts_no_prob': 42
        }
    
    elif script_name == 'SCRIPT_RELEGATION_BATTLE':
        probabilities['match_result'] = {
            'home_win_prob': 30,
            'draw_prob': 45,
            'away_win_prob': 25
        }
        probabilities['goals_over_under_2_5'] = {
            'over_2_5_prob': 35,
            'under_2_5_prob': 65
        }
        probabilities['btts'] = {
            'btts_yes_prob': 40,
            'btts_no_prob': 60
        }
    
    elif script_name == 'SCRIPT_CAGEY_TACTICAL_AFFAIR':
        probabilities['match_result'] = {
            'home_win_prob': 38,
            'draw_prob': 40,
            'away_win_prob': 22
        }
        probabilities['goals_over_under_2_5'] = {
            'over_2_5_prob': 38,
            'under_2_5_prob': 62
        }
        probabilities['btts'] = {
            'btts_yes_prob': 42,
            'btts_no_prob': 58
        }
    
    elif script_name == 'SCRIPT_UNSTABLE_FAVORITE':
        power_diff = power_home - power_away
        if power_diff > 0:
            probabilities['match_result'] = {
                'home_win_prob': 50,
                'draw_prob': 28,
                'away_win_prob': 22
            }
        else:
            probabilities['match_result'] = {
                'home_win_prob': 25,
                'draw_prob': 30,
                'away_win_prob': 45
            }
        probabilities['goals_over_under_2_5'] = {
            'over_2_5_prob': 52,
            'under_2_5_prob': 48
        }
        probabilities['btts'] = {
            'btts_yes_prob': 52,
            'btts_no_prob': 48
        }
    
    elif script_name == 'SCRIPT_OPEN_HIGH_SCORING_GAME':
        probabilities['match_result'] = {
            'home_win_prob': 40,
            'draw_prob': 25,
            'away_win_prob': 35
        }
        probabilities['goals_over_under_2_5'] = {
            'over_2_5_prob': 72,
            'under_2_5_prob': 28
        }
        probabilities['btts'] = {
            'btts_yes_prob': 68,
            'btts_no_prob': 32
        }
    
    return probabilities


async def _analyze_strength_of_schedule(team_id, league_id):
    """
    TASK 2: Analisa Strength of Schedule (SoS) - força dos últimos 5 adversários.
    
    Busca últimos 5 jogos e usa QSC Dinâmico para avaliar força dos oponentes.
    
    Args:
        team_id: ID do time
        league_id: ID da liga
    
    Returns:
        dict: {
            'sos_score': float,  # Média de QSC dos últimos 5 adversários
            'opponents_qsc': list,  # Lista de QSCs dos adversários
            'difficulty_level': str  # 'very_hard', 'hard', 'medium', 'easy'
        }
    """
    from api_client import buscar_ultimos_jogos_time
    from analysts.context_analyzer import calculate_dynamic_qsc
    
    ultimos_jogos = await buscar_ultimos_jogos_time(team_id, limite=5)
    
    if not ultimos_jogos or len(ultimos_jogos) == 0:
        return {
            'sos_score': 50.0,
            'opponents_qsc': [],
            'difficulty_level': 'medium'
        }
    
    opponents_qsc = []
    
    for jogo in ultimos_jogos[:5]:
        # Identificar o adversário - acessar corretamente a estrutura aninhada
        teams_data = jogo.get('teams', {})
        home_team_id = teams_data.get('home', {}).get('id')
        away_team_id = teams_data.get('away', {}).get('id')
        
        if home_team_id == team_id:
            opponent_id = away_team_id
            opponent_name = jogo.get('away_team', teams_data.get('away', {}).get('name', 'Unknown'))
        else:
            opponent_id = home_team_id
            opponent_name = jogo.get('home_team', teams_data.get('home', {}).get('name', 'Unknown'))
        
        # Validação robusta: pular jogo se opponent_id for inválido
        if opponent_id is None or not isinstance(opponent_id, int):
            print(f"    ⚠️ [SoS DEBUG] ID do adversário inválido (None ou não-inteiro) no jogo {jogo.get('fixture_id', 'unknown')} - pulando...")
            continue
        
        print(f"    🔍 [SoS DEBUG] Buscando stats para adversário ID: {opponent_id} ({opponent_name})")
        
        # Buscar stats do adversário para calcular QSC
        from api_client import buscar_estatisticas_gerais_time
        opponent_stats = await buscar_estatisticas_gerais_time(opponent_id, league_id)
        
        if opponent_stats:
            opponent_qsc = calculate_dynamic_qsc(opponent_stats, opponent_id, None, opponent_name, league_id, 0)
            opponents_qsc.append(opponent_qsc)
        else:
            print(f"    ⚠️ [SoS DEBUG] Não foi possível obter stats do adversário ID {opponent_id} - pulando...")
    
    if not opponents_qsc:
        return {
            'sos_score': 50.0,
            'opponents_qsc': [],
            'difficulty_level': 'medium'
        }
    
    # Calcular média de QSC dos adversários
    sos_score = sum(opponents_qsc) / len(opponents_qsc)
    
    # Classificar dificuldade
    if sos_score >= 75:
        difficulty = 'very_hard'
    elif sos_score >= 60:
        difficulty = 'hard'
    elif sos_score >= 45:
        difficulty = 'medium'
    else:
        difficulty = 'easy'
    
    print(f"    📅 SoS Analysis: Últimos {len(opponents_qsc)} jogos vs oponentes com QSC médio: {sos_score:.1f} ({difficulty})")
    
    return {
        'sos_score': sos_score,
        'opponents_qsc': opponents_qsc,
        'difficulty_level': difficulty
    }


async def _calculate_weighted_metrics(team_id, league_id, sos_data, team_stats=None):
    """
    🔥 PHOENIX V4.0 - FASE 1: ELIMINAR FALLBACK
    
    Calcula métricas ponderadas por força do adversário (SoS) usando DADOS REAIS.
    
    SEMPRE busca estatísticas detalhadas de cada jogo individual usando /fixtures/statistics.
    SEM FALLBACK. SEM COMPROMISSOS. Apenas análise baseada em evidências reais.
    
    Args:
        team_id: ID do time
        league_id: ID da liga
        sos_data: Dados de Strength of Schedule
        team_stats: Estatísticas gerais do time (não usado mais)
    
    Returns:
        dict: {
            'weighted_corners_for': float,
            'weighted_corners_against': float,
            'weighted_shots_for': float,
            'weighted_shots_against': float,
            'weighted_cards_for': float,
            'weighted_cards_against': float
        }
    """
    from api_client import buscar_ultimos_jogos_time, buscar_estatisticas_jogo
    
    print(f"    🔍 FASE 1: Buscando últimos jogos do time {team_id}...")
    ultimos_jogos = await buscar_ultimos_jogos_time(team_id, limite=5)
    
    if not ultimos_jogos or len(ultimos_jogos) == 0:
        print(f"    ❌ ERRO CRÍTICO: Nenhum jogo encontrado para o time {team_id}")
        print(f"    🛑 PHOENIX PROTOCOL: Análise IMPOSSÍVEL sem dados históricos")
        return None  # Sinaliza falha - não há dados para análise
    
    print(f"    ✅ {len(ultimos_jogos)} jogos encontrados. Buscando estatísticas DETALHADAS de cada jogo...")
    
    total_corners_for = 0
    total_corners_against = 0
    total_shots_for = 0
    total_shots_against = 0
    total_cards_for = 0
    total_cards_against = 0
    total_weight = 0
    jogos_processados = 0
    
    opponents_qsc = sos_data.get('opponents_qsc', [])
    
    for idx, jogo in enumerate(ultimos_jogos[:5]):
        fixture_id = jogo.get('fixture_id')
        
        if not fixture_id:
            print(f"    ⚠️ Jogo {idx+1}: Sem fixture_id, pulando...")
            continue
        
        # 🔥 PHOENIX PROTOCOL: BUSCAR ESTATÍSTICAS DETALHADAS DE CADA JOGO
        print(f"    🔎 Jogo {idx+1}/{len(ultimos_jogos[:5])}: Buscando stats do fixture {fixture_id}...")
        stats = await buscar_estatisticas_jogo(fixture_id)
        
        if not stats:
            print(f"    ⚠️ Jogo {idx+1}: Estatísticas não disponíveis para fixture {fixture_id}, pulando...")
            continue
        
        # Determinar se jogou em casa ou fora
        teams_data = jogo.get('teams', {})
        home_team_id = teams_data.get('home', {}).get('id')
        eh_casa = home_team_id == team_id
        team_key = 'home' if eh_casa else 'away'
        opponent_key = 'away' if eh_casa else 'home'
        
        # Extrair métricas do jogo
        corners_for = int(stats.get(team_key, {}).get('Corner Kicks', 0) or 0)
        corners_against = int(stats.get(opponent_key, {}).get('Corner Kicks', 0) or 0)
        shots_for = int(stats.get(team_key, {}).get('Shots on Goal', 0) or 0)
        shots_against = int(stats.get(opponent_key, {}).get('Shots on Goal', 0) or 0)
        yellow_cards_for = int(stats.get(team_key, {}).get('Yellow Cards', 0) or 0)
        red_cards_for = int(stats.get(team_key, {}).get('Red Cards', 0) or 0)
        yellow_cards_against = int(stats.get(opponent_key, {}).get('Yellow Cards', 0) or 0)
        red_cards_against = int(stats.get(opponent_key, {}).get('Red Cards', 0) or 0)
        
        # Calcular peso baseado no QSC do adversário
        opponent_qsc = opponents_qsc[idx] if idx < len(opponents_qsc) else 50.0
        weight = opponent_qsc / 50.0  # Normalizar (50 = peso 1.0)
        
        # Acumular valores ponderados
        total_corners_for += corners_for * weight
        total_corners_against += corners_against * weight
        total_shots_for += shots_for * weight
        total_shots_against += shots_against * weight
        total_cards_for += (yellow_cards_for + red_cards_for * 3) * weight  # Vermelho = 3 amarelos
        total_cards_against += (yellow_cards_against + red_cards_against * 3) * weight
        total_weight += weight
        jogos_processados += 1
        
        print(f"    ✅ Jogo {idx+1}: {corners_for} cantos | {shots_for} finalizações | {yellow_cards_for+red_cards_for} cartões (peso: {weight:.2f})")
    
    if jogos_processados == 0 or total_weight == 0:
        print(f"    ❌ ERRO CRÍTICO: Nenhum jogo processado com sucesso")
        print(f"    🛑 PHOENIX PROTOCOL: Análise IMPOSSÍVEL - estatísticas não disponíveis")
        return None  # Sinaliza falha - não conseguiu obter dados reais
    
    # Calcular médias ponderadas
    weighted_metrics = {
        'weighted_corners_for': total_corners_for / total_weight,
        'weighted_corners_against': total_corners_against / total_weight,
        'weighted_shots_for': total_shots_for / total_weight,
        'weighted_shots_against': total_shots_against / total_weight,
        'weighted_cards_for': total_cards_for / total_weight,
        'weighted_cards_against': total_cards_against / total_weight
    }
    
    print(f"    🎯 WEIGHTED METRICS CALCULADOS ({jogos_processados} jogos):")
    print(f"       🚩 Cantos: {weighted_metrics['weighted_corners_for']:.1f} feitos | {weighted_metrics['weighted_corners_against']:.1f} sofridos")
    print(f"       ⚽ Finalizações no gol: {weighted_metrics['weighted_shots_for']:.1f} feitas | {weighted_metrics['weighted_shots_against']:.1f} sofridas")
    print(f"       🟨 Cartões: {weighted_metrics['weighted_cards_for']:.1f} recebidos | {weighted_metrics['weighted_cards_against']:.1f} provocados")
    
    return weighted_metrics


def _extract_evidence_from_recent_games(ultimos_jogos, team_id, team_name):
    """
    EVIDENCE-BASED: Extrai evidências dos últimos jogos para usar no formato Evidence-Based.
    
    Retorna dados estruturados para cada mercado: gols, cantos, cartões, finalizações.
    
    Args:
        ultimos_jogos: Lista dos últimos jogos do time
        team_id: ID do time
        team_name: Nome do time
    
    Returns:
        dict: {
            'gols': [...],
            'cantos': [...],
            'cartoes': [...],
            'finalizacoes': [...]
        }
    """
    evidencias = {
        'gols': [],
        'cantos': [],
        'cartoes': [],
        'finalizacoes': []
    }
    
    if not ultimos_jogos:
        return evidencias
    
    for jogo in ultimos_jogos[:4]:  # Últimos 4 jogos
        # Determinar se jogou em casa ou fora
        teams_data = jogo.get('teams', {})
        home_team_id = teams_data.get('home', {}).get('id')
        away_team_id = teams_data.get('away', {}).get('id')
        
        eh_casa = home_team_id == team_id
        team_key = 'home' if eh_casa else 'away'
        opponent_key = 'away' if eh_casa else 'home'
        
        # Dados do adversário
        opponent_name = teams_data.get(opponent_key, {}).get('name', 'Adversário')
        
        # Dados dos gols
        goals_data = jogo.get('goals', {})
        team_goals = goals_data.get(team_key, 0) or 0
        opponent_goals = goals_data.get(opponent_key, 0) or 0
        total_goals = team_goals + opponent_goals
        
        # Estatísticas do jogo
        stats = jogo.get('statistics', {})
        team_stats = stats.get(team_key, {})
        opponent_stats = stats.get(opponent_key, {})
        
        # Escanteios
        corners_for = int(team_stats.get('Corner Kicks', 0) or 0)
        corners_against = int(opponent_stats.get('Corner Kicks', 0) or 0)
        total_corners = corners_for + corners_against
        
        # Finalizações
        shots_for = int(team_stats.get('Shots on Goal', 0) or 0)
        shots_against = int(opponent_stats.get('Shots on Goal', 0) or 0)
        total_shots = shots_for + shots_against
        
        # Cartões
        yellow_cards = int(team_stats.get('Yellow Cards', 0) or 0)
        red_cards = int(team_stats.get('Red Cards', 0) or 0)
        total_cards = yellow_cards + red_cards
        
        # Adicionar evidências
        evidencias['gols'].append({
            'opponent': opponent_name,
            'team_goals': team_goals,
            'opponent_goals': opponent_goals,
            'total_goals': total_goals,
            'result': f"{team_goals}-{opponent_goals}"
        })
        
        evidencias['cantos'].append({
            'opponent': opponent_name,
            'corners_for': corners_for,
            'corners_against': corners_against,
            'total_corners': total_corners
        })
        
        evidencias['finalizacoes'].append({
            'opponent': opponent_name,
            'shots_for': shots_for,
            'shots_against': shots_against,
            'total_shots': total_shots
        })
        
        evidencias['cartoes'].append({
            'opponent': opponent_name,
            'yellow_cards': yellow_cards,
            'red_cards': red_cards,
            'total_cards': total_cards
        })
    
    return evidencias


async def generate_match_analysis(jogo):
    """
    FUNÇÃO PRINCIPAL - Gera análise completa centralizada do jogo.
    TASK 2: Agora com SoS Analysis e Weighted Metrics integrados.
    
    Esta é a nova "mente central" do bot. Orquestra todo o processo analítico:
    1. Coleta dados da API
    2. Calcula Power Scores
    3. Calcula QSC Dinâmico
    4. Analisa Strength of Schedule (SoS)
    5. Calcula Weighted Metrics
    6. Identifica contexto
    7. Seleciona Match Script
    8. Calcula probabilidades
    9. Retorna pacote unificado
    
    Args:
        jogo: Objeto completo do jogo (da API)
    
    Returns:
        dict: Pacote de análise completo com script, raciocínio, QSC e weighted metrics
    """
    fixture_id = jogo['fixture']['id']
    print(f"\n🧠 MASTER ANALYZER: Iniciando análise do jogo {fixture_id}")
    
    print("📡 Extraindo dados do jogo...")
    home_team_id = jogo['teams']['home']['id']
    away_team_id = jogo['teams']['away']['id']
    home_team_name = jogo['teams']['home']['name']
    away_team_name = jogo['teams']['away']['name']
    league_id = jogo['league']['id']
    
    # Extrair rodada atual (para Season Start Adjustment)
    rodada_atual = 0
    league_round = jogo.get('league', {}).get('round', '')
    try:
        if league_round:
            rodada_atual = int(''.join(filter(str.isdigit, league_round)))
    except (ValueError, TypeError):
        rodada_atual = 0
    
    # 🏆 KNOCKOUT SCENARIO ANALYSIS - PHOENIX V3.0
    knockout_scenario = None
    from analysts.knockout_analyzer import is_knockout_match, is_second_leg, analyze_knockout_scenario
    from api_client import buscar_jogo_de_ida_knockout
    
    if is_knockout_match(league_id, league_round):
        print(f"🏆 KNOCKOUT DETECTADO: {league_round}")
        
        # Verificar se é jogo de volta
        if is_second_leg(league_round):
            print("   🔄 SEGUNDO JOGO - Buscando resultado do jogo de ida...")
            
            # Buscar resultado do 1º jogo via API
            first_leg = await buscar_jogo_de_ida_knockout(home_team_id, away_team_id, league_id)
            
            if first_leg:
                print(f"   ✅ Jogo de ida encontrado: {first_leg['home_goals']} x {first_leg['away_goals']}")
                
                # Determinar qual time jogou em casa no 1º jogo
                # Se home_team_id atual == away_team_id do 1º jogo, então ele jogou FORA no 1º jogo
                current_home_was_away_in_first_leg = (home_team_id == first_leg['away_team_id'])
                
                # CALCULAR QSC ANTES (necessário para análise de knockout)
                from analysts.context_analyzer import calculate_dynamic_qsc
                from api_client import buscar_classificacao_liga
                
                classificacao_temp = await buscar_classificacao_liga(league_id)
                
                # Buscar stats temporariamente para QSC
                home_stats_temp = await buscar_estatisticas_gerais_time(home_team_id, league_id)
                away_stats_temp = await buscar_estatisticas_gerais_time(away_team_id, league_id)
                
                qsc_home_temp = calculate_dynamic_qsc(home_stats_temp, home_team_id, classificacao_temp, home_team_name, league_id, rodada_atual) if home_stats_temp else 50
                qsc_away_temp = calculate_dynamic_qsc(away_stats_temp, away_team_id, classificacao_temp, away_team_name, league_id, rodada_atual) if away_stats_temp else 50
                
                # Analisar cenário de knockout
                knockout_scenario = analyze_knockout_scenario(
                    first_leg_home_goals=first_leg['home_goals'],
                    first_leg_away_goals=first_leg['away_goals'],
                    home_qsc=qsc_home_temp,
                    away_qsc=qsc_away_temp,
                    current_home_team_was_away_in_first_leg=current_home_was_away_in_first_leg
                )
                
                knockout_scenario['is_knockout'] = True
                knockout_scenario['is_second_leg'] = True
                
                print(f"   🎯 CENÁRIO: {knockout_scenario['scenario_type']}")
                print(f"   📖 {knockout_scenario['description']}")
                print(f"   ⚡ Script Modifier: {knockout_scenario['script_modifier']}")
            else:
                # Fallback se não encontrar 1º jogo
                knockout_scenario = {
                    'is_knockout': True,
                    'is_second_leg': True,
                    'scenario_type': 'BALANCED_TIE_DECIDER',
                    'description': 'Jogo de volta (resultado da ida não encontrado)',
                    'script_modifier': None
                }
                print(f"   ⚠️ Jogo de ida não encontrado - usando cenário padrão")
        else:
            # Primeiro jogo de mata-mata
            knockout_scenario = {
                'is_knockout': True,
                'is_second_leg': False,
                'scenario_type': 'FIRST_LEG',
                'description': 'Primeiro jogo de mata-mata',
                'script_modifier': 'SCRIPT_MATA_MATA_IDA',
                'tactical_implications': {
                    'expected_intensity': 'ALTA',
                    'home_approach': 'BUSCAR VANTAGEM SEM SE EXPOR',
                    'away_approach': 'NÃO TOMAR GOL É PRIORIDADE',
                    'goals_tendency': 'MÉDIO (ambos cautelosos)',
                    'btts_tendency': 'PROVÁVEL (ambos buscam gol fora)',
                }
            }
            print(f"   ✅ Primeiro jogo de mata-mata identificado")
    else:
        knockout_scenario = {'is_knockout': False}
    
    print("📊 Buscando estatísticas dos times...")
    print(f"  🔍 Home ID: {home_team_id} | League ID: {league_id} | Rodada: {rodada_atual}")
    home_stats = await buscar_estatisticas_gerais_time(home_team_id, league_id)
    print(f"  🏠 Home stats: {'OK' if home_stats else 'NONE'}")
    
    print(f"  🔍 Away ID: {away_team_id} | League ID: {league_id}")
    away_stats = await buscar_estatisticas_gerais_time(away_team_id, league_id)
    print(f"  ✈️ Away stats: {'OK' if away_stats else 'NONE'}")
    
    # Buscar classificação para QSC dinâmico
    print("📊 Buscando classificação da liga...")
    from api_client import buscar_classificacao_liga
    classificacao = await buscar_classificacao_liga(league_id)
    
    if not home_stats or not away_stats:
        print(f"  ❌ STATS MISSING - Home: {bool(home_stats)} | Away: {bool(away_stats)}")
        # Se stats falharem, usar valores padrão para continuar análise
        if not home_stats:
            home_stats = {'form': '', 'fixtures': {}, 'goals': {}}
            print("  ⚠️ Usando valores padrão para Home")
        if not away_stats:
            away_stats = {'form': '', 'fixtures': {}, 'goals': {}}
            print("  ⚠️ Usando valores padrão para Away")
    
    print("📊 Calculando Power Scores (Reputação Histórica)...")
    power_home = _calculate_power_score(home_stats) if home_stats else 50
    power_away = _calculate_power_score(away_stats) if away_stats else 50
    print(f"  ⚡ Power Casa: {power_home} | Power Fora: {power_away}")
    
    print("🧠 LAYER 1 (PHOENIX V2.0): Calculando QSC Dinâmico com League Weight e Season Adjustment...")
    from analysts.context_analyzer import calculate_dynamic_qsc
    qsc_home = calculate_dynamic_qsc(home_stats, home_team_id, classificacao, home_team_name, league_id, rodada_atual)
    qsc_away = calculate_dynamic_qsc(away_stats, away_team_id, classificacao, away_team_name, league_id, rodada_atual)
    
    print("🔥 Calculando Momento Atual (Forma Recente)...")
    moment_home = _calculate_moment_score(home_stats) if home_stats else 50
    moment_away = _calculate_moment_score(away_stats) if away_stats else 50
    print(f"  🔥 Momento Casa: {moment_home} | Momento Fora: {moment_away}")

    # ─── TASK 4: LESÕES E DESFALQUES ───────────────────────────────────────────
    print("🏥 TASK 4: Buscando lesões e desfalques...")
    injuries_raw = await buscar_lesoes_jogo(fixture_id)
    home_injuries = [p for p in injuries_raw if p.get('team_id') == home_team_id]
    away_injuries = [p for p in injuries_raw if p.get('team_id') == away_team_id]

    injury_penalty_home = _calculate_injury_impact(home_injuries)
    injury_penalty_away = _calculate_injury_impact(away_injuries)

    if injury_penalty_home > 0:
        moment_home = max(0, moment_home - injury_penalty_home)
        print(f"  🏥 Casa: {len(home_injuries)} ausência(s) → Momento ajustado -{injury_penalty_home} → {moment_home}")
    if injury_penalty_away > 0:
        moment_away = max(0, moment_away - injury_penalty_away)
        print(f"  🏥 Fora: {len(away_injuries)} ausência(s) → Momento ajustado -{injury_penalty_away} → {moment_away}")
    if not home_injuries and not away_injuries:
        print(f"  ✅ Sem desfalques confirmados ou endpoint indisponível")
    # ───────────────────────────────────────────────────────────────────────────

    print("📅 TASK 2: Analisando Strength of Schedule (SoS)...")
    sos_home = await _analyze_strength_of_schedule(home_team_id, league_id)
    sos_away = await _analyze_strength_of_schedule(away_team_id, league_id)
    
    print("⚖️ TASK 2: Calculando Weighted Metrics (Métricas Ponderadas)...")
    weighted_home = await _calculate_weighted_metrics(home_team_id, league_id, sos_home, home_stats)
    weighted_away = await _calculate_weighted_metrics(away_team_id, league_id, sos_away, away_stats)
    
    # 🔥 PHOENIX V4.0: VERIFICAR SE WEIGHTED METRICS FORAM CALCULADOS COM SUCESSO
    if weighted_home is None or weighted_away is None:
        print(f"  ❌ WEIGHTED METRICS INDISPONÍVEIS")
        print(f"  🛑 PHOENIX PROTOCOL: Impossível gerar análise sem dados históricos reais")
        print(f"  📋 Casa: {'✗ FALHOU' if weighted_home is None else '✓ OK'} | Fora: {'✗ FALHOU' if weighted_away is None else '✓ OK'}")
        return {
            'error': 'DADOS_INSUFICIENTES',
            'message': f'Não há dados históricos suficientes para {home_team_name} e/ou {away_team_name}. Análise impossível sem estatísticas reais.',
            'missing_data': {
                'home': weighted_home is None,
                'away': weighted_away is None
            }
        }
    
    print(f"  📊 Casa: {weighted_home['weighted_corners_for']:.1f} cantos | {weighted_home['weighted_shots_for']:.1f} finalizações (ponderado)")
    print(f"  📊 Fora: {weighted_away['weighted_corners_for']:.1f} cantos | {weighted_away['weighted_shots_for']:.1f} finalizações (ponderado)")
    
    print("🎯 Calculando Perfil Tático (Volume de Jogo)...")
    profile_home = _calculate_tactical_profile(home_stats, context='casa') if home_stats else {'corners_for_avg': 5, 'shots_for_avg': 12, 'offensive_style': 'neutro'}
    profile_away = _calculate_tactical_profile(away_stats, context='fora') if away_stats else {'corners_for_avg': 5, 'shots_for_avg': 12, 'offensive_style': 'neutro'}
    print(f"  ⚔️ Casa: {profile_home['offensive_style']} | Fora: {profile_away['offensive_style']}")
    
    print("🌍 Identificando fatores contextuais...")
    venue_info = jogo.get('fixture', {}).get('venue', {})
    contextual_factors = _identify_contextual_factors(venue_info)
    
    if contextual_factors['dominant_factor']:
        print(f"  🔥 Fator dominante detectado: {contextual_factors['dominant_factor']}")
    
    goals_home = home_stats.get('goals', {}).get('for', {}).get('average', {}).get('total', 0) if home_stats else 0
    goals_home = float(goals_home) if goals_home else 0.0
    goals_away = away_stats.get('goals', {}).get('for', {}).get('average', {}).get('total', 0) if away_stats else 0
    goals_away = float(goals_away) if goals_away else 0.0

    # FASE 2: Lambda individual por time para cálculo Poisson preciso
    # lambda_home = gols que o mandante marca jogando EM CASA (por jogo)
    # lambda_away = gols que o visitante marca jogando FORA (por jogo)
    _home_casa = home_stats.get('casa', {}) if isinstance(home_stats, dict) else {}
    _away_fora = away_stats.get('fora', {}) if isinstance(away_stats, dict) else {}

    lambda_home_raw = float(_home_casa.get('gols_marcados', 0) or 0)
    lambda_away_raw = float(_away_fora.get('gols_marcados', 0) or 0)
    gols_sofridos_home_def = float(_home_casa.get('gols_sofridos', 1.0) or 1.0)
    gols_sofridos_away_def = float(_away_fora.get('gols_sofridos', 1.0) or 1.0)

    # Garantir valores mínimos realistas (evitar lambda=0 que daria 0% de probabilidade)
    if lambda_home_raw <= 0:
        lambda_home_raw = 1.2
    if lambda_away_raw <= 0:
        lambda_away_raw = 0.9
    if gols_sofridos_home_def <= 0:
        gols_sofridos_home_def = 1.0
    if gols_sofridos_away_def <= 0:
        gols_sofridos_away_def = 1.0

    # Lambda efetivo = média ponderada ataque próprio + concedido pelo adversário
    # Isto combina o poder ofensivo com a vulnerabilidade defensiva do oponente
    lambda_effective_home = (lambda_home_raw + gols_sofridos_away_def) / 2
    lambda_effective_away = (lambda_away_raw + gols_sofridos_home_def) / 2
    lambda_total_effective = lambda_effective_home + lambda_effective_away

    # ─── TASK 4: xG APROXIMADO (blend 50/50 com lambda por médias de gols) ────
    # Cálculo: xG = shots_on_target × (goals / total_shots)
    # Onde conversion_rate = gols_marcados / finalizacoes_totais mede eficiência de finalização
    # O blend suaviza distorções: times eficientes com poucos chutes OU ineficientes com muitos.
    _sot_home = float(_home_casa.get('finalizacoes_no_gol', 0) or 0)   # Shots on target (casa)
    _sot_away = float(_away_fora.get('finalizacoes_no_gol', 0) or 0)   # Shots on target (fora)
    _shots_home = float(_home_casa.get('finalizacoes', 0) or 0)         # Total shots (casa)
    _shots_away = float(_away_fora.get('finalizacoes', 0) or 0)         # Total shots (fora)

    if _sot_home > 0 and _shots_home > 0 and _sot_away > 0 and _shots_away > 0:
        _conv_rate_home = lambda_home_raw / _shots_home   # gols por finalização total (casa)
        _conv_rate_away = lambda_away_raw / _shots_away   # gols por finalização total (fora)
        xg_home = _sot_home * _conv_rate_home
        xg_away = _sot_away * _conv_rate_away
        # Garantir que xG não seja absurdo
        xg_home = max(0.3, min(xg_home, 5.0))
        xg_away = max(0.2, min(xg_away, 5.0))
        # Blend 50/50: lambda por gols históricos + lambda estimado por xG
        lambda_effective_home = 0.5 * lambda_effective_home + 0.5 * xg_home
        lambda_effective_away = 0.5 * lambda_effective_away + 0.5 * xg_away
        lambda_total_effective = lambda_effective_home + lambda_effective_away
        print(f"  🎯 xG BLEND: Casa xG={xg_home:.2f}, Fora xG={xg_away:.2f}")
        print(f"  ⚽ Lambdas pós-xG: Casa={lambda_effective_home:.2f} | Fora={lambda_effective_away:.2f} | Total={lambda_total_effective:.2f}")
    else:
        print(f"  ℹ️ xG: Dados de finalizações insuficientes → usando lambda por médias de gols")
    # ─────────────────────────────────────────────────────────────────────────

    # Taxa de clean sheet defensiva:
    # Preferir dados empíricos da API quando disponíveis, caso contrário usar aproximação Poisson.
    # clean_sheet_rate_home_def = prob do mandante guardar CS em casa (baseada em jogos reais)
    # clean_sheet_rate_away_def = prob do visitante guardar CS fora (baseada em jogos reais)
    _cs_home_empirical = _home_casa.get('clean_sheet_rate', None)   # None se API não retornou
    _cs_away_empirical = _away_fora.get('clean_sheet_rate', None)   # None se API não retornou

    if _cs_home_empirical is not None:
        clean_sheet_rate_home_def = float(_cs_home_empirical)
        print(f"    ✅ CS Home (empírico): {clean_sheet_rate_home_def:.3f}")
    else:
        clean_sheet_rate_home_def = math.exp(-lambda_effective_away)  # Poisson fallback
        print(f"    ⚠️ CS Home (Poisson fallback): {clean_sheet_rate_home_def:.3f}")

    if _cs_away_empirical is not None:
        clean_sheet_rate_away_def = float(_cs_away_empirical)
        print(f"    ✅ CS Away (empírico): {clean_sheet_rate_away_def:.3f}")
    else:
        clean_sheet_rate_away_def = math.exp(-lambda_effective_home)  # Poisson fallback
        print(f"    ⚠️ CS Away (Poisson fallback): {clean_sheet_rate_away_def:.3f}")

    # Ratio HT ajustado pelo perfil tático dos dois times
    _style_home = profile_home.get('offensive_style', 'neutro')
    _style_away = profile_away.get('offensive_style', 'neutro')
    if _style_home == 'ofensivo' and _style_away == 'ofensivo':
        ht_ratio = 0.47   # times agressivos desde o início
    elif _style_home == 'defensivo' and _style_away == 'defensivo':
        ht_ratio = 0.38   # times lentos/cautelosos no 1º tempo
    else:
        ht_ratio = 0.43   # padrão histórico global

    print(f"  ⚽ FASE 2 Lambdas: Casa={lambda_effective_home:.2f} | Fora={lambda_effective_away:.2f} | Total={lambda_total_effective:.2f} | HT ratio={ht_ratio}")

    analysis_data = {
        'power_score_home': power_home,
        'power_score_away': power_away,
        'moment_home': moment_home,
        'moment_away': moment_away,
        'profile_home': profile_home,
        'profile_away': profile_away,
        'contextual_factors': contextual_factors,
        'league_round': jogo.get('league', {}).get('round', ''),
        'goals_avg_home': goals_home,
        'goals_avg_away': goals_away,
        'venue_city': venue_info.get('city', ''),
        'relegation_battle': False,
        'knockout_scenario': knockout_scenario  # PHOENIX V3.0: Knockout Intelligence
    }
    
    print("🎬 Selecionando Match Script...")
    script_name, reasoning = _select_match_script(analysis_data)
    print(f"  📜 Script selecionado: {script_name}")
    print(f"  💭 Raciocínio: {reasoning}")
    
    print("🎲 Calculando probabilidades baseadas no script...")
    probabilities = _calculate_probabilities_from_script(script_name, power_home, power_away)
    
    print("📊 EVIDENCE-BASED: Buscando últimos 4 jogos para evidências...")
    from api_client import buscar_ultimos_jogos_time
    ultimos_jogos_casa = await buscar_ultimos_jogos_time(home_team_id, limite=4)
    ultimos_jogos_fora = await buscar_ultimos_jogos_time(away_team_id, limite=4)
    
    # Extrair evidências dos últimos jogos para cada mercado
    evidencias_home = _extract_evidence_from_recent_games(ultimos_jogos_casa, home_team_id, home_team_name) if ultimos_jogos_casa else {}
    evidencias_away = _extract_evidence_from_recent_games(ultimos_jogos_fora, away_team_id, away_team_name) if ultimos_jogos_fora else {}
    
    print(f"  ✅ Evidências extraídas: Casa ({len(evidencias_home.get('gols', []))} jogos) | Fora ({len(evidencias_away.get('gols', []))} jogos)")

    print("🔗 H2H: Buscando confrontos diretos...")
    h2h_list = await buscar_h2h(home_team_id, away_team_id, limite=5)
    h2h_stats = await _process_h2h_data(h2h_list)
    if h2h_stats:
        print(f"  ✅ H2H: {h2h_stats['count']} jogos | avg_goals={h2h_stats['avg_goals']:.2f} | avg_corners={h2h_stats['avg_corners']}")
    else:
        print(f"  ⚠️ H2H: Dados insuficientes (menos de 3 jogos válidos)")
    
    # Sumário de desfalques e severidade para exibição e confidence downgrade (Task 4)
    _injuries_summary_home = [f"{p['name']} ({p['type']})" for p in home_injuries] if home_injuries else []
    _injuries_summary_away = [f"{p['name']} ({p['type']})" for p in away_injuries] if away_injuries else []
    injury_severity_home = _get_injury_severity_label(home_injuries)
    injury_severity_away = _get_injury_severity_label(away_injuries)
    injury_role_home = _get_injury_role_label(home_injuries)
    injury_role_away = _get_injury_role_label(away_injuries)

    # Adicionar contexto de desfalques ao reasoning tático para narrativa completa
    if home_injuries or away_injuries:
        _injury_lines = []
        if home_injuries:
            _suspended_h = [p['name'] for p in home_injuries if p.get('type', '').lower() == 'suspended']
            _injured_h   = [p['name'] for p in home_injuries if p.get('type', '').lower() != 'suspended']
            _parts = []
            if _suspended_h:
                _parts.append(f"suspensos: {', '.join(_suspended_h)}")
            if _injured_h:
                _parts.append(f"lesionados: {', '.join(_injured_h)}")
            _injury_lines.append(f"🏥 {home_team_name} ({injury_severity_home.upper()}) — " + " | ".join(_parts))
        if away_injuries:
            _suspended_a = [p['name'] for p in away_injuries if p.get('type', '').lower() == 'suspended']
            _injured_a   = [p['name'] for p in away_injuries if p.get('type', '').lower() != 'suspended']
            _parts = []
            if _suspended_a:
                _parts.append(f"suspensos: {', '.join(_suspended_a)}")
            if _injured_a:
                _parts.append(f"lesionados: {', '.join(_injured_a)}")
            _injury_lines.append(f"🏥 {away_team_name} ({injury_severity_away.upper()}) — " + " | ".join(_parts))
        reasoning = reasoning + "\n\n⚠️ DESFALQUES:\n" + "\n".join(_injury_lines)

    analysis_packet = {
        'fixture_id': fixture_id,
        'analysis_summary': {
            'selected_script': script_name,
            'reasoning': reasoning,
            'dominant_factor': contextual_factors.get('dominant_factor'),
            'power_score_home': power_home,
            'power_score_away': power_away,
            'qsc_home': qsc_home,
            'qsc_away': qsc_away,
            'moment_home': moment_home,
            'moment_away': moment_away,
            'profile_home': profile_home,
            'profile_away': profile_away,
            'sos_home': sos_home,
            'sos_away': sos_away,
            'weighted_metrics_home': weighted_home,
            'weighted_metrics_away': weighted_away,
            'injuries_home': _injuries_summary_home,
            'injuries_away': _injuries_summary_away,
            'injury_penalty_home': injury_penalty_home,
            'injury_penalty_away': injury_penalty_away,
            'injury_severity_home': injury_severity_home,
            'injury_severity_away': injury_severity_away,
            'injury_role_home': injury_role_home,
            'injury_role_away': injury_role_away,
        },
        'calculated_probabilities': {
            **probabilities,
            'lambda_goals': {
                'lambda_home': lambda_effective_home,
                'lambda_away': lambda_effective_away,
                'lambda_total': lambda_total_effective,
                'ht_ratio': ht_ratio,
                'clean_sheet_rate_home_def': clean_sheet_rate_home_def,
                'clean_sheet_rate_away_def': clean_sheet_rate_away_def
            }
        },
        'evidence': {
            'home': evidencias_home,
            'away': evidencias_away,
            'home_team_name': home_team_name,
            'away_team_name': away_team_name
        },
        'raw_data': {
            'home_stats': home_stats,
            'away_stats': away_stats,
            'fixture_data': jogo
        },
        'h2h': h2h_stats
    }
    
    print("✅ MASTER ANALYZER: Análise completa gerada com QSC, SoS, Weighted Metrics e Evidências!\n")
    
    return analysis_packet
