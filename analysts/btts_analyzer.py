# analysts/btts_analyzer.py
import math
from config import MIN_CONFIANCA_BTTS_SIM, MIN_CONFIANCA_BTTS_NAO
from analysts.confidence_calculator import calculate_final_confidence


def analisar_mercado_btts(stats_casa, stats_fora, odds, script_name=None):
    """
    Analisa o mercado de Ambas Marcam (BTTS - Both Teams To Score).

    PHOENIX V4.0 - FASE 2: BTTS com clean sheet defensivo via Poisson.

    P(BTTS) = P(home marca) × P(away marca)

    P(home marca) = 1 - P(away defense keeps clean sheet)
                 = 1 - e^(-lambda_efetivo_home)
    onde lambda_efetivo_home = média(gols_marcados_casa_em_casa, gols_sofridos_fora_em_fora)

    P(away marca) = 1 - P(home defense keeps clean sheet)
                 = 1 - e^(-lambda_efetivo_away)
    onde lambda_efetivo_away = média(gols_marcados_fora_fora, gols_sofridos_casa_em_casa)

    Esta abordagem combina poder ofensivo do atacante com vulnerabilidade defensiva do oponente,
    sendo mais precisa que simplesmente dividir a média de gols por uma constante arbitrária.
    """
    if not stats_casa or not stats_fora or not odds:
        return None

    # Extrair lambdas de ataque (em contexto casa/fora)
    lambda_home_attack = float(stats_casa.get('casa', {}).get('gols_marcados', 0) or 0)
    lambda_away_attack = float(stats_fora.get('fora', {}).get('gols_marcados', 0) or 0)

    # Extrair lambdas defensivos (gols concedidos no contexto casa/fora)
    lambda_home_def_conceded = float(stats_casa.get('casa', {}).get('gols_sofridos', 1.0) or 1.0)
    lambda_away_def_conceded = float(stats_fora.get('fora', {}).get('gols_sofridos', 1.0) or 1.0)

    # Garantir mínimos realistas
    if lambda_home_attack <= 0:
        lambda_home_attack = 1.2
    if lambda_away_attack <= 0:
        lambda_away_attack = 0.9
    if lambda_home_def_conceded <= 0:
        lambda_home_def_conceded = 1.0
    if lambda_away_def_conceded <= 0:
        lambda_away_def_conceded = 1.0

    # Lambda efetivo = média do ataque próprio + fragilidade defensiva do adversário
    lambda_eff_home = (lambda_home_attack + lambda_away_def_conceded) / 2
    lambda_eff_away = (lambda_away_attack + lambda_home_def_conceded) / 2

    # Probabilidade de marcar ao menos 1 gol via Poisson: P(X ≥ 1) = 1 - e^(-λ)
    p_home_scores = 1 - math.exp(-lambda_eff_home)
    p_away_scores = 1 - math.exp(-lambda_eff_away)

    # P(BTTS) = P(home marca) × P(away marca)
    prob_btts_pct = round(p_home_scores * p_away_scores * 100, 1)
    prob_no_btts_pct = round(100 - prob_btts_pct, 1)

    palpites_btts = []

    if 'btts_yes' in odds:
        confianca, breakdown = calculate_final_confidence(
            statistical_probability_pct=prob_btts_pct,
            bet_type="BTTS Sim",
            tactical_script=script_name
        )
        if confianca >= MIN_CONFIANCA_BTTS_SIM:
            palpites_btts.append({
                "tipo": "Sim",
                "confianca": confianca,
                "odd": odds['btts_yes'],
                "breakdown": breakdown
            })

    if 'btts_no' in odds:
        confianca, breakdown = calculate_final_confidence(
            statistical_probability_pct=prob_no_btts_pct,
            bet_type="BTTS Não",
            tactical_script=script_name
        )
        if confianca >= MIN_CONFIANCA_BTTS_NAO:
            palpites_btts.append({
                "tipo": "Não",
                "confianca": confianca,
                "odd": odds['btts_no'],
                "breakdown": breakdown
            })

    if palpites_btts:
        dados_suporte = (
            f"   - <b>Probabilidade Ambas Marcam:</b> {prob_btts_pct}%\n"
            f"   - <b>P(Casa marca):</b> {round(p_home_scores * 100, 1)}% "
            f"[λ_casa={lambda_eff_home:.2f}] | "
            f"<b>P(Fora marca):</b> {round(p_away_scores * 100, 1)}% "
            f"[λ_fora={lambda_eff_away:.2f}]\n"
            f"   - <b>Ataque Casa (casa):</b> {lambda_home_attack:.2f} gols/jogo | "
            f"<b>Ataque Fora (fora):</b> {lambda_away_attack:.2f} gols/jogo\n"
            f"   - <b>Defesa Casa concede (casa):</b> {lambda_home_def_conceded:.2f} | "
            f"<b>Defesa Fora concede (fora):</b> {lambda_away_def_conceded:.2f}\n"
        )
        return {
            "mercado": "BTTS",
            "palpites": palpites_btts,
            "dados_suporte": dados_suporte
        }

    return None


