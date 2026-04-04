"""
Motor de Modificadores Contextuais Quantitativos — AnalyTips v5.0
=================================================================

Detecta cenários contextuais e computa multiplicadores de lambda/cantos/cartões/finalizações
antes de alimentar os analisadores Poisson downstream.

Cenários detectados:
- PRECISA_VENCER_HOME / _AWAY  : time em zona de rebaixamento ou pressionado
- SEM_MOTIVACAO_HOME / _AWAY   : time no meio da tabela sem objetivos
- CANSADO_HOME / _AWAY         : 3+ jogos em 7 dias (fadiga física)
- CLASICO                      : derby/clássico detectado
- ALTITUDE_AWAY                : estádio em altitude elevada
- KNOCKOUT_REVERSAL_HOME / _AWAY: mata-mata — time que precisa reverter
- KNOCKOUT_ADVANTAGE_HOME / _AWAY: mata-mata — time com vantagem no agregado
"""

from datetime import datetime, timedelta
from typing import Optional


# --------------------------------------------------------------------------
# Multiplicadores por cenário
# --------------------------------------------------------------------------
_SCENARIO_MULTIPLIERS = {
    "PRECISA_VENCER_HOME": {
        "home": {"lambda_goals": 1.20, "corners": 1.25, "cards": 1.20, "shots": 1.15},
        "away": {},
    },
    "PRECISA_VENCER_AWAY": {
        "home": {},
        "away": {"lambda_goals": 1.20, "corners": 1.25, "cards": 1.20, "shots": 1.15},
    },
    "SEM_MOTIVACAO_HOME": {
        "home": {"lambda_goals": 0.92, "shots": 0.92},
        "away": {},
    },
    "SEM_MOTIVACAO_AWAY": {
        "home": {},
        "away": {"lambda_goals": 0.92, "shots": 0.92},
    },
    "CANSADO_HOME": {
        "home": {"lambda_goals": 0.88, "shots": 0.85, "corners": 0.90},
        "away": {},
    },
    "CANSADO_AWAY": {
        "home": {},
        "away": {"lambda_goals": 0.88, "shots": 0.85, "corners": 0.90},
    },
    "CLASICO": {
        "home": {"cards": 1.30, "shots": 1.10},
        "away": {"cards": 1.30, "shots": 1.10},
    },
    "ALTITUDE_AWAY": {
        "home": {"lambda_goals": 1.05},
        "away": {"lambda_goals": 0.90, "shots": 0.90},
    },
    "KNOCKOUT_REVERSAL_HOME": {
        "home": {"lambda_goals": 1.20, "corners": 1.20, "shots": 1.15},
        "away": {},
    },
    "KNOCKOUT_REVERSAL_AWAY": {
        "home": {},
        "away": {"lambda_goals": 1.20, "corners": 1.20, "shots": 1.15},
    },
    "KNOCKOUT_REVERSAL_BOTH": {
        "home": {"lambda_goals": 1.15, "corners": 1.15, "shots": 1.10},
        "away": {"lambda_goals": 1.15, "corners": 1.15, "shots": 1.10},
    },
    "KNOCKOUT_ADVANTAGE_HOME": {
        "home": {"lambda_goals": 0.88},
        "away": {},
    },
    "KNOCKOUT_ADVANTAGE_AWAY": {
        "home": {},
        "away": {"lambda_goals": 0.88},
    },
}

# Cidades conhecidas em altitude elevada (>1800m)
_ALTITUDE_CITIES = {
    "la paz", "quito", "bogotá", "bogota", "medellín", "medellin",
    "mexico city", "ciudad de mexico", "ciudad de méxico", "denver",
    "addis ababa", "cusco", "cochabamba", "potosí", "potosi",
    "toluca", "sucre", "manizales", "pasto", "armenia", "tegucigalpa",
    "san jose", "san josé",
}

# Pares de clássicos conhecidos
_CLASICO_PAIRS = [
    # Brasil
    {"flamengo", "fluminense"}, {"flamengo", "vasco"}, {"flamengo", "botafogo"},
    {"corinthians", "palmeiras"}, {"corinthians", "santos"}, {"corinthians", "são paulo"},
    {"palmeiras", "santos"}, {"palmeiras", "são paulo"}, {"santos", "são paulo"},
    {"grêmio", "internacional"}, {"gremio", "internacional"},
    {"atlético mineiro", "cruzeiro"}, {"atletico mineiro", "cruzeiro"},
    {"bahia", "vitória"}, {"bahia", "vitoria"},
    # Espanha
    {"barcelona", "real madrid"}, {"real madrid", "atlético de madrid"},
    {"real madrid", "atletico madrid"}, {"barcelona", "atlético de madrid"},
    {"sevilla", "real betis"}, {"real madrid", "atletico"},
    {"villarreal", "valencia"}, {"espanyol", "barcelona"},
    # Inglaterra
    {"arsenal", "tottenham"}, {"manchester city", "manchester united"},
    {"liverpool", "everton"}, {"chelsea", "arsenal"}, {"chelsea", "tottenham"},
    {"aston villa", "birmingham"}, {"leeds", "manchester united"},
    {"west ham", "millwall"}, {"crystal palace", "brighton"},
    # Itália
    {"ac milan", "inter"}, {"milan", "inter"}, {"juventus", "torino"},
    {"roma", "lazio"}, {"napoli", "juventus"}, {"atalanta", "brescia"},
    # Alemanha
    {"borussia dortmund", "schalke"}, {"hamburger", "werder"},
    {"hamburg", "werder"}, {"borussia mönchengladbach", "köln"},
    {"bayer leverkusen", "köln"},
    # França
    {"paris saint-germain", "olympique marseille"}, {"psg", "marseille"},
    {"paris saint-germain", "lyon"}, {"paris saint-germain", "olympique lyonnais"},
    {"marseille", "nice"},
    # Portugal
    {"benfica", "porto"}, {"benfica", "sporting"}, {"porto", "sporting"},
    {"benfica", "sporting cp"}, {"porto", "sporting cp"},
    # Argentina
    {"boca juniors", "river plate"}, {"independiente", "racing"},
    {"san lorenzo", "huracan"},
    # Holanda
    {"ajax", "feyenoord"}, {"ajax", "psv"},
    # Escócia
    {"celtic", "rangers"},
    # Turquia
    {"galatasaray", "fenerbahçe"}, {"galatasaray", "fenerbahce"},
    {"galatasaray", "besiktas"}, {"fenerbahçe", "besiktas"},
]


def compute_context_modifiers(
    analysis_packet: dict,
    classificacao: Optional[list],
    jogo: dict,
) -> dict:
    """
    Computa modificadores contextuais quantitativos para todos os mercados.

    Args:
        analysis_packet : Pacote do Master Analyzer (já inclui lambdas e weighted_metrics)
        classificacao   : Tabela de classificação da liga (pode ser None)
        jogo            : Dados raw do fixture (API-Football)

    Returns:
        dict com:
        - multipliers_home  : {lambda_goals, corners, cards, shots}
        - multipliers_away  : {lambda_goals, corners, cards, shots}
        - context_bullets   : [str]  bullets humanos para a seção CONTEXTO
        - scenarios_detected: [str]  tags de cenários
        - referee           : str    nome do árbitro (se disponível)
    """
    home_name = jogo.get("teams", {}).get("home", {}).get("name", "Casa")
    away_name = jogo.get("teams", {}).get("away", {}).get("name", "Fora")
    match_date_str = jogo.get("fixture", {}).get("date", "")
    venue_city = (jogo.get("fixture", {}).get("venue", {}).get("city") or "").strip()
    referee = (jogo.get("fixture", {}).get("referee") or "").strip()

    home_pos = analysis_packet.get("home_position")
    away_pos = analysis_packet.get("away_position")

    raw = analysis_packet.get("raw_data", {})
    recent_home = raw.get("recent_fixtures_home", [])
    recent_away = raw.get("recent_fixtures_away", [])

    total_teams = len(classificacao) if classificacao else 20

    scenarios_detected: list = []
    context_bullets: list = []

    # 1. PRECISA_VENCER / SEM_MOTIVACAO
    if home_pos and home_pos != "N/A":
        _detect_motivation(home_pos, total_teams, home_name, "HOME",
                           scenarios_detected, context_bullets)
    if away_pos and away_pos != "N/A":
        _detect_motivation(away_pos, total_teams, away_name, "AWAY",
                           scenarios_detected, context_bullets)

    # 2. CANSADO (fadiga — 3+ jogos em 7 dias)
    match_date = _parse_date(match_date_str)
    if match_date:
        n_home = _count_games_7days(recent_home, match_date)
        n_away = _count_games_7days(recent_away, match_date)
        if n_home >= 3:
            scenarios_detected.append("CANSADO_HOME")
            context_bullets.append(
                f"😴 {home_name}: DESGASTE — {n_home} jogos em 7 dias "
                f"(λ−12%, finalizações−15%, escanteios−10%)"
            )
        if n_away >= 3:
            scenarios_detected.append("CANSADO_AWAY")
            context_bullets.append(
                f"😴 {away_name}: DESGASTE — {n_away} jogos em 7 dias "
                f"(λ−12%, finalizações−15%, escanteios−10%)"
            )

    # 3. CLÁSSICO
    if _is_clasico(home_name, away_name):
        scenarios_detected.append("CLASICO")
        context_bullets.append(
            f"🔥 CLÁSSICO detectado — {home_name} vs {away_name} "
            f"(cartões+30%, finalizações+10%)"
        )

    # 4. ALTITUDE
    if venue_city and venue_city.lower() in _ALTITUDE_CITIES:
        scenarios_detected.append("ALTITUDE_AWAY")
        context_bullets.append(
            f"⛰️ ALTITUDE — estádio em {venue_city} "
            f"(casa λ+5%, visitante λ−10% / finalizações−10%)"
        )

    # 5. MATA-MATA (knockout)
    _summary = analysis_packet.get("analysis_summary", {})
    knockout_scenario = _summary.get("knockout_scenario")
    if knockout_scenario and knockout_scenario.get("is_knockout"):
        scenario_type = knockout_scenario.get("scenario_type", "")
        _REVERSAL_TYPES = {
            "GIANT_NEEDS_MIRACLE",
            "UNDERDOG_MIRACLE_ATTEMPT",
            "BALANCED_TIE_DECIDER",
        }
        _ADVANTAGE_TYPES = {
            "MANAGING_THE_LEAD",
            "NARROW_LEAD_DEFENSE",
        }
        if scenario_type in _REVERSAL_TYPES:
            scenarios_detected.append("KNOCKOUT_REVERSAL_BOTH")
            context_bullets.append(
                f"⚡ MATA-MATA (2ª mão) — cenário REVERSÃO "
                f"(ambos buscam gols: λ+15%, escanteios+15%)"
            )
        elif scenario_type in _ADVANTAGE_TYPES:
            scenarios_detected.append("KNOCKOUT_ADVANTAGE_AWAY")
            context_bullets.append(
                f"🛡️ MATA-MATA (2ª mão) — time com vantagem pode gerir o jogo "
                f"(λ visitante −12%)"
            )

    # 6. Árbitro (informativo — sem perfil estatístico ainda)
    if referee:
        context_bullets.append(
            f"👨‍⚖️ Árbitro: {referee} — sem perfil de cartões registado"
        )

    # Calcular multiplicadores finais (produto composto de todos os cenários)
    mult_home = {"lambda_goals": 1.0, "corners": 1.0, "cards": 1.0, "shots": 1.0}
    mult_away = {"lambda_goals": 1.0, "corners": 1.0, "cards": 1.0, "shots": 1.0}

    for scenario in scenarios_detected:
        s = _SCENARIO_MULTIPLIERS.get(scenario, {})
        for k, v in s.get("home", {}).items():
            mult_home[k] = round(mult_home.get(k, 1.0) * v, 4)
        for k, v in s.get("away", {}).items():
            mult_away[k] = round(mult_away.get(k, 1.0) * v, 4)

    if scenarios_detected:
        print(f"  🧭 CONTEXTO: {scenarios_detected}")
        for b in context_bullets:
            print(f"     • {b}")
        print(f"  📐 Mult Casa: {mult_home}")
        print(f"  📐 Mult Fora: {mult_away}")

    return {
        "multipliers_home": mult_home,
        "multipliers_away": mult_away,
        "context_bullets": context_bullets,
        "scenarios_detected": scenarios_detected,
        "referee": referee,
    }


def apply_context_multipliers(analysis_packet: dict, context_modifiers: dict) -> None:
    """
    Aplica os multiplicadores contextuais aos campos relevantes do analysis_packet.
    Modifica in-place: lambda_goals, weighted_metrics_home/away.
    Chamado ANTES dos analisadores especializados.
    """
    if not context_modifiers or not context_modifiers.get("scenarios_detected"):
        return

    mult_home = context_modifiers.get("multipliers_home", {})
    mult_away = context_modifiers.get("multipliers_away", {})

    # Lambda goals (Poisson — afeta todos os mercados de gols)
    lambda_data = analysis_packet.get("calculated_probabilities", {}).get("lambda_goals", {})
    if lambda_data:
        lh = lambda_data.get("lambda_home", 0.0)
        la = lambda_data.get("lambda_away", 0.0)
        lh_new = round(max(0.20, lh * mult_home.get("lambda_goals", 1.0)), 4)
        la_new = round(max(0.15, la * mult_away.get("lambda_goals", 1.0)), 4)
        if lh_new != lh or la_new != la:
            print(f"  🔧 CONTEXTO→λ: Casa {lh:.2f}→{lh_new:.2f} | Fora {la:.2f}→{la_new:.2f}")
        lambda_data["lambda_home"] = lh_new
        lambda_data["lambda_away"] = la_new
        lambda_data["lambda_total"] = round(lh_new + la_new, 4)

    # Weighted metrics: cantos, cartões, finalizações
    _apply_weighted(
        analysis_packet, "weighted_metrics_home", mult_home,
        [
            ("weighted_corners_for", "corners"),
            ("weighted_cards_for", "cards"),
            ("weighted_shots_for", "shots"),
        ]
    )
    _apply_weighted(
        analysis_packet, "weighted_metrics_away", mult_away,
        [
            ("weighted_corners_for", "corners"),
            ("weighted_cards_for", "cards"),
            ("weighted_shots_for", "shots"),
        ]
    )


def _apply_weighted(analysis_packet: dict, key: str, mult: dict, field_map: list) -> None:
    wm = analysis_packet.get("analysis_summary", {}).get(key, {})
    if not wm:
        return
    for wm_field, mult_key in field_map:
        m = mult.get(mult_key, 1.0)
        if m != 1.0 and wm_field in wm and wm[wm_field] is not None:
            wm[wm_field] = round(float(wm[wm_field]) * m, 3)


# --------------------------------------------------------------------------
# Helpers internos
# --------------------------------------------------------------------------

def _detect_motivation(
    pos, total_teams: int, team_name: str, side: str,
    scenarios_detected: list, context_bullets: list
) -> None:
    """Detects PRECISA_VENCER or SEM_MOTIVACAO from league position."""
    try:
        pos = int(pos)
    except (TypeError, ValueError):
        return

    if total_teams <= 1:
        return

    relegation_start = total_teams - 2   # últimas 3 posições
    danger_start = total_teams - 5       # próximas 3 posições acima do rebaixamento
    mid_start = 8
    mid_end = total_teams - 6

    if pos >= relegation_start:
        scenarios_detected.append(f"PRECISA_VENCER_{side}")
        context_bullets.append(
            f"🚨 {team_name}: {pos}º lugar — ZONA DE REBAIXAMENTO — PRECISA VENCER "
            f"(λ+20%, escanteios+25%, cartões+20%)"
        )
    elif pos >= danger_start:
        scenarios_detected.append(f"PRECISA_VENCER_{side}")
        context_bullets.append(
            f"⚠️ {team_name}: {pos}º lugar — pressionado, à beira do rebaixamento "
            f"(λ+20%, escanteios+25%, cartões+20%)"
        )
    elif total_teams >= 16 and mid_start <= pos <= mid_end:
        scenarios_detected.append(f"SEM_MOTIVACAO_{side}")
        context_bullets.append(
            f"😐 {team_name}: {pos}º lugar — meio de tabela sem objetivos claros "
            f"(λ−8%, finalizações−8%)"
        )


def _count_games_7days(recent_fixtures: list, match_date: datetime) -> int:
    """Conta jogos disputados nos últimos 7 dias antes da partida."""
    if not recent_fixtures:
        return 0
    count = 0
    cutoff = match_date - timedelta(days=7)
    for fixture in recent_fixtures:
        if not isinstance(fixture, dict):
            continue
        fd = fixture.get("fixture", {})
        date_str = fd.get("date", "") if isinstance(fd, dict) else ""
        d = _parse_date(date_str)
        if d and cutoff <= d < match_date:
            count += 1
    return count


def _parse_date(date_str: str) -> Optional[datetime]:
    """Parse ISO date string para datetime UTC-aware."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _is_clasico(home_name: str, away_name: str) -> bool:
    """Detecta clássicos conhecidos por correspondência de nome."""
    h = home_name.lower()
    a = away_name.lower()
    for pair in _CLASICO_PAIRS:
        pair_list = list(pair)
        match_h = any(p in h for p in pair_list)
        match_a = any(p in a for p in pair_list)
        if match_h and match_a and h != a:
            return True
    return False
