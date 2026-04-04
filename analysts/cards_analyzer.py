# analysts/cards_analyzer.py
"""
CARDS ANALYZER V3.0 - DEEP ANALYSIS PROTOCOL

BLUEPRINT IMPLEMENTATION:
- Retorna LISTA de múltiplas predições (~6 predições)
- Analisa submercados: Total Cards (Over/Under 3.5, 4.5, 5.5)
- Cada predição tem confiança calculada via confidence_calculator
- Implementa Script-Based Probability Modifier
"""

from config import MIN_CONFIANCA_CARTOES
from analysts.confidence_calculator import (
    calculate_statistical_probability_cards_over,
    calculate_final_confidence
)


def analisar_mercado_cartoes(analysis_packet, odds):
    """
    FUNÇÃO PRINCIPAL - Análise profunda do mercado de cartões.
    
    PHOENIX V4.0 - ALVO #2 CORRIGIDO:
    Agora usa WEIGHTED METRICS (ponderado por força do adversário) quando disponível.
    
    ACTION 1.3: Retorna LISTA de múltiplas predições (~6 predições) com submercados:
    - Total Cards FT: Over/Under 3.5, 4.5, 5.5
    
    Args:
        analysis_packet: Pacote completo do Master Analyzer
        odds: Dicionário de odds disponíveis
    
    Returns:
        dict: Análise com lista de predições ou None
    """
    if 'error' in analysis_packet:
        return None
    
    stats_casa = analysis_packet.get('raw_data', {}).get('home_stats', {})
    stats_fora = analysis_packet.get('raw_data', {}).get('away_stats', {})
    script_name = analysis_packet.get('analysis_summary', {}).get('selected_script', None)
    
    print(f"\n  🔍 CARTÕES V4.0: Iniciando análise profunda...")
    
    if not stats_casa or not stats_fora:
        print(f"  ⚠️ CARTÕES: Faltam estatísticas")
        return None

    # STEP 1: EXTRAIR MÉTRICAS DE CARTÕES
    # 🔥 PHOENIX V4.0: PRIORIZAR WEIGHTED METRICS
    cartoes_casa = 0.0
    cartoes_fora = 0.0
    use_weighted = False
    
    if 'analysis_summary' in analysis_packet:
        weighted_home = analysis_packet['analysis_summary'].get('weighted_metrics_home', {})
        weighted_away = analysis_packet['analysis_summary'].get('weighted_metrics_away', {})
        
        if weighted_home and weighted_away:
            use_weighted = True
            cartoes_casa = weighted_home.get('weighted_cards_for', 0.0)
            cartoes_fora = weighted_away.get('weighted_cards_for', 0.0)
            print(f"  ⚖️ CARTÕES V4.0: Usando WEIGHTED METRICS (ponderado por SoS)")
    
    if not use_weighted:
        cartoes_amarelos_casa = stats_casa.get('casa', {}).get('cartoes_amarelos', 0.0)
        cartoes_vermelhos_casa = stats_casa.get('casa', {}).get('cartoes_vermelhos', 0.0)
        cartoes_amarelos_fora = stats_fora.get('fora', {}).get('cartoes_amarelos', 0.0)
        cartoes_vermelhos_fora = stats_fora.get('fora', {}).get('cartoes_vermelhos', 0.0)
        cartoes_casa = cartoes_amarelos_casa + cartoes_vermelhos_casa
        cartoes_fora = cartoes_amarelos_fora + cartoes_vermelhos_fora
        print(f"  📊 CARTÕES V4.0: Usando médias simples")

    if cartoes_casa == 0.0 and cartoes_fora == 0.0:
        return None

    # STEP 2: CALCULAR MÉDIAS ESPERADAS
    media_exp_total = (cartoes_casa + cartoes_fora) / 2
    media_casa = cartoes_casa
    media_fora = cartoes_fora

    # H2H blend dinâmico para cartões
    h2h_data = analysis_packet.get('h2h')
    if h2h_data and h2h_data.get('count', 0) >= 3:
        h2h_avg_cards = h2h_data.get('avg_cards')
        if h2h_avg_cards is not None and h2h_avg_cards > 0:
            count = h2h_data['count']
            base_w = 0.40 + min(count - 3, 2) * 0.05
            divergence = abs(media_exp_total - h2h_avg_cards)
            div_bonus = min(divergence * 0.05, 0.10)
            h2h_weight = min(base_w + div_bonus, 0.55)
            media_exp_total = (1.0 - h2h_weight) * media_exp_total + h2h_weight * h2h_avg_cards

    all_predictions = []

    if not odds:
        print(f"  ⚠️ CARTÕES: Sem odds disponíveis")
        return None

    # ========== 1. TOTAL CARDS FULL TIME ==========
    
    linhas_total = [3.5, 4.5, 5.5]
    
    for linha in linhas_total:
        # Over
        odd_key_over = f"cartoes_over_{linha}"
        if odd_key_over in odds:
            prob_pct = calculate_statistical_probability_cards_over(
                weighted_cards_avg=media_exp_total,
                line=linha
            )
            
            bet_type = f"Over {linha} Cartões"
            conf_final, breakdown = calculate_final_confidence(
                statistical_probability_pct=prob_pct,
                bet_type=bet_type,
                tactical_script=script_name,
                odd=odds.get(odd_key_over),
            )
            
            if conf_final >= MIN_CONFIANCA_CARTOES:
                all_predictions.append({
                    "mercado": "Cartões",
                    "tipo": f"Over {linha}",
                    "confianca": conf_final,
                    "odd": odds[odd_key_over],
                    "time": "Total",
                    "breakdown": breakdown,
                    "probabilidade_estatistica": prob_pct
                })
        
        # Under
        odd_key_under = f"cartoes_under_{linha}"
        if odd_key_under in odds:
            prob_over = calculate_statistical_probability_cards_over(
                weighted_cards_avg=media_exp_total,
                line=linha
            )
            prob_under = 100.0 - prob_over
            
            bet_type = f"Under {linha} Cartões"
            conf_final, breakdown = calculate_final_confidence(
                statistical_probability_pct=prob_under,
                bet_type=bet_type,
                tactical_script=script_name,
                odd=odds.get(odd_key_under),
            )
            
            if conf_final >= MIN_CONFIANCA_CARTOES:
                all_predictions.append({
                    "mercado": "Cartões",
                    "tipo": f"Under {linha}",
                    "confianca": conf_final,
                    "odd": odds[odd_key_under],
                    "time": "Total",
                    "breakdown": breakdown,
                    "probabilidade_estatistica": prob_under
                })

    print(f"  ✅ CARTÕES V3.0: {len(all_predictions)} predições geradas (deep analysis)")
    
    if all_predictions:
        suporte = (f"Expectativa Cartões Total: {media_exp_total:.1f}\n"
                   f"Casa: {media_casa:.1f} cartões/jogo\n"
                   f"Fora: {media_fora:.1f} cartões/jogo\n")
        
        return {"mercado": "Cartões", "palpites": all_predictions, "dados_suporte": suporte}
    
    print(f"  ❌ CARTÕES: Nenhuma predição passou nos filtros")
    return None
