# api_client.py
import httpx
import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import cache_manager

import os
from dotenv import load_dotenv
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

load_dotenv()
logger = logging.getLogger(__name__)

API_URL = "https://v3.football.api-sports.io/"
HEADERS = {
    "x-rapidapi-host": "v3.football.api-sports.io",
    "x-rapidapi-key": os.getenv("API_FOOTBALL_KEY")
}

# Cliente HTTP será gerenciado pelo Application context
# Não usar variável global para evitar conflitos de event loop
_http_client_instance = None

def set_http_client(client):
    """Define o cliente HTTP gerenciado pelo Application."""
    global _http_client_instance
    _http_client_instance = client

def get_http_client():
    """
    Retorna o cliente HTTP gerenciado pelo Application.
    Se não houver cliente configurado, cria um temporário.
    """
    if _http_client_instance is not None:
        return _http_client_instance
    
    # Fallback: criar cliente temporário (não ideal, mas previne crash)
    logger.warning("⚠️ HTTP client não configurado via Application, criando temporário")
    return httpx.AsyncClient(
        timeout=10.0,
        headers=HEADERS,
        limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
    )

def create_http_client():
    """Cria um novo cliente HTTP com configurações apropriadas."""
    return httpx.AsyncClient(
        timeout=10.0,
        headers=HEADERS,
        limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        http2=False  # Desabilitar HTTP/2 para maior compatibilidade
    )

async def close_http_client(client=None):
    """Fecha o cliente HTTP especificado ou o global."""
    global _http_client_instance
    
    target_client = client if client is not None else _http_client_instance
    
    if target_client is not None:
        try:
            await target_client.aclose()
            logger.info("✅ Cliente HTTP fechado com sucesso")
        except RuntimeError as e:
            if "Event loop is closed" in str(e):
                logger.warning("⚠️ Event loop já fechado, ignorando erro ao fechar HTTP client")
            else:
                raise
        except Exception as e:
            logger.error(f"❌ Erro ao fechar HTTP client: {e}")
    
    if client is None:
        _http_client_instance = None

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException, httpx.NetworkError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True
)
async def api_request_with_retry(method: str, url: str, **kwargs):
    """
    Wrapper para requisições HTTP com retry automático e exponential backoff.
    
    Estratégia de Retry:
    - Tentativas: até 5
    - Backoff: 1s, 2s, 4s, 8s (exponencial)
    - Retry em: 502 Bad Gateway, 503 Service Unavailable, Timeout, Network Errors
    
    Args:
        method: Método HTTP ('GET', 'POST', etc)
        url: URL completa da requisição
        **kwargs: Parâmetros adicionais (params, headers, etc)
    
    Returns:
        httpx.Response: Resposta da requisição
        
    Raises:
        httpx.HTTPStatusError: Após todas as tentativas falharem
    """
    client = get_http_client()
    response = await client.request(method, url, **kwargs)
    
    if response.status_code in (502, 503):
        response.raise_for_status()
    
    return response

# ============================================
# LIGAS DE INTERESSE - COBERTURA GLOBAL
# ============================================
LIGAS_DE_INTERESSE = [
    # COMPETIÇÕES DE SELEÇÕES - FIFA/UEFA/CONMEBOL/CONCACAF
    1,  # Copa do Mundo FIFA
    4,  # Eurocopa (UEFA Euro)
    9,  # Copa América
    15,  # FIFA Club World Cup (Mundial de Clubes)
    
    # EUROPA - UEFA
    2, 3, 848,  # Champions League, Europa League, Conference League
    5,  # UEFA Nations League
    
    # Inglaterra
    39, 40, 41, 42,  # Premier League, Championship, League One, League Two
    46,  # National League (5ª Divisão)
    45, 48,  # FA Cup, EFL Cup (League Cup)
    
    # Espanha
    140, 141,  # La Liga, La Liga 2
    667,  # Primera RFEF (3ª Divisão)
    143,  # Copa del Rey
    
    # Alemanha
    78, 79,  # Bundesliga, 2. Bundesliga
    80,  # 3. Liga (3ª Divisão)
    81,  # DFB Pokal (Copa da Alemanha)
    
    # Itália
    135, 136,  # Serie A, Serie B
    138,  # Serie C (3ª Divisão)
    137,  # Coppa Italia
    
    # França
    61, 62,  # Ligue 1, Ligue 2
    63,  # National (3ª Divisão)
    66,  # Coupe de France
    
    # Portugal
    94,  # Primeira Liga
    95,  # Segunda Liga (2ª Divisão)
    96, 242,  # Taça de Portugal, Taça da Liga
    
    # Holanda
    88,  # Eredivisie
    89,  # Eerste Divisie (2ª Divisão)
    35,  # KNVB Beker (Copa da Holanda)
    
    # Bélgica
    144,  # Jupiler Pro League
    127,  # Belgian Cup (Copa da Bélgica)
    
    # Turquia
    203,  # Süper Lig
    204,  # Turkish Cup
    
    # Grécia
    197,  # Super League Greece
    
    # Rússia
    235,  # Russian Premier League
    
    # Áustria
    218,  # Austrian Bundesliga
    
    # Suíça
    207,  # Swiss Super League
    
    # Escócia
    179,  # Scottish Premiership
    181,  # Championship (2ª Divisão)
    180,  # Scottish Cup
    
    # Ucrânia
    333,  # Ukrainian Premier League
    
    # Dinamarca
    119,  # Superligaen
    
    # Noruega
    103,  # Eliteserien
    
    # Suécia
    113,  # Allsvenskan
    
    # Polônia
    106,  # Ekstraklasa
    
    # República Tcheca
    345,  # Czech First League
    
    # Croácia
    210,  # HNL
    
    # Romênia
    283,  # Liga I
    
    # Sérvia
    286,  # Serbian SuperLiga
    
    # Irlanda
    357,  # Premier Division
    
    # Finlândia
    244,  # Veikkausliiga
    
    # AMÉRICA DO SUL - CONMEBOL
    13, 11,  # Copa Libertadores, Copa Sudamericana
    
    # Brasil
    71, 72,  # Brasileirão Série A, Série B
    74,  # Brasileirão Série C (3ª Divisão)
    75,  # Brasileirão Série D (4ª Divisão)
    73,  # Copa do Brasil
    
    # Argentina
    128,  # Liga Profesional
    129,  # Primera Nacional (2ª Divisão)
    213,  # Copa Argentina
    
    # Colômbia
    239,  # Categoría Primera A
    
    # Chile
    265,  # Primera División
    
    # Equador
    240,  # Liga Pro
    
    # Paraguai
    250,  # Primera División
    
    # Uruguai
    274,  # Primera División
    
    # Peru
    281,  # Liga 1
    
    # Bolívia
    353,  # División Profesional
    
    # Venezuela
    299,  # Liga FUTVE
    
    # AMÉRICA DO NORTE E CENTRAL - CONCACAF
    18,  # CONCACAF Champions League
    253,  # MLS (EUA/Canadá)
    256,  # US Open Cup
    262,  # Liga MX (México)
    263,  # Liga de Expansión MX (2ª Divisão México)
    159,  # Primera División (Costa Rica)
    
    # ÁSIA - AFC
    16,  # AFC Champions League
    83,  # J1 League (Japão)
    84,  # J2 League (2ª Divisão Japão)
    292,  # K League 1 (Coreia do Sul)
    307,  # Saudi Pro League (Arábia Saudita)
    188,  # A-League (Austrália)
    17,  # Chinese Super League (China)
    301,  # UAE Pro League (Emirados Árabes)
    305,  # Qatar Stars League (Catar)
    
    # ÁFRICA - CAF
    12,  # CAF Champions League
    233,  # Egyptian Premier League (Egito)
    288,  # PSL (África do Sul)
    200,  # Botola Pro (Marrocos)
    202,  # Ligue Professionnelle 1 (Tunísia)
]

# Mapeamento: País -> Ordem (para ordenação)
ORDEM_PAISES = {
    'Brasil': 1,
    'Argentina': 2,
    'Uruguai': 3,
    'Colômbia': 4,
    'Chile': 5,
    'Equador': 6,
    'Paraguai': 7,
    'Peru': 8,
    'Bolívia': 9,
    'Venezuela': 10,
    'Internacional': 11,
    
    'Inglaterra': 20,
    'Espanha': 21,
    'Alemanha': 22,
    'Itália': 23,
    'França': 24,
    'Portugal': 25,
    'Holanda': 26,
    'Bélgica': 27,
    'Turquia': 28,
    'Grécia': 29,
    'Rússia': 30,
    'Áustria': 31,
    'Suíça': 32,
    'Escócia': 33,
    'Ucrânia': 34,
    'Dinamarca': 35,
    'Noruega': 36,
    'Suécia': 37,
    'Polônia': 38,
    'República Tcheca': 39,
    'Croácia': 40,
    'Romênia': 41,
    'Sérvia': 42,
    'Irlanda': 43,
    'Finlândia': 44,
    
    'EUA/Canadá': 50,
    'México': 51,
    'Costa Rica': 52,
    
    'Japão': 60,
    'Coreia do Sul': 61,
    'Arábia Saudita': 62,
    'Austrália': 63,
    'China': 64,
    'Emirados Árabes': 65,
    'Catar': 66,
    
    'Egito': 70,
    'África do Sul': 71,
    'Marrocos': 72,
    'Tunísia': 73,
}

# Nomes das ligas em português com bandeiras
# Formato: ID: ("bandeira Nome da Liga", "País para ordenação")
NOMES_LIGAS_PT = {
    # ========================================
    # COMPETIÇÕES DE SELEÇÕES
    # ========================================
    1: ("🏆 Copa do Mundo FIFA", "Internacional"),
    4: ("🏆 Eurocopa (UEFA Euro)", "Internacional"),
    9: ("🏆 Copa América", "Internacional"),
    
    # ========================================
    # EUROPA - UEFA
    # ========================================
    2: ("🏆 UEFA Champions League", "Internacional"),
    3: ("🏆 UEFA Europa League", "Internacional"),
    848: ("🏆 UEFA Conference League", "Internacional"),
    5: ("🏆 UEFA Nations League", "Internacional"),
    
    # INGLATERRA
    39: ("🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League", "Inglaterra"),
    40: ("🏴󠁧󠁢󠁥󠁮󠁧󠁿 Championship", "Inglaterra"),
    41: ("🏴󠁧󠁢󠁥󠁮󠁧󠁿 League One", "Inglaterra"),
    42: ("🏴󠁧󠁢󠁥󠁮󠁧󠁿 League Two", "Inglaterra"),
    46: ("🏴󠁧󠁢󠁥󠁮󠁧󠁿 National League", "Inglaterra"),
    45: ("🏴󠁧󠁢󠁥󠁮󠁧󠁿 FA Cup", "Inglaterra"),
    48: ("🏴󠁧󠁢󠁥󠁮󠁧󠁿 EFL Cup", "Inglaterra"),
    
    # ESPANHA
    140: ("🇪🇸 La Liga", "Espanha"),
    141: ("🇪🇸 La Liga 2", "Espanha"),
    667: ("🇪🇸 Primera RFEF", "Espanha"),
    143: ("🇪🇸 Copa del Rey", "Espanha"),
    
    # ALEMANHA
    78: ("🇩🇪 Bundesliga", "Alemanha"),
    79: ("🇩🇪 2. Bundesliga", "Alemanha"),
    80: ("🇩🇪 3. Liga", "Alemanha"),
    81: ("🇩🇪 DFB Pokal", "Alemanha"),
    
    # ITÁLIA
    135: ("🇮🇹 Serie A", "Itália"),
    136: ("🇮🇹 Serie B", "Itália"),
    138: ("🇮🇹 Serie C", "Itália"),
    137: ("🇮🇹 Coppa Italia", "Itália"),
    
    # FRANÇA
    61: ("🇫🇷 Ligue 1", "França"),
    62: ("🇫🇷 Ligue 2", "França"),
    63: ("🇫🇷 National", "França"),
    66: ("🇫🇷 Coupe de France", "França"),
    
    # PORTUGAL  
    94: ("🇵🇹 Primeira Liga", "Portugal"),
    95: ("🇵🇹 Segunda Liga", "Portugal"),
    96: ("🇵🇹 Taça de Portugal", "Portugal"),
    242: ("🇵🇹 Taça da Liga", "Portugal"),
    
    # HOLANDA
    88: ("🇳🇱 Eredivisie", "Holanda"),
    89: ("🇳🇱 Eerste Divisie", "Holanda"),
    35: ("🇳🇱 KNVB Beker", "Holanda"),
    
    # BÉLGICA
    144: ("🇧🇪 Jupiler Pro League", "Bélgica"),
    127: ("🇧🇪 Copa da Bélgica", "Bélgica"),
    
    # TURQUIA
    203: ("🇹🇷 Süper Lig", "Turquia"),
    204: ("🇹🇷 Copa da Turquia", "Turquia"),
    
    # GRÉCIA
    197: ("🇬🇷 Super League Greece", "Grécia"),
    
    # RÚSSIA
    235: ("🇷🇺 Russian Premier League", "Rússia"),
    
    # ÁUSTRIA
    218: ("🇦🇹 Austrian Bundesliga", "Áustria"),
    
    # SUÍÇA
    207: ("🇨🇭 Swiss Super League", "Suíça"),
    
    # ESCÓCIA
    179: ("🏴󠁧󠁢󠁳󠁣󠁴󠁿 Scottish Premiership", "Escócia"),
    181: ("🏴󠁧󠁢󠁳󠁣󠁴󠁿 Championship", "Escócia"),
    180: ("🏴󠁧󠁢󠁳󠁣󠁴󠁿 Scottish Cup", "Escócia"),
    
    # UCRÂNIA
    333: ("🇺🇦 Ukrainian Premier League", "Ucrânia"),
    
    # DINAMARCA  
    119: ("🇩🇰 Superligaen", "Dinamarca"),
    
    # NORUEGA
    103: ("🇳🇴 Eliteserien", "Noruega"),
    
    # SUÉCIA
    113: ("🇸🇪 Allsvenskan", "Suécia"),
    
    # POLÔNIA
    106: ("🇵🇱 Ekstraklasa", "Polônia"),
    
    # REPÚBLICA TCHECA
    345: ("🇨🇿 Czech First League", "República Tcheca"),
    
    # CROÁCIA
    210: ("🇭🇷 HNL", "Croácia"),
    
    # ROMÊNIA
    283: ("🇷🇴 Liga I", "Romênia"),
    
    # SÉRVIA
    286: ("🇷🇸 Serbian SuperLiga", "Sérvia"),
    
    # IRLANDA
    357: ("🇮🇪 Premier Division", "Irlanda"),
    
    # FINLÂNDIA
    244: ("🇫🇮 Veikkausliiga", "Finlândia"),
    
    # ========================================
    # AMÉRICA DO SUL - CONMEBOL
    # ========================================
    13: ("🏆 Copa Libertadores", "Internacional"),
    11: ("🏆 Copa Sudamericana", "Internacional"),
    
    # BRASIL
    71: ("🇧🇷 Brasileirão Série A", "Brasil"),
    72: ("🇧🇷 Brasileirão Série B", "Brasil"),
    74: ("🇧🇷 Brasileirão Série C", "Brasil"),
    73: ("🇧🇷 Copa do Brasil", "Brasil"),
    
    # ARGENTINA
    128: ("🇦🇷 Liga Profesional", "Argentina"),
    129: ("🇦🇷 Primera Nacional", "Argentina"),
    213: ("🇦🇷 Copa Argentina", "Argentina"),
    
    # COLÔMBIA
    239: ("🇨🇴 Categoría Primera A", "Colômbia"),
    
    # CHILE
    265: ("🇨🇱 Primera División", "Chile"),
    
    # EQUADOR
    240: ("🇪🇨 Liga Pro", "Equador"),
    
    # PARAGUAI
    250: ("🇵🇾 Primera División", "Paraguai"),
    
    # URUGUAI
    274: ("🇺🇾 Primera División", "Uruguai"),
    
    # PERU
    281: ("🇵🇪 Liga 1", "Peru"),
    
    # BOLÍVIA
    353: ("🇧🇴 División Profesional", "Bolívia"),
    
    # VENEZUELA
    299: ("🇻🇪 Liga FUTVE", "Venezuela"),
    
    # ========================================
    # AMÉRICA DO NORTE E CENTRAL - CONCACAF
    # ========================================
    18: ("🏆 CONCACAF Champions League", "Internacional"),
    253: ("🇺🇸 MLS", "EUA/Canadá"),
    256: ("🇺🇸 US Open Cup", "EUA/Canadá"),
    262: ("🇲🇽 Liga MX", "México"),
    263: ("🇲🇽 Liga de Expansión MX", "México"),
    159: ("🇨🇷 Primera División", "Costa Rica"),
    
    # ========================================
    # ÁSIA - AFC
    # ========================================
    16: ("🏆 AFC Champions League", "Internacional"),
    83: ("🇯🇵 J1 League", "Japão"),
    84: ("🇯🇵 J2 League", "Japão"),
    292: ("🇰🇷 K League 1", "Coreia do Sul"),
    307: ("🇸🇦 Saudi Pro League", "Arábia Saudita"),
    188: ("🇦🇺 A-League", "Austrália"),
    17: ("🇨🇳 Chinese Super League", "China"),
    301: ("🇦🇪 UAE Pro League", "Emirados Árabes"),
    305: ("🇶🇦 Qatar Stars League", "Catar"),
    
    # ========================================
    # ÁFRICA - CAF
    # ========================================
    12: ("🏆 CAF Champions League", "Internacional"),
    233: ("🇪🇬 Egyptian Premier League", "Egito"),
    288: ("🇿🇦 PSL", "África do Sul"),
    200: ("🇲🇦 Botola Pro", "Marrocos"),
    202: ("🇹🇳 Ligue Professionnelle 1", "Tunísia"),
}

async def get_current_season(league_id):
    """
    Determina dinamicamente a temporada atual de uma liga usando a API.
    
    Args:
        league_id: ID da liga
        
    Returns:
        str: Ano da temporada atual (ex: "2025")
    """
    cache_key = f"current_season_{league_id}"
    
    if cached_season := cache_manager.get(cache_key):
        return str(cached_season)
    
    try:
        response = await api_request_with_retry(
            "GET",
            f"{API_URL}leagues",
            params={"id": league_id, "current": "true"}
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('response') and len(data['response']) > 0:
                league_data = data['response'][0]
                if 'seasons' in league_data and len(league_data['seasons']) > 0:
                    current_season = league_data['seasons'][0]
                    season_year = current_season.get('year')
                    
                    if season_year:
                        cache_manager.set(cache_key, season_year)
                        return str(season_year)
    
    except Exception as e:
        print(f"⚠️ Erro ao buscar temporada dinâmica para liga {league_id}: {e}")
    
    brasilia_tz = ZoneInfo("America/Sao_Paulo")
    agora = datetime.now(brasilia_tz)
    ano_atual = agora.year
    
    fallback_season = str(ano_atual - 1)
    print(f"ℹ️ Usando fallback de temporada para liga {league_id}: {fallback_season}")
    cache_manager.set(cache_key, fallback_season)
    
    return fallback_season

async def buscar_jogos_do_dia():
    # Obter hora atual no horário de Brasília
    brasilia_tz = ZoneInfo("America/Sao_Paulo")
    agora_brasilia = datetime.now(brasilia_tz)
    
    # Determinar temporada atual automaticamente
    mes_atual = agora_brasilia.month
    ano_atual = agora_brasilia.year
    season = str(ano_atual) if mes_atual >= 7 else str(ano_atual - 1)
    
    # 🎯 LÓGICA DE BUSCA POR HORÁRIO
    # Antes das 20:30 BRT: buscar apenas HOJE
    # Após 20:30 BRT: buscar HOJE + AMANHÃ (jogos noturnos aparecem no dia seguinte na API UTC)
    hoje_brt = agora_brasilia.strftime('%Y-%m-%d')
    amanha_brt = (agora_brasilia + timedelta(days=1)).strftime('%Y-%m-%d')
    
    # Verificar se deve buscar amanhã também
    hora_atual = agora_brasilia.hour
    minuto_atual = agora_brasilia.minute
    horario_decimal = hora_atual + (minuto_atual / 60.0)
    
    if horario_decimal >= 20.5:  # 20:30 ou depois
        datas_buscar = [hoje_brt, amanha_brt]
        print(f"🌙 Após 20:30 BRT - Buscando HOJE ({hoje_brt}) + AMANHÃ ({amanha_brt})")
        cache_key = f"jogos_{hoje_brt}_{amanha_brt}_s{season}"
    else:
        datas_buscar = [hoje_brt]
        print(f"☀️ Antes das 20:30 BRT - Buscando apenas HOJE ({hoje_brt})")
        cache_key = f"jogos_{hoje_brt}_s{season}"
    
    print(f"   (Horário Brasília: {agora_brasilia.strftime('%H:%M')}, Season: {season})")
    
    if cached_data := cache_manager.get(cache_key):
        print(f"✅ CACHE HIT: {len(cached_data)} jogos encontrados no cache")
        return cached_data

    print(f"⚡ CACHE MISS: Buscando jogos da API ({len(LIGAS_DE_INTERESSE)} ligas)")
    todos_os_jogos = []

    for data_busca in datas_buscar:
        print(f"\n📅 Buscando data: {data_busca} (Season: {season})")
        
        for idx, liga_id in enumerate(LIGAS_DE_INTERESSE, 1):
            params = {"league": str(liga_id), "season": season, "date": data_busca, "status": "NS"}
            
            # 🔍 DEBUG: Log dos parâmetros enviados à API
            if idx == 1:  # Log apenas na primeira liga para não poluir
                print(f"   [DEBUG] Parâmetros API: {params}")
                print(f"   [DEBUG] URL: {API_URL}fixtures")
            
            try:
                response = await api_request_with_retry("GET", API_URL + "fixtures", params=params)
                response.raise_for_status()

                if data := response.json():
                    if data['results'] > 0:
                        jogos_novos = len(data['response'])
                        todos_os_jogos.extend(data['response'])
                        print(f"  [{idx}/{len(LIGAS_DE_INTERESSE)}] Liga {liga_id}: +{jogos_novos} jogos (Total: {len(todos_os_jogos)})")
            except httpx.TimeoutException:
                print(f"  [{idx}/{len(LIGAS_DE_INTERESSE)}] Liga {liga_id}: TIMEOUT")
                continue
            except httpx.HTTPError as e:
                print(f"  [{idx}/{len(LIGAS_DE_INTERESSE)}] Liga {liga_id}: ERRO - {str(e)[:50]}")
                continue

    # 🔄 FALLBACK: Se não encontrou jogos hoje E não estamos após 20:30, tentar AMANHÃ
    if len(todos_os_jogos) == 0 and horario_decimal < 20.5:
        print(f"\n🔄 FALLBACK: Nenhum jogo encontrado para HOJE, buscando AMANHÃ ({amanha_brt})...")
        
        for idx, liga_id in enumerate(LIGAS_DE_INTERESSE, 1):
            params = {"league": str(liga_id), "season": season, "date": amanha_brt, "status": "NS"}
            try:
                response = await api_request_with_retry("GET", API_URL + "fixtures", params=params)
                response.raise_for_status()

                if data := response.json():
                    if data['results'] > 0:
                        jogos_novos = len(data['response'])
                        todos_os_jogos.extend(data['response'])
                        print(f"  [{idx}/{len(LIGAS_DE_INTERESSE)}] Liga {liga_id}: +{jogos_novos} jogos (Total: {len(todos_os_jogos)})")
            except (httpx.TimeoutException, httpx.HTTPError) as e:
                logger.warning(f"  [{idx}/{len(LIGAS_DE_INTERESSE)}] Liga {liga_id} (AMANHÃ): Erro - {str(e)[:80]}")
                continue
        
        if len(todos_os_jogos) > 0:
            print(f"✅ FALLBACK bem-sucedido: {len(todos_os_jogos)} jogos encontrados para AMANHÃ")

    print(f"\n✅ Busca completa: {len(todos_os_jogos)} jogos encontrados")
    cache_manager.set(cache_key, todos_os_jogos)  # Usa padrão de 240 min (4h)
    return todos_os_jogos

async def buscar_classificacao_liga(id_liga: int):
    cache_key = f"classificacao_{id_liga}"
    if cached_data := cache_manager.get(cache_key): return cached_data
    
    season = await get_current_season(id_liga)
    
    params = {"league": str(id_liga), "season": season}
    try:
        await asyncio.sleep(1.6)
        print(f"  🔍 Buscando classificação: Liga {id_liga}, Season {season}")
        response = await api_request_with_retry("GET", API_URL + "standings", params=params)
        response.raise_for_status()
        if data := response.json().get('response'):
            if data and data[0]['league']['standings']:
                classificacao = data[0]['league']['standings'][0]
                cache_manager.set(cache_key, classificacao)
                print(f"  ✅ Classificação retornada: {len(classificacao)} times")
                return classificacao
        print(f"  ⚠️ Nenhuma classificação encontrada para Liga {id_liga}, Season {season}")
    except Exception as e:
        print(f"  ❌ Erro ao buscar classificação: {str(e)[:100]}")
    return None

async def buscar_estatisticas_gerais_time(time_id: int, id_liga: int):
    cache_key = f"stats_{time_id}_liga_{id_liga}"
    if cached_data := cache_manager.get(cache_key): return cached_data

    season = await get_current_season(id_liga)

    params = {"team": str(time_id), "league": str(id_liga), "season": season}
    try:
        await asyncio.sleep(1.6)
        response = await api_request_with_retry("GET", API_URL + "teams/statistics", params=params)
        response.raise_for_status()

        response_data = response.json()
        data = response_data.get('response')

        # 🔍 INVESTIGAÇÃO COMPLETA: Mostrar TODA a resposta da API
        print(f"\n  🔬 INVESTIGAÇÃO /teams/statistics:")
        print(f"     → Time: {time_id}, Liga: {id_liga}, Season: {season}")
        print(f"     → URL: {API_URL}teams/statistics")
        print(f"     → Status: {response.status_code}")
        
        # DEBUG: Verificar se a API retornou dados
        if not data:
            print(f"     ❌ Campo 'response' está vazio ou None")
            print(f"     🔍 JSON completo retornado: {response_data}")
            return None

        print(f"     ✅ Campo 'response' presente")
        
        # Mostrar estrutura completa de 'corners'
        corners_data = data.get('corners', {})
        print(f"\n     📦 ESTRUTURA COMPLETA DE CANTOS:")
        print(f"        data.get('corners'): {corners_data}")
        print(f"        Chaves disponíveis em corners: {list(corners_data.keys()) if corners_data else 'VAZIO'}")
        
        if corners_data:
            for chave, valor in corners_data.items():
                print(f"        → corners['{chave}']: {valor}")

        # Extrair dados de gols
        goals_data = data.get('goals', {})
        goals_for = goals_data.get('for', {}).get('average', {})
        goals_against = goals_data.get('against', {}).get('average', {})

        gols_casa_marcados = float(goals_for.get('home', 0) or 0)
        gols_fora_marcados = float(goals_for.get('away', 0) or 0)
        gols_casa_sofridos = float(goals_against.get('home', 0) or 0)
        gols_fora_sofridos = float(goals_against.get('away', 0) or 0)

        # Extrair dados de cantos
        corners_avg = corners_data.get('average', {})
        cantos_avg_casa = float(corners_avg.get('home', 0) or 0)
        cantos_avg_fora = float(corners_avg.get('away', 0) or 0)
        
        # DEBUG: Mostrar valores finais extraídos
        print(f"\n     📊 VALORES EXTRAÍDOS:")
        print(f"        Gols Casa: {gols_casa_marcados:.1f} | Fora: {gols_fora_marcados:.1f}")
        print(f"        Cantos Casa: {cantos_avg_casa:.1f} | Fora: {cantos_avg_fora:.1f}")

        # 🎯 FALLBACK: Se API retornar 0.0, calcular dos últimos jogos (cantos, finalizações, etc)
        # Inicializar TODAS as variáveis que podem não ser calculadas
        cantos_sofridos_casa = 0.0
        cantos_sofridos_fora = 0.0
        finalizacoes_casa = 0.0
        finalizacoes_fora = 0.0
        finalizacoes_no_gol_casa = 0.0
        finalizacoes_no_gol_fora = 0.0
        cartoes_amarelos_casa = 0.0
        cartoes_vermelhos_casa = 0.0
        cartoes_amarelos_fora = 0.0
        cartoes_vermelhos_fora = 0.0
        vitorias_casa = 0
        vitorias_fora = 0

        if cantos_avg_casa == 0.0 and cantos_avg_fora == 0.0:
            print(f"  🔄 FALLBACK: API retornou 0.0, buscando estatísticas dos últimos jogos...")
            ultimos_jogos = await buscar_ultimos_jogos_time(time_id, limite=5)

            if ultimos_jogos:
                cantos_feitos_casa_soma = 0
                cantos_feitos_fora_soma = 0
                cantos_cedidos_casa_soma = 0
                cantos_cedidos_fora_soma = 0
                finalizacoes_casa_soma = 0
                finalizacoes_fora_soma = 0
                finalizacoes_gol_casa_soma = 0
                finalizacoes_gol_fora_soma = 0
                cartoes_amarelos_casa_soma = 0
                cartoes_amarelos_fora_soma = 0
                cartoes_vermelhos_casa_soma = 0
                cartoes_vermelhos_fora_soma = 0
                jogos_casa = 0
                jogos_fora = 0
                vitorias_casa = 0
                vitorias_fora = 0

                for jogo in ultimos_jogos:
                    # Buscar estatísticas detalhadas usando a função existente
                    fixture_id = jogo.get('fixture_id')
                    stats = jogo.get('statistics', {})
                    teams_info = jogo.get('teams', {})

                    if not stats or not fixture_id:
                        # Tentar buscar estatísticas detalhadas
                        print(f"     🔍 DEBUG: Buscando stats para fixture {fixture_id}...")
                        stats_detalhadas = await buscar_estatisticas_jogo(fixture_id)
                        if stats_detalhadas:
                            stats = stats_detalhadas
                            print(f"     ✅ DEBUG: Stats encontradas para fixture {fixture_id}")
                        else:
                            print(f"     ⚠️ DEBUG: Nenhuma stat encontrada para fixture {fixture_id}")

                    # Determinar se o time jogou em casa ou fora
                    home_id = teams_info.get('home', {}).get('id')
                    away_id = teams_info.get('away', {}).get('id')
                    eh_casa = home_id == time_id
                    eh_fora = away_id == time_id

                    if not eh_casa and not eh_fora:
                        continue

                    # ✅ FIX: Contar o jogo SEMPRE, independente dos valores
                    if eh_casa:
                        jogos_casa += 1
                    else:
                        jogos_fora += 1

                    team_key = 'home' if eh_casa else 'away'
                    opponent_key = 'away' if eh_casa else 'home'

                    # Cantos (aceitar valores 0 também)
                    cantos_feitos = stats.get(team_key, {}).get('Corner Kicks', 0) or 0
                    cantos_sofridos = stats.get(opponent_key, {}).get('Corner Kicks', 0) or 0

                    if eh_casa:
                        cantos_feitos_casa_soma += int(cantos_feitos)
                        cantos_cedidos_casa_soma += int(cantos_sofridos)
                    else:
                        cantos_feitos_fora_soma += int(cantos_feitos)
                        cantos_cedidos_fora_soma += int(cantos_sofridos)

                    # Finalizações (aceitar valores 0 também)
                    finalizacoes_total = stats.get(team_key, {}).get('Total Shots', 0) or 0
                    finalizacoes_gol = stats.get(team_key, {}).get('Shots on Goal', 0) or 0

                    if eh_casa:
                        finalizacoes_casa_soma += int(finalizacoes_total)
                        finalizacoes_gol_casa_soma += int(finalizacoes_gol)
                    else:
                        finalizacoes_fora_soma += int(finalizacoes_total)
                        finalizacoes_gol_fora_soma += int(finalizacoes_gol)

                    # Cartões (aceitar valores 0 também)
                    cartoes_amarelos = stats.get(team_key, {}).get('Yellow Cards', 0) or 0
                    cartoes_vermelhos = stats.get(team_key, {}).get('Red Cards', 0) or 0

                    if eh_casa:
                        cartoes_amarelos_casa_soma += int(cartoes_amarelos)
                        cartoes_vermelhos_casa_soma += int(cartoes_vermelhos)
                    else:
                        cartoes_amarelos_fora_soma += int(cartoes_amarelos)
                        cartoes_vermelhos_fora_soma += int(cartoes_vermelhos)

                    # Vitórias (para análise de resultado)
                    if eh_casa:
                        home_goals = jogo.get('score', {}).get('fulltime', {}).get('home', 0)
                        away_goals = jogo.get('score', {}).get('fulltime', {}).get('away', 0)
                        if home_goals and away_goals is not None and home_goals > away_goals:
                            vitorias_casa += 1
                    else:
                        home_goals = jogo.get('score', {}).get('fulltime', {}).get('home', 0)
                        away_goals = jogo.get('score', {}).get('fulltime', {}).get('away', 0)
                        if home_goals is not None and away_goals and away_goals > home_goals:
                            vitorias_fora += 1

                # Calcular médias
                # ⚠️ IMPORTANTE: Inicializar ANTES dos condicionais para evitar "variable not associated with a value"
                cartoes_amarelos_casa = 0.0
                cartoes_vermelhos_casa = 0.0
                cartoes_amarelos_fora = 0.0
                cartoes_vermelhos_fora = 0.0
                
                if jogos_casa > 0:
                    cantos_avg_casa = cantos_feitos_casa_soma / jogos_casa
                    cantos_sofridos_casa = cantos_cedidos_casa_soma / jogos_casa
                    finalizacoes_casa = finalizacoes_casa_soma / jogos_casa
                    finalizacoes_no_gol_casa = finalizacoes_gol_casa_soma / jogos_casa
                    cartoes_amarelos_casa = cartoes_amarelos_casa_soma / jogos_casa
                    cartoes_vermelhos_casa = cartoes_vermelhos_casa_soma / jogos_casa

                if jogos_fora > 0:
                    cantos_avg_fora = cantos_feitos_fora_soma / jogos_fora
                    cantos_sofridos_fora = cantos_cedidos_fora_soma / jogos_fora
                    finalizacoes_fora = finalizacoes_fora_soma / jogos_fora
                    finalizacoes_no_gol_fora = finalizacoes_gol_fora_soma / jogos_fora
                    cartoes_amarelos_fora = cartoes_amarelos_fora_soma / jogos_fora
                    cartoes_vermelhos_fora = cartoes_vermelhos_fora_soma / jogos_fora

                print(f"\n  ✅ DADOS CALCULADOS FALLBACK ({jogos_casa} jogos casa / {jogos_fora} jogos fora):")
                print(f"     🚩 CANTOS: Casa {cantos_avg_casa:.1f} (cede {cantos_sofridos_casa:.1f}) | Fora {cantos_avg_fora:.1f} (cede {cantos_sofridos_fora:.1f})")
                print(f"     ⚽ FINALIZAÇÕES: Casa {finalizacoes_casa:.1f} total ({finalizacoes_no_gol_casa:.1f} no gol) | Fora {finalizacoes_fora:.1f} total ({finalizacoes_no_gol_fora:.1f} no gol)")
                print(f"     🟨 CARTÕES: Casa {cartoes_amarelos_casa:.1f} amarelos + {cartoes_vermelhos_casa:.1f} vermelhos | Fora {cartoes_amarelos_fora:.1f} amarelos + {cartoes_vermelhos_fora:.1f} vermelhos")
                print(f"     📊 SOMAS BRUTAS:")
                print(f"        Cantos Casa: {cantos_feitos_casa_soma} feitos / {cantos_cedidos_casa_soma} cedidos")
                print(f"        Cantos Fora: {cantos_feitos_fora_soma} feitos / {cantos_cedidos_fora_soma} cedidos")
                print(f"        Finalizações Casa: {finalizacoes_casa_soma} total / {finalizacoes_gol_casa_soma} no gol")
                print(f"        Finalizações Fora: {finalizacoes_fora_soma} total / {finalizacoes_gol_fora_soma} no gol")
                print(f"        Cartões Casa: {cartoes_amarelos_casa_soma} amarelos / {cartoes_vermelhos_casa_soma} vermelhos")
                print(f"        Cartões Fora: {cartoes_amarelos_fora_soma} amarelos / {cartoes_vermelhos_fora_soma} vermelhos")

        # Preservar campos essenciais do API para cálculo de QSC Dinâmico
        # 🔧 FIX: Garantir que nunca seja None (API pode retornar None explicitamente)
        form_string = data.get('form') or ''
        goals_raw = data.get('goals') or {}

        # FASE 2: Extrair taxa de clean sheet empírica da API
        clean_sheet_data = data.get('clean_sheet') or {}
        fixtures_played = data.get('fixtures', {}).get('played') or {}
        cs_home_count = int(clean_sheet_data.get('home', 0) or 0)
        cs_away_count = int(clean_sheet_data.get('away', 0) or 0)
        fp_home = int(fixtures_played.get('home', 0) or 0)
        fp_away = int(fixtures_played.get('away', 0) or 0)
        # Taxa de clean sheet = clean_sheets / jogos disputados no contexto (0.0 se sem dados)
        clean_sheet_rate_home = (cs_home_count / fp_home) if fp_home > 0 else None
        clean_sheet_rate_away = (cs_away_count / fp_away) if fp_away > 0 else None

        print(f"  📋 Campos essenciais capturados:")
        print(f"     Form: '{form_string}' (len: {len(form_string)})")
        print(f"     Goals structure: {bool(goals_raw)}")
        print(f"     Clean sheets: casa={cs_home_count}/{fp_home}={clean_sheet_rate_home} | fora={cs_away_count}/{fp_away}={clean_sheet_rate_away}")
        
        analise = {
            "casa": {
                "gols_marcados": gols_casa_marcados,
                "gols_sofridos": gols_casa_sofridos,
                "cantos_feitos": cantos_avg_casa,
                "cantos_sofridos": cantos_sofridos_casa,
                "finalizacoes": finalizacoes_casa,
                "finalizacoes_no_gol": finalizacoes_no_gol_casa,
                "cartoes_amarelos": cartoes_amarelos_casa,
                "cartoes_vermelhos": cartoes_vermelhos_casa,
                "vitorias": vitorias_casa,
                "clean_sheet_rate": clean_sheet_rate_home  # taxa empírica de CS em casa (None se sem dados)
            },
            "fora": {
                "gols_marcados": gols_fora_marcados,
                "gols_sofridos": gols_fora_sofridos,
                "cantos_feitos": cantos_avg_fora,
                "cantos_sofridos": cantos_sofridos_fora,
                "finalizacoes": finalizacoes_fora,
                "finalizacoes_no_gol": finalizacoes_no_gol_fora,
                "cartoes_amarelos": cartoes_amarelos_fora,
                "cartoes_vermelhos": cartoes_vermelhos_fora,
                "vitorias": vitorias_fora,
                "clean_sheet_rate": clean_sheet_rate_away  # taxa empírica de CS fora (None se sem dados)
            },
            # CAMPOS ESSENCIAIS PARA QSC DINÂMICO
            "form": form_string,
            "goals": goals_raw
        }

        cache_manager.set(cache_key, analise)
        return analise

    except httpx.TimeoutException:
        print(f"  ⏱️ TIMEOUT buscando stats do time {time_id}")
        return None
    except Exception as e:
        print(f"  ❌ ERRO buscando stats do time {time_id}: {e}")
        return None

async def buscar_jogo_de_ida_knockout(home_team_id: int, away_team_id: int, league_id: int):
    """
    Busca o jogo de ida de uma eliminatória (1st Leg) entre dois times.
    
    Args:
        home_team_id: ID do time mandante atual (jogo de volta)
        away_team_id: ID do time visitante atual (jogo de volta)
        league_id: ID da liga/competição
        
    Returns:
        dict ou None: {
            'home_team_id': int,
            'away_team_id': int,
            'home_goals': int,
            'away_goals': int,
            'date': str
        }
    """
    cache_key = f"first_leg_{home_team_id}_{away_team_id}_{league_id}"
    if cached_data := cache_manager.get(cache_key):
        return cached_data
    
    params = {"h2h": f"{home_team_id}-{away_team_id}", "league": str(league_id), "last": "3"}
    
    try:
        await asyncio.sleep(1.6)
        response = await api_request_with_retry("GET", API_URL + "fixtures/headtohead", params=params)
        response.raise_for_status()
        
        response_json = response.json()
        
        print(f"\n  🔍 Buscando jogo de ida: Time {home_team_id} vs {away_team_id} (Liga {league_id})")
        
        if data := response_json.get('response'):
            print(f"     → {len(data)} jogos encontrados no H2H")
            
            # Procurar o jogo mais recente que seja "1st Leg" ou jogo de ida
            for jogo in data:
                league_round = jogo.get('league', {}).get('round', '')
                fixture_status = jogo['fixture']['status']['short']
                
                # Deve ser finalizado
                if fixture_status not in ['FT', 'AET', 'PEN']:
                    continue
                
                # Deve ter "1st Leg" ou "ida" no nome da rodada
                first_leg_keywords = ["1st Leg", "ida", "Ida", "Andata", "Hinspiel"]
                is_first_leg = any(keyword.lower() in league_round.lower() for keyword in first_leg_keywords)
                
                if is_first_leg:
                    resultado = {
                        'home_team_id': jogo['teams']['home']['id'],
                        'away_team_id': jogo['teams']['away']['id'],
                        'home_goals': jogo['goals']['home'],
                        'away_goals': jogo['goals']['away'],
                        'date': jogo['fixture']['date'],
                        'round': league_round
                    }
                    
                    print(f"     ✅ Jogo de ida encontrado: {resultado['home_goals']} x {resultado['away_goals']} ({league_round})")
                    cache_manager.set(cache_key, resultado, expiration_minutes=1440)  # 24h
                    return resultado
            
            print(f"     ⚠️ Nenhum jogo de ida encontrado nos últimos confrontos")
            return None
        else:
            print(f"     ⚠️ Nenhum H2H encontrado")
            return None
    
    except Exception as e:
        print(f"  ❌ ERRO buscando jogo de ida: {e}")
        return None

async def buscar_h2h(time1_id: int, time2_id: int, limite: int = 5):
    """
    Busca histórico de confrontos diretos (H2H) entre dois times.
    
    Args:
        time1_id: ID do primeiro time
        time2_id: ID do segundo time
        limite: Número de jogos a buscar
    
    Returns:
        Lista com histórico de confrontos
    """
    cache_key = f"h2h_{time1_id}_{time2_id}_{limite}"
    if cached_data := cache_manager.get(cache_key):
        return cached_data
    
    params = {"h2h": f"{time1_id}-{time2_id}", "last": str(limite)}
    try:
        await asyncio.sleep(1.6)
        response = await api_request_with_retry("GET", API_URL + "fixtures/headtohead", params=params)
        response.raise_for_status()
        
        response_json = response.json()
        
        print(f"\n  🔬 H2H: Time {time1_id} vs Time {time2_id}")
        print(f"     → Status: {response.status_code}")
        
        if data := response_json.get('response'):
            print(f"     ✅ {len(data)} confrontos históricos encontrados")
            
            confrontos = []
            for jogo in data:
                if jogo['fixture']['status']['short'] not in ['FT', 'AET', 'PEN']:
                    continue
                
                confrontos.append({
                    'date': jogo['fixture']['date'],
                    'home_team': jogo['teams']['home']['name'],
                    'away_team': jogo['teams']['away']['name'],
                    'home_goals': jogo['goals']['home'],
                    'away_goals': jogo['goals']['away'],
                    'winner': jogo['teams']['home']['winner'] if jogo['teams']['home']['winner'] else 
                             ('away' if jogo['teams']['away']['winner'] else 'draw')
                })
            
            cache_manager.set(cache_key, confrontos)
            return confrontos
        else:
            print(f"     ⚠️ Nenhum H2H encontrado")
            return []
    
    except Exception as e:
        print(f"  ❌ ERRO buscando H2H: {e}")
        return []

async def buscar_ultimos_jogos_time(time_id: int, limite: int = 5, _tentativa: int = 1):
    """
    Busca últimos jogos FINALIZADOS de um time.
    Se não encontrar jogos finalizados, aumenta automaticamente o limite (retry).
    
    Args:
        time_id: ID do time
        limite: Número de jogos a buscar
        _tentativa: Controle interno de retry (não usar)
    """
    cache_key = f"ultimos_jogos_finalizados_{time_id}_{limite}"
    if cached_data := cache_manager.get(cache_key):
        return cached_data

    # Determinar temporada atual automaticamente (horário de Brasília)
    brasilia_tz = ZoneInfo("America/Sao_Paulo")
    agora = datetime.now(brasilia_tz)
    mes_atual = agora.month
    ano_atual = agora.year
    season = str(ano_atual) if mes_atual >= 7 else str(ano_atual - 1)

    params = {"team": str(time_id), "season": season, "last": str(limite)}
    try:
        await asyncio.sleep(1.6)
        response = await api_request_with_retry("GET", API_URL + "fixtures", params=params)
        response.raise_for_status()
        
        response_json = response.json()
        
        # 🔍 INVESTIGAÇÃO: Logging completo
        print(f"\n  🔬 INVESTIGAÇÃO /fixtures (últimos jogos) - Tentativa {_tentativa}:")
        print(f"     → Time: {time_id}, Season: {season}, Limite: {limite}")
        print(f"     → URL: {API_URL}fixtures")
        print(f"     → Status: {response.status_code}")

        if data := response_json.get('response'):
            print(f"     ✅ {len(data)} jogos retornados pela API")
            
            jogos_processados = []
            jogos_finalizados = 0
            jogos_futuros = 0
            
            for jogo in data:
                fixture_status = jogo['fixture']['status']['short']
                fixture_id = jogo['fixture']['id']
                
                # 🚨 FILTRO CRÍTICO: Apenas jogos FINALIZADOS (FT, AET, PEN)
                if fixture_status not in ['FT', 'AET', 'PEN']:
                    print(f"     ⏭️  IGNORADO Fixture {fixture_id}: Status '{fixture_status}' (não finalizado)")
                    jogos_futuros += 1
                    continue
                
                jogos_finalizados += 1
                jogo_info = {
                    "fixture_id": fixture_id,
                    "date": jogo['fixture']['date'],
                    "status": fixture_status,
                    "home_team": jogo['teams']['home']['name'],
                    "away_team": jogo['teams']['away']['name'],
                    "teams": {
                        "home": {"id": jogo['teams']['home']['id'], "name": jogo['teams']['home']['name']},
                        "away": {"id": jogo['teams']['away']['id'], "name": jogo['teams']['away']['name']}
                    },
                    "score": jogo.get('score', {}),
                    "home_goals": jogo.get('goals', {}).get('home', 0),
                    "away_goals": jogo.get('goals', {}).get('away', 0),
                    "statistics": {}  # Será preenchido depois
                }
                jogos_processados.append(jogo_info)
                print(f"     ✅ INCLUÍDO Fixture {fixture_id}: {jogo_info['home_team']} vs {jogo_info['away_team']} (Status: {fixture_status})")

            print(f"\n     📊 RESUMO: {jogos_finalizados} finalizados / {jogos_futuros} futuros ou em andamento")
            print(f"     → Jogos válidos para análise: {len(jogos_processados)}")
            
            # 🔄 RETRY: Se nenhum jogo finalizado encontrado e ainda não tentamos com mais jogos
            if len(jogos_processados) == 0 and _tentativa < 3:
                novo_limite = limite * 2  # Dobrar limite
                print(f"\n     🔄 RETRY: Nenhum jogo finalizado encontrado, tentando com {novo_limite} jogos...")
                return await buscar_ultimos_jogos_time(time_id, limite=novo_limite, _tentativa=_tentativa + 1)
            
            # ⚠️ GUARDRAIL: Se após 3 tentativas ainda não há jogos finalizados
            if len(jogos_processados) == 0:
                print(f"\n     ❌ FALHA CRÍTICA: Nenhum jogo finalizado encontrado após {_tentativa} tentativas")
                print(f"        → Time {time_id} pode não ter histórico na temporada {season}")
                print(f"        → Ou todos os jogos são futuros/em andamento")
                return []
            
            cache_manager.set(cache_key, jogos_processados)
            return jogos_processados
        else:
            print(f"     ❌ Campo 'response' vazio")
            
    except Exception as e:
        print(f"  ❌ ERRO buscando últimos jogos do time {time_id}: {e}")
        import traceback
        traceback.print_exc()

    return []

def normalizar_odds(odds_formatadas):
    """
    Normaliza odds recebidas do formato API-Football para o formato usado pelos analisadores.
    """
    odds_normalizadas = {}

    for mercado_key, odds_dict in odds_formatadas.items():
        if mercado_key.startswith("match_winner"):
            # Mercado 1X2 (Resultado do Jogo)
            odds_normalizadas["casa_vence"] = odds_dict.get("Home", 0)
            odds_normalizadas["empate"] = odds_dict.get("Draw", 0)
            odds_normalizadas["fora_vence"] = odds_dict.get("Away", 0)

        elif mercado_key.startswith("goals_over_under"):
            # Mercado Over/Under Gols
            periodo = "ft" if "ft" in mercado_key else "ht"
            for linha, valor in odds_dict.items():
                if "over" in linha.lower():
                    linha_num = linha.replace("Over ", "").replace("over ", "")
                    odds_normalizadas[f"gols_{periodo}_over_{linha_num}"] = valor
                elif "under" in linha.lower():
                    linha_num = linha.replace("Under ", "").replace("under ", "")
                    odds_normalizadas[f"gols_{periodo}_under_{linha_num}"] = valor

        elif mercado_key.startswith("btts"):
            # Mercado BTTS (Both Teams To Score)
            odds_normalizadas["btts_sim"] = odds_dict.get("Yes", 0)
            odds_normalizadas["btts_nao"] = odds_dict.get("No", 0)

        elif mercado_key.startswith("double_chance"):
            # Mercado Dupla Chance
            odds_normalizadas["dupla_1x"] = odds_dict.get("Home/Draw", 0)
            odds_normalizadas["dupla_12"] = odds_dict.get("Home/Away", 0)
            odds_normalizadas["dupla_x2"] = odds_dict.get("Draw/Away", 0)

        elif "corner" in mercado_key.lower():
            # Mercado Cantos
            periodo = "ft" if "ft" in mercado_key or "full" in mercado_key else "ht"
            time = "total" if "total" in mercado_key else ("casa" if "home" in mercado_key else "fora")

            for linha, valor in odds_dict.items():
                linha_limpa = linha.lower().replace("over ", "").replace("under ", "").strip()
                if "over" in linha.lower():
                    odds_normalizadas[f"cantos_{periodo}_over_{linha_limpa}"] = valor
                elif "under" in linha.lower():
                    odds_normalizadas[f"cantos_{periodo}_under_{linha_limpa}"] = valor

        elif "card" in mercado_key.lower():
            # Mercado Cartões
            time = "total" if "total" in mercado_key else ("casa" if "home" in mercado_key else "fora")

            for linha, valor in odds_dict.items():
                linha_limpa = linha.lower().replace("over ", "").replace("under ", "").strip()
                if "over" in linha.lower():
                    odds_normalizadas[f"cartoes_{time}_over_{linha_limpa}"] = valor
                elif "under" in linha.lower():
                    odds_normalizadas[f"cartoes_{time}_under_{linha_limpa}"] = valor

        elif "handicap" in mercado_key.lower() or "spread" in mercado_key.lower():
            # Mercado Handicaps
            for linha, valor in odds_dict.items():
                if "Home" in linha:
                    linha_num = linha.replace("Home ", "").replace("home ", "").strip()
                    odds_normalizadas[f"handicap_casa_{linha_num}"] = valor
                elif "Away" in linha:
                    linha_num = linha.replace("Away ", "").replace("away ", "").strip()
                    odds_normalizadas[f"handicap_fora_{linha_num}"] = valor

    return odds_normalizadas

async def buscar_odds_do_jogo(id_jogo: int):
    cache_key = f"odds_{id_jogo}"
    if cached_data := cache_manager.get(cache_key): return cached_data

    params = {"fixture": str(id_jogo)}
    odds_formatadas = {}

    try:
        await asyncio.sleep(1.6)
        response = await api_request_with_retry("GET", API_URL + "odds", params=params)
        response.raise_for_status()
        
        response_json = response.json()

        if data := response_json.get('response'):
            if not data:
                return {}

            bookmaker_data = data[0].get('bookmakers', [])
            if not bookmaker_data:
                return {}

            # Usar primeira casa de apostas (geralmente Bet365)
            bookmaker = bookmaker_data[0]
            all_bets = bookmaker.get('bets', [])
            
            # 🔍 DEBUG: Mostrar TODOS os mercados disponíveis
            mercados_disponiveis = [bet['name'] for bet in all_bets]
            print(f"  📊 DEBUG ODDS - Mercados disponíveis para fixture {id_jogo}:")
            print(f"     {mercados_disponiveis}")

            for bet in all_bets:
                bet_name = bet['name']
                values_raw = bet.get('values', [])

                # Processar odds de acordo com o tipo de mercado
                if bet_name == "Match Winner":
                    odds_formatadas["match_winner"] = {v['value']: float(v['odd']) for v in values_raw}

                elif bet_name == "Goals Over/Under":
                    odds_formatadas["goals_over_under_ft"] = {v['value']: float(v['odd']) for v in values_raw}

                elif bet_name == "Goals Over/Under First Half":
                    odds_formatadas["goals_over_under_ht"] = {v['value']: float(v['odd']) for v in values_raw}

                elif bet_name == "Both Teams Score":
                    odds_formatadas["btts"] = {v['value']: float(v['odd']) for v in values_raw}

                elif bet_name == "Double Chance":
                    odds_formatadas["double_chance"] = {v['value']: float(v['odd']) for v in values_raw}

                elif "Corner" in bet_name:
                    periodo = "ht" if "First Half" in bet_name or "1st Half" in bet_name else "ft"
                    if "Home" in bet_name:
                        odds_formatadas[f"corners_{periodo}_home"] = {v['value']: float(v['odd']) for v in values_raw}
                    elif "Away" in bet_name:
                        odds_formatadas[f"corners_{periodo}_away"] = {v['value']: float(v['odd']) for v in values_raw}
                    else:
                        odds_formatadas[f"corners_{periodo}_total"] = {v['value']: float(v['odd']) for v in values_raw}

                elif "Card" in bet_name:
                    if "Home" in bet_name:
                        odds_formatadas["cards_home"] = {v['value']: float(v['odd']) for v in values_raw}
                    elif "Away" in bet_name:
                        odds_formatadas["cards_away"] = {v['value']: float(v['odd']) for v in values_raw}
                    else:
                        odds_formatadas["cards_total"] = {v['value']: float(v['odd']) for v in values_raw}

                elif "Handicap" in bet_name or "Spread" in bet_name:
                    odds_formatadas["handicap"] = {v['value']: float(v['odd']) for v in values_raw}

    except httpx.TimeoutException:
        print(f"  ⏱️ TIMEOUT buscando odds do jogo {id_jogo}")
    except Exception as e:
        print(f"  ⚠️ Erro ao buscar odds do jogo {id_jogo}: {e}")

    # Normalizar odds para formato usado pelos analisadores
    if odds_formatadas:
        odds_normalizadas = normalizar_odds(odds_formatadas)
        cache_manager.set(cache_key, odds_normalizadas)
        return odds_normalizadas

    return {}

async def buscar_ligas_disponiveis_hoje():
    """Retorna lista de ligas que têm jogos hoje, ORDENADAS POR PAÍS."""
    jogos = await buscar_jogos_do_dia()
    if not jogos:
        return []

    ligas_com_jogos = {}
    for jogo in jogos:
        liga_id = jogo['league']['id']
        if liga_id not in ligas_com_jogos:
            if liga_id in NOMES_LIGAS_PT:
                nome_com_bandeira, pais = NOMES_LIGAS_PT[liga_id]
                ligas_com_jogos[liga_id] = {
                    'id': liga_id,
                    'nome': nome_com_bandeira,
                    'pais': pais,
                    'ordem_pais': ORDEM_PAISES.get(pais, 999)
                }

    # Ordenar por país (usando ordem personalizada) e depois por nome da liga
    ligas_ordenadas = sorted(
        ligas_com_jogos.values(),
        key=lambda x: (x['ordem_pais'], x['nome'])
    )

    return ligas_ordenadas

def buscar_todas_ligas_suportadas():
    """Retorna TODAS as 80+ ligas suportadas pelo bot, ORDENADAS POR PAÍS."""
    todas_ligas = []
    
    for liga_id in LIGAS_DE_INTERESSE:
        if liga_id in NOMES_LIGAS_PT:
            nome_com_bandeira, pais = NOMES_LIGAS_PT[liga_id]
            todas_ligas.append({
                'id': liga_id,
                'nome': nome_com_bandeira,
                'pais': pais,
                'ordem_pais': ORDEM_PAISES.get(pais, 999)
            })
    
    # Ordenar por país (usando ordem personalizada) e depois por nome da liga
    ligas_ordenadas = sorted(
        todas_ligas,
        key=lambda x: (x['ordem_pais'], x['nome'])
    )
    
    return ligas_ordenadas

async def buscar_jogos_por_liga(liga_id: int):
    """Retorna jogos de uma liga específica para hoje."""
    jogos_todos = await buscar_jogos_do_dia()
    return [jogo for jogo in jogos_todos if jogo['league']['id'] == liga_id]

async def buscar_estatisticas_jogo(fixture_id: int):
    """Busca estatísticas detalhadas de um jogo específico (cantos, cartões, finalizações, etc)."""
    cache_key = f"stats_jogo_{fixture_id}"
    if cached_data := cache_manager.get(cache_key):
        return cached_data

    params = {"fixture": str(fixture_id)}
    try:
        await asyncio.sleep(1.6)
        response = await api_request_with_retry("GET", API_URL + "fixtures/statistics", params=params)
        response.raise_for_status()
        
        response_json = response.json()
        
        # --- RAW API-FUTEBOL **STATS** RESPONSE ---
        import json
        print("--- RAW API-FUTEBOL **STATS** RESPONSE ---")
        print(json.dumps(response_json, indent=2))
        print("------------------------------------------")
        
        print(f"  🔍 DEBUG FIXTURE {fixture_id} - Resumo da Resposta:")
        print(f"     Status code: {response.status_code}")

        if data := response_json.get('response'):
            if not data or len(data) == 0:
                print(f"     ⚠️ Response vazio para fixture {fixture_id} - jogo pode não ter acontecido ainda")
                return None
                
            # 🔍 DEBUG: Mostrar dados RAW completos da API
            print(f"     ✅ {len(data)} times encontrados na resposta")
            
            # API retorna array com 2 elementos: [home_stats, away_stats]
            stats_processadas = {
                'home': {},
                'away': {}
            }

            for team_stats in data:
                team_type = 'home' if team_stats['team']['id'] == data[0]['team']['id'] else 'away'
                team_name = team_stats['team']['name']

                # Extrair estatísticas relevantes
                stats_dict = {}
                for stat in team_stats.get('statistics', []):
                    tipo = stat.get('type', '')
                    valor = stat.get('value', 0)

                    # Converter para número quando possível
                    if valor and isinstance(valor, str) and '%' not in valor:
                        try:
                            valor = int(valor)
                        except (ValueError, TypeError):
                            # Manter valor original se conversão falhar
                            pass

                    stats_dict[tipo] = valor

                stats_processadas[team_type] = stats_dict
                
                # 🔍 DEBUG: Mostrar dados processados de CANTOS, CARTÕES e FINALIZAÇÕES
                print(f"     {team_type.upper()} ({team_name}):")
                print(f"       🚩 Cantos: {stats_dict.get('Corner Kicks', 'N/A')}")
                print(f"       ⚽ Finalizações: {stats_dict.get('Total Shots', 'N/A')} total, {stats_dict.get('Shots on Goal', 'N/A')} no gol")
                print(f"       🟨 Cartões: {stats_dict.get('Yellow Cards', 'N/A')} amarelos, {stats_dict.get('Red Cards', 'N/A')} vermelhos")

            cache_manager.set(cache_key, stats_processadas, expiration_minutes=240)
            return stats_processadas
        else:
            print(f"     ⚠️ Campo 'response' não encontrado ou vazio no JSON")
            return None

    except Exception as e:
        print(f"  ❌ ERRO buscando stats do jogo {fixture_id}: {e}")
        import traceback
        traceback.print_exc()

    return None
