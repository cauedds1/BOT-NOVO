# cache_manager.py
import json
import os
import threading
import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# 🇧🇷 HORÁRIO DE BRASÍLIA: Todas as operações de datetime usam timezone de Brasília
BRASILIA_TZ = ZoneInfo("America/Sao_Paulo")

def agora_brasilia():
    """Retorna datetime atual no horário de Brasília"""
    return datetime.now(BRASILIA_TZ)

_cache = {}
_cache_lock = threading.RLock()  # RLock (reentrant) para evitar deadlocks
CACHE_FILE = "cache.json"
_is_dirty = False  # Flag para indicar se o cache precisa ser salvo

# Configurações inteligentes de expiração por tipo de dado
# ⚡ CACHE CALIBRADO: TTLs otimizados por sensibilidade temporal
CACHE_EXPIRATION = {
    'jogos_': 1440,              # 24 HORAS - jogos do dia
    'odds_': 1440,               # 24 HORAS - odds (dados sensíveis ao tempo)
    'stats_': 1440,              # 24 HORAS - estatísticas de times (dados recentes)
    'classificacao_': 1440,      # 24 HORAS - classificação (atualização moderada)
    'analise_jogo_': 1440,       # 24 HORAS - análise completa de jogo
    'fixture_stats_': 1440,      # 24 HORAS - estatísticas de fixture (dados recentes)
    'ultimos_jogos_': 1440,      # 24 HORAS - últimos jogos do time (dados recentes)
    'ligas_': 1440,              # 24 HORAS - lista de ligas disponíveis (dados estáveis)
    'h2h_': 10080,               # 7 DIAS - confrontos diretos históricos (dados históricos)
    'current_season_': 1440,     # 24 HORAS - temporada atual da liga
    'default': 1440              # 24 HORAS - padrão
}

def get_expiration_for_key(key):
    """Determina tempo de expiração baseado no prefixo da chave"""
    for prefix, minutes in CACHE_EXPIRATION.items():
        if key.startswith(prefix):
            return minutes
    return CACHE_EXPIRATION['default']

def set(key, value, expiration_minutes=None):
    """
    Adiciona um valor ao cache com tempo de expiração inteligente.
    Se não especificar tempo, usa valores otimizados por tipo.
    Marca o cache como dirty para salvamento periódico em background.
    
    PHOENIX V3.0 - CACHE GROWTH FIX: Agora com logging detalhado
    """
    global _cache, _is_dirty

    if expiration_minutes is None:
        expiration_minutes = get_expiration_for_key(key)

    now = agora_brasilia()
    expiration_time = now + timedelta(minutes=expiration_minutes)

    with _cache_lock:
        is_new_key = key not in _cache
        _cache[key] = {
            "value": value, 
            "expires_at": expiration_time.isoformat(),
            "created_at": now.isoformat()
        }
        _is_dirty = True  # Marcar para salvamento posterior
        
        if is_new_key:
            print(f"💾 CACHE_SET: NEW key '{key[:50]}...' added (Total: {len(_cache)} items)")

def get(key):
    """
    Busca um valor no cache, verificando se não expirou.
    """
    global _cache, _is_dirty
    with _cache_lock:
        data = _cache.get(key)

        if not data:
            return None

        if data.get("expires_at"):
            try:
                expiration_time = datetime.fromisoformat(data["expires_at"])
                if agora_brasilia() > expiration_time:
                    del _cache[key]
                    _is_dirty = True  # Marcar para salvamento posterior
                    return None
            except (TypeError, ValueError):
                 pass

        return data.get("value")

def clear():
    """Limpa todo o cache"""
    global _cache, _is_dirty
    with _cache_lock:
        _cache = {}
        _is_dirty = True  # Marcar para salvamento periódico
    print("✅ CACHE CLEARED: Toda memória foi limpa! (Salvamento agendado)")

def get_stats():
    """Retorna estatísticas do cache sem alterar o dict durante iteração"""
    global _cache
    total = len(_cache)
    # Iterar sobre cópia para evitar RuntimeError
    cache_items = list(_cache.items())
    validos = 0

    for key, data in cache_items:
        if data.get("expires_at"):
            try:
                expiration_time = datetime.fromisoformat(data["expires_at"])
                if agora_brasilia() <= expiration_time:
                    validos += 1
            except (TypeError, ValueError):
                validos += 1  # Contar como válido se não tem expiração
        else:
            validos += 1

    expirados = total - validos
    return {
        'total': total,
        'validos': validos,
        'expirados': expirados
    }

def save_cache_to_disk():
    """Salva o conteúdo do cache em um arquivo JSON"""
    global _cache, _is_dirty
    try:
        with _cache_lock:
            cache_copy = _cache.copy()  # Criar cópia para evitar race condition

        with open(CACHE_FILE, 'w') as f:
            if cache_copy:
                json.dump(cache_copy, f, indent=4)
            else:
                f.write('{}')
        
        # Resetar flag APENAS após escrita bem-sucedida
        with _cache_lock:
            _is_dirty = False
            
    except Exception as e:
        print(f"❌ ERRO ao salvar o cache em disco: {e}")
        # Flag permanece True para retry na próxima tentativa

async def periodic_cache_saver(interval_minutes=5):
    """
    Tarefa em background que salva o cache periodicamente se houver mudanças.
    Previne bloqueio do event loop ao desacoplar atualizações de salvamento.
    Continua tentando mesmo após falhas de I/O para garantir persistência.
    
    PHOENIX V3.0 - CACHE GROWTH FIX: Agora com stats detalhadas
    
    Args:
        interval_minutes: Intervalo entre verificações (padrão: 5 minutos)
    """
    global _is_dirty
    
    print(f"🔄 Cache saver iniciado: salvamento a cada {interval_minutes} minutos")
    
    while True:
        try:
            await asyncio.sleep(interval_minutes * 60)
            
            if _is_dirty:
                stats = get_stats()
                print(f"💾 Salvando cache em background... ({stats['validos']} válidos / {stats['total']} total)")
                # Executar I/O em thread separada para não bloquear event loop
                await asyncio.to_thread(save_cache_to_disk)
                print(f"✅ Cache salvo com sucesso! Tamanho: {stats['total']} itens")
        except asyncio.CancelledError:
            # Permitir shutdown limpo re-raising CancelledError
            print("🛑 Cache saver cancelado (shutdown em progresso)")
            raise
        except Exception as e:
            print(f"❌ Erro no periodic cache saver: {e}")
            # Continuar loop para tentar novamente na próxima iteração
            # _is_dirty permanece True para retry automático
            continue

def cleanup_expired():
    """
    Remove itens expirados do cache para liberar memória.
    Executado automaticamente ao carregar o cache.
    """
    global _cache, _is_dirty
    removidos = 0

    with _cache_lock:
        keys_to_remove = []
        for key, data in _cache.items():
            if data.get("expires_at"):
                try:
                    expiration_time = datetime.fromisoformat(data["expires_at"])
                    if agora_brasilia() > expiration_time:
                        keys_to_remove.append(key)
                except (TypeError, ValueError):
                    pass

        for key in keys_to_remove:
            del _cache[key]
            removidos += 1
        
        if removidos > 0:
            _is_dirty = True  # Marcar para salvamento periódico

    if removidos > 0:
        print(f"🧹 CACHE CLEANUP: {removidos} itens expirados removidos (Salvamento agendado)")

    return removidos

def load_cache_from_disk():
    """Carrega o cache do arquivo JSON ao iniciar o bot"""
    global _cache
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r') as f:
                content = f.read()
                if content:
                    _cache = json.loads(content)
                    # Limpar expirados ao carregar
                    cleanup_expired()
                    stats = get_stats()
                    print(f"✅ CACHE LOADED: {stats['validos']} itens válidos carregados (Total: {stats['total']})")
                else:
                    _cache = {}
                    print("ℹ️  CACHE vazio. Iniciando com memória limpa.")
        else:
            print("ℹ️  Cache não encontrado. Iniciando com memória limpa.")
    except (json.JSONDecodeError, Exception) as e:
        print(f"❌ ERRO ao carregar cache: {e}")
        _cache = {}
