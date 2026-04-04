# analysts/btts_analyzer.py
import math
from config import MIN_CONFIANCA_BTTS_SIM, MIN_CONFIANCA_BTTS_NAO
from analysts.confidence_calculator import calculate_final_confidence


def analisar_mercado_btts(stats_casa, stats_fora, odds, script_name=None, analysis_packet=None):
    """
    Analisa o mercado de Ambas Marcam (BTTS - Both Teams To Score).

    PHOENIX V4.0 - FASE 2: BTTS com clean sheet defensivo via Poisson.

    TASK 7: Quando analysis_packet está disponível, usa lambdas já ajustados
    por desfalques confirmados (home_injuries/away_injuries) em vez dos lambdas
    brutos das estatísticas de temporada. Isso garante que BTTS reflita ausências
    de jogadores-chave (e.g., centroavante suspenso → menor P(BTTS Sim)).

    P(BTTS) = P(home marca) × P(away marca)
    P(home marca) = 1 - e^(-lambda_eff_home)
    P(away marca) = 1 - e^(-lambda_eff_away)
    """
    if not stats_casa or not stats_fora or not odds:
        return None

    lambda_adj_notes = []
    lambda_adjusted = False

    # TASK 7: Usar lambdas ajustados por desfalques do analysis_packet quando disponível
    if analysis_packet:
        lambda_data = analysis_packet.get('calculated_probabilities', {}).get('lambda_goals', {})
        lambda_home_adj = lambda_data.get('lambda_home')
        lambda_away_adj = lambda_data.get('lambda_away')
        adj_meta = lambda_data.get('lambda_adjustments', {})
        lambda_adjusted = adj_meta.get('adjusted', False)
        lambda_adj_notes = adj_meta.get('notes', []) if lambda_adjusted else []

        if lambda_home_adj and lambda_away_adj and lambda_home_adj > 0 and lambda_away_adj > 0:
            lambda_eff_home = lambda_home_adj
            lambda_eff_away = lambda_away_adj
            print(f"  🔗 BTTS: Usando lambdas ajustados do Master ({lambda_eff_home:.2f}/{lambda_eff_away:.2f})")

            p_home_scores = 1 - math.exp(-lambda_eff_home)
            p_away_scores = 1 - math.exp(-lambda_eff_away)
            prob_btts_pct = round(p_home_scores * p_away_scores * 100, 1)
            prob_no_btts_pct = round(100 - prob_btts_pct, 1)

            palpites_btts = _build_btts_palpites(
                odds, prob_btts_pct, prob_no_btts_pct, script_name,
                lambda_eff_home, lambda_eff_away, p_home_scores, p_away_scores,
                lambda_adj_notes=lambda_adj_notes
            )
            if palpites_btts is not None:
                return palpites_btts
            return None

    # Fallback: cálculo clássico via estatísticas brutas
    lambda_home_attack = float(stats_casa.get('casa', {}).get('gols_marcados', 0) or 0)
    lambda_away_attack = float(stats_fora.get('fora', {}).get('gols_marcados', 0) or 0)
    lambda_home_def_conceded = float(stats_casa.get('casa', {}).get('gols_sofridos', 1.0) or 1.0)
    lambda_away_def_conceded = float(stats_fora.get('fora', {}).get('gols_sofridos', 1.0) or 1.0)

    if lambda_home_attack <= 0:
        lambda_home_attack = 1.2
    if lambda_away_attack <= 0:
        lambda_away_attack = 0.9
    if lambda_home_def_conceded <= 0:
        lambda_home_def_conceded = 1.0
    if lambda_away_def_conceded <= 0:
        lambda_away_def_conceded = 1.0

    lambda_eff_home = (lambda_home_attack + lambda_away_def_conceded) / 2
    lambda_eff_away = (lambda_away_attack + lambda_home_def_conceded) / 2

    p_home_scores = 1 - math.exp(-lambda_eff_home)
    p_away_scores = 1 - math.exp(-lambda_eff_away)

    prob_btts_pct = round(p_home_scores * p_away_scores * 100, 1)
    prob_no_btts_pct = round(100 - prob_btts_pct, 1)

    return _build_btts_palpites(
        odds, prob_btts_pct, prob_no_btts_pct, script_name,
        lambda_eff_home, lambda_eff_away, p_home_scores, p_away_scores,
        lambda_home_attack=lambda_home_attack, lambda_away_attack=lambda_away_attack,
        lambda_home_def_conceded=lambda_home_def_conceded, lambda_away_def_conceded=lambda_away_def_conceded,
    )


def _build_btts_palpites(
    odds, prob_btts_pct, prob_no_btts_pct, script_name,
    lambda_eff_home, lambda_eff_away, p_home_scores, p_away_scores,
    lambda_home_attack=None, lambda_away_attack=None,
    lambda_home_def_conceded=None, lambda_away_def_conceded=None,
    lambda_adj_notes=None,
):
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
        stats_lines = ""
        if lambda_home_attack is not None:
            stats_lines = (
                f"   - <b>Ataque Casa (casa):</b> {lambda_home_attack:.2f} gols/jogo | "
                f"<b>Ataque Fora (fora):</b> {lambda_away_attack:.2f} gols/jogo\n"
                f"   - <b>Defesa Casa concede (casa):</b> {lambda_home_def_conceded:.2f} | "
                f"<b>Defesa Fora concede (fora):</b> {lambda_away_def_conceded:.2f}\n"
            )
        adj_line = ""
        if lambda_adj_notes:
            adj_line = "   - ⚠️ " + " | ".join(lambda_adj_notes[:2]) + "\n"

        dados_suporte = (
            f"   - <b>Probabilidade Ambas Marcam:</b> {prob_btts_pct}%\n"
            f"   - <b>P(Casa marca):</b> {round(p_home_scores * 100, 1)}% "
            f"[λ_casa={lambda_eff_home:.2f}] | "
            f"<b>P(Fora marca):</b> {round(p_away_scores * 100, 1)}% "
            f"[λ_fora={lambda_eff_away:.2f}]\n"
            f"{stats_lines}"
            f"{adj_line}"
        )
        return {
            "mercado": "BTTS",
            "palpites": palpites_btts,
            "dados_suporte": dados_suporte
        }

    return None
