# result_tracker.py
"""
Job noturno (03:00 BRT) para rastrear resultados reais de jogos analisados.

Pipeline:
  1. Busca fixtures analisados sem resultado em resultado_jogos (janela 48h)
  2. Para cada fixture, consulta /fixtures?id=... na API-Football
  3. Se status FT/AET/PEN → grava placar em resultado_jogos
  4. Para cada palpite pendente → avalia acertou + roi_unitario
"""
import asyncio
from datetime import datetime
from typing import Optional, Tuple
from zoneinfo import ZoneInfo

BRASILIA_TZ = ZoneInfo("America/Sao_Paulo")

# Status da API-Football que indicam jogo encerrado
STATUS_ENCERRADO = {"FT", "AET", "PEN"}

# Atraso entre chamadas à API (rate limit: free plan = 10 req/min)
_DELAY_ENTRE_REQUESTS = 7.0


async def _buscar_resultado_fixture(fixture_id: int) -> Optional[dict]:
    """
    Consulta /fixtures?id=<fixture_id> na API-Football.

    Returns:
        Dict com dados do fixture (incluindo placar e status) ou None se falhar.
    """
    try:
        from api_client import get_http_client, API_URL
        client = get_http_client()
        if client is None:
            print(f"⚠️ [ResultTracker] HTTP client não inicializado para fixture #{fixture_id}")
            return None

        await asyncio.sleep(_DELAY_ENTRE_REQUESTS)
        response = await client.get(
            API_URL + "fixtures",
            params={"id": str(fixture_id)},
        )
        response.raise_for_status()

        data = response.json().get("response", [])
        if data:
            return data[0]
        return None

    except Exception as e:
        print(f"❌ [ResultTracker] Erro ao buscar fixture #{fixture_id}: {e}")
        return None


async def _buscar_estatisticas_cantos(fixture_id: int) -> Optional[dict]:
    """
    Busca estatísticas de cantos do jogo via /fixtures/statistics.

    Returns:
        Dict {home_corners, away_corners} ou None.
    """
    try:
        from api_client import get_http_client, API_URL
        client = get_http_client()
        if client is None:
            return None

        await asyncio.sleep(_DELAY_ENTRE_REQUESTS)
        response = await client.get(
            API_URL + "fixtures/statistics",
            params={"fixture": str(fixture_id)},
        )
        response.raise_for_status()

        teams_data = response.json().get("response", [])
        if len(teams_data) < 2:
            return None

        def _extrair_cantos(team_stats):
            for stat in team_stats.get("statistics", []):
                if stat.get("type") == "Corner Kicks":
                    v = stat.get("value")
                    return int(v) if v is not None else 0
            return 0

        return {
            "home_corners": _extrair_cantos(teams_data[0]),
            "away_corners": _extrair_cantos(teams_data[1]),
        }

    except Exception as e:
        print(f"⚠️ [ResultTracker] Não foi possível buscar cantos para fixture #{fixture_id}: {e}")
        return None


def _avaliar_palpite(
    linha: str,
    mercado: str,
    periodo: str,
    gols_casa: int,
    gols_fora: int,
    cantos_data: Optional[dict],
    status_final: str,
) -> Optional[bool]:
    """
    Avalia se um palpite acertou com base no resultado real do jogo.

    Args:
        linha: Descrição do palpite (ex: "Over 2.5", "Casa Vence (1)", "BTTS - Sim")
        mercado: Mercado do palpite (ex: "Gols", "Cantos", "BTTS", "Resultado")
        periodo: "FT" ou "HT"
        gols_casa: Gols marcados pela casa (FT)
        gols_fora: Gols marcados pelo visitante (FT)
        cantos_data: Dict com home_corners/away_corners ou None
        status_final: Status do jogo (FT, AET, PEN)

    Returns:
        True se acertou, False se errou, None se não foi possível avaliar.
    """
    linha_lower = linha.lower().strip()
    total_gols = gols_casa + gols_fora

    # ── Gols ──────────────────────────────────────────────────────────────
    if mercado in ("Gols", "Goals") and periodo == "FT":
        if "over" in linha_lower:
            try:
                threshold = float([t for t in linha_lower.split() if "." in t][0])
                return total_gols > threshold
            except (IndexError, ValueError):
                return None

        if "under" in linha_lower:
            try:
                threshold = float([t for t in linha_lower.split() if "." in t][0])
                return total_gols < threshold
            except (IndexError, ValueError):
                return None

    # ── BTTS ──────────────────────────────────────────────────────────────
    if mercado == "BTTS":
        ambos_marcaram = gols_casa > 0 and gols_fora > 0
        if "sim" in linha_lower or "yes" in linha_lower:
            return ambos_marcaram
        if "não" in linha_lower or "no" in linha_lower:
            return not ambos_marcaram

    # ── Resultado Final (1X2) ─────────────────────────────────────────────
    if mercado in ("Resultado", "Result"):
        casa_venceu = gols_casa > gols_fora
        fora_venceu = gols_fora > gols_casa
        empate = gols_casa == gols_fora

        if any(x in linha_lower for x in ("casa vence", "home win", " 1 ", "(1)")):
            return casa_venceu
        if any(x in linha_lower for x in ("fora vence", "away win", " 2 ", "(2)")):
            return fora_venceu
        if any(x in linha_lower for x in ("empate", "draw", " x ", "(x)")):
            return empate

        # Dupla chance
        if any(x in linha_lower for x in ("1x", "dupla 1x", "double 1x")):
            return casa_venceu or empate
        if any(x in linha_lower for x in ("x2", "dupla x2", "double x2")):
            return empate or fora_venceu
        if any(x in linha_lower for x in ("12", "dupla 12", "double 12")):
            return casa_venceu or fora_venceu

    # ── Cantos ─────────────────────────────────────────────────────────────
    if mercado in ("Cantos", "Corners") and cantos_data is not None:
        total_cantos = cantos_data.get("home_corners", 0) + cantos_data.get("away_corners", 0)
        if "over" in linha_lower:
            try:
                threshold = float([t for t in linha_lower.split() if "." in t][0])
                return total_cantos > threshold
            except (IndexError, ValueError):
                return None
        if "under" in linha_lower:
            try:
                threshold = float([t for t in linha_lower.split() if "." in t][0])
                return total_cantos < threshold
            except (IndexError, ValueError):
                return None

    return None  # Mercado não avaliável automaticamente


async def rastrear_resultados(db) -> dict:
    """
    Função principal do job noturno.

    Para cada fixture analisado sem resultado nas últimas 48h:
      1. Consulta a API para verificar se o jogo encerrou.
      2. Salva o resultado em resultado_jogos.
      3. Avalia cada palpite pendente e salva acertou + roi_unitario.

    Args:
        db: Instância de DatabaseManager já inicializada.

    Returns:
        Dict com estatísticas da execução.
    """
    print("🌙 [ResultTracker] Iniciando job noturno de rastreamento de resultados...")

    if not db.enabled:
        print("⚠️ [ResultTracker] Banco de dados não habilitado. Job abortado.")
        return {"status": "aborted", "motivo": "banco_desabilitado"}

    fixtures_pendentes = db.buscar_fixtures_sem_resultado(janela_horas=48)
    print(f"🔍 [ResultTracker] {len(fixtures_pendentes)} fixtures pendentes de resultado")

    stats = {
        "fixtures_verificados": 0,
        "resultados_salvos": 0,
        "palpites_avaliados": 0,
        "palpites_acertados": 0,
        "erros": 0,
    }

    for fixture_id in fixtures_pendentes:
        try:
            dados = await _buscar_resultado_fixture(fixture_id)
            if dados is None:
                stats["erros"] += 1
                continue

            fixture_info = dados.get("fixture", {})
            status_short = fixture_info.get("status", {}).get("short", "")

            if status_short not in STATUS_ENCERRADO:
                print(f"  ⏳ Fixture #{fixture_id} ainda não encerrou (status: {status_short})")
                continue

            # Extrair placar final
            score = dados.get("score", {})
            fulltime = score.get("fulltime", {})
            gols_casa = fulltime.get("home") or 0
            gols_fora = fulltime.get("away") or 0

            db.salvar_resultado_jogo(fixture_id, int(gols_casa), int(gols_fora), status_short)
            stats["resultados_salvos"] += 1
            print(f"  ✅ Fixture #{fixture_id} | {gols_casa}×{gols_fora} ({status_short})")

            # Buscar cantos (para avaliar palpites de cantos)
            cantos_data = await _buscar_estatisticas_cantos(fixture_id)

            # Avaliar palpites pendentes
            palpites = db.buscar_palpites_pendentes(fixture_id)
            for p in palpites:
                acertou = _avaliar_palpite(
                    linha=p.get("linha", ""),
                    mercado=p.get("mercado", ""),
                    periodo=p.get("periodo", "FT"),
                    gols_casa=int(gols_casa),
                    gols_fora=int(gols_fora),
                    cantos_data=cantos_data,
                    status_final=status_short,
                )

                if acertou is None:
                    continue  # Mercado não avaliável; deixar NULL

                try:
                    odd = float(p.get("odd") or 0)
                except (TypeError, ValueError):
                    odd = 0.0

                roi = round(odd - 1, 4) if acertou else -1.0

                db.atualizar_palpite_resultado(p["id"], acertou, roi)
                stats["palpites_avaliados"] += 1
                if acertou:
                    stats["palpites_acertados"] += 1

            stats["fixtures_verificados"] += 1

        except Exception as e:
            print(f"❌ [ResultTracker] Erro inesperado no fixture #{fixture_id}: {e}")
            stats["erros"] += 1

    taxa = 0.0
    if stats["palpites_avaliados"] > 0:
        taxa = round(stats["palpites_acertados"] / stats["palpites_avaliados"] * 100, 1)

    print(
        f"🌙 [ResultTracker] Job concluído | "
        f"{stats['resultados_salvos']} resultados | "
        f"{stats['palpites_avaliados']} palpites avaliados | "
        f"Taxa de acerto: {taxa}%"
    )
    return {**stats, "taxa_acerto_pct": taxa}


async def _scheduler_job_noturno(db):
    """
    Loop que aguarda até as 03:00 BRT e executa rastrear_resultados() diariamente.
    Deve ser criado como asyncio Task no startup do servidor.
    """
    from datetime import timedelta
    while True:
        agora = datetime.now(BRASILIA_TZ)
        target = agora.replace(hour=3, minute=0, second=0, microsecond=0)
        if agora >= target:
            target = target + timedelta(days=1)

        wait_secs = (target - agora).total_seconds()
        print(f"⏰ [ResultTracker] Próxima execução às {target.strftime('%Y-%m-%d %H:%M')} BRT ({wait_secs/3600:.1f}h)")

        await asyncio.sleep(wait_secs)

        try:
            await rastrear_resultados(db)
        except Exception as e:
            print(f"❌ [ResultTracker] Erro na execução do job noturno: {e}")
