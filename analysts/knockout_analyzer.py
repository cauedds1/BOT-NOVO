"""
Knockout Scenario Analyzer - PHOENIX V3.0

Analisa jogos de mata-mata (Champions League, Libertadores, copas)
considerando o contexto completo da eliminatória, não apenas um jogo isolado.
"""

from typing import Dict, Optional, Tuple


# Competições de mata-mata (copas e continentais)
KNOCKOUT_COMPETITIONS = {
    1: "Copa do Mundo",
    2: "Champions League", 
    3: "Europa League",
    4: "Eurocopa",
    9: "Copa América",
    11: "Copa Sudamericana",
    13: "Copa Libertadores",
    15: "Mundial de Clubes",
    16: "Champions League Asiática",
    18: "Champions League CONCACAF",
    12: "Champions League Africana",
    848: "Conference League",
    
    # Copas nacionais
    45: "FA Cup",
    48: "EFL Cup",
    73: "Copa do Brasil",
    81: "DFB Pokal",
    96: "Taça de Portugal",
    137: "Coppa Italia",
    143: "Copa del Rey",
    213: "Copa Argentina",
}

# Palavras-chave que indicam mata-mata
KNOCKOUT_STAGE_KEYWORDS = [
    "Final",
    "Semi-finals",
    "Quarter-finals",
    "Round of 16",
    "Round of 32",
    "8th Finals",
    "Oitavas",
    "Quartas",
    "Semifinal",
    "Eliminatórias",
    "Play-offs"
]


def is_knockout_match(league_id: int, round_name: str) -> bool:
    """
    Verifica se é um jogo de mata-mata.
    
    Args:
        league_id: ID da liga/competição
        round_name: Nome da rodada (e.g., "Round of 16", "Quarter-finals")
    
    Returns:
        bool: True se for mata-mata
    """
    if league_id not in KNOCKOUT_COMPETITIONS:
        return False
    
    if not round_name:
        return False
    
    # Verificar se o nome da rodada contém palavras-chave de mata-mata
    for keyword in KNOCKOUT_STAGE_KEYWORDS:
        if keyword.lower() in round_name.lower():
            return True
    
    return False


def is_second_leg(round_name: str) -> bool:
    """
    Verifica se é o jogo de volta (2nd Leg).
    
    Args:
        round_name: Nome da rodada
        
    Returns:
        bool: True se for jogo de volta
    """
    if not round_name:
        return False
    
    second_leg_keywords = ["2nd Leg", "volta", "Vuelta", "Return"]
    
    for keyword in second_leg_keywords:
        if keyword.lower() in round_name.lower():
            return True
    
    return False


def analyze_knockout_scenario(first_leg_home_goals: int, first_leg_away_goals: int,
                               home_qsc: float, away_qsc: float,
                               current_home_team_was_away_in_first_leg: bool) -> Dict:
    """
    Analisa o cenário de um jogo de mata-mata baseado no resultado do jogo de ida.
    
    Args:
        first_leg_home_goals: Gols do mandante no jogo de ida
        first_leg_away_goals: Gols do visitante no jogo de ida
        home_qsc: QSC do mandante atual (time que joga em casa AGORA)
        away_qsc: QSC do visitante atual (time que joga fora AGORA)
        current_home_team_was_away_in_first_leg: Se o mandante atual jogou FORA no 1º jogo
    
    Returns:
        dict: {
            'scenario_type': str (GIANT_NEEDS_MIRACLE, MANAGING_THE_LEAD, etc),
            'description': str,
            'tactical_implications': dict,
            'script_modifier': str (script tático recomendado)
        }
    """
    # Determinar quem está em vantagem
    if current_home_team_was_away_in_first_leg:
        # Time atual em casa JOGOU FORA no 1º jogo
        # Exemplo: Jogo de ida: Palmeiras 1 x 2 Flamengo (em casa do Palmeiras)
        # Jogo de volta: Flamengo (casa) vs Palmeiras (fora)
        # Do ponto de vista do Flamengo (mandante agora que jogou fora):
        # Flamengo fez 2 gols fora (away) no 1º jogo, Palmeiras fez 1 em casa (home)
        current_home_advantage = first_leg_away_goals - first_leg_home_goals  # 2 - 1 = +1
    else:
        # Time atual em casa JOGOU EM CASA no 1º jogo
        # Exemplo: Jogo de ida: Flamengo 2 x 1 Palmeiras (casa do Flamengo)
        # Jogo de volta: Flamengo (casa) vs Palmeiras (fora)
        # Do ponto de vista do Flamengo (mandante agora que jogou em casa):
        # Flamengo fez 2 gols em casa (home) no 1º jogo, Palmeiras fez 1 fora (away)
        current_home_advantage = first_leg_home_goals - first_leg_away_goals  # 2 - 1 = +1
    
    goal_difference = abs(current_home_advantage)
    qsc_difference = abs(home_qsc - away_qsc)
    
    # ========================================
    # CENÁRIO 1: GIANT_NEEDS_MIRACLE
    # ========================================
    # Time muito melhor (QSC +15) perdeu por 2+ gols e joga em casa
    if (current_home_advantage <= -2 and 
        home_qsc > away_qsc and 
        qsc_difference >= 15):
        
        return {
            'scenario_type': 'GIANT_NEEDS_MIRACLE',
            'description': f'Time favorito precisa reverter desvantagem de {goal_difference} gols jogando em casa',
            'first_leg_result': f'{first_leg_home_goals} x {first_leg_away_goals}',
            'aggregate_situation': f'Precisa de {goal_difference + 1}+ gols para avançar',
            'tactical_implications': {
                'expected_intensity': 'ALTÍSSIMA',
                'home_approach': 'ATAQUE TOTAL (all-out attack)',
                'away_approach': 'DEFESA PROFUNDA (counter-attack)',
                'corners_tendency': 'MUITO ALTO (pressão constante)',
                'cards_tendency': 'ALTO (jogo nervoso + faltas táticas)',
                'goals_tendency': 'OVER favorecido (time forte atacando)',
                'btts_tendency': 'PROVÁVEL (contra-ataques perigosos)',
            },
            'script_modifier': 'SCRIPT_HOME_DOMINANT_ATTACK_PRESSURE'
        }
    
    # ========================================
    # CENÁRIO 2: MANAGING_THE_LEAD
    # ========================================
    # Time venceu fora por 2+ e joga em casa (administra vantagem)
    if current_home_advantage >= 2:
        return {
            'scenario_type': 'MANAGING_THE_LEAD',
            'description': f'Time administra vantagem de {goal_difference} gols jogando em casa',
            'first_leg_result': f'{first_leg_home_goals} x {first_leg_away_goals}',
            'aggregate_situation': 'Ampla vantagem para administrar',
            'tactical_implications': {
                'expected_intensity': 'CONTROLADA',
                'home_approach': 'CONTROLE DE POSSE (jogo seguro)',
                'away_approach': 'DESESPERO OFENSIVO',
                'corners_tendency': 'MÉDIO/BAIXO (jogo controlado)',
                'cards_tendency': 'MÉDIO (visitante pode ser agressivo)',
                'goals_tendency': 'UNDER favorecido (ritmo lento)',
                'btts_tendency': 'IMPROVÁVEL (mandante joga no seguro)',
            },
            'script_modifier': 'SCRIPT_LOW_SCORING_CONTROLLED'
        }
    
    # ========================================
    # CENÁRIO 3: NARROW_LEAD_DEFENSE
    # ========================================
    # Vantagem mínima (1 gol) jogando em casa
    if current_home_advantage == 1:
        return {
            'scenario_type': 'NARROW_LEAD_DEFENSE',
            'description': 'Time defende vantagem mínima de 1 gol em casa',
            'first_leg_result': f'{first_leg_home_goals} x {first_leg_away_goals}',
            'aggregate_situation': 'Vantagem frágil, qualquer gol equilibra',
            'tactical_implications': {
                'expected_intensity': 'ALTA',
                'home_approach': 'EQUILÍBRIO (não se expor)',
                'away_approach': 'PRESSÃO MODERADA',
                'corners_tendency': 'MÉDIO',
                'cards_tendency': 'ALTO (tensão, ninguém pode errar)',
                'goals_tendency': 'BAIXO (ambos cautelosos)',
                'btts_tendency': 'MÉDIO/BAIXO',
            },
            'script_modifier': 'SCRIPT_BALANCED_TACTICAL_BATTLE'
        }
    
    # ========================================
    # CENÁRIO 4: BALANCED_TIE_DECIDER
    # ========================================
    # Empate no primeiro jogo ou diferença mínima com times equilibrados
    if -1 <= current_home_advantage <= 0 or qsc_difference < 10:
        return {
            'scenario_type': 'BALANCED_TIE_DECIDER',
            'description': 'Confronto equilibrado, jogo decisivo tenso',
            'first_leg_result': f'{first_leg_home_goals} x {first_leg_away_goals}',
            'aggregate_situation': 'Eliminatória em aberto, qualquer time pode avançar',
            'tactical_implications': {
                'expected_intensity': 'MUITO ALTA',
                'home_approach': 'BUSCAR VITÓRIA SEM SE EXPOR',
                'away_approach': 'BUSCAR VITÓRIA SEM SE EXPOR',
                'corners_tendency': 'MÉDIO/ALTO (ambos buscam gol)',
                'cards_tendency': 'MUITO ALTO (tensão máxima)',
                'goals_tendency': 'UNDER favorecido (medo de errar)',
                'btts_tendency': 'BAIXO (ninguém quer tomar gol)',
            },
            'script_modifier': 'SCRIPT_TIGHT_LOW_SCORING'
        }
    
    # ========================================
    # CENÁRIO 5: UNDERDOG_MIRACLE_ATTEMPT
    # ========================================
    # Time fraco (QSC -15) precisa reverter desvantagem em casa
    if (current_home_advantage <= -2 and 
        home_qsc < away_qsc and 
        qsc_difference >= 15):
        
        return {
            'scenario_type': 'UNDERDOG_MIRACLE_ATTEMPT',
            'description': f'Azarão tenta reverter desvantagem de {goal_difference} gols em casa',
            'first_leg_result': f'{first_leg_home_goals} x {first_leg_away_goals}',
            'aggregate_situation': f'Cenário difícil, precisa de {goal_difference + 1}+ gols',
            'tactical_implications': {
                'expected_intensity': 'DESESPERADA',
                'home_approach': 'ATAQUE SEM QUALIDADE (desorganizado)',
                'away_approach': 'CONTROLE FÁCIL',
                'corners_tendency': 'ALTO (volume sem qualidade)',
                'cards_tendency': 'MUITO ALTO (frustração)',
                'goals_tendency': 'IMPREVISÍVEL (pode abrir ou travar)',
                'btts_tendency': 'PROVÁVEL (espaços para o favorito)',
            },
            'script_modifier': 'SCRIPT_CHAOTIC_OPEN_GAME'
        }
    
    # Default: Cenário balanceado
    return {
        'scenario_type': 'BALANCED_TIE_DECIDER',
        'description': 'Cenário equilibrado de mata-mata',
        'first_leg_result': f'{first_leg_home_goals} x {first_leg_away_goals}',
        'aggregate_situation': 'Jogo aberto',
        'tactical_implications': {
            'expected_intensity': 'ALTA',
            'home_approach': 'EQUILIBRADO',
            'away_approach': 'EQUILIBRADO',
            'corners_tendency': 'MÉDIO',
            'cards_tendency': 'MÉDIO/ALTO',
            'goals_tendency': 'MÉDIO',
            'btts_tendency': 'MÉDIO',
        },
        'script_modifier': 'SCRIPT_BALANCED_TACTICAL_BATTLE'
    }
