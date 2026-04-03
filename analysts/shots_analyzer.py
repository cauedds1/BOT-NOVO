# analysts/shots_analyzer.py
"""
PHOENIX V3.0 - SHOTS ANALYZER (REFATORADO)
==========================================
UNIFIED CONFIDENCE SYSTEM: Usa exclusivamente confidence_calculator.py
para todos os cálculos de confiança.

ARQUITETURA:
1. Calcular probabilidade estatística de cada mercado de finalizações
2. Chamar calculate_final_confidence para obter confiança final
3. Usar breakdown para evidências e transparência
"""

from analysts.confidence_calculator import (
    calculate_statistical_probability_shots_over,
    calculate_final_confidence
)


def analisar_mercado_finalizacoes(stats_casa, stats_fora, odds=None, master_data=None, script_name=None, analysis_packet=None):
    """
    Analisa mercado de finalizações usando o sistema unificado de confiança.
    
    PHOENIX V4.0 - ALVO #2 CORRIGIDO:
    Agora usa WEIGHTED METRICS (ponderado por força do adversário) quando disponível.
    
    PHOENIX V3.0 REFACTORING:
    - ✅ USA confidence_calculator.py para TODOS os cálculos
    - ✅ Calcula probabilidade estatística primeiro
    - ✅ Aplica modificadores contextuais via calculate_final_confidence
    - ✅ Retorna breakdown para transparência
    
    Args:
        stats_casa: Estatísticas do time da casa
        stats_fora: Estatísticas do time visitante
        odds: Dicionário de odds disponíveis (raramente disponível para shots)
        master_data: Dados do master_analyzer (tactical script)
        script_name: Nome do script tático
        analysis_packet: Pacote completo do Master Analyzer (para weighted metrics)
    
    Returns:
        dict: Análise de finalizações com palpites ou None
    """
    print(f"  🔍 FINALIZAÇÕES V4.0: Verificando dados disponíveis...")

    # TASK 4: Extrair severidade de desfalques para penalidade de confiança
    _sev_home = analysis_packet.get('analysis_summary', {}).get('injury_severity_home', 'none') if analysis_packet else 'none'
    _sev_away = analysis_packet.get('analysis_summary', {}).get('injury_severity_away', 'none') if analysis_packet else 'none'
    
    if not stats_casa or not stats_fora:
        print(f"  ⚠️ FINALIZAÇÕES: Faltam estatísticas")
        return None

    # ✅ STEP 1: EXTRAIR MÉTRICAS DE FINALIZAÇÕES
    # 🔥 PHOENIX V4.0: PRIORIZAR WEIGHTED METRICS
    finalizacoes_casa = 0.0
    finalizacoes_fora = 0.0
    finalizacoes_gol_casa = 0.0
    finalizacoes_gol_fora = 0.0
    use_weighted = False
    
    if analysis_packet and 'analysis_summary' in analysis_packet:
        weighted_home = analysis_packet['analysis_summary'].get('weighted_metrics_home', {})
        weighted_away = analysis_packet['analysis_summary'].get('weighted_metrics_away', {})
        
        if weighted_home and weighted_away:
            use_weighted = True
            finalizacoes_casa = weighted_home.get('weighted_shots_for', 0.0)
            finalizacoes_fora = weighted_away.get('weighted_shots_for', 0.0)
            finalizacoes_gol_casa = finalizacoes_casa * 0.35
            finalizacoes_gol_fora = finalizacoes_fora * 0.35
            print(f"  ⚖️ FINALIZAÇÕES V4.0: Usando WEIGHTED METRICS (ponderado por SoS)")
    
    if not use_weighted:
        finalizacoes_casa = stats_casa['casa'].get('finalizacoes', 0.0)
        finalizacoes_fora = stats_fora['fora'].get('finalizacoes', 0.0)
        finalizacoes_gol_casa = stats_casa['casa'].get('finalizacoes_no_gol', 0.0)
        finalizacoes_gol_fora = stats_fora['fora'].get('finalizacoes_no_gol', 0.0)
        print(f"  📊 FINALIZAÇÕES V4.0: Usando médias simples")

    print(f"\n  📊 FINALIZAÇÕES - Dados:")
    print(f"     Casa: {finalizacoes_casa:.1f} total ({finalizacoes_gol_casa:.1f} no gol)")
    print(f"     Fora: {finalizacoes_fora:.1f} total ({finalizacoes_gol_fora:.1f} no gol)")

    if (finalizacoes_casa == 0.0 and finalizacoes_fora == 0.0 and 
        finalizacoes_gol_casa == 0.0 and finalizacoes_gol_fora == 0.0):
        print("  ❌ FINALIZAÇÕES BLOQUEADO: Dados insuficientes (todos 0.0)")
        return None

    # ✅ STEP 2: CALCULAR MÉDIAS ESPERADAS
    media_exp_total = finalizacoes_casa + finalizacoes_fora
    media_exp_no_gol = finalizacoes_gol_casa + finalizacoes_gol_fora

    print(f"  📊 Médias esperadas: Total={media_exp_total:.1f}, No gol={media_exp_no_gol:.1f}")

    palpites = []

    # ✅ STEP 3: ANALISAR MERCADOS
    # Nota: Odds raramente disponíveis para finalizações, então odds geralmente será None
    
    # --- TOTAL DE FINALIZAÇÕES OVER ---
    linhas_over_total = [21.5, 18.5, 15.5]
    for linha in linhas_over_total:
        # ✅ REFATORADO: Calcular probabilidade estatística
        prob_pct = calculate_statistical_probability_shots_over(
            weighted_shots_avg=media_exp_total,
            line=linha
        )
        
        # ✅ PURE ANALYST: Calculate confidence based purely on statistical probability
        bet_type = f"Over {linha} Finalizações"
        conf_final, breakdown = calculate_final_confidence(
            statistical_probability_pct=prob_pct,
            bet_type=bet_type,
            tactical_script=script_name,
            injury_severity_home=_sev_home,
            injury_severity_away=_sev_away
        )
        
        print(f"     {bet_type}: Prob={prob_pct:.1f}% → Conf={conf_final:.1f}")
        
        # Threshold mais alto para shots (menos confiável que outros mercados)
        if conf_final >= 5.5:
            palpites.append({
                "tipo": f"{bet_type} (Total)",
                "confianca": conf_final,
                "odd": None,  # Raramente disponível
                "time": "Total",
                "breakdown": breakdown,
                "probabilidade_estatistica": prob_pct
            })

    # --- TOTAL DE FINALIZAÇÕES UNDER ---
    linhas_under_total = [18.5, 15.5]
    for linha in linhas_under_total:
        prob_over = calculate_statistical_probability_shots_over(
            weighted_shots_avg=media_exp_total,
            line=linha
        )
        prob_under = 100.0 - prob_over
        
        bet_type = f"Under {linha} Finalizações"
        conf_final, breakdown = calculate_final_confidence(
            statistical_probability_pct=prob_under,
            bet_type=bet_type,
            tactical_script=script_name,
            injury_severity_home=_sev_home,
            injury_severity_away=_sev_away
        )
        
        if conf_final >= 5.5:
            palpites.append({
                "tipo": f"{bet_type} (Total)",
                "confianca": conf_final,
                "odd": None,
                "time": "Total",
                "breakdown": breakdown,
                "probabilidade_estatistica": prob_under
            })

    # --- FINALIZAÇÕES NO GOL (Shots on Target) OVER/UNDER ---
    if media_exp_no_gol > 0:
        # Over 9.5
        prob_pct = calculate_statistical_probability_shots_over(
            weighted_shots_avg=media_exp_no_gol,
            line=9.5
        )
        
        if prob_pct >= 45:  # Mínimo de probabilidade
            bet_type = "Over 9.5 Finalizações no Gol"
            conf_final, breakdown = calculate_final_confidence(
                statistical_probability_pct=prob_pct,
                bet_type=bet_type,
                tactical_script=script_name
            )
            
            if conf_final >= 5.5:
                palpites.append({
                    "tipo": f"{bet_type} (Total)",
                    "confianca": conf_final,
                    "odd": None,
                    "time": "Total",
                    "breakdown": breakdown,
                    "probabilidade_estatistica": prob_pct
                })
        
        # Under 7.5
        prob_over = calculate_statistical_probability_shots_over(
            weighted_shots_avg=media_exp_no_gol,
            line=7.5
        )
        prob_under = 100.0 - prob_over
        
        if prob_under >= 45:
            bet_type = "Under 7.5 Finalizações no Gol"
            conf_final, breakdown = calculate_final_confidence(
                statistical_probability_pct=prob_under,
                bet_type=bet_type,
                tactical_script=script_name
            )
            
            if conf_final >= 5.5:
                palpites.append({
                    "tipo": f"{bet_type} (Total)",
                    "confianca": conf_final,
                    "odd": None,
                    "time": "Total",
                    "breakdown": breakdown,
                    "probabilidade_estatistica": prob_under
                })

    # --- FINALIZAÇÕES POR TIME ---
    # Casa Over/Under
    if finalizacoes_casa > 0:
        # Over 11.5 Casa
        prob_pct = calculate_statistical_probability_shots_over(
            weighted_shots_avg=finalizacoes_casa,
            line=11.5
        )
        
        if prob_pct >= 45:
            bet_type = "Over 11.5 Finalizações Casa"
            conf_final, breakdown = calculate_final_confidence(
                statistical_probability_pct=prob_pct,
                bet_type=bet_type,
                tactical_script=script_name
            )
            
            if conf_final >= 5.5:
                palpites.append({
                    "tipo": "Over 11.5 Finalizações (Casa)",
                    "confianca": conf_final,
                    "odd": None,
                    "time": "Casa",
                    "breakdown": breakdown,
                    "probabilidade_estatistica": prob_pct
                })
        
        # Under 8.5 Casa
        prob_over = calculate_statistical_probability_shots_over(
            weighted_shots_avg=finalizacoes_casa,
            line=8.5
        )
        prob_under = 100.0 - prob_over
        
        if prob_under >= 45:
            bet_type = "Under 8.5 Finalizações Casa"
            conf_final, breakdown = calculate_final_confidence(
                statistical_probability_pct=prob_under,
                bet_type=bet_type,
                tactical_script=script_name
            )
            
            if conf_final >= 5.5:
                palpites.append({
                    "tipo": "Under 8.5 Finalizações (Casa)",
                    "confianca": conf_final,
                    "odd": None,
                    "time": "Casa",
                    "breakdown": breakdown,
                    "probabilidade_estatistica": prob_under
                })

    # Fora Over/Under
    if finalizacoes_fora > 0:
        # Over 11.5 Fora
        prob_pct = calculate_statistical_probability_shots_over(
            weighted_shots_avg=finalizacoes_fora,
            line=11.5
        )
        
        if prob_pct >= 45:
            bet_type = "Over 11.5 Finalizações Fora"
            conf_final, breakdown = calculate_final_confidence(
                statistical_probability_pct=prob_pct,
                bet_type=bet_type,
                tactical_script=script_name
            )
            
            if conf_final >= 5.5:
                palpites.append({
                    "tipo": "Over 11.5 Finalizações (Fora)",
                    "confianca": conf_final,
                    "odd": None,
                    "time": "Fora",
                    "breakdown": breakdown,
                    "probabilidade_estatistica": prob_pct
                })
        
        # Under 8.5 Fora
        prob_over = calculate_statistical_probability_shots_over(
            weighted_shots_avg=finalizacoes_fora,
            line=8.5
        )
        prob_under = 100.0 - prob_over
        
        if prob_under >= 45:
            bet_type = "Under 8.5 Finalizações Fora"
            conf_final, breakdown = calculate_final_confidence(
                statistical_probability_pct=prob_under,
                bet_type=bet_type,
                tactical_script=script_name
            )
            
            if conf_final >= 5.5:
                palpites.append({
                    "tipo": "Under 8.5 Finalizações (Fora)",
                    "confianca": conf_final,
                    "odd": None,
                    "time": "Fora",
                    "breakdown": breakdown,
                    "probabilidade_estatistica": prob_under
                })

    # ✅ RETORNO FINAL
    print(f"  ✅ FINALIZAÇÕES: {len(palpites)} palpites gerados")
    
    if palpites:
        suporte = (f"   - <b>Expectativa Finalizações:</b> {media_exp_total:.1f} total ({media_exp_no_gol:.1f} no gol)\n"
                   f"   - <b>Casa:</b> {finalizacoes_casa:.1f} finalizações/jogo ({finalizacoes_gol_casa:.1f} no gol)\n"
                   f"   - <b>Fora:</b> {finalizacoes_fora:.1f} finalizações/jogo ({finalizacoes_gol_fora:.1f} no gol)\n"
                   f"   - <i>⚠️ Odds raramente disponíveis - análise baseada em probabilidades estatísticas</i>\n")
        
        return {"mercado": "Finalizações", "palpites": palpites, "dados_suporte": suporte}

    print(f"  ❌ FINALIZAÇÕES: Nenhum palpite passou nos filtros de qualidade")
    return None
