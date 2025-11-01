# logger.py
"""
Sistema de logging padronizado para o bot - PHOENIX V3.0

Formato padrão:
[INFO] Mensagem informativa
[DEBUG] Mensagem de debug
[WARNING] Aviso importante
[ERROR] Erro crítico
[API] Chamadas de API
[CACHE] Operações de cache
[DB] Operações de banco de dados
"""

def info(message: str):
    """Log de informação geral"""
    print(f"[INFO] {message}")

def debug(message: str):
    """Log de debug (detalhes técnicos)"""
    print(f"[DEBUG] {message}")

def warning(message: str):
    """Log de aviso"""
    print(f"[WARNING] {message}")

def error(message: str):
    """Log de erro"""
    print(f"[ERROR] {message}")

def api(message: str):
    """Log de chamadas de API"""
    print(f"[API] {message}")

def cache(message: str):
    """Log de operações de cache"""
    print(f"[CACHE] {message}")

def db(message: str):
    """Log de operações de banco de dados"""
    print(f"[DB] {message}")

def analysis(message: str):
    """Log de análises (master_analyzer, analisadores)"""
    print(f"[ANALYSIS] {message}")

def success(message: str):
    """Log de sucesso"""
    print(f"✅ {message}")
