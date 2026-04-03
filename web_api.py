"""
AnalyTips Web API - FastAPI Backend
Expõe os dados de análise via REST para o frontend React.
O bot Telegram (main.py) continua intacto e funciona em paralelo.
"""

import asyncio
import os
from datetime import datetime
from typing import Dict, Optional
from zoneinfo import ZoneInfo

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# ── Módulos do projeto ──────────────────────────────────────────────────
import api_client
from api_client import (
    buscar_jogos_do_dia,
    buscar_odds_do_jogo,
    buscar_classificacao_liga,
    NOMES_LIGAS_PT,
    LIGAS_DE_INTERESSE,
)
import httpx as _httpx
import db_manager as _db_module
from analysts.master_analyzer import generate_match_analysis
from analysts.goals_analyzer_v2 import analisar_mercado_gols
from analysts.match_result_analyzer_v2 import analisar_mercado_resultado_final
from analysts.corners_analyzer import analisar_mercado_cantos
from analysts.btts_analyzer import analisar_mercado_btts
from analysts.cards_analyzer import analisar_mercado_cartoes
from analysts.shots_analyzer import analisar_mercado_finalizacoes
from analysts.handicaps_analyzer import analisar_mercado_handicaps
from analysts.double_chance_analyzer import analisar_mercado_dupla_chance
from analysts.gabt_analyzer import analisar_mercado_gabt
from analysts.correct_score_analyzer import analisar_mercado_placar_exato
from analysts.european_handicap_analyzer import analisar_mercado_handicap_europeu
from analysts.first_goal_analyzer import analisar_mercado_primeiro_a_marcar
from config import LEAGUE_WEIGHTING_FACTOR, QUALITY_SCORES

BRASILIA_TZ = ZoneInfo("America/Sao_Paulo")

# ── Instância do banco ───────────────────────────────────────────────────
db = _db_module.DatabaseManager()

# ── Status em memória (processamento de análises) ────────────────────────
_processing_status: Dict[int, str] = {}   # fixture_id -> "processing" | "ready" | "error"

# ── FastAPI ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="AnalyTips API",
    description="Backend de análise de apostas esportivas",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Lifecycle ────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    """Inicializa o cliente HTTP compartilhado."""
    api_key = os.environ.get("API_FOOTBALL_KEY")
    headers = {k: v for k, v in {
        "x-rapidapi-host": "v3.football.api-sports.io",
        "x-rapidapi-key": api_key,
    }.items() if v is not None}

    client = _httpx.AsyncClient(
        timeout=10.0,
        headers=headers,
        limits=_httpx.Limits(max_keepalive_connections=5, max_connections=10),
        http2=False,
    )
    api_client.set_http_client(client)
    if api_key:
        print("✅ [WebAPI] HTTP client inicializado com chave de API")
    else:
        print("⚠️ [WebAPI] HTTP client iniciado SEM chave de API. Configure API_FOOTBALL_KEY.")


@app.on_event("shutdown")
async def shutdown_event():
    from api_client import close_http_client
    await close_http_client()
    print("✅ [WebAPI] HTTP client fechado")


# ─────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────

def _calcular_score_destaque(liga_id: int, time_casa_id: int, time_fora_id: int) -> float:
    """
    Calcula um score de destaque (0–100) combinando:
    - Peso da liga (LEAGUE_WEIGHTING_FACTOR)
    - Qualidade média dos dois times (QUALITY_SCORES)
    Score = liga_peso * (qs_casa + qs_fora) / 2
    Liga 1.0 com dois times de 90 → score 90.0
    Liga 0.60 com dois times de 65 → score 39.0
    """
    liga_peso = LEAGUE_WEIGHTING_FACTOR.get(liga_id, 0.60)
    qs_casa = QUALITY_SCORES.get(time_casa_id, 65)
    qs_fora = QUALITY_SCORES.get(time_fora_id, 65)
    return round(liga_peso * (qs_casa + qs_fora) / 2, 1)


def _formatar_jogo(jogo: dict, tem_analise: bool = False) -> dict:
    """Serializa um fixture da API-Football para o formato do frontend."""
    liga_id = jogo.get("league", {}).get("id")
    liga_info = NOMES_LIGAS_PT.get(liga_id)
    nome_liga = liga_info[0] if liga_info else jogo.get("league", {}).get("name", "")
    pais_liga = liga_info[1] if liga_info else jogo.get("league", {}).get("country", "")

    data_utc = jogo.get("fixture", {}).get("date", "")
    horario_brt = ""
    if data_utc:
        try:
            dt_utc = datetime.fromisoformat(data_utc.replace("Z", "+00:00"))
            dt_brt = dt_utc.astimezone(BRASILIA_TZ)
            horario_brt = dt_brt.strftime("%H:%M")
        except Exception:
            horario_brt = ""

    time_casa_id = jogo.get("teams", {}).get("home", {}).get("id")
    time_fora_id = jogo.get("teams", {}).get("away", {}).get("id")
    liga_peso = LEAGUE_WEIGHTING_FACTOR.get(liga_id, 0.60)
    score_destaque = _calcular_score_destaque(liga_id, time_casa_id, time_fora_id)

    return {
        "fixture_id": jogo.get("fixture", {}).get("id"),
        "status": jogo.get("fixture", {}).get("status", {}).get("short", "NS"),
        "horario_brt": horario_brt,
        "data_iso": data_utc,
        "liga": {
            "id": liga_id,
            "nome": nome_liga,
            "pais": pais_liga,
            "logo": jogo.get("league", {}).get("logo", ""),
            "bandeira": jogo.get("league", {}).get("flag", ""),
        },
        "time_casa": {
            "id": time_casa_id,
            "nome": jogo.get("teams", {}).get("home", {}).get("name", ""),
            "logo": jogo.get("teams", {}).get("home", {}).get("logo", ""),
        },
        "time_fora": {
            "id": time_fora_id,
            "nome": jogo.get("teams", {}).get("away", {}).get("name", ""),
            "logo": jogo.get("teams", {}).get("away", {}).get("logo", ""),
        },
        "tem_analise": tem_analise,
        "score_destaque": score_destaque,
        "liga_peso": liga_peso,
    }


def _estruturar_palpites(mercado_nome: str, analise: Optional[dict]) -> Optional[dict]:
    """Converte o resultado de um analyzer para o formato JSON da API."""
    if not analise or not analise.get("palpites"):
        return None
    palpites = analise["palpites"]
    if not palpites:
        return None
    return {
        "mercado": mercado_nome,
        "palpites": [
            {
                "tipo": p.get("tipo", ""),
                "confianca": p.get("confianca", 0),
                "probabilidade": p.get("probabilidade", 0),
                "odd": p.get("odd"),
                "edge": p.get("edge"),
                "periodo": p.get("periodo", "FT"),
                "time": p.get("time", ""),
                "mercado": p.get("mercado", mercado_nome),
                "justificativa": p.get("justificativa", ""),
                "confidence_breakdown": p.get("confidence_breakdown", {}),
            }
            for p in palpites
        ],
    }


async def _executar_analise_completa(fixture_id: int, jogo: dict):
    """
    Executa o pipeline completo de análise para um jogo e salva no DB.
    Chamada como BackgroundTask — não bloqueia o endpoint.
    """
    _processing_status[fixture_id] = "processing"
    print(f"[WebAPI] Iniciando análise em background para fixture #{fixture_id}")

    try:
        id_liga = jogo["league"]["id"]

        # 1. Master Analyzer
        analysis_packet = await generate_match_analysis(jogo)
        if "error" in analysis_packet:
            print(f"[WebAPI] Master Analyzer retornou erro: {analysis_packet['error']}")
            _processing_status[fixture_id] = "error"
            return

        # 2. Odds e classificação
        odds = await buscar_odds_do_jogo(fixture_id)
        classificacao = await buscar_classificacao_liga(id_liga)

        pos_casa = "N/A"
        pos_fora = "N/A"
        if classificacao:
            for t in classificacao:
                if t["team"]["name"] == jogo["teams"]["home"]["name"]:
                    pos_casa = t["rank"]
                if t["team"]["name"] == jogo["teams"]["away"]["name"]:
                    pos_fora = t["rank"]

        analysis_packet["home_position"] = pos_casa
        analysis_packet["away_position"] = pos_fora
        analysis_packet["league_standings"] = classificacao

        script = analysis_packet["analysis_summary"]["selected_script"]
        stats_casa = analysis_packet["raw_data"]["home_stats"]
        stats_fora = analysis_packet["raw_data"]["away_stats"]

        # 3. Analyzers especializados
        analise_gols = analisar_mercado_gols(analysis_packet, odds)
        analise_resultado = analisar_mercado_resultado_final(analysis_packet, odds)
        analise_cantos = analisar_mercado_cantos(analysis_packet, odds)
        analise_btts = analisar_mercado_btts(stats_casa, stats_fora, odds, script)
        analise_cartoes = analisar_mercado_cartoes(analysis_packet, odds)
        analise_finalizacoes = analisar_mercado_finalizacoes(stats_casa, stats_fora, odds, analysis_packet, script)
        analise_handicaps = analisar_mercado_handicaps(stats_casa, stats_fora, odds, classificacao, pos_casa, pos_fora, script)
        analise_dupla_chance = analisar_mercado_dupla_chance(analysis_packet, odds)
        analise_gabt = analisar_mercado_gabt(analysis_packet, odds)
        analise_placar_exato = analisar_mercado_placar_exato(analysis_packet, odds)
        analise_handicap_europeu = analisar_mercado_handicap_europeu(analysis_packet, odds)
        analise_primeiro_marcador = analisar_mercado_primeiro_a_marcar(analysis_packet, odds)

        # 4. Salvar no banco
        data_utc = jogo.get("fixture", {}).get("date", "")
        dt_brt = datetime.now(BRASILIA_TZ)
        if data_utc:
            try:
                dt_utc = datetime.fromisoformat(data_utc.replace("Z", "+00:00"))
                dt_brt = dt_utc.astimezone(BRASILIA_TZ)
            except Exception:
                pass

        liga_info = NOMES_LIGAS_PT.get(id_liga)
        nome_liga = liga_info[0] if liga_info else jogo.get("league", {}).get("name", "")

        dados_jogo = {
            "data_jogo": dt_brt,
            "liga": nome_liga,
            "time_casa": jogo["teams"]["home"]["name"],
            "time_fora": jogo["teams"]["away"]["name"],
        }
        analises = {
            "gols": analise_gols,
            "cantos": analise_cantos,
            "btts": analise_btts,
            "resultado": analise_resultado,
            "cartoes": analise_cartoes,
            "finalizacoes": analise_finalizacoes,
            "handicaps": analise_handicaps,
            "dupla_chance": analise_dupla_chance,
            "gabt": analise_gabt,
            "placar_exato": analise_placar_exato,
            "handicap_europeu": analise_handicap_europeu,
            "primeiro_marcador": analise_primeiro_marcador,
        }
        stats = {
            "stats_casa": stats_casa,
            "stats_fora": stats_fora,
            "classificacao": classificacao,
        }
        db.salvar_analise(fixture_id, dados_jogo, analises, stats)

        _processing_status[fixture_id] = "ready"
        print(f"[WebAPI] Análise concluída e salva para fixture #{fixture_id}")

    except Exception as e:
        print(f"[WebAPI] Erro na análise de fixture #{fixture_id}: {e}")
        _processing_status[fixture_id] = "error"


def _db_to_api_response(analise_db: dict, fixture_id: int) -> dict:
    """Converte o resultado do db_manager para o formato JSON da API."""
    mercados = []
    mapa = [
        ("Gols", "analise_gols"),
        ("Resultado", "analise_resultado"),
        ("BTTS", "analise_btts"),
        ("Cantos", "analise_cantos"),
        ("Cartões", "analise_cartoes"),
        ("Finalizações", "analise_finalizacoes"),
        ("Handicaps", "analise_handicaps"),
        ("Dupla Chance", "analise_dupla_chance"),
        ("Gols Ambos Tempos", "analise_gabt"),
        ("Placar Exato", "analise_placar_exato"),
        ("Handicap Europeu", "analise_handicap_europeu"),
        ("Primeiro a Marcar", "analise_primeiro_marcador"),
    ]
    for nome, chave in mapa:
        dados = analise_db.get(chave)
        if dados:
            estruturado = _estruturar_palpites(nome, dados)
            if estruturado:
                mercados.append(estruturado)

    total_palpites = sum(len(m["palpites"]) for m in mercados)
    melhor_confianca = 0.0
    for m in mercados:
        for p in m["palpites"]:
            melhor_confianca = max(melhor_confianca, p.get("confianca", 0))

    return {
        "fixture_id": fixture_id,
        "status": "ready",
        "time_casa": analise_db.get("time_casa", ""),
        "time_fora": analise_db.get("time_fora", ""),
        "liga": analise_db.get("liga", ""),
        "data_analise": str(analise_db.get("data_analise", "")),
        "total_palpites": total_palpites,
        "melhor_confianca": melhor_confianca,
        "mercados": mercados,
    }


# ─────────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────

def _logo_time(team_id: int) -> str:
    return f"https://media.api-sports.io/football/teams/{team_id}.png"

def _logo_liga(league_id: int) -> str:
    return f"https://media.api-sports.io/football/leagues/{league_id}.png"

def _demo_jogo(fid, liga_id, liga_nome, liga_pais, liga_bandeira,
               home_id, home_nome, away_id, away_nome, horario) -> dict:
    peso = LEAGUE_WEIGHTING_FACTOR.get(liga_id, 0.60)
    score = _calcular_score_destaque(liga_id, home_id, away_id)
    return {
        "fixture_id": fid,
        "status": "NS",
        "horario_brt": horario,
        "data_iso": f"2026-04-03T{horario}:00-03:00",
        "liga": {
            "id": liga_id,
            "nome": liga_nome,
            "pais": liga_pais,
            "logo": _logo_liga(liga_id),
            "bandeira": liga_bandeira,
        },
        "time_casa": {"id": home_id, "nome": home_nome, "logo": _logo_time(home_id)},
        "time_fora": {"id": away_id, "nome": away_nome, "logo": _logo_time(away_id)},
        "tem_analise": False,
        "score_destaque": score,
        "liga_peso": peso,
    }

def _get_demo_jogos() -> list:
    """Dados de demonstração com times e ligas reais para testar a interface."""
    flag = lambda c: f"https://media.api-sports.io/flags/{c}.svg"
    jogos = [
        # ── UEFA Champions League ────────────────────────────────
        _demo_jogo(90001, 2, "🏆 UEFA Champions League", "Internacional", "",
                   541, "Real Madrid", 42, "Arsenal", "16:00"),
        _demo_jogo(90002, 2, "🏆 UEFA Champions League", "Internacional", "",
                   157, "Bayern Munich", 505, "Inter Milan", "16:00"),
        _demo_jogo(90003, 2, "🏆 UEFA Champions League", "Internacional", "",
                   529, "Barcelona", 165, "Borussia Dortmund", "19:00"),
        _demo_jogo(90004, 2, "🏆 UEFA Champions League", "Internacional", "",
                   85,  "Paris Saint-Germain", 496, "Juventus", "19:00"),

        # ── Premier League ───────────────────────────────────────
        _demo_jogo(90010, 39, "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League", "Inglaterra", flag("gb"),
                   33, "Manchester City", 40, "Liverpool", "13:30"),
        _demo_jogo(90011, 39, "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League", "Inglaterra", flag("gb"),
                   42, "Arsenal", 35, "Chelsea", "16:00"),
        _demo_jogo(90012, 39, "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League", "Inglaterra", flag("gb"),
                   50, "Manchester United", 49, "Tottenham Hotspur", "16:00"),
        _demo_jogo(90013, 39, "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League", "Inglaterra", flag("gb"),
                   66, "Aston Villa", 51, "Brighton & Hove Albion", "16:00"),

        # ── La Liga ──────────────────────────────────────────────
        _demo_jogo(90020, 140, "🇪🇸 La Liga", "Espanha", flag("es"),
                   530, "Atletico Madrid", 536, "Sevilla", "17:00"),
        _demo_jogo(90021, 140, "🇪🇸 La Liga", "Espanha", flag("es"),
                   531, "Athletic Bilbao", 548, "Real Sociedad", "20:00"),

        # ── Serie A ──────────────────────────────────────────────
        _demo_jogo(90030, 135, "🇮🇹 Serie A", "Itália", flag("it"),
                   505, "Inter Milan", 496, "Juventus", "17:00"),
        _demo_jogo(90031, 135, "🇮🇹 Serie A", "Itália", flag("it"),
                   487, "AC Milan", 492, "Napoli", "20:45"),
        _demo_jogo(90032, 135, "🇮🇹 Serie A", "Itália", flag("it"),
                   497, "AS Roma", 499, "Atalanta", "14:30"),

        # ── Bundesliga ───────────────────────────────────────────
        _demo_jogo(90040, 78, "🇩🇪 Bundesliga", "Alemanha", flag("de"),
                   157, "Bayern Munich", 165, "Borussia Dortmund", "16:30"),
        _demo_jogo(90041, 78, "🇩🇪 Bundesliga", "Alemanha", flag("de"),
                   168, "Bayer Leverkusen", 173, "RB Leipzig", "14:30"),

        # ── Ligue 1 ──────────────────────────────────────────────
        _demo_jogo(90050, 61, "🇫🇷 Ligue 1", "França", flag("fr"),
                   85, "Paris Saint-Germain", 81, "Olympique Marseille", "17:00"),
        _demo_jogo(90051, 61, "🇫🇷 Ligue 1", "França", flag("fr"),
                   80, "AS Monaco", 83, "Olympique Lyonnais", "14:00"),

        # ── Brasileirão ──────────────────────────────────────────
        _demo_jogo(90060, 71, "🇧🇷 Brasileirão Série A", "Brasil", flag("br"),
                   127, "Flamengo", 131, "Palmeiras", "19:00"),
        _demo_jogo(90061, 71, "🇧🇷 Brasileirão Série A", "Brasil", flag("br"),
                   126, "São Paulo", 128, "Corinthians", "21:30"),
        _demo_jogo(90062, 71, "🇧🇷 Brasileirão Série A", "Brasil", flag("br"),
                   118, "Atlético-MG", 124, "Internacional", "19:00"),
        _demo_jogo(90063, 71, "🇧🇷 Brasileirão Série A", "Brasil", flag("br"),
                   130, "Grêmio", 120, "Fluminense", "21:30"),

        # ── Primeira Liga ────────────────────────────────────────
        _demo_jogo(90070, 94, "🇵🇹 Primeira Liga", "Portugal", flag("pt"),
                   211, "Benfica", 212, "Porto", "18:00"),
        _demo_jogo(90071, 94, "🇵🇹 Primeira Liga", "Portugal", flag("pt"),
                   228, "Sporting CP", 217, "Sporting Braga", "20:30"),

        # ── Eredivisie ───────────────────────────────────────────
        _demo_jogo(90080, 88, "🇳🇱 Eredivisie", "Holanda", flag("nl"),
                   194, "Ajax", 196, "PSV Eindhoven", "16:45"),
        _demo_jogo(90081, 88, "🇳🇱 Eredivisie", "Holanda", flag("nl"),
                   193, "Feyenoord", 197, "AZ Alkmaar", "14:30"),

        # ── Copa Libertadores ────────────────────────────────────
        _demo_jogo(90090, 13, "🏆 Copa Libertadores", "Internacional", "",
                   127, "Flamengo", 131, "Palmeiras", "21:30"),

        # ── Liga Profesional Argentina ───────────────────────────
        _demo_jogo(90100, 128, "🇦🇷 Liga Profesional", "Argentina", flag("ar"),
                   1005, "Boca Juniors", 1006, "River Plate", "21:00"),
    ]
    return sorted(jogos, key=lambda x: x["horario_brt"])


@app.get("/api/jogos/hoje")
async def jogos_hoje():
    """
    Retorna os jogos do dia organizados em duas estruturas:
    - principais: top 8 jogos por score_destaque (liga × qualidade dos times)
    - por_pais: todos os jogos agrupados País → Liga → Partidas
    """
    from api_client import ORDEM_PAISES

    jogos_raw = await buscar_jogos_do_dia()
    resultado_raw: list
    is_demo = False

    if jogos_raw:
        resultado_raw_list = []
        for jogo in jogos_raw:
            fid = jogo.get("fixture", {}).get("id")
            tem_analise = False
            if fid:
                cached = db.buscar_analise(fid, max_idade_horas=24)
                tem_analise = cached is not None
            resultado_raw_list.append(_formatar_jogo(jogo, tem_analise=tem_analise))
        resultado = sorted(resultado_raw_list, key=lambda x: x.get("data_iso", ""))
    else:
        resultado = _get_demo_jogos()
        is_demo = True
        print("⚠️ [DEMO] API retornou 0 jogos — usando dados de demonstração")

    # ── Principais: top 8 por score_destaque ────────────────────────────
    principais = sorted(resultado, key=lambda x: x.get("score_destaque", 0), reverse=True)[:8]

    # ── Por País: País → Liga → Partidas ─────────────────────────────────
    paises_map: dict = {}
    for item in resultado:
        pais = item["liga"]["pais"] or "Outros"
        liga_id = item["liga"]["id"]

        if pais not in paises_map:
            paises_map[pais] = {"ligas": {}, "peso_max": 0.0}

        liga_peso = item.get("liga_peso", 0.60)
        if liga_peso > paises_map[pais]["peso_max"]:
            paises_map[pais]["peso_max"] = liga_peso

        if liga_id not in paises_map[pais]["ligas"]:
            paises_map[pais]["ligas"][liga_id] = {
                "liga": item["liga"],
                "liga_peso": liga_peso,
                "jogos": [],
            }
        paises_map[pais]["ligas"][liga_id]["jogos"].append(item)

    def _ordem_pais(pais_nome: str) -> tuple:
        peso_max = paises_map[pais_nome]["peso_max"]
        ordem_fallback = ORDEM_PAISES.get(pais_nome, 999)
        return (-peso_max, ordem_fallback, pais_nome)

    por_pais = []
    for pais_nome in sorted(paises_map.keys(), key=_ordem_pais):
        info = paises_map[pais_nome]
        ligas_ordenadas = sorted(
            info["ligas"].values(),
            key=lambda l: -l["liga_peso"],
        )
        por_pais.append({
            "pais": pais_nome,
            "peso_max": info["peso_max"],
            "ligas": [
                {"liga": l["liga"], "jogos": l["jogos"]}
                for l in ligas_ordenadas
            ],
        })

    return {
        "total": len(resultado),
        "principais": principais,
        "por_pais": por_pais,
        "is_demo": is_demo,
    }


@app.get("/api/analise/{fixture_id}")
async def get_analise(fixture_id: int):
    """
    Retorna análise já salva no banco para um jogo.
    Se estiver sendo processada, retorna status 'processing'.
    Se não existir, retorna 404.
    """
    status_atual = _processing_status.get(fixture_id)
    if status_atual == "processing":
        return {"fixture_id": fixture_id, "status": "processing"}
    if status_atual == "error":
        raise HTTPException(status_code=500, detail="Erro na análise. Tente novamente.")

    analise_db = db.buscar_analise(fixture_id, max_idade_horas=24)
    if not analise_db:
        if status_atual == "ready":
            _processing_status.pop(fixture_id, None)
        raise HTTPException(status_code=404, detail="Análise não encontrada. Use POST /api/analisar/{fixture_id} para gerar.")

    return _db_to_api_response(analise_db, fixture_id)


@app.post("/api/analisar/{fixture_id}")
async def analisar_jogo(fixture_id: int, background_tasks: BackgroundTasks):
    """
    Dispara análise completa em background para um fixture_id.
    Retorna imediatamente com status 'processing'.
    O cliente deve fazer polling em GET /api/analise/{fixture_id}.
    """
    # Verifica se já existe análise recente
    analise_db = db.buscar_analise(fixture_id, max_idade_horas=6)
    if analise_db:
        return {"fixture_id": fixture_id, "status": "ready", "message": "Análise já disponível em cache."}

    # Verifica se já está sendo processada
    if _processing_status.get(fixture_id) == "processing":
        return {"fixture_id": fixture_id, "status": "processing", "message": "Análise em andamento."}

    # Buscar dados do jogo para o pipeline
    jogos_raw = await buscar_jogos_do_dia()
    jogo_encontrado = None
    if jogos_raw:
        for j in jogos_raw:
            if j.get("fixture", {}).get("id") == fixture_id:
                jogo_encontrado = j
                break

    if not jogo_encontrado:
        raise HTTPException(status_code=404, detail=f"Jogo #{fixture_id} não encontrado nos jogos do dia.")

    background_tasks.add_task(_executar_analise_completa, fixture_id, jogo_encontrado)
    _processing_status[fixture_id] = "processing"

    return {
        "fixture_id": fixture_id,
        "status": "processing",
        "message": "Análise iniciada. Faça polling em GET /api/analise/{fixture_id}.",
    }


@app.get("/api/status/{fixture_id}")
async def status_analise(fixture_id: int):
    """Verifica o status de processamento de uma análise."""
    status = _processing_status.get(fixture_id)
    if status:
        return {"fixture_id": fixture_id, "status": status}

    analise_db = db.buscar_analise(fixture_id, max_idade_horas=24)
    if analise_db:
        return {"fixture_id": fixture_id, "status": "ready"}

    return {"fixture_id": fixture_id, "status": "not_found"}


@app.get("/api/ligas")
async def listar_ligas():
    """Retorna as ligas suportadas pelo sistema."""
    ligas = []
    for liga_id in LIGAS_DE_INTERESSE:
        info = NOMES_LIGAS_PT.get(liga_id)
        if info:
            ligas.append({
                "id": liga_id,
                "nome": info[0],
                "pais": info[1],
            })
    return {"ligas": ligas, "total": len(ligas)}


@app.get("/api/stats")
async def stats_gerais():
    """Retorna estatísticas gerais do sistema."""
    try:
        with db._get_connection() as conn:
            if conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM analises_jogos")
                total = cursor.fetchone()[0]

                cursor.execute(
                    "SELECT COUNT(*) FROM analises_jogos WHERE data_analise >= NOW() - INTERVAL '24 hours'"
                )
                hoje = cursor.fetchone()[0]
                cursor.close()

                return {
                    "total_analises": total,
                    "analises_hoje": hoje,
                    "mercados_suportados": 12,
                    "ligas_suportadas": len(LIGAS_DE_INTERESSE),
                }
    except Exception:
        pass

    return {
        "total_analises": 0,
        "analises_hoje": 0,
        "mercados_suportados": 12,
        "ligas_suportadas": len(LIGAS_DE_INTERESSE),
    }


@app.get("/api/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(BRASILIA_TZ).isoformat()}


# ── Servir o frontend React ──────────────────────────────────────────────
FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "frontend", "dist")

if os.path.isdir(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        index = os.path.join(FRONTEND_DIST, "index.html")
        if os.path.exists(index):
            return FileResponse(index)
        raise HTTPException(status_code=404, detail="Frontend não encontrado.")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("web_api:app", host="0.0.0.0", port=port, reload=False)
