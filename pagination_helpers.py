import json
from typing import List, Dict, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from db_manager import DatabaseManager

def get_paginated_analyses(
    db_manager: DatabaseManager,
    user_id: int,
    analysis_type: str,
    page: int = 0,
    limit: int = 5
) -> Dict:
    """
    Recupera análises paginadas do banco de dados.
    
    Args:
        db_manager: Instância do DatabaseManager
        user_id: ID do usuário
        analysis_type: Tipo de análise
        page: Número da página (começa em 0)
        limit: Limite de resultados por página
        
    Returns:
        Dict com 'analyses', 'total', 'has_more', 'current_page'
    """
    offset = page * limit
    
    analyses = db_manager.get_daily_analyses(
        user_id=user_id,
        analysis_type=analysis_type,
        offset=offset,
        limit=limit
    )
    
    total = db_manager.count_daily_analyses(
        user_id=user_id,
        analysis_type=analysis_type
    )
    
    has_more = (offset + len(analyses)) < total
    
    return {
        'analyses': analyses,
        'total': total,
        'has_more': has_more,
        'current_page': page,
        'total_pages': (total + limit - 1) // limit if total > 0 else 0
    }

def create_pagination_keyboard(
    current_page: int,
    has_more: bool,
    analysis_type: str,
    total_pages: int
) -> InlineKeyboardMarkup:
    """
    Cria teclado inline com botões de paginação.
    
    Args:
        current_page: Página atual (0-indexed)
        has_more: Se há mais resultados
        analysis_type: Tipo de análise
        total_pages: Total de páginas
        
    Returns:
        InlineKeyboardMarkup com botões de navegação
    """
    keyboard = []
    nav_buttons = []
    
    if current_page > 0:
        nav_buttons.append(
            InlineKeyboardButton(
                "◀️ Anterior",
                callback_data=f"page_{analysis_type}_{current_page - 1}"
            )
        )
    
    nav_buttons.append(
        InlineKeyboardButton(
            f"📄 {current_page + 1}/{total_pages}",
            callback_data="noop"
        )
    )
    
    if has_more:
        nav_buttons.append(
            InlineKeyboardButton(
                "Próxima ▶️",
                callback_data=f"page_{analysis_type}_{current_page + 1}"
            )
        )
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([
        InlineKeyboardButton("🔙 Voltar ao Menu", callback_data="voltar_menu")
    ])
    
    return InlineKeyboardMarkup(keyboard)

def parse_dossier_from_analysis(analysis_row: Dict) -> Dict:
    """
    Extrai e parseia o dossier JSON de uma linha de análise.
    
    Args:
        analysis_row: Linha retornada do banco de dados
        
    Returns:
        Dossier parseado como dict
    """
    dossier_json = analysis_row.get('dossier_json', '{}')
    
    if isinstance(dossier_json, str):
        return json.loads(dossier_json)
    
    return dossier_json
