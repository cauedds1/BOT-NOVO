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
    """Inicializa o cliente HTTP compartilhado e agenda job noturno."""
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

    # Inicializar schema do banco (inclui palpites_historico e resultado_jogos)
    db.initialize_database()

    # Iniciar job noturno de rastreamento de resultados (03:00 BRT)
    try:
        from result_tracker import _scheduler_job_noturno
        asyncio.create_task(_scheduler_job_noturno(db))
        print("✅ [WebAPI] Job noturno de resultados agendado (03:00 BRT)")
    except Exception as e:
        print(f"⚠️ [WebAPI] Não foi possível iniciar job noturno: {e}")


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


def _formatar_jogo(jogo: dict, tem_analise: bool = False, analise_db: Optional[dict] = None) -> dict:
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

    # Rodada da competição
    rodada = jogo.get("league", {}).get("round", "")

    # Venue/árbitro (quando disponível na API)
    venue = jogo.get("fixture", {}).get("venue", {})
    venue_nome = venue.get("name", "") if venue else ""
    venue_cidade = venue.get("city", "") if venue else ""
    arbitro = jogo.get("fixture", {}).get("referee", "") or ""

    # Melhores palpites (top 3 se análise disponível)
    best_palpites = []
    if analise_db:
        mapa_mercados = [
            ("Gols", "analise_gols"),
            ("Resultado", "analise_resultado"),
            ("BTTS", "analise_btts"),
            ("Cantos", "analise_cantos"),
        ]
        todos_palpites = []
        for nome_m, chave in mapa_mercados:
            dados = analise_db.get(chave) or {}
            for p in (dados.get("palpites") or []):
                if isinstance(p, dict) and p.get("confianca"):
                    prob = p.get("probabilidade")
                    if prob is None:
                        confianca_val = p.get("confianca", 0)
                        prob = round(min(99, float(confianca_val) * 10), 1)
                    todos_palpites.append({
                        "tipo": p.get("tipo", ""),
                        "mercado": nome_m,
                        "confianca": p.get("confianca", 0),
                        "probabilidade": prob,
                        "odd": p.get("odd"),
                    })
        todos_palpites.sort(key=lambda x: x["confianca"], reverse=True)
        best_palpites = todos_palpites[:3]

    return {
        "fixture_id": jogo.get("fixture", {}).get("id"),
        "status": jogo.get("fixture", {}).get("status", {}).get("short", "NS"),
        "horario_brt": horario_brt,
        "data_iso": data_utc,
        "rodada": rodada,
        "venue": venue_nome,
        "venue_cidade": venue_cidade,
        "arbitro": arbitro,
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
        "best_palpites": best_palpites,
        "score_destaque": score_destaque,
        "liga_peso": liga_peso,
        "fixture_metadata": {
            "lineup_confirmado": False,
            "rodada": rodada,
            "venue": venue_nome,
            "venue_cidade": venue_cidade,
            "arbitro": arbitro,
        },
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

        # 3b. Aplicar ajuste histórico de confiança por mercado (learning layer)
        # Mapeia nome de mercado → resultado do analyzer
        _mercado_nome_map = {
            "Gols": analise_gols,
            "Resultado": analise_resultado,
            "Cantos": analise_cantos,
            "BTTS": analise_btts,
            "Cartões": analise_cartoes,
            "Finalizações": analise_finalizacoes,
            "Handicaps": analise_handicaps,
            "Dupla Chance": analise_dupla_chance,
            "Gols Ambos Tempos": analise_gabt,
            "Placar Exato": analise_placar_exato,
            "Handicap Europeu": analise_handicap_europeu,
            "Primeiro a Marcar": analise_primeiro_marcador,
        }
        for _nome_mercado, _analise in _mercado_nome_map.items():
            if not _analise:
                continue
            _adj = db.get_market_confidence_adjustment(
                mercado=_nome_mercado,
                liga_id=id_liga,
                script=script,
            )
            if _adj == 0.0:
                continue
            palpites_list = _analise if isinstance(_analise, list) else _analise.get("palpites", [])
            for _p in palpites_list:
                if isinstance(_p, dict) and "confianca" in _p:
                    _p["confianca"] = round(max(1.0, min(10.0, _p["confianca"] + _adj)), 2)
                    if "confidence_breakdown" in _p and isinstance(_p["confidence_breakdown"], dict):
                        _p["confidence_breakdown"]["modificador_historico"] = _adj
                        _p["confidence_breakdown"]["confianca_final"] = _p["confianca"]

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


def _extrair_forma_recente(stats: Optional[dict]) -> list:
    """Extrai últimos 5 resultados de forma da estrutura raw_data do master_analyzer."""
    if not stats:
        return []
    forma = stats.get("forma_recente") or stats.get("recent_form") or []
    if isinstance(forma, list):
        return forma[:5]
    if isinstance(forma, str):
        return list(forma[:5])
    return []


def _extrair_h2h(stats_casa: Optional[dict]) -> list:
    """Extrai histórico H2H se armazenado em stats_casa."""
    if not stats_casa:
        return []
    h2h = stats_casa.get("h2h") or []
    if isinstance(h2h, list):
        return h2h[:5]
    return []


def _extrair_stats_comparativas(stats_casa: Optional[dict], stats_fora: Optional[dict]) -> dict:
    """Extrai métricas comparativas (médias gols, cantos, etc.) dos stats raw."""
    campos = [
        ("media_gols_marcados", "avg_goals_scored", "media_gols_marcados_casa"),
        ("media_gols_sofridos", "avg_goals_conceded", "media_gols_sofridos_casa"),
        ("media_cantos", "avg_corners", "media_cantos_casa"),
        ("media_cartoes", "avg_cards", "media_cartoes_casa"),
    ]
    resultado = {}
    for c_home, c_alt, c_label in campos:
        val_casa = (stats_casa or {}).get(c_home) or (stats_casa or {}).get(c_alt)
        val_fora = (stats_fora or {}).get(c_home) or (stats_fora or {}).get(c_alt)
        if val_casa is not None:
            resultado[f"{c_home}_casa"] = round(float(val_casa), 2)
        if val_fora is not None:
            resultado[f"{c_home}_fora"] = round(float(val_fora), 2)

    # Campos extras úteis
    for campo in ["media_finalizacoes", "avg_shots", "posse_media", "avg_possession",
                  "media_escanteios_casa", "media_escanteios_fora"]:
        v_c = (stats_casa or {}).get(campo)
        v_f = (stats_fora or {}).get(campo)
        if v_c is not None:
            resultado[f"{campo}_casa"] = round(float(v_c), 2)
        if v_f is not None:
            resultado[f"{campo}_fora"] = round(float(v_f), 2)

    # BTTS% e Over 2.5 (frequências das últimas partidas)
    for campo_src, campo_dst in [
        ("btts_percent", "btts_percent"),
        ("btts_freq", "btts_percent"),
        ("over25_percent", "over25_percent"),
        ("over25_freq", "over25_percent"),
        ("over25_rate", "over25_percent"),
    ]:
        v_c = (stats_casa or {}).get(campo_src)
        v_f = (stats_fora or {}).get(campo_src)
        if v_c is not None and f"{campo_dst}_casa" not in resultado:
            try:
                resultado[f"{campo_dst}_casa"] = round(float(v_c), 1)
            except (TypeError, ValueError):
                pass
        if v_f is not None and f"{campo_dst}_fora" not in resultado:
            try:
                resultado[f"{campo_dst}_fora"] = round(float(v_f), 1)
            except (TypeError, ValueError):
                pass

    return resultado


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
    mercados_vetados = []
    for nome, chave in mapa:
        dados = analise_db.get(chave)
        if dados:
            estruturado = _estruturar_palpites(nome, dados)
            if estruturado:
                mercados.append(estruturado)
            else:
                motivo = dados.get("motivo_veto") or dados.get("justificativa_veto") or dados.get("razao") or "Dados insuficientes ou confiança abaixo do limiar"
                mercados_vetados.append({"mercado": nome, "motivo": motivo})

    total_palpites = sum(len(m["palpites"]) for m in mercados)
    melhor_confianca = 0.0
    for m in mercados:
        for p in m["palpites"]:
            melhor_confianca = max(melhor_confianca, p.get("confianca", 0))

    # Extrair dados enriquecidos dos JSONB stats
    stats_casa = analise_db.get("stats_casa") or {}
    stats_fora = analise_db.get("stats_fora") or {}
    classificacao = analise_db.get("classificacao") or []

    # Script tático vindo de analise_gols ou analise_resultado
    script_tatico = None
    for chave_analise in ["analise_gols", "analise_resultado", "analise_btts"]:
        dados_script = analise_db.get(chave_analise) or {}
        if isinstance(dados_script, dict):
            script_tatico = (
                dados_script.get("script_selecionado")
                or dados_script.get("selected_script")
                or dados_script.get("script")
            )
            if script_tatico:
                break

    # Posições na tabela
    pos_casa = stats_casa.get("posicao_tabela") or stats_casa.get("home_position")
    pos_fora = stats_fora.get("posicao_tabela") or stats_fora.get("away_position")

    # QSC scores
    qsc_home = stats_casa.get("qsc") or stats_casa.get("quality_score")
    qsc_away = stats_fora.get("qsc") or stats_fora.get("quality_score")

    # Forma recente
    forma_casa = _extrair_forma_recente(stats_casa)
    forma_fora = _extrair_forma_recente(stats_fora)

    # H2H (armazenado em stats_casa pelo master_analyzer)
    h2h = _extrair_h2h(stats_casa)

    # Stats comparativas
    stats_comparativas = _extrair_stats_comparativas(stats_casa, stats_fora)

    # Data do jogo (ISO) a partir da DB
    data_jogo_iso = ""
    dj = analise_db.get("data_jogo")
    if dj:
        try:
            data_jogo_iso = dj.isoformat() if hasattr(dj, "isoformat") else str(dj)
        except Exception:
            data_jogo_iso = str(dj)

    # Fixture metadata: venue, árbitro, rodada (armazenados em stats_casa quando disponível)
    fixture_metadata = {
        "rodada": stats_casa.get("rodada") or stats_fora.get("rodada") or "",
        "venue": stats_casa.get("venue") or stats_fora.get("venue") or "",
        "venue_cidade": stats_casa.get("venue_cidade") or stats_fora.get("venue_cidade") or "",
        "arbitro": stats_casa.get("arbitro") or stats_fora.get("arbitro") or "",
        "data_analise": str(analise_db.get("data_analise", "")),
        "lineup_confirmado": False,
    }

    # H2H summary: avg goals + BTTS frequency
    h2h_summary = {}
    if h2h:
        total_gols_h2h = 0
        btts_count = 0
        valid = 0
        for jh in h2h:
            gc = jh.get("gols_casa") if jh.get("gols_casa") is not None else jh.get("home_goals")
            gf = jh.get("gols_fora") if jh.get("gols_fora") is not None else jh.get("away_goals")
            if gc is not None and gf is not None:
                try:
                    gc, gf = int(gc), int(gf)
                    total_gols_h2h += gc + gf
                    if gc > 0 and gf > 0:
                        btts_count += 1
                    valid += 1
                except (TypeError, ValueError):
                    pass
        if valid > 0:
            h2h_summary = {
                "media_gols": round(total_gols_h2h / valid, 2),
                "btts_freq": round(btts_count / valid * 100, 1),
                "total_jogos": valid,
            }

    # Script tático reasoning (from analise_contexto if stored)
    analise_contexto = analise_db.get("analise_contexto") or {}
    script_reasoning = (
        analise_contexto.get("reasoning")
        or analise_contexto.get("script_reasoning")
        or analise_contexto.get("justificativa")
        or ""
    )

    return {
        "fixture_id": fixture_id,
        "status": "ready",
        "time_casa": analise_db.get("time_casa", ""),
        "time_fora": analise_db.get("time_fora", ""),
        "liga": analise_db.get("liga", ""),
        "data_analise": str(analise_db.get("data_analise", "")),
        "data_jogo_iso": data_jogo_iso,
        "total_palpites": total_palpites,
        "melhor_confianca": melhor_confianca,
        "mercados": mercados,
        # Dados enriquecidos
        "fixture_metadata": fixture_metadata,
        "script_tatico": script_tatico,
        "script_reasoning": script_reasoning,
        "pos_casa": pos_casa,
        "pos_fora": pos_fora,
        "qsc_home": qsc_home,
        "qsc_away": qsc_away,
        "forma_recente_casa": forma_casa,
        "forma_recente_fora": forma_fora,
        "h2h": h2h,
        "h2h_summary": h2h_summary,
        "stats_comparativas": stats_comparativas,
        "classificacao": classificacao[:20] if isinstance(classificacao, list) else [],
        "mercados_vetados": mercados_vetados,
    }


# ─────────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────

def _logo_time(team_id: int) -> str:
    return f"https://media.api-sports.io/football/teams/{team_id}.png"

def _logo_liga(league_id: int) -> str:
    return f"https://media.api-sports.io/football/leagues/{league_id}.png"


# ─────────────────────────────────────────────────────────────────────────
# DEMO DATA — Dados ricos para modo demonstração (sem API key)
# ─────────────────────────────────────────────────────────────────────────

_DEMO_FIXTURE_IDS = set(range(90001, 90101))

_DEMO_TEAM_LINEUPS: dict = {
    541:  {"t": [("Courtois","GK"),("Carvajal","RB"),("Militão","CB"),("Rüdiger","CB"),("Mendy","LB"),("Valverde","CM"),("Tchouaméni","CDM"),("Bellingham","CAM"),("Rodrygo","RW"),("Vinicius Jr.","LW"),("Mbappé","ST")], "r": [("Lunin","GK"),("Camavinga","CM"),("Arda Güler","CAM")]},
    42:   {"t": [("Raya","GK"),("Ben White","RB"),("Saliba","CB"),("Gabriel","CB"),("Zinchenko","LB"),("Rice","CDM"),("Ødegaard","CM"),("Havertz","CAM"),("Saka","RW"),("Martinelli","LW"),("Jesus","ST")], "r": [("Ramsdale","GK"),("Timber","CM"),("Nketiah","ST")]},
    157:  {"t": [("Neuer","GK"),("Kimmich","RB"),("Upamecano","CB"),("Min-jae Kim","CB"),("Davies","LB"),("Goretzka","CM"),("Laimer","CDM"),("Müller","CAM"),("Sané","RW"),("Musiala","LW"),("Kane","ST")], "r": [("Ulreich","GK"),("Gnabry","RW"),("Tel","ST")]},
    505:  {"t": [("Sommer","GK"),("Pavard","RB"),("Acerbi","CB"),("Bastoni","CB"),("Darmian","LB"),("Barella","CM"),("Calhanoglu","CDM"),("Mkhitaryan","CAM"),("Dumfries","RW"),("Lautaro","ST"),("Thuram","LW")], "r": [("Di Gennaro","GK"),("de Vrij","CB"),("Frattesi","CM")]},
    529:  {"t": [("Ter Stegen","GK"),("Koundé","RB"),("Cubarsí","CB"),("Iñigo Martínez","CB"),("Balde","LB"),("Pedri","CM"),("Gavi","CDM"),("De Jong","CAM"),("Yamal","RW"),("Raphinha","LW"),("Lewandowski","ST")], "r": [("Iñaki Peña","GK"),("Cancelo","RB"),("Olmo","CM")]},
    165:  {"t": [("Kobel","GK"),("Ryerson","RB"),("Hummels","CB"),("Schlotterbeck","CB"),("Maatsen","LB"),("Can","CDM"),("Nmecha","CM"),("Brandt","CAM"),("Adeyemi","RW"),("Sancho","LW"),("Füllkrug","ST")], "r": [("Meyer","GK"),("Wolf","RB"),("Bynoe-Gittens","LW")]},
    85:   {"t": [("Donnarumma","GK"),("Hakimi","RB"),("Marquinhos","CB"),("Pacho","CB"),("Beraldo","LB"),("Vitinha","CDM"),("Ruiz","CM"),("Zaire-Emery","CAM"),("Dembelé","RW"),("Barcola","LW"),("Ramos","ST")], "r": [("Safonov","GK"),("Mendes","LB"),("Lee Kang-in","CAM")]},
    496:  {"t": [("Di Gregorio","GK"),("Weah","RB"),("Bremer","CB"),("Gatti","CB"),("Cambiaso","LB"),("McKennie","CM"),("Locatelli","CDM"),("Rabiot","CAM"),("Yildiz","LW"),("Vlahovic","ST"),("Milik","RW")], "r": [("Perin","GK"),("Danilo","CB"),("Chiesa","RW")]},
    33:   {"t": [("Ederson","GK"),("Walker","RB"),("Akanji","CB"),("Dias","CB"),("Gvardiol","LB"),("Rodri","CDM"),("De Bruyne","CM"),("B. Silva","CAM"),("Doku","RW"),("Foden","LW"),("Haaland","ST")], "r": [("Ortega","GK"),("Lewis","RB"),("Palmer","CAM")]},
    40:   {"t": [("Alisson","GK"),("Alexander-Arnold","RB"),("Konaté","CB"),("Van Dijk","CB"),("Robertson","LB"),("Mac Allister","CDM"),("Jones","CM"),("Szoboszlai","CAM"),("Salah","RW"),("Díaz","LW"),("Núñez","ST")], "r": [("Kelleher","GK"),("Tsimikas","LB"),("Gakpo","LW")]},
    35:   {"t": [("Sánchez","GK"),("R. James","RB"),("Chalobah","CB"),("Colwill","CB"),("Chilwell","LB"),("Caicedo","CDM"),("Gallagher","CM"),("Palmer","CAM"),("Sterling","RW"),("Mudryk","LW"),("Jackson","ST")], "r": [("Petrovic","GK"),("Disasi","CB"),("Broja","ST")]},
    50:   {"t": [("Onana","GK"),("Dalot","RB"),("Maguire","CB"),("Martínez","CB"),("Shaw","LB"),("Casemiro","CDM"),("B. Fernandes","CM"),("Eriksen","CAM"),("Rashford","LW"),("Garnacho","RW"),("Højlund","ST")], "r": [("Bayindir","GK"),("Varane","CB"),("Antony","RW")]},
    49:   {"t": [("Vicario","GK"),("Porro","RB"),("Romero","CB"),("Van de Ven","CB"),("Udogie","LB"),("Bissouma","CDM"),("Sarr","CM"),("Maddison","CAM"),("Kulusevski","RW"),("Son","LW"),("Richarlison","ST")], "r": [("Forster","GK"),("Doherty","RB"),("Werner","LW")]},
    66:   {"t": [("Martínez","GK"),("Cash","RB"),("Konsa","CB"),("Torres","CB"),("Digne","LB"),("Douglas Luiz","CDM"),("Kamara","CM"),("McGinn","CAM"),("Bailey","RW"),("Diaby","LW"),("Watkins","ST")], "r": [("Olsen","GK"),("Carlos","LB"),("Tielemans","CM")]},
    51:   {"t": [("Steele","GK"),("Lamptey","RB"),("Dunk","CB"),("Webster","CB"),("Estupiñán","LB"),("Caicedo","CDM"),("Gross","CM"),("Mac Allister","CAM"),("Sarmiento","RW"),("Mitoma","LW"),("Welbeck","ST")], "r": [("Sánchez","GK"),("Ferguson","CM"),("March","RB")]},
    530:  {"t": [("Oblak","GK"),("Molina","RB"),("Witsel","CB"),("Savić","CB"),("Reinildo","LB"),("Llorente","CM"),("Koke","CDM"),("Barrios","CAM"),("Griezmann","RW"),("Álvarez","ST"),("Correa","LW")], "r": [("Grbic","GK"),("Hermoso","CB"),("Riquelme","RW")]},
    536:  {"t": [("Bounou","GK"),("Navas","RB"),("Gudelj","CB"),("Badé","CB"),("Acuña","LB"),("Rakitic","CDM"),("Fernández","CM"),("Suso","CAM"),("Ocampos","RW"),("En-Nesyri","ST"),("Lamela","LW")], "r": [("Dmitrovic","GK"),("Rekik","CB"),("Mir","ST")]},
    531:  {"t": [("Simón","GK"),("De Marcos","RB"),("Vivian","CB"),("Yeray","CB"),("Berchiche","LB"),("Dani García","CDM"),("Vesga","CM"),("Muniain","CAM"),("Williams I.","RW"),("Williams N.","LW"),("Sancet","ST")], "r": [("Padilla","GK"),("Lekue","RB"),("Guruzeta","ST")]},
    548:  {"t": [("Remiro","GK"),("Zaldua","RB"),("Le Normand","CB"),("Zubeldia","CB"),("Aihen","LB"),("Guevara","CDM"),("Merino","CM"),("Silva","CAM"),("Kubo","RW"),("Oyarzabal","ST"),("Barrenetxea","LW")], "r": [("Zubikarai","GK"),("Gorosabel","RB"),("Sorloth","ST")]},
    487:  {"t": [("Maignan","GK"),("Florenzi","RB"),("Thiaw","CB"),("Tomori","CB"),("Theo","LB"),("Musah","CM"),("Reijnders","CDM"),("Loftus-Cheek","CAM"),("Chukwueze","RW"),("Pulisic","LW"),("Giroud","ST")], "r": [("Mirante","GK"),("Gabbia","CB"),("Okafor","ST")]},
    492:  {"t": [("Meret","GK"),("Di Lorenzo","RB"),("Rrahmani","CB"),("Natan","CB"),("Olivera","LB"),("Anguissa","CM"),("Lobotka","CDM"),("Zielinski","CAM"),("Politano","RW"),("Kvaratskhelia","LW"),("Osimhen","ST")], "r": [("Contini","GK"),("Mazzocchi","RB"),("Raspadori","ST")]},
    497:  {"t": [("Svilar","GK"),("Çelik","RB"),("Mancini","CB"),("Smalling","CB"),("Spinazzola","LB"),("Bove","CM"),("Cristante","CDM"),("Pellegrini","CAM"),("El Shaarawy","LW"),("Dybala","RW"),("Lukaku","ST")], "r": [("Rui Patrício","GK"),("Llorente","CB"),("Belotti","ST")]},
    499:  {"t": [("Musso","GK"),("Hateboer","RB"),("Djimsiti","CB"),("Hien","CB"),("Ruggeri","LB"),("De Roon","CDM"),("Ederson","CM"),("Pasalic","CAM"),("Zappacosta","RW"),("De Ketelaere","LW"),("Scamacca","ST")], "r": [("Rossi","GK"),("Scalvini","CB"),("Muriel","ST")]},
    168:  {"t": [("Hradecky","GK"),("Frimpong","RB"),("Tapsoba","CB"),("Tah","CB"),("Grimaldo","LB"),("Andrich","CDM"),("Xhaka","CM"),("Palacios","CAM"),("Wirtz","RW"),("Hofmann","LW"),("Boniface","ST")], "r": [("Flekken","GK"),("Hincapié","LB"),("Adli","CAM")]},
    173:  {"t": [("Gulacsi","GK"),("Simakan","RB"),("Orbán","CB"),("Gvardiol","CB"),("Henrichs","LB"),("Laimer","CDM"),("Kampl","CM"),("Forsberg","CAM"),("Simons","RW"),("Szoboszlai","LW"),("Sesko","ST")], "r": [("Blaswich","GK"),("Raum","LB"),("Openda","ST")]},
    81:   {"t": [("Pau López","GK"),("Kolasinac","LB"),("Mbemba","CB"),("Balerdi","CB"),("Clauss","RB"),("Guendouzi","CM"),("Rongier","CDM"),("Sanchez","CAM"),("Mughe","RW"),("Aubameyang","ST"),("Ndiaye","LW")], "r": [("Blanco","GK"),("Touré","CB"),("Vitinha","ST")]},
    80:   {"t": [("Majecki","GK"),("Vanderson","RB"),("Disasi","CB"),("Maripan","CB"),("Caio Henrique","LB"),("Camara","CDM"),("Minamino","CM"),("Golovin","CAM"),("Akliouche","RW"),("Ben Yedder","ST"),("Balogun","LW")], "r": [("Yannis","GK"),("Badiashile","CB"),("Diatta","LW")]},
    83:   {"t": [("Lopes","GK"),("Gusto","RB"),("Lovren","CB"),("Lukeba","CB"),("Tagliafico","LB"),("Tolisso","CDM"),("Caqueret","CM"),("Cherki","CAM"),("Tetê","RW"),("Lacazette","ST"),("Jeffinho","LW")], "r": [("Bengui","GK"),("Bard","CB"),("Diabaté","ST")]},
    127:  {"t": [("Agustín","GK"),("Varela","RB"),("David Luiz","CB"),("Léo Pereira","CB"),("Filipe Luís","LB"),("Gerson","CM"),("Thiago Maia","CDM"),("Arrascaeta","CAM"),("Everton R.","RW"),("Pedro","ST"),("Gabigol","LW")], "r": [("Santos","GK"),("Isla","RB"),("Marinho","RW")]},
    131:  {"t": [("Weverton","GK"),("Marcos Rocha","RB"),("Gustavo Gómez","CB"),("Murilo","CB"),("Piquerez","LB"),("Danilo","CDM"),("Zé Rafael","CM"),("Gabriel Menino","CAM"),("Raphael Veiga","RW"),("Dudu","LW"),("Endrick","ST")], "r": [("Marcelo Lomba","GK"),("Mayke","RB"),("Scarpa","CAM")]},
    126:  {"t": [("Rafael","GK"),("Rafinha","RB"),("Miranda","CB"),("Beraldo","CB"),("Wellington","LB"),("Pablo Maia","CDM"),("Rodrigo Nestor","CM"),("Alisson","CAM"),("Moreira","RW"),("Calleri","ST"),("Luciano","LW")], "r": [("Jandrei","GK"),("Ferraresi","CB"),("Nikão","LW")]},
    128:  {"t": [("Carlos Miguel","GK"),("Fagner","RB"),("Murillo","CB"),("Gil","CB"),("Fábio Santos","LB"),("Maycon","CDM"),("Renato Augusto","CM"),("Giuliano","CAM"),("Róger Guedes","RW"),("Yuri Alberto","ST"),("Mantuan","LW")], "r": [("Cássio","GK"),("João Victor","CB"),("Du Queiroz","CM")]},
    118:  {"t": [("Everson","GK"),("Mariano","RB"),("Jr. Alonso","CB"),("Igor Rabello","CB"),("Guilherme Arana","LB"),("Otávio","CDM"),("Allan","CM"),("Zaracho","CAM"),("Sávio","RW"),("Hulk","ST"),("Paulinho","LW")], "r": [("Fábio","GK"),("Nathan","RB"),("Ademir","LW")]},
    124:  {"t": [("Daniel","GK"),("Bustos","RB"),("Vitão","CB"),("Mercado","CB"),("Renê","LB"),("Gabriel","CDM"),("Edenilson","CM"),("Maurício","CAM"),("Wanderson","RW"),("Aleksander","ST"),("Boschilia","LW")], "r": [("Keiller","GK"),("Rodrigo Dourado","CM"),("Caio Vidal","RW")]},
    130:  {"t": [("Grando","GK"),("Bruno Alves","RB"),("Geromel","CB"),("Kannemann","CB"),("Reinaldo","LB"),("Lucas Silva","CDM"),("Villasanti","CM"),("Everton Galdino","CAM"),("Campaz","RW"),("Diego Souza","ST"),("Suárez","LW")], "r": [("Brenno","GK"),("Rodrigues","CB"),("Ferreira","RW")]},
    120:  {"t": [("Fábio","GK"),("Samuel Xavier","RB"),("Manoel","CB"),("Nino","CB"),("Marcelo","LB"),("André","CDM"),("Martinelli","CM"),("Ganso","CAM"),("Arias","RW"),("Cano","ST"),("Jhon Arias","LW")], "r": [("Marcos Felipe","GK"),("Natan","CB"),("Willian","LW")]},
    211:  {"t": [("Trubin","GK"),("Bah","RB"),("A. Silva","CB"),("Otamendi","CB"),("Grimaldo","LB"),("Chiquinho","CM"),("J. Neves","CDM"),("Florentino","CAM"),("Rafa","RW"),("G. Ramos","ST"),("David Neres","LW")], "r": [("Vlachodimos","GK"),("Morato","CB"),("Musa","LW")]},
    212:  {"t": [("Diogo Costa","GK"),("João Mário","RB"),("Pepe","CB"),("David Carmo","CB"),("Wendell","LB"),("Pepe Jr.","CM"),("Uribe","CDM"),("Otávio","CAM"),("Galeno","LW"),("Taremi","ST"),("Evanilson","RW")], "r": [("Marchesín","GK"),("Veron","RB"),("Pepê","RW")]},
    228:  {"t": [("Adán","GK"),("Inácio","RB"),("Coates","CB"),("Matheus Reis","CB"),("Porro","LB"),("Morita","CDM"),("Ugarte","CM"),("Nuno Santos","CAM"),("Trincão","RW"),("Paulinho","LW"),("Marcus Edwards","ST")], "r": [("Franco","GK"),("Gonçalo Inácio","CB"),("Slimani","ST")]},
    217:  {"t": [("Matheus","GK"),("Yan Couto","RB"),("Diogo Leite","CB"),("Carmo","CB"),("Wenderson Galeno","LB"),("Al Musrati","CDM"),("Vítor Carvalho","CM"),("Iuri Medeiros","CAM"),("Rodrigo Gomes","RW"),("Abel Ruiz","ST"),("Banza","LW")], "r": [("Tiago Sá","GK"),("Borja","CB"),("Vitinha","LW")]},
    194:  {"t": [("Pasveer","GK"),("Rensch","RB"),("Timber","CB"),("Blind","CB"),("Wijndal","LB"),("Álvarez","CDM"),("Taylor","CM"),("Berghuis","CAM"),("Bergwijn","RW"),("Tadić","LW"),("Brobbey","ST")], "r": [("Gorter","GK"),("Sanchez","CB"),("Neres","LW")]},
    196:  {"t": [("Benítez","GK"),("Dumfries","RB"),("André Ramalho","CB"),("Teze","CB"),("Max","LB"),("Sangaré","CDM"),("Propper","CM"),("Til","CAM"),("Simons","RW"),("Veerman","LW"),("L. de Jong","ST")], "r": [("Mvogo","GK"),("Obispo","CB"),("Lozano","RW")]},
    193:  {"t": [("Bijlow","GK"),("Geertruida","RB"),("Trauner","CB"),("Hancko","CB"),("Hartman","LB"),("Kökçü","CDM"),("Timber","CM"),("Szymanski","CAM"),("Paixão","RW"),("Danilo","LW"),("Giménez","ST")], "r": [("Didulica","GK"),("Pedersen","RB"),("Walemark","LW")]},
    197:  {"t": [("Verhulst","GK"),("Sugawara","RB"),("Penetra","CB"),("Martins Indi","CB"),("Svensson","LB"),("Midtsjø","CDM"),("Clasie","CM"),("Van Brederode","CAM"),("Lahdo","RW"),("Pavlidis","ST"),("Evjen","LW")], "r": [("Owusu-Oduro","GK"),("Botman","CB"),("Gudmundsson","LW")]},
    1005: {"t": [("Rossi","GK"),("Advíncula","RB"),("Rojo","CB"),("Zambrano","CB"),("Fabra","LB"),("Medina","CDM"),("Almendra","CM"),("Óscar Romero","CAM"),("Briasco","RW"),("Cavani","ST"),("Zeballos","LW")], "r": [("Javier García","GK"),("Weigandt","RB"),("Vázquez","LW")]},
    1006: {"t": [("Armani","GK"),("Enzo Díaz","RB"),("Paulo Díaz","CB"),("Mammana","CB"),("Casco","LB"),("Enzo Pérez","CDM"),("Nacho Fernández","CM"),("Barco","CAM"),("Borré","RW"),("Beltrán","ST"),("Solari","LW")], "r": [("Centurión","GK"),("Milton Casco","LB"),("Pratto","ST")]},
}

_DEMO_FIXTURES_INFO: dict = {}

def _build_demo_fixture_map():
    global _DEMO_FIXTURES_INFO
    if _DEMO_FIXTURES_INFO:
        return
    for j in _get_demo_jogos():
        _DEMO_FIXTURES_INFO[j["fixture_id"]] = j

def _get_demo_fixture_info(fixture_id: int) -> Optional[dict]:
    _build_demo_fixture_map()
    return _DEMO_FIXTURES_INFO.get(fixture_id)

def _demo_player(nome: str, posicao: str, foi_titular: bool, eh_mandante: bool, seed: int) -> dict:
    """Gera um perfil de jogador demo realista."""
    is_att = posicao in ("ST", "LW", "RW", "CAM")
    is_def = posicao in ("GK", "CB", "CDM")
    gols = (1 if seed % 3 == 0 else 0) if is_att else 0
    assists = (1 if seed % 4 == 0 else 0) if not is_def else 0
    fins = (2 + seed % 3) if is_att else (1 if posicao == "CM" else 0)
    media_g = round((0.25 + (seed % 5) * 0.05) if is_att else 0.0, 2)
    media_a = round((0.15 + (seed % 4) * 0.04) if not is_def else 0.0, 2)
    media_f = round((1.5 + (seed % 4) * 0.3) if is_att else (0.3 if posicao == "CM" else 0.0), 2)
    u5g = [1 if (i + seed) % 3 == 0 else 0 for i in range(5)] if is_att else [0]*5
    u5a = [1 if (i + seed) % 4 == 0 else 0 for i in range(5)] if not is_def else [0]*5
    u5f = [fins // 2 + (1 if i % 2 == 0 else 0) for i in range(5)] if is_att else [0]*5
    return {
        "jogador_id": None,
        "nome": nome,
        "posicao": posicao,
        "foi_titular": foi_titular,
        "minutos": 90 if foi_titular else (15 + seed % 25),
        "gols": gols,
        "assistencias": assists,
        "finalizacoes": fins,
        "cartao_amarelo": (seed % 17 == 0),
        "cartao_vermelho": False,
        "eh_mandante": eh_mandante,
        "n_jogos": 20 + seed % 12,
        "n_jogos_casa": 10 + seed % 6,
        "n_jogos_fora": 10 + seed % 6,
        "media_gols": media_g,
        "media_assistencias": media_a,
        "media_finalizacoes": media_f,
        "media_gols_casa": round(media_g * 1.1, 2),
        "media_gols_fora": round(media_g * 0.9, 2),
        "ultimos_5_gols": u5g,
        "ultimos_5_assistencias": u5a,
        "ultimos_5_finalizacoes": u5f,
        "amostra_pequena": False,
        "lesionado": False,
        "suspenso": False,
    }

def _get_demo_lineup(fixture_id: int) -> dict:
    """Retorna escalação demo completa para um fixture demo."""
    info = _get_demo_fixture_info(fixture_id)
    if not info:
        return {"fixture_id": fixture_id, "mandantes": [], "visitantes": [], "total": 0, "lineup_confirmado": False, "lineup_fonte": None}

    home_id = info["time_casa"]["id"]
    away_id = info["time_fora"]["id"]
    seed_base = fixture_id % 100

    def _build_team(team_id: int, eh_mandante: bool) -> list:
        data = _DEMO_TEAM_LINEUPS.get(team_id, {})
        titulares = data.get("t", [])
        reservas = data.get("r", [])
        players = []
        for i, (nome, pos) in enumerate(titulares):
            players.append(_demo_player(nome, pos, True, eh_mandante, seed_base + i))
        for i, (nome, pos) in enumerate(reservas):
            players.append(_demo_player(nome, pos, False, eh_mandante, seed_base + 20 + i))
        if not players:
            for i in range(11):
                players.append(_demo_player(f"Jogador {i+1}", "CM", True, eh_mandante, seed_base + i))
        return players

    mandantes = _build_team(home_id, True)
    visitantes = _build_team(away_id, False)
    return {
        "fixture_id": fixture_id,
        "mandantes": mandantes,
        "visitantes": visitantes,
        "total": len(mandantes) + len(visitantes),
        "lineup_confirmado": True,
        "lineup_fonte": "demo",
    }

_DEMO_VENUES = {
    541: ("Estadio Santiago Bernabeu", "Madrid"),
    157: ("Allianz Arena", "Munique"),
    529: ("Camp Nou", "Barcelona"),
    85:  ("Parc des Princes", "Paris"),
    33:  ("Etihad Stadium", "Manchester"),
    40:  ("Anfield", "Liverpool"),
    42:  ("Emirates Stadium", "Londres"),
    35:  ("Stamford Bridge", "Londres"),
    50:  ("Old Trafford", "Manchester"),
    49:  ("Tottenham Hotspur Stadium", "Londres"),
    505: ("Stadio San Siro", "Milão"),
    487: ("Stadio San Siro", "Milão"),
    496: ("Allianz Stadium", "Turin"),
    497: ("Stadio Olimpico", "Roma"),
    499: ("Gewiss Stadium", "Bérgamo"),
    492: ("Stadio Diego Armando Maradona", "Nápoles"),
    168: ("BayArena", "Leverkusen"),
    173: ("Red Bull Arena", "Leipzig"),
    165: ("Signal Iduna Park", "Dortmund"),
    530: ("Estadio Civitas Metropolitano", "Madrid"),
    536: ("Estadio Ramon Sanchez-Pizjuan", "Sevilha"),
    531: ("San Mamés", "Bilbao"),
    548: ("Reale Arena", "San Sebastián"),
    81:  ("Stade Velodrome", "Marselha"),
    80:  ("Stade Louis-II", "Mônaco"),
    83:  ("Groupama Stadium", "Lyon"),
    127: ("Estádio do Maracanã", "Rio de Janeiro"),
    131: ("Allianz Parque", "São Paulo"),
    126: ("Morumbi", "São Paulo"),
    128: ("Neo Química Arena", "São Paulo"),
    118: ("Arena MRV", "Belo Horizonte"),
    124: ("Estádio Beira-Rio", "Porto Alegre"),
    130: ("Arena do Grêmio", "Porto Alegre"),
    120: ("Estádio Nilton Santos", "Rio de Janeiro"),
    211: ("Estádio da Luz", "Lisboa"),
    212: ("Estádio do Dragão", "Porto"),
    228: ("Estádio José Alvalade", "Lisboa"),
    217: ("Estádio Municipal de Braga", "Braga"),
    194: ("Johan Cruyff Arena", "Amsterdam"),
    196: ("Philips Stadion", "Eindhoven"),
    193: ("De Kuip", "Rotterdam"),
    197: ("AFAS Stadion", "Alkmaar"),
    1005: ("Estadio La Bombonera", "Buenos Aires"),
    1006: ("Estadio Monumental", "Buenos Aires"),
}

_DEMO_ARBITROS = [
    "Szymon Marciniak", "Anthony Taylor", "Daniele Orsato",
    "Slavko Vincic", "Clement Turpin", "Carlos del Cerro Grande",
    "Felix Zwayer", "Marco Guida", "Fernando Rapallini",
    "Michael Oliver", "Daniel Siebert", "Ivan Kružliak",
    "Wilton Pereira Sampaio", "Braulio Machado", "Ramon Abatti Abel",
]

_DEMO_FORMAS = [
    ["V","V","E","V","D"], ["V","V","V","E","V"], ["D","V","V","V","E"],
    ["V","E","V","D","V"], ["D","D","V","V","V"], ["V","V","D","E","V"],
    ["E","V","V","V","D"], ["V","D","V","V","E"], ["V","V","E","E","V"],
    ["D","V","E","V","V"],
]

_DEMO_H2H = {
    90001: [{"data":"2023-04-18","gols_casa":3,"gols_fora":0},{"data":"2022-10-04","gols_casa":2,"gols_fora":1},{"data":"2021-03-16","gols_casa":1,"gols_fora":0},{"data":"2019-11-06","gols_casa":0,"gols_fora":0},{"data":"2018-02-15","gols_casa":2,"gols_fora":1}],
    90010: [{"data":"2024-03-10","gols_casa":1,"gols_fora":1},{"data":"2023-11-25","gols_casa":4,"gols_fora":1},{"data":"2023-04-01","gols_casa":4,"gols_fora":1},{"data":"2022-10-16","gols_casa":3,"gols_fora":2},{"data":"2022-04-10","gols_casa":2,"gols_fora":2}],
    90030: [{"data":"2024-02-04","gols_casa":2,"gols_fora":1},{"data":"2023-10-08","gols_casa":0,"gols_fora":1},{"data":"2023-04-19","gols_casa":2,"gols_fora":0},{"data":"2022-09-26","gols_casa":0,"gols_fora":0},{"data":"2022-02-26","gols_casa":1,"gols_fora":2}],
    90060: [{"data":"2024-06-01","gols_casa":1,"gols_fora":0},{"data":"2023-10-14","gols_casa":2,"gols_fora":1},{"data":"2023-07-09","gols_casa":0,"gols_fora":1},{"data":"2023-05-03","gols_casa":1,"gols_fora":1},{"data":"2022-11-19","gols_casa":3,"gols_fora":2}],
    90070: [{"data":"2024-01-06","gols_casa":3,"gols_fora":1},{"data":"2023-04-01","gols_casa":2,"gols_fora":2},{"data":"2022-11-10","gols_casa":3,"gols_fora":0},{"data":"2022-02-10","gols_casa":1,"gols_fora":0},{"data":"2021-10-09","gols_casa":1,"gols_fora":1}],
    90100: [{"data":"2024-05-12","gols_casa":2,"gols_fora":1},{"data":"2023-12-17","gols_casa":0,"gols_fora":1},{"data":"2023-09-03","gols_casa":1,"gols_fora":2},{"data":"2023-03-26","gols_casa":3,"gols_fora":0},{"data":"2022-11-06","gols_casa":1,"gols_fora":1}],
}

_DEMO_STANDINGS_BY_LEAGUE: dict = {
    2: [
        {"rank":1,"team":{"name":"Real Madrid","logo":_logo_time(541)},"all":{"played":6,"win":5,"draw":1,"lose":0},"points":16},
        {"rank":2,"team":{"name":"Bayern Munich","logo":_logo_time(157)},"all":{"played":6,"win":4,"draw":1,"lose":1},"points":13},
        {"rank":3,"team":{"name":"Manchester City","logo":_logo_time(33)},"all":{"played":6,"win":4,"draw":0,"lose":2},"points":12},
        {"rank":4,"team":{"name":"Barcelona","logo":_logo_time(529)},"all":{"played":6,"win":3,"draw":2,"lose":1},"points":11},
        {"rank":5,"team":{"name":"Arsenal","logo":_logo_time(42)},"all":{"played":6,"win":3,"draw":1,"lose":2},"points":10},
        {"rank":6,"team":{"name":"Inter Milan","logo":_logo_time(505)},"all":{"played":6,"win":3,"draw":1,"lose":2},"points":10},
        {"rank":7,"team":{"name":"Paris Saint-Germain","logo":_logo_time(85)},"all":{"played":6,"win":2,"draw":2,"lose":2},"points":8},
        {"rank":8,"team":{"name":"Borussia Dortmund","logo":_logo_time(165)},"all":{"played":6,"win":2,"draw":1,"lose":3},"points":7},
    ],
    39: [
        {"rank":1,"team":{"name":"Manchester City","logo":_logo_time(33)},"all":{"played":30,"win":21,"draw":5,"lose":4},"points":68},
        {"rank":2,"team":{"name":"Arsenal","logo":_logo_time(42)},"all":{"played":30,"win":20,"draw":5,"lose":5},"points":65},
        {"rank":3,"team":{"name":"Liverpool","logo":_logo_time(40)},"all":{"played":30,"win":18,"draw":7,"lose":5},"points":61},
        {"rank":4,"team":{"name":"Aston Villa","logo":_logo_time(66)},"all":{"played":30,"win":17,"draw":4,"lose":9},"points":55},
        {"rank":5,"team":{"name":"Tottenham Hotspur","logo":_logo_time(49)},"all":{"played":30,"win":14,"draw":6,"lose":10},"points":48},
        {"rank":6,"team":{"name":"Chelsea","logo":_logo_time(35)},"all":{"played":30,"win":13,"draw":7,"lose":10},"points":46},
        {"rank":7,"team":{"name":"Manchester United","logo":_logo_time(50)},"all":{"played":30,"win":11,"draw":6,"lose":13},"points":39},
        {"rank":8,"team":{"name":"Brighton & Hove Albion","logo":_logo_time(51)},"all":{"played":30,"win":10,"draw":8,"lose":12},"points":38},
    ],
    140: [
        {"rank":1,"team":{"name":"Real Madrid","logo":_logo_time(541)},"all":{"played":30,"win":23,"draw":5,"lose":2},"points":74},
        {"rank":2,"team":{"name":"Barcelona","logo":_logo_time(529)},"all":{"played":30,"win":20,"draw":5,"lose":5},"points":65},
        {"rank":3,"team":{"name":"Atletico Madrid","logo":_logo_time(530)},"all":{"played":30,"win":18,"draw":6,"lose":6},"points":60},
        {"rank":4,"team":{"name":"Athletic Bilbao","logo":_logo_time(531)},"all":{"played":30,"win":16,"draw":5,"lose":9},"points":53},
        {"rank":5,"team":{"name":"Real Sociedad","logo":_logo_time(548)},"all":{"played":30,"win":14,"draw":7,"lose":9},"points":49},
        {"rank":6,"team":{"name":"Sevilla","logo":_logo_time(536)},"all":{"played":30,"win":12,"draw":6,"lose":12},"points":42},
        {"rank":7,"team":{"name":"Villarreal","logo":_logo_time(533)},"all":{"played":30,"win":11,"draw":8,"lose":11},"points":41},
        {"rank":8,"team":{"name":"Real Betis","logo":_logo_time(543)},"all":{"played":30,"win":10,"draw":8,"lose":12},"points":38},
    ],
    135: [
        {"rank":1,"team":{"name":"Inter Milan","logo":_logo_time(505)},"all":{"played":30,"win":24,"draw":4,"lose":2},"points":76},
        {"rank":2,"team":{"name":"AC Milan","logo":_logo_time(487)},"all":{"played":30,"win":18,"draw":7,"lose":5},"points":61},
        {"rank":3,"team":{"name":"Juventus","logo":_logo_time(496)},"all":{"played":30,"win":17,"draw":5,"lose":8},"points":56},
        {"rank":4,"team":{"name":"Atalanta","logo":_logo_time(499)},"all":{"played":30,"win":16,"draw":5,"lose":9},"points":53},
        {"rank":5,"team":{"name":"Napoli","logo":_logo_time(492)},"all":{"played":30,"win":14,"draw":6,"lose":10},"points":48},
        {"rank":6,"team":{"name":"AS Roma","logo":_logo_time(497)},"all":{"played":30,"win":13,"draw":5,"lose":12},"points":44},
        {"rank":7,"team":{"name":"Lazio","logo":_logo_time(487)},"all":{"played":30,"win":12,"draw":7,"lose":11},"points":43},
        {"rank":8,"team":{"name":"Fiorentina","logo":_logo_time(502)},"all":{"played":30,"win":11,"draw":6,"lose":13},"points":39},
    ],
    78: [
        {"rank":1,"team":{"name":"Bayern Munich","logo":_logo_time(157)},"all":{"played":28,"win":19,"draw":4,"lose":5},"points":61},
        {"rank":2,"team":{"name":"Bayer Leverkusen","logo":_logo_time(168)},"all":{"played":28,"win":18,"draw":5,"lose":5},"points":59},
        {"rank":3,"team":{"name":"RB Leipzig","logo":_logo_time(173)},"all":{"played":28,"win":16,"draw":4,"lose":8},"points":52},
        {"rank":4,"team":{"name":"Borussia Dortmund","logo":_logo_time(165)},"all":{"played":28,"win":14,"draw":6,"lose":8},"points":48},
        {"rank":5,"team":{"name":"Union Berlin","logo":_logo_time(182)},"all":{"played":28,"win":12,"draw":5,"lose":11},"points":41},
        {"rank":6,"team":{"name":"SC Freiburg","logo":_logo_time(160)},"all":{"played":28,"win":11,"draw":7,"lose":10},"points":40},
        {"rank":7,"team":{"name":"Mainz","logo":_logo_time(164)},"all":{"played":28,"win":10,"draw":7,"lose":11},"points":37},
        {"rank":8,"team":{"name":"Wolfsburg","logo":_logo_time(170)},"all":{"played":28,"win":9,"draw":7,"lose":12},"points":34},
    ],
    61: [
        {"rank":1,"team":{"name":"Paris Saint-Germain","logo":_logo_time(85)},"all":{"played":30,"win":24,"draw":4,"lose":2},"points":76},
        {"rank":2,"team":{"name":"Olympique Marseille","logo":_logo_time(81)},"all":{"played":30,"win":18,"draw":5,"lose":7},"points":59},
        {"rank":3,"team":{"name":"AS Monaco","logo":_logo_time(80)},"all":{"played":30,"win":16,"draw":6,"lose":8},"points":54},
        {"rank":4,"team":{"name":"Olympique Lyonnais","logo":_logo_time(83)},"all":{"played":30,"win":14,"draw":6,"lose":10},"points":48},
        {"rank":5,"team":{"name":"Lens","logo":_logo_time(116)},"all":{"played":30,"win":13,"draw":7,"lose":10},"points":46},
        {"rank":6,"team":{"name":"Rennes","logo":_logo_time(111)},"all":{"played":30,"win":12,"draw":6,"lose":12},"points":42},
        {"rank":7,"team":{"name":"Lille","logo":_logo_time(79)},"all":{"played":30,"win":11,"draw":7,"lose":12},"points":40},
        {"rank":8,"team":{"name":"Strasbourg","logo":_logo_time(95)},"all":{"played":30,"win":9,"draw":8,"lose":13},"points":35},
    ],
    71: [
        {"rank":1,"team":{"name":"Flamengo","logo":_logo_time(127)},"all":{"played":30,"win":19,"draw":7,"lose":4},"points":64},
        {"rank":2,"team":{"name":"Palmeiras","logo":_logo_time(131)},"all":{"played":30,"win":18,"draw":7,"lose":5},"points":61},
        {"rank":3,"team":{"name":"Atlético-MG","logo":_logo_time(118)},"all":{"played":30,"win":16,"draw":7,"lose":7},"points":55},
        {"rank":4,"team":{"name":"Fluminense","logo":_logo_time(120)},"all":{"played":30,"win":14,"draw":8,"lose":8},"points":50},
        {"rank":5,"team":{"name":"São Paulo","logo":_logo_time(126)},"all":{"played":30,"win":13,"draw":8,"lose":9},"points":47},
        {"rank":6,"team":{"name":"Corinthians","logo":_logo_time(128)},"all":{"played":30,"win":11,"draw":9,"lose":10},"points":42},
        {"rank":7,"team":{"name":"Internacional","logo":_logo_time(124)},"all":{"played":30,"win":11,"draw":7,"lose":12},"points":40},
        {"rank":8,"team":{"name":"Grêmio","logo":_logo_time(130)},"all":{"played":30,"win":10,"draw":8,"lose":12},"points":38},
    ],
    94: [
        {"rank":1,"team":{"name":"Benfica","logo":_logo_time(211)},"all":{"played":28,"win":19,"draw":6,"lose":3},"points":63},
        {"rank":2,"team":{"name":"Porto","logo":_logo_time(212)},"all":{"played":28,"win":18,"draw":5,"lose":5},"points":59},
        {"rank":3,"team":{"name":"Sporting CP","logo":_logo_time(228)},"all":{"played":28,"win":16,"draw":7,"lose":5},"points":55},
        {"rank":4,"team":{"name":"Sporting Braga","logo":_logo_time(217)},"all":{"played":28,"win":13,"draw":5,"lose":10},"points":44},
        {"rank":5,"team":{"name":"Vitória","logo":_logo_time(220)},"all":{"played":28,"win":11,"draw":7,"lose":10},"points":40},
        {"rank":6,"team":{"name":"Estoril","logo":_logo_time(727)},"all":{"played":28,"win":10,"draw":6,"lose":12},"points":36},
        {"rank":7,"team":{"name":"Famalicão","logo":_logo_time(779)},"all":{"played":28,"win":9,"draw":7,"lose":12},"points":34},
        {"rank":8,"team":{"name":"Moreirense","logo":_logo_time(231)},"all":{"played":28,"win":8,"draw":8,"lose":12},"points":32},
    ],
    88: [
        {"rank":1,"team":{"name":"PSV Eindhoven","logo":_logo_time(196)},"all":{"played":28,"win":22,"draw":3,"lose":3},"points":69},
        {"rank":2,"team":{"name":"Feyenoord","logo":_logo_time(193)},"all":{"played":28,"win":18,"draw":5,"lose":5},"points":59},
        {"rank":3,"team":{"name":"AZ Alkmaar","logo":_logo_time(197)},"all":{"played":28,"win":17,"draw":4,"lose":7},"points":55},
        {"rank":4,"team":{"name":"Ajax","logo":_logo_time(194)},"all":{"played":28,"win":13,"draw":7,"lose":8},"points":46},
        {"rank":5,"team":{"name":"Twente","logo":_logo_time(203)},"all":{"played":28,"win":12,"draw":6,"lose":10},"points":42},
        {"rank":6,"team":{"name":"Utrecht","logo":_logo_time(206)},"all":{"played":28,"win":11,"draw":7,"lose":10},"points":40},
        {"rank":7,"team":{"name":"NEC","logo":_logo_time(202)},"all":{"played":28,"win":9,"draw":7,"lose":12},"points":34},
        {"rank":8,"team":{"name":"Vitesse","logo":_logo_time(198)},"all":{"played":28,"win":7,"draw":8,"lose":13},"points":29},
    ],
    13: [
        {"rank":1,"team":{"name":"Flamengo","logo":_logo_time(127)},"all":{"played":6,"win":4,"draw":1,"lose":1},"points":13},
        {"rank":2,"team":{"name":"Palmeiras","logo":_logo_time(131)},"all":{"played":6,"win":3,"draw":2,"lose":1},"points":11},
        {"rank":3,"team":{"name":"Atlético-MG","logo":_logo_time(118)},"all":{"played":6,"win":3,"draw":1,"lose":2},"points":10},
        {"rank":4,"team":{"name":"Internacional","logo":_logo_time(124)},"all":{"played":6,"win":2,"draw":2,"lose":2},"points":8},
    ],
    128: [
        {"rank":1,"team":{"name":"River Plate","logo":_logo_time(1006)},"all":{"played":10,"win":7,"draw":1,"lose":2},"points":22},
        {"rank":2,"team":{"name":"Boca Juniors","logo":_logo_time(1005)},"all":{"played":10,"win":6,"draw":2,"lose":2},"points":20},
        {"rank":3,"team":{"name":"Racing Club","logo":_logo_time(1008)},"all":{"played":10,"win":5,"draw":3,"lose":2},"points":18},
        {"rank":4,"team":{"name":"San Lorenzo","logo":_logo_time(1007)},"all":{"played":10,"win":4,"draw":3,"lose":3},"points":15},
    ],
}

_DEMO_SCRIPTS = ["high_scoring","home_dominant","balanced","defensive","away_upset"]
_DEMO_SCRIPT_REASONINGS = {
    "high_scoring": "Ambas as equipes apresentam médias ofensivas elevadas na temporada. Os dados de forma recente e H2H indicam tendência clara para partidas com mais de 2.5 gols. A postura tática de ambos os treinadores privilegia o jogo ofensivo.",
    "home_dominant": "O mandante tem vantagem histórica significativa neste duelo e apresenta sólida forma em casa. Métricas de QSC e posição na tabela reforçam a superioridade da equipe da casa neste contexto.",
    "balanced": "Jogo equilibrado com ambas as equipes em formas similares. Nenhum fator contextual aponta dominância clara; empate é cenário plausível junto com vitória por margem mínima.",
    "defensive": "Tendência defensiva de ambas as equipes fica clara nos dados: médias baixas de gols e alta frequência de resultados com menos de 2.5 gols. Árbitro e contexto de campeonato reforçam cautela.",
    "away_upset": "Visitante vem de sequência positiva e tem histórico recente favorável contra este oponente. A pressão sobre o mandante abre espaço para cenários de surpresa ou empate.",
}

def _get_demo_analise(fixture_id: int) -> dict:
    """Retorna análise demo completa no formato de _db_to_api_response."""
    info = _get_demo_fixture_info(fixture_id)
    if not info:
        raise HTTPException(status_code=404, detail="Fixture demo não encontrado.")

    home = info["time_casa"]["nome"]
    away = info["time_fora"]["nome"]
    home_id = info["time_casa"]["id"]
    liga_id = info["liga"]["id"]
    liga_nome = info["liga"]["nome"]
    horario = info["horario_brt"]
    idx = (fixture_id - 90001) % 5
    script = _DEMO_SCRIPTS[idx]

    venue, cidade = _DEMO_VENUES.get(home_id, ("Estádio Demo", "—"))
    arbitro = _DEMO_ARBITROS[fixture_id % len(_DEMO_ARBITROS)]
    rodada = f"Rodada {(fixture_id % 15) + 18}"

    pos_casa = ((fixture_id - 90001) % 8) + 1
    pos_fora = ((fixture_id - 90001 + 3) % 8) + 1
    qsc_home = round(70 + (fixture_id % 25), 1)
    qsc_away = round(60 + ((fixture_id * 3) % 30), 1)

    forma_casa = _DEMO_FORMAS[fixture_id % len(_DEMO_FORMAS)]
    forma_fora = _DEMO_FORMAS[(fixture_id + 3) % len(_DEMO_FORMAS)]

    h2h_raw = _DEMO_H2H.get(fixture_id)
    if not h2h_raw:
        seed = fixture_id % 10
        h2h_raw = [
            {"data": f"2024-0{i+1}-15", "gols_casa": (seed+i)%4, "gols_fora": (seed+i+1)%3}
            for i in range(5)
        ]
    h2h_summary: dict = {}
    if h2h_raw:
        total_g = sum(g.get("gols_casa",0)+g.get("gols_fora",0) for g in h2h_raw)
        btts = sum(1 for g in h2h_raw if g.get("gols_casa",0)>0 and g.get("gols_fora",0)>0)
        h2h_summary = {"media_gols": round(total_g/len(h2h_raw),2), "btts_freq": round(btts/len(h2h_raw)*100,1), "total_jogos": len(h2h_raw)}

    stats_comparativas: dict = {
        "media_gols_marcados_casa": round(1.5 + (idx*0.2), 2),
        "media_gols_marcados_fora": round(1.2 + (idx*0.15), 2),
        "media_gols_sofridos_casa": round(1.1 + ((idx+1)*0.15), 2),
        "media_gols_sofridos_fora": round(1.3 + ((idx+2)*0.1), 2),
        "media_cantos_casa": round(5.2 + (idx*0.3), 2),
        "media_cantos_fora": round(4.8 + (idx*0.25), 2),
        "media_cartoes_casa": round(1.8 + (idx*0.1), 2),
        "media_cartoes_fora": round(2.0 + (idx*0.12), 2),
        "btts_percent_casa": round(55 + (idx*3), 1),
        "btts_percent_fora": round(48 + (idx*2.5), 1),
        "over25_percent_casa": round(58 + (idx*2), 1),
        "over25_percent_fora": round(52 + (idx*2), 1),
        "media_finalizacoes_casa": round(13.5 + (idx*0.8), 2),
        "media_finalizacoes_fora": round(11.2 + (idx*0.6), 2),
        "posse_media_casa": round(54 + (idx*1.5), 1),
        "posse_media_fora": round(46 + (idx*1.2), 1),
    }

    classificacao = _DEMO_STANDINGS_BY_LEAGUE.get(liga_id, [])

    if script == "high_scoring":
        mercados = [
            {"mercado":"Gols","palpites":[
                {"tipo":"Over 2.5","confianca":8.2,"probabilidade":72.0,"odd":1.75,"periodo":"FT","mercado":"Gols","justificativa":f"Ambos {home} e {away} possuem médias ofensivas acima de 1.5 gols/jogo. H2H aponta média de {h2h_summary.get('media_gols',2.8)} gols nas últimas partidas.","confidence_breakdown":{}},
                {"tipo":"Over 1.5","confianca":9.0,"probabilidade":85.0,"odd":1.35,"periodo":"FT","mercado":"Gols","justificativa":"Alta probabilidade de ao menos 2 gols dado o perfil ofensivo das equipes.","confidence_breakdown":{}},
                {"tipo":"Over 3.5","confianca":6.5,"probabilidade":48.0,"odd":2.70,"periodo":"FT","mercado":"Gols","justificativa":"Menos provável mas viável dado o ritmo da partida esperado.","confidence_breakdown":{}},
                {"tipo":"Over 0.5 1T","confianca":7.5,"probabilidade":68.0,"odd":1.55,"periodo":"HT","mercado":"Gols","justificativa":"Ambas equipes costumam marcar no primeiro tempo.","confidence_breakdown":{}},
            ]},
            {"mercado":"BTTS","palpites":[
                {"tipo":"Sim","confianca":7.8,"probabilidade":69.0,"odd":1.80,"periodo":"FT","mercado":"BTTS","justificativa":f"{home} e {away} marcam em {h2h_summary.get('btts_freq',60)}% dos duelos. Frequência de BTTS acima da média da liga.","confidence_breakdown":{}},
            ]},
            {"mercado":"Resultado","palpites":[
                {"tipo":"Casa Vence","confianca":7.0,"probabilidade":58.0,"odd":1.90,"periodo":"FT","mercado":"Resultado","justificativa":f"{home} em forte forma em casa com {pos_casa}º lugar na tabela.","confidence_breakdown":{}},
                {"tipo":"Empate","confianca":5.2,"probabilidade":24.0,"odd":3.50,"periodo":"FT","mercado":"Resultado","justificativa":"Empate é possível dado o nível técnico equilibrado.","confidence_breakdown":{}},
            ]},
            {"mercado":"Cantos","palpites":[
                {"tipo":"Over 9.5","confianca":7.2,"probabilidade":62.0,"odd":1.85,"periodo":"FT","mercado":"Cantos","justificativa":"Jogo ofensivo tende a gerar muitos escanteios. Ambas equipes pressionam alto.","confidence_breakdown":{}},
                {"tipo":"Over 8.5","confianca":8.0,"probabilidade":70.0,"odd":1.60,"periodo":"FT","mercado":"Cantos","justificativa":"Volume de jogo elevado esperado dada a postura das equipes.","confidence_breakdown":{}},
            ]},
            {"mercado":"Cartões","palpites":[
                {"tipo":"Over 3.5","confianca":6.0,"probabilidade":52.0,"odd":2.10,"periodo":"FT","mercado":"Cartões","justificativa":"Árbitro com média de 3.8 cartões por jogo nesta temporada.","confidence_breakdown":{}},
            ]},
            {"mercado":"Handicaps","palpites":[
                {"tipo":"Casa -0.5","confianca":6.8,"probabilidade":56.0,"odd":2.05,"periodo":"FT","mercado":"Handicaps","justificativa":f"{home} tem vantagem de QSC de {qsc_home-qsc_away:.0f} pontos sobre o visitante.","confidence_breakdown":{}},
            ]},
            {"mercado":"Gols Ambos Tempos","palpites":[
                {"tipo":"Sim","confianca":6.5,"probabilidade":54.0,"odd":2.30,"periodo":"FT","mercado":"Gols Ambos Tempos","justificativa":"Perfil ofensivo de ambas equipes sugere gols em ambos os tempos.","confidence_breakdown":{}},
            ]},
        ]
        mercados_vetados = [
            {"mercado":"Placar Exato","motivo":"Baixa confiança estatística — variância alta em jogos ofensivos dificulta previsão precisa de placar."},
            {"mercado":"Handicap Europeu","motivo":"Odds de mercado não refletem edge estatístico suficiente neste contexto."},
        ]
    elif script == "home_dominant":
        mercados = [
            {"mercado":"Resultado","palpites":[
                {"tipo":"Casa Vence","confianca":8.5,"probabilidade":68.0,"odd":1.65,"periodo":"FT","mercado":"Resultado","justificativa":f"{home} é {pos_casa}º na tabela com QSC {qsc_home:.0f} vs QSC {qsc_away:.0f} do visitante. Domínio histórico em casa.","confidence_breakdown":{}},
                {"tipo":"Casa ou Empate","confianca":9.0,"probabilidade":80.0,"odd":1.28,"periodo":"FT","mercado":"Resultado","justificativa":"Alta probabilidade de não derrota para o mandante.","confidence_breakdown":{}},
            ]},
            {"mercado":"Gols","palpites":[
                {"tipo":"Over 1.5","confianca":8.0,"probabilidade":75.0,"odd":1.42,"periodo":"FT","mercado":"Gols","justificativa":"Mandante em boa forma ofensiva e visitante tem defesa porosa fora de casa.","confidence_breakdown":{}},
                {"tipo":"Over 2.5","confianca":6.5,"probabilidade":52.0,"odd":2.00,"periodo":"FT","mercado":"Gols","justificativa":"Moderada probabilidade — mandante pode vencer por margem mínima.","confidence_breakdown":{}},
                {"tipo":"Under 3.5","confianca":7.0,"probabilidade":68.0,"odd":1.55,"periodo":"FT","mercado":"Gols","justificativa":"Visitante tende a se fechar na segunda metade quando em desvantagem.","confidence_breakdown":{}},
            ]},
            {"mercado":"BTTS","palpites":[
                {"tipo":"Não","confianca":6.8,"probabilidade":58.0,"odd":1.75,"periodo":"FT","mercado":"BTTS","justificativa":f"{home} tem clean sheet em 45% dos jogos em casa nesta temporada.","confidence_breakdown":{}},
            ]},
            {"mercado":"Cantos","palpites":[
                {"tipo":"Over 8.5","confianca":7.0,"probabilidade":63.0,"odd":1.72,"periodo":"FT","mercado":"Cantos","justificativa":"Mandante domina posse e gera mais escanteios. Média casa: {:.1f} escanteios.".format(stats_comparativas["media_cantos_casa"]),"confidence_breakdown":{}},
                {"tipo":"Casa Over 5.5","confianca":7.5,"probabilidade":66.0,"odd":1.80,"periodo":"FT","mercado":"Cantos","justificativa":"Mandante domina territorialmente com média de escanteios alta.","confidence_breakdown":{}},
            ]},
            {"mercado":"Handicaps","palpites":[
                {"tipo":"Casa -1","confianca":6.2,"probabilidade":48.0,"odd":2.40,"periodo":"FT","mercado":"Handicaps","justificativa":"Casa vencendo por margem de 2+ é plausível dado o desequilíbrio de qualidade.","confidence_breakdown":{}},
            ]},
            {"mercado":"Cartões","palpites":[
                {"tipo":"Under 3.5","confianca":6.5,"probabilidade":57.0,"odd":1.85,"periodo":"FT","mercado":"Cartões","justificativa":"Visitante sem motivação extra para faltas excessivas — jogo pode ser controlado pelo mandante.","confidence_breakdown":{}},
            ]},
        ]
        mercados_vetados = [
            {"mercado":"Placar Exato","motivo":"Alta incerteza no placar exato apesar de tendência clara de vitória para o mandante."},
            {"mercado":"Primeiro a Marcar","motivo":"Dados insuficientes de primeira finalização para gerar previsão confiável."},
        ]
    elif script == "balanced":
        mercados = [
            {"mercado":"Resultado","palpites":[
                {"tipo":"Empate","confianca":6.8,"probabilidade":34.0,"odd":3.10,"periodo":"FT","mercado":"Resultado","justificativa":"Equipes em formas equivalentes — empate é o resultado mais provável estatisticamente.","confidence_breakdown":{}},
                {"tipo":"Casa Vence","confianca":6.2,"probabilidade":38.0,"odd":2.20,"periodo":"FT","mercado":"Resultado","justificativa":f"{home} tem ligeira vantagem de QSC mas não o suficiente para alta confiança.","confidence_breakdown":{}},
            ]},
            {"mercado":"BTTS","palpites":[
                {"tipo":"Sim","confianca":7.2,"probabilidade":64.0,"odd":1.82,"periodo":"FT","mercado":"BTTS","justificativa":"Ambas equipes marcam regularmente e podem se anular defensivamente.","confidence_breakdown":{}},
            ]},
            {"mercado":"Gols","palpites":[
                {"tipo":"Over 2.5","confianca":6.5,"probabilidade":55.0,"odd":1.95,"periodo":"FT","mercado":"Gols","justificativa":f"Média H2H de {h2h_summary.get('media_gols',2.5):.1f} gols nas últimas 5 partidas entre as equipes.","confidence_breakdown":{}},
                {"tipo":"Over 1.5","confianca":8.2,"probabilidade":78.0,"odd":1.38,"periodo":"FT","mercado":"Gols","justificativa":"Muito provável — ambas equipes têm bons atacantes.","confidence_breakdown":{}},
            ]},
            {"mercado":"Cantos","palpites":[
                {"tipo":"Over 9.5","confianca":6.8,"probabilidade":58.0,"odd":1.90,"periodo":"FT","mercado":"Cantos","justificativa":"Jogo equilibrado com intensidade gera volume de escanteios.","confidence_breakdown":{}},
            ]},
            {"mercado":"Handicaps","palpites":[
                {"tipo":"Fora +0.5","confianca":6.5,"probabilidade":54.0,"odd":1.75,"periodo":"FT","mercado":"Handicaps","justificativa":"Visitante tem qualidade para não perder, ou empate é cenário plausível.","confidence_breakdown":{}},
            ]},
            {"mercado":"Cartões","palpites":[
                {"tipo":"Over 3.5","confianca":6.2,"probabilidade":53.0,"odd":2.05,"periodo":"FT","mercado":"Cartões","justificativa":"Jogo equilibrado com disputa intensa tende a gerar mais cartões.","confidence_breakdown":{}},
            ]},
            {"mercado":"Gols Ambos Tempos","palpites":[
                {"tipo":"Sim","confianca":5.8,"probabilidade":47.0,"odd":2.60,"periodo":"FT","mercado":"Gols Ambos Tempos","justificativa":"Probabilidade moderada de gols em ambos os tempos dado equilíbrio técnico.","confidence_breakdown":{}},
            ]},
        ]
        mercados_vetados = [
            {"mercado":"Placar Exato","motivo":"Equilíbrio entre equipes dificulta previsão confiável de placar exato."},
            {"mercado":"Handicap Europeu","motivo":"Odd de mercado sem edge estatístico relevante."},
        ]
    elif script == "defensive":
        mercados = [
            {"mercado":"Gols","palpites":[
                {"tipo":"Under 2.5","confianca":7.8,"probabilidade":65.0,"odd":1.75,"periodo":"FT","mercado":"Gols","justificativa":"Ambas equipes com perfil defensivo — média de gols abaixo de 2 por jogo nesta temporada.","confidence_breakdown":{}},
                {"tipo":"Under 1.5","confianca":6.2,"probabilidade":48.0,"odd":2.30,"periodo":"FT","mercado":"Gols","justificativa":"Possível jogo de baixo scoring — especialmente em confrontos diretos.","confidence_breakdown":{}},
                {"tipo":"Over 0.5","confianca":9.0,"probabilidade":88.0,"odd":1.22,"periodo":"FT","mercado":"Gols","justificativa":"Mínimo de 1 gol é virtualmente certo neste confronto.","confidence_breakdown":{}},
            ]},
            {"mercado":"BTTS","palpites":[
                {"tipo":"Não","confianca":7.5,"probabilidade":62.0,"odd":1.70,"periodo":"FT","mercado":"BTTS","justificativa":f"{home} e {away} têm clean sheet combinado de 42% esta temporada. Defesas sólidas.","confidence_breakdown":{}},
            ]},
            {"mercado":"Resultado","palpites":[
                {"tipo":"Casa Vence ou Empate","confianca":7.0,"probabilidade":64.0,"odd":1.55,"periodo":"FT","mercado":"Resultado","justificativa":f"{home} como mandante tem vantagem sutil — placar mínimo ou empate sem gols é frequente.","confidence_breakdown":{}},
            ]},
            {"mercado":"Cantos","palpites":[
                {"tipo":"Under 9.5","confianca":7.2,"probabilidade":61.0,"odd":1.78,"periodo":"FT","mercado":"Cantos","justificativa":"Jogo mais fechado e de transições rápidas gera menos escanteios.","confidence_breakdown":{}},
                {"tipo":"Under 8.5","confianca":6.5,"probabilidade":54.0,"odd":2.10,"periodo":"FT","mercado":"Cantos","justificativa":"Possível se ambas equipes jogarem de forma direta.","confidence_breakdown":{}},
            ]},
            {"mercado":"Cartões","palpites":[
                {"tipo":"Over 4.5","confianca":6.0,"probabilidade":50.0,"odd":2.40,"periodo":"FT","mercado":"Cartões","justificativa":"Jogos defensivos com pressão intensa tendem a gerar mais faltas e cartões.","confidence_breakdown":{}},
            ]},
            {"mercado":"Handicaps","palpites":[
                {"tipo":"Casa 0","confianca":6.8,"probabilidade":58.0,"odd":1.88,"periodo":"FT","mercado":"Handicaps","justificativa":"Linha zero protege em caso de empate dado perfil defensivo do jogo.","confidence_breakdown":{}},
            ]},
        ]
        mercados_vetados = [
            {"mercado":"Gols Ambos Tempos","motivo":"Baixa frequência de BTTS em jogos defensivos — confiança abaixo do limiar mínimo."},
            {"mercado":"Placar Exato","motivo":"Embora a tendência seja baixo placar, a previsão exata tem variância alta demais."},
        ]
    else:
        mercados = [
            {"mercado":"Resultado","palpites":[
                {"tipo":"Fora Vence","confianca":7.0,"probabilidade":45.0,"odd":2.80,"periodo":"FT","mercado":"Resultado","justificativa":f"{away} vem de boa sequência (últimos 5: {''.join(forma_fora)}) e historicamente performa bem como visitante.","confidence_breakdown":{}},
                {"tipo":"Empate","confianca":6.5,"probabilidade":30.0,"odd":3.20,"periodo":"FT","mercado":"Resultado","justificativa":"Empate é cenário provável se {home} não conseguir criar suficiente.","confidence_breakdown":{}},
            ]},
            {"mercado":"BTTS","palpites":[
                {"tipo":"Sim","confianca":7.5,"probabilidade":65.0,"odd":1.78,"periodo":"FT","mercado":"BTTS","justificativa":f"Visitante marca em 68% dos jogos fora de casa. Mandante vulnerável defensivamente.","confidence_breakdown":{}},
            ]},
            {"mercado":"Gols","palpites":[
                {"tipo":"Over 2.5","confianca":6.8,"probabilidade":57.0,"odd":1.98,"periodo":"FT","mercado":"Gols","justificativa":"Visitante agressivo e mandante pressionado tende a abrir o jogo.","confidence_breakdown":{}},
                {"tipo":"Over 1.5","confianca":8.5,"probabilidade":80.0,"odd":1.40,"periodo":"FT","mercado":"Gols","justificativa":"Alta probabilidade independente do placar final.","confidence_breakdown":{}},
            ]},
            {"mercado":"Handicaps","palpites":[
                {"tipo":"Fora -0.5","confianca":6.2,"probabilidade":45.0,"odd":3.10,"periodo":"FT","mercado":"Handicaps","justificativa":"Visitante em melhor forma recente oferece valor nesta linha.","confidence_breakdown":{}},
                {"tipo":"Fora +0.5","confianca":7.8,"probabilidade":62.0,"odd":1.55,"periodo":"FT","mercado":"Handicaps","justificativa":"Visitante com qualidade para ao menos empatar.","confidence_breakdown":{}},
            ]},
            {"mercado":"Cantos","palpites":[
                {"tipo":"Over 9.5","confianca":6.5,"probabilidade":56.0,"odd":1.92,"periodo":"FT","mercado":"Cantos","justificativa":"Visitante dominando posse gera volume de escanteios para o mandante explorar também.","confidence_breakdown":{}},
            ]},
            {"mercado":"Cartões","palpites":[
                {"tipo":"Over 3.5","confianca":6.8,"probabilidade":58.0,"odd":2.00,"periodo":"FT","mercado":"Cartões","justificativa":"Pressão do mandante em busca de gol tende a gerar mais faltas e cartões.","confidence_breakdown":{}},
            ]},
        ]
        mercados_vetados = [
            {"mercado":"Placar Exato","motivo":"Upset games têm alta imprevisibilidade de placar — confiança insuficiente."},
            {"mercado":"Primeiro a Marcar","motivo":"Dados históricos insuficientes para definir tendência de primeiro gol com confiança."},
        ]

    total_palpites = sum(len(m["palpites"]) for m in mercados)
    melhor_confianca = max((p["confianca"] for m in mercados for p in m["palpites"]), default=0)

    return {
        "fixture_id": fixture_id,
        "status": "ready",
        "time_casa": home,
        "time_fora": away,
        "liga": liga_nome,
        "data_analise": datetime.now(BRASILIA_TZ).isoformat(),
        "data_jogo_iso": f"2026-04-03T{horario}:00-03:00",
        "total_palpites": total_palpites,
        "melhor_confianca": melhor_confianca,
        "mercados": mercados,
        "fixture_metadata": {
            "rodada": rodada,
            "venue": venue,
            "venue_cidade": cidade,
            "arbitro": arbitro,
            "data_analise": datetime.now(BRASILIA_TZ).isoformat(),
            "lineup_confirmado": True,
        },
        "script_tatico": script,
        "script_reasoning": _DEMO_SCRIPT_REASONINGS[script],
        "pos_casa": pos_casa,
        "pos_fora": pos_fora,
        "qsc_home": qsc_home,
        "qsc_away": qsc_away,
        "forma_recente_casa": forma_casa,
        "forma_recente_fora": forma_fora,
        "h2h": h2h_raw,
        "h2h_summary": h2h_summary,
        "stats_comparativas": stats_comparativas,
        "classificacao": classificacao,
        "mercados_vetados": mercados_vetados,
    }


def _demo_best_palpites(fixture_id: int) -> list:
    """Retorna os 2-3 melhores palpites demo para um jogo (usado na home)."""
    idx = (fixture_id - 90001) % 5
    if idx == 0:
        return [
            {"mercado":"Gols","tipo":"Over 2.5","odd":1.75,"probabilidade":72.0,"confianca":8.2},
            {"mercado":"BTTS","tipo":"Sim","odd":1.80,"probabilidade":69.0,"confianca":7.8},
            {"mercado":"Gols","tipo":"Over 1.5","odd":1.35,"probabilidade":85.0,"confianca":9.0},
        ]
    elif idx == 1:
        return [
            {"mercado":"Resultado","tipo":"Casa Vence","odd":1.65,"probabilidade":68.0,"confianca":8.5},
            {"mercado":"Cantos","tipo":"Over 8.5","odd":1.60,"probabilidade":70.0,"confianca":8.0},
        ]
    elif idx == 2:
        return [
            {"mercado":"BTTS","tipo":"Sim","odd":1.82,"probabilidade":64.0,"confianca":7.2},
            {"mercado":"Gols","tipo":"Over 1.5","odd":1.38,"probabilidade":78.0,"confianca":8.2},
        ]
    elif idx == 3:
        return [
            {"mercado":"Gols","tipo":"Under 2.5","odd":1.75,"probabilidade":65.0,"confianca":7.8},
            {"mercado":"BTTS","tipo":"Não","odd":1.70,"probabilidade":62.0,"confianca":7.5},
        ]
    else:
        return [
            {"mercado":"BTTS","tipo":"Sim","odd":1.78,"probabilidade":65.0,"confianca":7.5},
            {"mercado":"Resultado","tipo":"Fora Vence","odd":2.80,"probabilidade":45.0,"confianca":7.0},
        ]


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
        "tem_analise": True,
        "best_palpites": _demo_best_palpites(fid),
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

    _api_key = os.environ.get("API_FOOTBALL_KEY", "").strip()
    resultado_raw: list
    is_demo = False

    if not _api_key:
        resultado = _get_demo_jogos()
        is_demo = True
        print("⚡ [DEMO] Sem API key — usando dados de demonstração instantâneos")
    else:
        jogos_raw = await buscar_jogos_do_dia()

        if jogos_raw:
            resultado_raw_list = []
            for jogo in jogos_raw:
                fid = jogo.get("fixture", {}).get("id")
                tem_analise = False
                cached = None
                if fid:
                    # Extrair data do kickoff para TTL inteligente
                    data_utc_str = jogo.get("fixture", {}).get("date", "")
                    data_kickoff = None
                    if data_utc_str:
                        try:
                            from zoneinfo import ZoneInfo as _ZI
                            dt_utc = datetime.fromisoformat(data_utc_str.replace("Z", "+00:00"))
                            data_kickoff = dt_utc.astimezone(_ZI("America/Sao_Paulo"))
                        except Exception:
                            pass
                    cached = db.buscar_analise(fid, data_jogo=data_kickoff, permitir_stale=True)
                    tem_analise = cached is not None
                resultado_raw_list.append(_formatar_jogo(jogo, tem_analise=tem_analise, analise_db=cached))
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
    if fixture_id in _DEMO_FIXTURE_IDS:
        return _get_demo_analise(fixture_id)

    status_atual = _processing_status.get(fixture_id)
    if status_atual == "processing":
        return {"fixture_id": fixture_id, "status": "processing"}

    # Se houve erro no processamento, tentar servir cache stale antes de falhar
    if status_atual == "error":
        analise_stale = db.buscar_analise(fixture_id, permitir_stale=True)
        if analise_stale:
            print(f"⚠️ [WebAPI] Servindo análise stale para fixture #{fixture_id} (erro na última tentativa)")
            return _db_to_api_response(analise_stale, fixture_id)
        raise HTTPException(status_code=500, detail="Erro na análise. Tente novamente.")

    # Tentar extrair kickoff do cache de jogos para aplicar TTL inteligente
    _kickoff_ge = None
    try:
        _jogos_ge = await buscar_jogos_do_dia()
        if _jogos_ge:
            for _j in _jogos_ge:
                if _j.get("fixture", {}).get("id") == fixture_id:
                    _dt = datetime.fromisoformat(
                        _j.get("fixture", {}).get("date", "").replace("Z", "+00:00")
                    )
                    _kickoff_ge = _dt.astimezone(ZoneInfo("America/Sao_Paulo"))
                    break
    except Exception:
        pass

    analise_db = db.buscar_analise(fixture_id, data_jogo=_kickoff_ge, permitir_stale=True)
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
    # Buscar dados do jogo para extrair kickoff e aplicar TTL inteligente
    jogos_raw = await buscar_jogos_do_dia()
    jogo_encontrado = None
    if jogos_raw:
        for j in jogos_raw:
            if j.get("fixture", {}).get("id") == fixture_id:
                jogo_encontrado = j
                break

    if not jogo_encontrado:
        raise HTTPException(status_code=404, detail=f"Jogo #{fixture_id} não encontrado nos jogos do dia.")

    # Extrair data/hora do kickoff para TTL inteligente (<2h = não usar cache fixo)
    _data_kickoff_post = None
    try:
        from zoneinfo import ZoneInfo as _ZI_post
        _dt_utc_post = datetime.fromisoformat(
            jogo_encontrado.get("fixture", {}).get("date", "").replace("Z", "+00:00")
        )
        _data_kickoff_post = _dt_utc_post.astimezone(_ZI_post("America/Sao_Paulo"))
    except Exception:
        pass

    # Verifica se já existe análise recente com TTL inteligente baseado no kickoff
    analise_db = db.buscar_analise(fixture_id, data_jogo=_data_kickoff_post)
    if analise_db:
        return {"fixture_id": fixture_id, "status": "ready", "message": "Análise já disponível em cache."}

    # Verifica se já está sendo processada
    if _processing_status.get(fixture_id) == "processing":
        return {"fixture_id": fixture_id, "status": "processing", "message": "Análise em andamento."}

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

    # Tentar extrair kickoff para aplicar TTL inteligente
    _kickoff_sa = None
    try:
        _jogos_sa = await buscar_jogos_do_dia()
        if _jogos_sa:
            for _j in _jogos_sa:
                if _j.get("fixture", {}).get("id") == fixture_id:
                    _dt = datetime.fromisoformat(
                        _j.get("fixture", {}).get("date", "").replace("Z", "+00:00")
                    )
                    _kickoff_sa = _dt.astimezone(ZoneInfo("America/Sao_Paulo"))
                    break
    except Exception:
        pass

    analise_db = db.buscar_analise(fixture_id, data_jogo=_kickoff_sa)
    if analise_db:
        return {"fixture_id": fixture_id, "status": "ready"}

    return {"fixture_id": fixture_id, "status": "not_found"}


@app.get("/api/jogadores/{fixture_id}")
async def get_jogadores_fixture(fixture_id: int):
    """
    Retorna mercados de jogadores (player props) relacionados a um fixture específico.
    Inclui mercado/confiança/odd/média/últimos 5/amostra para fins de aposta.
    """
    if fixture_id in _DEMO_FIXTURE_IDS:
        return _get_demo_lineup(fixture_id)

    try:
        with db._get_connection() as conn:
            if conn:
                from psycopg2.extras import RealDictCursor
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                # Buscar estatísticas + perfis para construir player market records
                cursor.execute(
                    """
                    SELECT
                        ej.jogador_id, ej.time_id, ej.minutos, ej.gols, ej.assistencias,
                        ej.finalizacoes, ej.finalizacoes_no_gol, ej.cartao_amarelo, ej.cartao_vermelho,
                        ej.eh_mandante, ej.foi_titular,
                        pj.nome, pj.n_jogos_total, pj.n_jogos_casa, pj.n_jogos_fora,
                        pj.media_gols, pj.media_assistencias,
                        pj.media_finalizacoes, pj.stddev_gols, pj.stddev_finalizacoes
                    FROM estatisticas_jogadores ej
                    LEFT JOIN perfis_jogadores pj ON pj.jogador_id = ej.jogador_id
                    WHERE ej.fixture_id = %s
                    ORDER BY ej.eh_mandante DESC, ej.foi_titular DESC, ej.minutos DESC
                    """,
                    (fixture_id,),
                )
                rows = cursor.fetchall()

                # Fetch last-5 game history per player from estatisticas_jogadores
                player_ids = list({r["jogador_id"] for r in rows if r.get("jogador_id")})
                last5_gols: dict = {}
                last5_assist: dict = {}
                last5_fins: dict = {}
                media_casa: dict = {}
                media_fora: dict = {}

                if player_ids:
                    cursor.execute(
                        """
                        SELECT jogador_id, gols, assistencias, finalizacoes, eh_mandante,
                               ROW_NUMBER() OVER (PARTITION BY jogador_id ORDER BY fixture_id DESC) AS rn
                        FROM estatisticas_jogadores
                        WHERE jogador_id = ANY(%s) AND fixture_id != %s
                        """,
                        (player_ids, fixture_id),
                    )
                    hist_rows = cursor.fetchall()
                    from collections import defaultdict
                    hist_by_player: dict = defaultdict(list)
                    for hr in hist_rows:
                        if hr["rn"] <= 5:
                            hist_by_player[hr["jogador_id"]].append(dict(hr))

                    for pid, games in hist_by_player.items():
                        last5_gols[pid] = [g["gols"] or 0 for g in games[:5]]
                        last5_assist[pid] = [g["assistencias"] or 0 for g in games[:5]]
                        last5_fins[pid] = [g["finalizacoes"] or 0 for g in games[:5]]
                        casa = [g for g in games if g["eh_mandante"]]
                        fora = [g for g in games if not g["eh_mandante"]]
                        media_casa[pid] = round(sum(g["gols"] or 0 for g in casa) / len(casa), 3) if casa else None
                        media_fora[pid] = round(sum(g["gols"] or 0 for g in fora) / len(fora), 3) if fora else None

                cursor.close()

                def _formatar_perfil_jogador(row: dict) -> dict:
                    """Serializa o perfil histórico de um jogador (sem previsões sintéticas)."""
                    pid = row.get("jogador_id")
                    n = row.get("n_jogos_total") or 0
                    n_casa = row.get("n_jogos_casa") or 0
                    n_fora = row.get("n_jogos_fora") or 0
                    return {
                        "jogador_id": pid,
                        "nome": row.get("nome") or f"Jogador #{pid}",
                        "foi_titular": row.get("foi_titular", False),
                        "minutos": row.get("minutos") or 0,
                        "gols": row.get("gols") or 0,
                        "assistencias": row.get("assistencias") or 0,
                        "finalizacoes": row.get("finalizacoes") or 0,
                        "cartao_amarelo": bool(row.get("cartao_amarelo")),
                        "cartao_vermelho": bool(row.get("cartao_vermelho")),
                        "eh_mandante": row.get("eh_mandante", True),
                        "n_jogos": n,
                        "n_jogos_casa": n_casa,
                        "n_jogos_fora": n_fora,
                        "media_gols": row.get("media_gols"),
                        "media_assistencias": row.get("media_assistencias"),
                        "media_finalizacoes": row.get("media_finalizacoes"),
                        "media_gols_casa": media_casa.get(pid),
                        "media_gols_fora": media_fora.get(pid),
                        "ultimos_5_gols": last5_gols.get(pid, []),
                        "ultimos_5_assistencias": last5_assist.get(pid, []),
                        "ultimos_5_finalizacoes": last5_fins.get(pid, []),
                        "amostra_pequena": n > 0 and n < 6,
                        "lesionado": bool(row.get("lesionado")),
                        "suspenso": bool(row.get("suspenso")),
                    }

                all_rows = [dict(r) for r in rows]
                mandantes_rows = [_formatar_perfil_jogador(r) for r in all_rows if r.get("eh_mandante")]
                visitantes_rows = [_formatar_perfil_jogador(r) for r in all_rows if not r.get("eh_mandante")]

                return {
                    "fixture_id": fixture_id,
                    "mandantes": mandantes_rows,
                    "visitantes": visitantes_rows,
                    "total": len(rows),
                    "lineup_confirmado": False,
                    "lineup_fonte": "historico",
                }
    except Exception as e:
        print(f"[WebAPI] Erro ao buscar jogadores para fixture #{fixture_id}: {e}")

    return {
        "fixture_id": fixture_id,
        "mandantes": [],
        "visitantes": [],
        "total": 0,
        "lineup_confirmado": False,
        "lineup_fonte": None,
    }


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


@app.get("/api/performance")
async def get_performance():
    """
    Retorna a performance histórica do sistema.

    Response:
        - mercados: performance agregada por mercado (taxa de acerto, n_amostras, ROI)
        - por_liga: breakdown por mercado + liga_id para detalhamento geográfico
        - evolucao: série temporal diária de taxa de acerto (últimos 30 dias)
        - ultimos_palpites: últimos 20 palpites com resultado conhecido
        - resumo: totais globais (taxa geral, ROI total, n_amostras)
    """
    try:
        mercados_raw = db.buscar_performance_mercados()
        por_liga_raw = db.buscar_performance_por_liga()
        evolucao_raw = db.buscar_evolucao_acerto(dias=30)
        ultimos_raw = db.buscar_ultimos_palpites(limite=20)

        total_palpites = sum(int(m.get("total_palpites", 0) or 0) for m in mercados_raw)
        total_acertos = sum(int(m.get("total_acertos", 0) or 0) for m in mercados_raw)
        roi_total = sum(float(m.get("roi_total", 0) or 0) for m in mercados_raw)
        taxa_geral = round(total_acertos / total_palpites * 100, 1) if total_palpites > 0 else 0.0

        mercados = [
            {
                "mercado": m["mercado"],
                "total_palpites": int(m.get("total_palpites", 0) or 0),
                "total_acertos": int(m.get("total_acertos", 0) or 0),
                "total_erros": int(m.get("total_erros", 0) or 0),
                "taxa_acerto": float(m.get("taxa_acerto") or 0),
                "roi_total": float(m.get("roi_total") or 0),
                "atualizado_em": str(m.get("atualizado_em", "")),
            }
            for m in mercados_raw
        ]

        por_liga = [
            {
                "mercado": r["mercado"],
                "liga_id": int(r["liga_id"]),
                "liga_nome": NOMES_LIGAS_PT.get(int(r["liga_id"]), [str(r["liga_id"])])[0],
                "n_amostras": int(r["n_amostras"] or 0),
                "total_acertos": int(r["total_acertos"] or 0),
                "taxa_acerto": float(r["taxa_acerto"] or 0),
                "roi_total": float(r["roi_total"] or 0),
            }
            for r in por_liga_raw
        ]

        ultimos_palpites = [
            {
                "id": p["id"],
                "fixture_id": p["fixture_id"],
                "time_casa": p.get("time_casa", ""),
                "time_fora": p.get("time_fora", ""),
                "liga": p.get("liga", ""),
                "data_jogo": str(p.get("data_jogo", "")),
                "mercado": p["mercado"],
                "linha": p["linha"],
                "time_aposta": p.get("time_aposta", "Total"),
                "confianca": p["confianca"],
                "odd": float(p["odd"]) if p.get("odd") is not None else None,
                "periodo": p.get("periodo", "FT"),
                "acertou": p["acertou"],
                "roi_unitario": float(p.get("roi_unitario") or 0),
                "criado_em": str(p.get("criado_em", "")),
            }
            for p in ultimos_raw
        ]

        return {
            "mercados": mercados,
            "por_liga": por_liga,
            "evolucao": evolucao_raw,
            "ultimos_palpites": ultimos_palpites,
            "resumo": {
                "total_palpites_avaliados": total_palpites,
                "total_acertos": total_acertos,
                "taxa_acerto_geral": taxa_geral,
                "roi_total": round(roi_total, 4),
            },
        }

    except Exception as e:
        print(f"❌ [WebAPI] Erro ao buscar performance: {e}")
        return {
            "mercados": [],
            "por_liga": [],
            "evolucao": [],
            "ultimos_palpites": [],
            "resumo": {
                "total_palpites_avaliados": 0,
                "total_acertos": 0,
                "taxa_acerto_geral": 0.0,
                "roi_total": 0.0,
            },
        }


@app.get("/api/health")
async def health():
    api_key = os.environ.get("API_FOOTBALL_KEY", "").strip()
    return {
        "status": "ok",
        "timestamp": datetime.now(BRASILIA_TZ).isoformat(),
        "is_demo": not bool(api_key),
    }


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
