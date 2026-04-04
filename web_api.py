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
from analysts.htft_analyzer import analisar_mercado_htft
from analysts.win_to_nil_analyzer import analisar_mercado_win_to_nil
from analysts.draw_no_bet_analyzer import analisar_mercado_draw_no_bet
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
    from analysts.confidence_calculator import detect_value_bet

    if not analise or not analise.get("palpites"):
        return None
    palpites = analise["palpites"]
    if not palpites:
        return None

    resultado_palpites = []
    for p in palpites:
        prob = p.get("probabilidade", 0) or 0
        odd = p.get("odd")
        # Usar valor pre-computado pelo analyzer se disponível, caso contrário calcular
        if p.get("is_value") is not None and p.get("edge") is not None:
            is_value = p["is_value"]
            edge = p["edge"]
            prob_implicita = p.get("prob_implicita", 0)
        else:
            is_value, edge, prob_implicita = detect_value_bet(prob, odd) if odd else (False, 0.0, 0.0)

        resultado_palpites.append({
            "tipo": p.get("tipo", ""),
            "confianca": p.get("confianca", 0),
            "probabilidade": prob,
            "prob_implicita": prob_implicita,
            "edge": edge,
            "is_value": is_value,
            "odd": odd,
            "periodo": p.get("periodo", "FT"),
            "time": p.get("time", ""),
            "mercado": p.get("mercado", mercado_nome),
            "justificativa": p.get("justificativa", ""),
            "confidence_breakdown": p.get("confidence_breakdown", {}),
        })

    return {
        "mercado": mercado_nome,
        "palpites": resultado_palpites,
    }


def _validar_consistencia_cruzada(analise_gols, analise_btts):
    """
    Remove palpites logicamente contraditórios entre os mercados de Gols e BTTS.

    Conflitos tratados:
    - BTTS Sim + Under 0.5 FT → impossível (nenhuma equipe marca + ambas marcam)
    - BTTS Sim + Under 1.5 FT → quase impossível (max 1 gol, mas ambas devem marcar ≥2)
    - BTTS Não + Over 2.5 FT  → inconsistente (3+ gols concentrados num time é raro)

    Os conflitos são verificados tanto entre analise_gols e analise_btts (mercados
    separados) quanto dentro da própria analise_gols (goals_analyzer_v2 gera palpites
    de BTTS dentro do mesmo array de gols).

    Para cada conflito, o palpite de menor confiança é removido. Em caso de empate,
    remove-se o palpite de BTTS (mais difícil de prever).

    Modifica as listas de palpites in-place — chamada antes de db.salvar_analise().
    """
    def _get_palpites(analise):
        if not analise:
            return []
        if isinstance(analise, list):
            return analise
        return analise.get("palpites", [])

    def _remove_tipo_from(analise, tipo, label):
        palpites = _get_palpites(analise)
        original_len = len(palpites)
        if isinstance(analise, list):
            analise[:] = [p for p in analise if p.get("tipo") != tipo]
        elif isinstance(analise, dict):
            analise["palpites"] = [p for p in palpites if p.get("tipo") != tipo]
        removed = original_len - len(_get_palpites(analise))
        if removed:
            print(f"  ⚠️  CONSISTÊNCIA: Removido '{tipo}' de [{label}] ({removed} palpite(s)) — conflito cruzado")

    def _normalize_btts_tipo(tipo):
        """
        Normaliza nomes de tipo de palpites BTTS.
        btts_analyzer emite "Sim"/"Não"; goals_analyzer_v2 emite "BTTS Sim"/"BTTS Não".
        Retorna sempre a forma longa "BTTS Sim" / "BTTS Não", ou o tipo original se não for BTTS.
        """
        if tipo == "Sim":
            return "BTTS Sim"
        if tipo == "Não":
            return "BTTS Não"
        return tipo

    def _build_btts_index(analise):
        """
        Constrói índice {tipo_normalizado: confiança} para palpites BTTS.
        Aceita tanto o formato de btts_analyzer ("Sim"/"Não")
        quanto o de goals_analyzer_v2 ("BTTS Sim"/"BTTS Não").
        """
        return {_normalize_btts_tipo(p["tipo"]): p["confianca"]
                for p in _get_palpites(analise)
                if isinstance(p, dict) and "tipo" in p}

    def _remove_btts_from(analise, btts_tipo_normalizado, label):
        """Remove palpites BTTS (aceitando forma curta ou longa do tipo)."""
        forma_curta = btts_tipo_normalizado.replace("BTTS ", "")  # "Sim" ou "Não"
        palpites = _get_palpites(analise)
        original_len = len(palpites)
        filtrado = [p for p in palpites
                    if p.get("tipo") not in (btts_tipo_normalizado, forma_curta)]
        if isinstance(analise, list):
            analise[:] = filtrado
        elif isinstance(analise, dict):
            analise["palpites"] = filtrado
        removed = original_len - len(filtrado)
        if removed:
            print(f"  ⚠️  CONSISTÊNCIA: Removido '{btts_tipo_normalizado}' de [{label}] ({removed} palpite(s)) — conflito cruzado")

    def _apply_rules(btts_index, under_goals_index, over_goals_index,
                     btts_src, btts_label, gols_src, gols_label):
        """
        Aplica as 3 regras de conflito entre um índice BTTS e um índice de gols.
        btts_src / gols_src são as analises de onde os palpites devem ser removidos.
        """
        # Regra 1: BTTS Sim + Under 0.5 FT → impossível; remove BTTS Sim sempre
        if "BTTS Sim" in btts_index and "Under 0.5" in under_goals_index:
            _remove_btts_from(btts_src, "BTTS Sim", btts_label)
            return True  # regra 2 não se aplica mais

        # Regra 2: BTTS Sim + Under 1.5 FT → quase impossível; mantém o de maior confiança
        if "BTTS Sim" in btts_index and "Under 1.5" in under_goals_index:
            conf_btts = btts_index["BTTS Sim"]
            conf_under = under_goals_index["Under 1.5"]
            if conf_btts <= conf_under:
                _remove_btts_from(btts_src, "BTTS Sim", btts_label)
            else:
                _remove_tipo_from(gols_src, "Under 1.5", gols_label)

        # Regra 3: BTTS Não + Over 2.5 FT → inconsistente; mantém o de maior confiança
        if "BTTS Não" in btts_index and "Over 2.5" in over_goals_index:
            conf_btts = btts_index["BTTS Não"]
            conf_over = over_goals_index["Over 2.5"]
            if conf_btts <= conf_over:
                _remove_btts_from(btts_src, "BTTS Não", btts_label)
            else:
                _remove_tipo_from(gols_src, "Over 2.5", gols_label)
        return False

    # Helper para Under/Over FT dentro de analise_gols
    def _gols_under_index(analise):
        return {p["tipo"]: p["confianca"]
                for p in _get_palpites(analise)
                if isinstance(p, dict) and p.get("periodo") == "FT"
                and p.get("tipo", "").startswith("Under")}

    def _gols_over_index(analise):
        return {p["tipo"]: p["confianca"]
                for p in _get_palpites(analise)
                if isinstance(p, dict) and p.get("periodo") == "FT"
                and p.get("tipo", "").startswith("Over")}

    # --- Caso A: conflitos entre analise_btts (btts_analyzer) e analise_gols ---
    # btts_analyzer emite tipo="Sim"/"Não"; normalizar para "BTTS Sim"/"BTTS Não".
    btts_ext_index = _build_btts_index(analise_btts)
    _apply_rules(btts_ext_index, _gols_under_index(analise_gols), _gols_over_index(analise_gols),
                 analise_btts, "BTTS", analise_gols, "Gols")

    # --- Caso B: conflitos DENTRO de analise_gols ---
    # goals_analyzer_v2 também gera BTTS Sim/Não no mesmo array (mercado="BTTS").
    # Recalcula índices após possíveis remoções acima.
    btts_int_index = {_normalize_btts_tipo(p["tipo"]): p["confianca"]
                      for p in _get_palpites(analise_gols)
                      if isinstance(p, dict) and p.get("mercado") == "BTTS"}
    _apply_rules(btts_int_index, _gols_under_index(analise_gols), _gols_over_index(analise_gols),
                 analise_gols, "Gols(BTTS)", analise_gols, "Gols")


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
        _home_team = jogo["teams"]["home"]["name"]
        _away_team = jogo["teams"]["away"]["name"]
        _match_date = jogo["fixture"].get("date", "")
        odds = await buscar_odds_do_jogo(
            fixture_id,
            home_team=_home_team,
            away_team=_away_team,
            match_date=_match_date,
            league_id=id_liga,
        )
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
        analise_btts = analisar_mercado_btts(stats_casa, stats_fora, odds, script, analysis_packet=analysis_packet)
        analise_cartoes = analisar_mercado_cartoes(analysis_packet, odds)
        analise_finalizacoes = analisar_mercado_finalizacoes(stats_casa, stats_fora, odds, analysis_packet, script)
        analise_handicaps = analisar_mercado_handicaps(stats_casa, stats_fora, odds, classificacao, pos_casa, pos_fora, script, analysis_packet=analysis_packet)
        analise_dupla_chance = analisar_mercado_dupla_chance(analysis_packet, odds)
        analise_gabt = analisar_mercado_gabt(analysis_packet, odds)
        analise_placar_exato = analisar_mercado_placar_exato(analysis_packet, odds)
        analise_handicap_europeu = analisar_mercado_handicap_europeu(analysis_packet, odds)
        analise_primeiro_marcador = analisar_mercado_primeiro_a_marcar(analysis_packet, odds)
        analise_htft = analisar_mercado_htft(analysis_packet, odds)
        analise_win_to_nil = analisar_mercado_win_to_nil(analysis_packet, odds)
        analise_draw_no_bet = analisar_mercado_draw_no_bet(analysis_packet, odds)

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
            "HT/FT": analise_htft,
            "Win to Nil": analise_win_to_nil,
            "Draw No Bet": analise_draw_no_bet,
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

        # 3c. Validação de consistência cruzada entre mercados
        _validar_consistencia_cruzada(analise_gols, analise_btts)

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
            "htft": analise_htft,
            "win_to_nil": analise_win_to_nil,
            "draw_no_bet": analise_draw_no_bet,
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
        ("HT/FT", "analise_htft"),
        ("Win to Nil", "analise_win_to_nil"),
        ("Draw No Bet", "analise_draw_no_bet"),
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


@app.get("/api/jogos/hoje")
async def jogos_hoje():
    """
    Retorna os jogos do dia organizados em duas estruturas:
    - principais: top 8 jogos por score_destaque (liga × qualidade dos times)
    - por_pais: todos os jogos agrupados País → Liga → Partidas
    """
    from api_client import ORDEM_PAISES

    resultado = []
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
    return {
        "status": "ok",
        "timestamp": datetime.now(BRASILIA_TZ).isoformat(),
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
