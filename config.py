# config.py

"""
Arquivo central para todas as configurações e constantes do projeto.
"""

# --- CONFIGURAÇÕES GLOBAIS DO BOT ---
JOGOS_POR_PAGINA = 5

# --- CONFIGURAÇÕES DOS ANALISTAS ---
ODD_MINIMA_DE_VALOR = 1.20  # Reduzido para capturar valor em favoritos

# --- THRESHOLDS DE CONFIANÇA RECALIBRADOS (PHOENIX V2.0 - FINAL STAGE) ---
# Valores ajustados para aumentar produtividade sem sacrificar qualidade
MIN_CONFIANCA_GERAL = 5.0  # Threshold base para aceitar palpites
MIN_CONFIANCA_GOLS_OVER_UNDER = 5.0  # Over/Under 2.5 gols
MIN_CONFIANCA_GOLS_OVER_1_5 = 5.5  # Over 1.5 (mais seguro)
MIN_CONFIANCA_GOLS_OVER_3_5 = 5.0  # Over 3.5 (mais arriscado)
MIN_CONFIANCA_CANTOS = 5.0  # Escanteios
MIN_CONFIANCA_CANTOS_UNDER = 5.5  # Under escanteios (mais conservador)
MIN_CONFIANCA_CARTOES = 5.0  # Cartões
MIN_CONFIANCA_BTTS_SIM = 5.5  # BTTS Sim
MIN_CONFIANCA_BTTS_NAO = 6.0  # BTTS Não (mais difícil prever)
MIN_CONFIANCA_HANDICAPS_FORTE = 6.5  # Handicap alto (ex: -1.5, -2.5)
MIN_CONFIANCA_HANDICAPS_MEDIO = 6.2  # Handicap médio (ex: -1.0)
MIN_CONFIANCA_HANDICAPS_BAIXO = 5.5  # Handicap baixo (ex: -0.5, +0.5)
MIN_CONFIANCA_APOSTA_SIMPLES = 6.0  # Para aposta simples (principal pick)
MIN_CONFIANCA_MULTIPLA = 5.5  # Para múltiplas
MIN_CONFIANCA_BINGO = 5.5  # Para bingo (odd alta)

# --- THRESHOLDS DE ODD ---
ODD_MINIMA_PENALIDADE = 1.40  # Odds abaixo disso têm confiança penalizada
ODD_MINIMA_TACTICAL_TIP = 1.20  # Mínimo para considerar como tactical tip válido

# --- THRESHOLDS DE PROBABILIDADES E MÉTRICAS ESTATÍSTICAS ---
# BTTS (Both Teams to Score)
BTTS_PROB_THRESHOLD_SIM = 0.50  # Probabilidade mínima para BTTS Sim
BTTS_PROB_THRESHOLD_NAO = 0.45  # Probabilidade máxima para BTTS Não (< 45%)

# Médias de Gols para Análise Contextual
GOLS_CASA_ATAQUE_FORTE = 1.8  # Casa marca em média 1.8+ gols
GOLS_FORA_ATAQUE_FORTE = 1.5  # Fora marca em média 1.5+ gols
GOLS_CASA_DEFESA_FRACA = 1.5  # Casa sofre em média 1.5+ gols
GOLS_FORA_DEFESA_FRACA = 1.2  # Fora sofre em média 1.2+ gols
GOLS_JOGO_ABERTO_THRESHOLD = 1.3  # Threshold para detectar jogo aberto

# Médias de Cantos para Análise Contextual
CANTOS_CASA_ALTO = 6.0  # Casa força 6+ cantos em média
CANTOS_CASA_MEDIO = 5.5  # Casa força 5.5+ cantos
CANTOS_CASA_BAIXO = 4.5  # Casa força menos de 4.5 cantos
CANTOS_LINHA_MINIMA_FT_TOTAL = 7.5  # Linha mínima para Under FT Total

# Médias de Cartões para Análise Contextual
CARTOES_TIME_FALTOSO = 3.5  # Time com 3.5+ cartões é considerado faltoso
CARTOES_JOGO_TRUNCADO = 3.0  # 3+ cartões/time indica jogo truncado
CARTOES_JOGO_TENSO = 2.5  # 2.5+ cartões/time indica tensão

# Handicaps - Diferença de Força
HANDICAP_DIFERENCA_FORTE = 2.5  # Diferença QSC >= 2.5 para handicaps altos

# Progresso de Temporada
TEMPORADA_RETA_FINAL = 0.75  # 75% da temporada = reta final

# --- DETECÇÃO DE VALOR CONTEXTUAL ---
# O bot pode aceitar odds menores quando identifica VALOR baseado em contexto:
# - Favorito forte com odd 1.50-1.80 = VALOR
# - Clássico/Derby com +4.5 cartões @1.80 = VALOR  
# - Jogo decisivo com +10.5 cantos @2.00 = VALOR

# --- QUALITY SCORES DOS TIMES ---
# Scores de qualidade técnica dos times (1-100)
# Usado para análise de diferença técnica e contexto de partidas
QUALITY_SCORES = {
    # Premier League - Inglaterra
    33: 95,   # Manchester City
    40: 92,   # Liverpool
    42: 90,   # Arsenal
    34: 88,   # Newcastle
    50: 87,   # Manchester United
    49: 86,   # Tottenham
    35: 85,   # Chelsea
    66: 83,   # Aston Villa
    48: 82,   # West Ham
    
    # La Liga - Espanha
    529: 94,  # Barcelona
    541: 93,  # Real Madrid
    530: 87,  # Atletico Madrid
    532: 82,  # Valencia
    536: 81,  # Sevilla
    548: 80,  # Real Sociedad
    724: 78,  # Villarreal
    531: 77,  # Athletic Bilbao
    
    # Serie A - Itália
    489: 91,  # Inter
    487: 90,  # AC Milan
    505: 89,  # Napoli
    496: 88,  # Juventus
    487: 86,  # AS Roma
    497: 84,  # Lazio
    
    # Bundesliga - Alemanha
    157: 93,  # Bayern Munich
    165: 89,  # Borussia Dortmund
    173: 86,  # RB Leipzig
    168: 83,  # Bayer Leverkusen
    
    # Ligue 1 - França
    85: 91,   # PSG
    81: 82,   # Marseille
    80: 80,   # Monaco
    83: 78,   # Lyon
    
    # Brasileirão
    127: 85,  # Flamengo
    131: 82,  # Palmeiras
    126: 80,  # São Paulo
    128: 78,  # Corinthians
    118: 77,  # Atlético-MG
    124: 76,  # Internacional
    130: 75,  # Grêmio
    120: 74,  # Fluminense
    
    # Times médios recebem score padrão: 70
}

# --- LAYER 1: LEAGUE WEIGHTING FACTOR (PHOENIX V2.0) ---
# Multiplicador de qualidade por liga (0.0-1.0)
# Ligas de elite recebem peso máximo (1.0), ligas secundárias peso menor
LEAGUE_WEIGHTING_FACTOR = {
    # ELITE TIER (1.0) - Top 5 Ligas Europeias
    39: 1.0,   # Premier League (Inglaterra)
    140: 1.0,  # La Liga (Espanha)
    135: 1.0,  # Serie A (Itália)
    78: 1.0,   # Bundesliga (Alemanha)
    61: 0.95,  # Ligue 1 (França)
    
    # COMPETIÇÕES UEFA (0.95-1.0)
    2: 1.0,    # Champions League
    3: 0.95,   # Europa League
    848: 0.90, # Conference League
    
    # HIGH TIER (0.85-0.92) - Ligas Fortes Europeias
    94: 0.90,  # Primeira Liga (Portugal)
    88: 0.88,  # Eredivisie (Holanda)
    144: 0.85, # Jupiler Pro League (Bélgica)
    203: 0.85, # Süper Lig (Turquia)
    
    # AMÉRICA DO SUL - COMPETIÇÕES INTERNACIONAIS (0.90-0.95)
    13: 0.95,  # Copa Libertadores
    11: 0.90,  # Copa Sudamericana
    
    # AMÉRICA DO SUL - LIGAS NACIONAIS (0.82-0.90)
    71: 0.90,  # Brasileirão Série A
    128: 0.88, # Liga Profesional (Argentina)
    239: 0.82, # Categoría Primera A (Colômbia)
    265: 0.80, # Primera División (Chile)
    274: 0.78, # Primera División (Uruguai)
    
    # COMPETIÇÕES SEGUNDO NÍVEL EUROPA (0.78-0.85)
    40: 0.85,  # Championship (Inglaterra)
    141: 0.82, # La Liga 2 (Espanha)
    136: 0.82, # Serie B (Itália)
    79: 0.82,  # 2. Bundesliga (Alemanha)
    62: 0.80,  # Ligue 2 (França)
    
    # MID TIER (0.70-0.80) - Ligas Médias Europeias
    179: 0.78, # Scottish Premiership (Escócia)
    218: 0.75, # Austrian Bundesliga (Áustria)
    207: 0.75, # Swiss Super League (Suíça)
    197: 0.73, # Super League Greece (Grécia)
    235: 0.73, # Russian Premier League (Rússia)
    119: 0.72, # Superligaen (Dinamarca)
    103: 0.70, # Eliteserien (Noruega)
    113: 0.70, # Allsvenskan (Suécia)
    
    # AMÉRICA DO NORTE (0.75-0.80)
    253: 0.78, # MLS (EUA/Canadá)
    262: 0.76, # Liga MX (México)
    
    # ÁSIA - TOP LEAGUES (0.72-0.78)
    307: 0.78, # Saudi Pro League (Arábia Saudita)
    83: 0.75,  # J1 League (Japão)
    292: 0.73, # K League 1 (Coreia do Sul)
    301: 0.72, # UAE Pro League (Emirados Árabes)
    
    # LOWER TIER (0.65-0.72) - Ligas Emergentes
    72: 0.72,  # Brasileirão Série B
    106: 0.70, # Ekstraklasa (Polônia)
    345: 0.68, # Czech First League (República Tcheca)
    210: 0.68, # HNL (Croácia)
    283: 0.67, # Liga I (Romênia)
    286: 0.66, # Serbian SuperLiga (Sérvia)
    240: 0.66, # Liga Pro (Equador)
    250: 0.65, # Primera División (Paraguai)
    281: 0.65, # Liga 1 (Peru)
    
    # EMERGING TIER (0.60-0.65) - Ligas em Desenvolvimento
    233: 0.65, # Egyptian Premier League (Egito)
    288: 0.64, # PSL (África do Sul)
    200: 0.63, # Botola Pro (Marrocos)
    188: 0.62, # A-League (Austrália)
    17: 0.60,  # Chinese Super League (China)
    
    # DEFAULT: Ligas não listadas recebem peso 0.70
}

# --- LAYER 3: SISTEMA DE VETO - MERCADOS VETADOS POR TACTICAL SCRIPT (PHOENIX V2.0) ---
# Define quais mercados NÃO FAZEM SENTIDO para cada script tático
# Previne apostas absurdas como "Under 2.5" quando time dominante joga
MERCADOS_VETADOS_POR_SCRIPT = {
    'SCRIPT_HOST_DOMINATION': {
        'vetados': ['Under 2.5', 'Under 1.5', 'BTTS Não'],
        'razao': 'Casa domina em altitude/vantagem extrema - gols esperados'
    },
    'SCRIPT_DOMINIO_CASA': {
        'vetados': ['Under 2.5', 'Under 1.5', 'Vitória Fora', 'BTTS Não'],
        'razao': 'Casa com clara superioridade - deve atacar e marcar'
    },
    'SCRIPT_DOMINIO_VISITANTE': {
        'vetados': ['Under 2.5', 'Under 1.5', 'Vitória Casa', 'BTTS Não'],
        'razao': 'Visitante dominante - jogo aberto com gols esperados'
    },
    'SCRIPT_TIME_EM_CHAMAS_CASA': {
        'vetados': ['Under 2.5', 'Under 1.5', 'Draw', 'Vitória Fora'],
        'razao': 'Casa em sequência incrível - vitória e gols prováveis'
    },
    'SCRIPT_TIME_EM_CHAMAS_FORA': {
        'vetados': ['Under 2.5', 'Under 1.5', 'Draw', 'Vitória Casa'],
        'razao': 'Visitante em chamas - vitória e gols prováveis'
    },
    'SCRIPT_MATA_MATA_IDA': {
        'vetados': ['BTTS Não'],
        'razao': 'Jogo de ida - ambos times devem buscar gol'
    },
    'SCRIPT_MATA_MATA_VOLTA': {
        'vetados': [],
        'razao': 'Jogo de volta - dinâmica depende do resultado da ida'
    },
    'SCRIPT_OPEN_HIGH_SCORING_GAME': {
        'vetados': ['Under 2.5', 'Under 1.5', 'BTTS Não'],
        'razao': 'Jogo aberto - muitos gols esperados, ambos devem marcar'
    },
    'SCRIPT_CAGEY_TACTICAL_AFFAIR': {
        'vetados': ['Over 3.5', 'Over 4.5'],
        'razao': 'Jogo travado taticamente - poucos gols esperados'
    },
    'SCRIPT_RELEGATION_BATTLE': {
        'vetados': ['Over 3.5', 'Over 4.5'],
        'razao': 'Jogo de 6 pontos - times cautelosos, jogo tenso'
    },
    'SCRIPT_JOGO_DE_COMPADRES': {
        'vetados': ['Over 3.5', 'Over 4.5'],
        'razao': 'Jogo sem motivação - ritmo lento, poucos gols'
    },
    'SCRIPT_BALANCED_RIVALRY_CLASH': {
        'vetados': [],
        'razao': 'Derby equilibrado - todos os mercados possíveis'
    },
    'SCRIPT_GIANT_VS_MINNOW': {
        'vetados': ['Under 2.5', 'Draw', 'Vitória Fora'],
        'razao': 'Gigante vs pequeno - vitória casa e gols esperados'
    },
    'SCRIPT_UNSTABLE_FAVORITE': {
        'vetados': [],
        'razao': 'Favorito instável - mercado aberto, cautela necessária'
    },
}

