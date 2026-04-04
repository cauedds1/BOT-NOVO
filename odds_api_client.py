# odds_api_client.py
"""
The Odds API integration — complemento para API-Football odds.

Estratégia híbrida:
  1. The Odds API → 1X2, Over/Under gols, BTTS, Handicap (melhor cobertura)
  2. API-Football  → cantos, cartões, placar exato, HT/FT (nichos não cobertos pela The Odds API)

A função principal é `buscar_odds_the_odds_api()` que:
  - Requer ODDS_API_KEY no ambiente
  - Faz cache em memória por 30 min (evita chamadas repetidas no mesmo dia)
  - Usa matching fuzzy de nomes de times para associar o fixture ao evento da The Odds API
  - Retorna dicionário no mesmo formato normalizado interno do sistema
"""

import os
import asyncio
import httpx
import logging
import difflib
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

ODDS_API_KEY = os.getenv("ODDS_API_KEY")
ODDS_API_BASE = "https://api.the-odds-api.com/v4"

# ── Mapeamento: league_id API-Football → sport key The Odds API ──────────────
# Ligas suportadas pela The Odds API (soccer)
LEAGUE_TO_SPORT_KEY = {
    # Europa — Elite
    39:  "soccer_england_premier_league",
    40:  "soccer_england_efl_champ",
    41:  "soccer_england_league1",
    42:  "soccer_england_league2",
    140: "soccer_spain_la_liga",
    141: "soccer_spain_segunda_division",
    135: "soccer_italy_serie_a",
    136: "soccer_italy_serie_b",
    78:  "soccer_germany_bundesliga",
    79:  "soccer_germany_bundesliga2",
    61:  "soccer_france_ligue_one",
    62:  "soccer_france_ligue_deux",
    # Europa — Outros
    88:  "soccer_netherlands_eredivisie",
    94:  "soccer_portugal_primeira_liga",
    144: "soccer_belgium_first_div",
    179: "soccer_scotland_premiership",
    203: "soccer_turkey_super_league",
    207: "soccer_switzerland_superleague",
    197: "soccer_greece_super_league",
    218: "soccer_austria_bundesliga",
    235: "soccer_russia_premier_league",
    119: "soccer_denmark_superliga",
    103: "soccer_norway_eliteserien",
    113: "soccer_sweden_allsvenskan",
    106: "soccer_poland_ekstraklasa",
    # UEFA
    2:   "soccer_uefa_champs_league",
    3:   "soccer_uefa_europa_league",
    848: "soccer_uefa_europa_conference_league",
    # América do Sul
    71:  "soccer_brazil_campeonato",
    72:  "soccer_brazil_serie_b",
    128: "soccer_argentina_primera_division",
    239: "soccer_colombia_primera_a",
    265: "soccer_chile_campeonato",
    274: "soccer_uruguay_primera_division",
    240: "soccer_ecuador_liga_pro",
    250: "soccer_paraguay_primera_division",
    281: "soccer_peru_liga_1",
    # Copa
    13:  "soccer_conmebol_copa_libertadores",
    11:  "soccer_conmebol_copa_sudamericana",
    # América do Norte
    253: "soccer_usa_mls",
    262: "soccer_mexico_ligamx",
    # Ásia / Outros
    307: "soccer_saudi_arabias_league",
    83:  "soccer_japan_j_league",
    292: "soccer_south_korea_kleague1",
}

# ── Cache em memória (chave: sport_key+date → (timestamp, lista_eventos)) ────
_events_cache: dict[str, tuple[float, list]] = {}
CACHE_TTL_SECONDS = 1800  # 30 minutos


def _cache_get(key: str) -> Optional[list]:
    entry = _events_cache.get(key)
    if entry is None:
        return None
    ts, data = entry
    if (datetime.now().timestamp() - ts) > CACHE_TTL_SECONDS:
        del _events_cache[key]
        return None
    return data


def _cache_set(key: str, data: list) -> None:
    _events_cache[key] = (datetime.now().timestamp(), data)


# ── Normalização de nomes para matching ──────────────────────────────────────
def _normalizar_nome(nome: str) -> str:
    """Remove sufixos comuns e lowercase para melhorar matching fuzzy."""
    import re
    nome = nome.lower().strip()
    # Remover sufixos comuns
    for sufixo in [" fc", " cf", " sc", " ac", " bc", " united", " city",
                   " utd", " afc", " fk", " sk", " bk", " if", " ik"]:
        if nome.endswith(sufixo):
            nome = nome[:-len(sufixo)].strip()
    # Remover caracteres especiais
    nome = re.sub(r"[^\w\s]", " ", nome)
    nome = re.sub(r"\s+", " ", nome).strip()
    return nome


def _similaridade(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, _normalizar_nome(a), _normalizar_nome(b)).ratio()


# ── Fetch eventos da The Odds API ────────────────────────────────────────────
async def _fetch_eventos_odds_api(sport_key: str, date_str: str) -> list:
    """
    Busca eventos com odds da The Odds API para um sport_key e data.
    Retorna lista de eventos ou [] em caso de erro.

    Chave de cache: sport_key+date_str
    """
    if not ODDS_API_KEY:
        return []

    cache_key = f"{sport_key}_{date_str}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    # The Odds API: pegar eventos com odds — mercados h2h, totals, alternate_totals, btts, spreads
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "eu",               # odds europeias (formato decimal)
        "markets": "h2h,totals,alternate_totals,btts,spreads",
        "oddsFormat": "decimal",
        "dateFormat": "iso",
        "commenceTimeFrom": f"{date_str}T00:00:00Z",
        "commenceTimeTo":   f"{date_str}T23:59:59Z",
    }

    url = f"{ODDS_API_BASE}/sports/{sport_key}/odds"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 401:
                logger.warning("[OddsAPI] Chave inválida (401)")
                return []
            if resp.status_code == 422:
                logger.debug(f"[OddsAPI] Sport key não suportada: {sport_key}")
                return []
            if resp.status_code == 429:
                logger.warning("[OddsAPI] Rate limit atingido (429)")
                return []
            resp.raise_for_status()
            eventos = resp.json()
            if isinstance(eventos, list):
                _cache_set(cache_key, eventos)
                logger.info(f"[OddsAPI] {len(eventos)} eventos para {sport_key} em {date_str}")
                return eventos
            return []
    except httpx.TimeoutException:
        logger.warning(f"[OddsAPI] Timeout ao buscar {sport_key}")
        return []
    except Exception as e:
        logger.warning(f"[OddsAPI] Erro ao buscar {sport_key}: {e}")
        return []


def _encontrar_evento(
    eventos: list, home_team: str, away_team: str, date_str: str = ""
) -> Optional[dict]:
    """
    Encontra o evento que melhor corresponde ao par home/away via matching fuzzy.

    Critérios:
    - Similaridade de nomes (difflib, threshold 0.75 na média home+away)
    - Verificação explícita de data: o evento deve iniciar no mesmo dia UTC que date_str
      (guarda de segurança contra edge cases de timezone ou listagens multi-dia)

    Retorna None se nenhum evento satisfizer os critérios.
    """
    melhor_score = 0.0
    melhor_evento = None

    for ev in eventos:
        # Verificação explícita de data quando disponível
        if date_str:
            ev_commence = ev.get("commence_time", "")
            if ev_commence and not ev_commence.startswith(date_str):
                # Aceitar também +/-1 dia para lidar com diferença de timezone
                try:
                    ev_date = ev_commence[:10]
                    target = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                    ev_dt = datetime.strptime(ev_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                    if abs((ev_dt - target).days) > 1:
                        continue
                except Exception:
                    pass

        ev_home = ev.get("home_team", "")
        ev_away = ev.get("away_team", "")

        score_home = _similaridade(home_team, ev_home)
        score_away = _similaridade(away_team, ev_away)
        score = (score_home + score_away) / 2

        if score > melhor_score:
            melhor_score = score
            melhor_evento = ev

    if melhor_score >= 0.75 and melhor_evento is not None:
        logger.debug(
            f"[OddsAPI] Match encontrado (score={melhor_score:.2f}): "
            f"'{home_team}' vs '{away_team}' → "
            f"'{melhor_evento.get('home_team')}' vs '{melhor_evento.get('away_team')}'"
        )
        return melhor_evento

    if melhor_score > 0:
        logger.debug(
            f"[OddsAPI] Match insuficiente (score={melhor_score:.2f}) para "
            f"'{home_team}' vs '{away_team}'"
        )
    return None


# ── Normalização do formato The Odds API → formato interno ───────────────────
def _normalizar_evento_odds_api(evento: dict) -> dict:
    """
    Converte evento da The Odds API para o dicionário normalizado interno.

    Formato The Odds API por mercado:
      h2h      → outcomes: [{name: "Team A", price: 2.5}, {name: "Draw"}, {name: "Team B"}]
      totals   → outcomes: [{name: "Over", price: 1.85, point: 2.5}, {name: "Under", ...}]
      btts     → outcomes: [{name: "Yes", price: 1.70}, {name: "No", price: 2.10}]
      spreads  → outcomes: [{name: "Team A", price: 1.90, point: -1.5}, ...]

    Estratégia: usar a MELHOR odd (mais alta) entre todos os bookmakers para cada desfecho.
    Isso maximiza o valor percebido sem precisar comparar casas manualmente.
    """
    home_team = evento.get("home_team", "")
    away_team = evento.get("away_team", "")
    bookmakers = evento.get("bookmakers", [])

    # Agregar todas as odds por mercado → outcome, pegando a melhor entre bookmakers
    # Estrutura: best_odds[market_key][outcome_key] = melhor_odd_float
    best_odds: dict[str, dict[str, float]] = {}

    for bm in bookmakers:
        for market in bm.get("markets", []):
            mkey = market.get("key", "")
            if mkey not in best_odds:
                best_odds[mkey] = {}
            for outcome in market.get("outcomes", []):
                oname = outcome.get("name", "")
                price = float(outcome.get("price", 0) or 0)
                point = outcome.get("point")  # para totals e spreads

                # Chave composta para totals/spreads (inclui linha)
                if point is not None:
                    okey = f"{oname}_{point}"
                else:
                    okey = oname

                # Guardar a MELHOR odd (mais alta) entre bookmakers
                if price > best_odds[mkey].get(okey, 0):
                    best_odds[mkey][okey] = price
                    # Guardar também o point separado para uso posterior
                    if point is not None:
                        best_odds[mkey][f"__point_{oname}_{point}"] = float(point)

    odds_norm = {}

    # ── h2h → 1X2 ────────────────────────────────────────────────────────────
    if "h2h" in best_odds:
        h = best_odds["h2h"]
        # Identificar home/away/draw pelos nomes dos outcomes
        for okey, price in h.items():
            if okey.startswith("__"):
                continue
            if okey == "Draw":
                odds_norm["empate"] = price
            elif okey == home_team or _similaridade(okey, home_team) >= 0.75:
                odds_norm["casa_vence"] = price
            elif okey == away_team or _similaridade(okey, away_team) >= 0.75:
                odds_norm["fora_vence"] = price

    # ── totals + alternate_totals → Over/Under gols ──────────────────────────
    # Processa ambos os mercados com a mesma lógica; alternate_totals cobre 1.5, 3.5, 4.5 etc.
    # A odd mais alta (best_odds) já foi selecionada entre bookmakers.
    def _process_totals_market(t: dict) -> None:
        linhas_vistas: set[float] = set()
        for okey in t:
            if okey.startswith("__"):
                continue
            # okey = "Over_2.5" ou "Under_2.5"
            parts = okey.split("_", 1)
            if len(parts) != 2:
                continue
            direcao, linha_str = parts
            try:
                linha = float(linha_str)
            except ValueError:
                continue
            linhas_vistas.add(linha)

        for linha in linhas_vistas:
            over_key = f"Over_{linha}"
            under_key = f"Under_{linha}"
            linha_fmt = str(int(linha)) if linha == int(linha) else str(linha)
            norm_over = f"gols_ft_over_{linha_fmt}"
            norm_under = f"gols_ft_under_{linha_fmt}"
            if over_key in t:
                # Manter a melhor odd entre totals e alternate_totals
                if t[over_key] > odds_norm.get(norm_over, 0):
                    odds_norm[norm_over] = t[over_key]
            if under_key in t:
                if t[under_key] > odds_norm.get(norm_under, 0):
                    odds_norm[norm_under] = t[under_key]

    if "totals" in best_odds:
        _process_totals_market(best_odds["totals"])
    if "alternate_totals" in best_odds:
        _process_totals_market(best_odds["alternate_totals"])

    # ── btts → Both Teams Score ───────────────────────────────────────────────
    if "btts" in best_odds:
        b = best_odds["btts"]
        for okey, price in b.items():
            if okey.startswith("__"):
                continue
            if okey.lower() in ("yes", "sim"):
                odds_norm["btts_yes"] = price
                odds_norm["btts_sim"] = price
            elif okey.lower() in ("no", "não", "nao"):
                odds_norm["btts_no"] = price
                odds_norm["btts_nao"] = price

    # ── spreads → Handicap Asiático ───────────────────────────────────────────
    if "spreads" in best_odds:
        s = best_odds["spreads"]
        for okey, price in s.items():
            if okey.startswith("__"):
                continue
            # okey = "Team A_-1.5" ou "Team B_+1.5"
            parts = okey.rsplit("_", 1)
            if len(parts) != 2:
                continue
            team_name, linha_str = parts
            try:
                linha = float(linha_str)
            except ValueError:
                continue
            linha_fmt = f"+{int(linha)}" if linha > 0 else str(int(linha)) if linha == int(linha) else (f"+{linha}" if linha > 0 else str(linha))
            if _similaridade(team_name, home_team) >= 0.75:
                odds_norm[f"handicap_casa_{linha_fmt}"] = price
            elif _similaridade(team_name, away_team) >= 0.75:
                odds_norm[f"handicap_fora_{linha_fmt}"] = price

    return odds_norm


# ── Função pública principal ─────────────────────────────────────────────────
async def buscar_odds_the_odds_api(
    fixture_id: int,
    home_team: str,
    away_team: str,
    match_date: str,
    league_id: int,
) -> dict:
    """
    Busca odds da The Odds API para um fixture, retornando dicionário normalizado.

    Retorna {} se:
    - ODDS_API_KEY não configurada
    - Liga não mapeada
    - Evento não encontrado pelo matching fuzzy
    - Qualquer erro de rede

    Args:
        fixture_id: ID do fixture (usado apenas para logging)
        home_team:  Nome do time da casa (API-Football)
        away_team:  Nome do time visitante (API-Football)
        match_date: Data do jogo ISO 8601 (ex: "2026-04-05T15:00:00+00:00")
        league_id:  ID da liga (API-Football)

    Returns:
        dict normalizado compatível com os analisadores
    """
    if not ODDS_API_KEY:
        return {}

    sport_key = LEAGUE_TO_SPORT_KEY.get(league_id)
    if not sport_key:
        logger.debug(f"[OddsAPI] Liga {league_id} não mapeada")
        return {}

    # Extrair data (YYYY-MM-DD) da string ISO
    try:
        if "T" in match_date:
            date_str = match_date[:10]
        else:
            date_str = match_date[:10]
    except Exception:
        logger.warning(f"[OddsAPI] Data inválida: {match_date}")
        return {}

    eventos = await _fetch_eventos_odds_api(sport_key, date_str)
    if not eventos:
        return {}

    evento = _encontrar_evento(eventos, home_team, away_team, date_str=date_str)
    if evento is None:
        logger.debug(f"[OddsAPI] Fixture {fixture_id}: evento não encontrado para '{home_team}' vs '{away_team}'")
        return {}

    odds = _normalizar_evento_odds_api(evento)
    logger.info(
        f"[OddsAPI] Fixture {fixture_id}: {len(odds)} chaves de odds obtidas "
        f"({sport_key})"
    )
    return odds


# ── Wrappers públicos com nomes da especificação ──────────────────────────────
async def buscar_eventos_odds_api(sport_key: str, date_str: str) -> list:
    """Wrapper público para buscar lista de eventos da The Odds API por sport+data."""
    return await _fetch_eventos_odds_api(sport_key, date_str)


def encontrar_evento_odds_api(
    eventos: list, home_team: str, away_team: str, date_str: str = ""
) -> Optional[dict]:
    """Wrapper público para matching fuzzy de fixture em lista de eventos."""
    return _encontrar_evento(eventos, home_team, away_team, date_str=date_str)


def normalizar_odds_api(evento: dict) -> dict:
    """Wrapper público para normalizar evento The Odds API → formato interno."""
    return _normalizar_evento_odds_api(evento)
