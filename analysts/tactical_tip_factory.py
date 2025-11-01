"""
Tactical Tip Factory - PHOENIX V3.0

Sistema para gerar "Tactical Tips" (sugestões táticas sem odds disponíveis).
Quando a análise estatística identifica uma tendência forte mas as odds não estão 
disponíveis na API, o bot ainda gera a sugestão como insight tático.
"""

def create_tactical_tip(market_type: str, suggestion: str, confidence: float, 
                        reasoning: str, statistical_data: dict = None) -> dict:
    """
    Cria uma dica tática (sem odd disponível na API).
    
    Args:
        market_type: Tipo do mercado (e.g., "Corners", "Goals", "Cards", "BTTS")
        suggestion: Sugestão específica (e.g., "Over 10.5 Corners", "Under 2.5 Goals")
        confidence: Confiança estatística (0-10)
        reasoning: Justificativa da sugestão
        statistical_data: Dados estatísticos que suportam a tip (opcional)
    
    Returns:
        dict: Dica tática formatada com tipo='tactical'
    """
    return {
        'tipo': suggestion,
        'confianca': round(confidence, 1),
        'odd': None,  # Marca como tactical tip
        'is_tactical': True,  # Flag para identificação
        'market': market_type,
        'reasoning': reasoning,
        'statistical_data': statistical_data or {},
        'periodo': extract_period(suggestion),
        'time': extract_team(suggestion)
    }


def extract_period(suggestion: str) -> str:
    """Extrai o período da sugestão (FT/HT)"""
    if 'HT' in suggestion or '1T' in suggestion or 'Primeiro' in suggestion:
        return 'HT'
    return 'FT'


def extract_team(suggestion: str) -> str:
    """Extrai o time da sugestão (Casa/Fora/Total)"""
    if 'Casa' in suggestion:
        return 'Casa'
    elif 'Fora' in suggestion:
        return 'Fora'
    return 'Total'


def should_generate_tactical_tip(confidence: float, market_type: str) -> bool:
    """
    Determina se deve gerar uma dica tática baseado na confiança estatística.
    
    Thresholds por mercado:
    - Goals: >= 6.5/10 (mercado mais confiável)
    - Corners: >= 7.0/10 (mais variável)
    - BTTS: >= 6.5/10
    - Cards: >= 7.5/10 (muito variável)
    - Shots: >= 7.0/10
    - Match Result: >= 7.0/10
    """
    thresholds = {
        'Goals': 6.5,
        'Corners': 7.0,
        'BTTS': 6.5,
        'Cards': 7.5,
        'Shots': 7.0,
        'Match Result': 7.0,
        'Handicaps': 7.0,
    }
    
    threshold = thresholds.get(market_type, 7.0)
    return confidence >= threshold


def format_tactical_tip_message(tip: dict) -> str:
    """
    Formata uma dica tática para exibição.
    
    Args:
        tip: Dicionário da dica tática
        
    Returns:
        str: Mensagem formatada
    """
    emoji_map = {
        'Goals': '⚽',
        'Corners': '🚩',
        'Cards': '🟨',
        'BTTS': '🎯',
        'Shots': '🎯',
        'Match Result': '🏆',
        'Handicaps': '📊'
    }
    
    emoji = emoji_map.get(tip.get('market', ''), '💡')
    sugestao = tip['tipo']
    confianca = tip['confianca']
    
    return f"{emoji} <b>{sugestao}</b> • Confiança: {confianca}/10"
