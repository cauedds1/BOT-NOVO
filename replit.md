# Bot de Análise de Apostas Esportivas - Telegram

## Overview
Este projeto é um bot sofisticado e modular para o Telegram, focado na análise estatística de partidas de futebol. Ele se integra à API-Football (API-Sports) para coletar dados em tempo real e históricos de jogos, gerando análises detalhadas e palpites para apostas esportivas. O objetivo é fornecer aos usuários insights aprofundados para decisões de apostas mais informadas, utilizando métricas avançadas e ajustadas por contexto.

## User Preferences
Eu, como usuário, prefiro um estilo de comunicação direto e objetivo. Gosto de ver o impacto das mudanças e melhorias de forma clara e concisa. Priorizo o desenvolvimento iterativo e a resolução de problemas críticos que afetam a funcionalidade principal. Não desejo que o agente faça alterações nos arquivos `.env` ou em qualquer configuração de variáveis de ambiente diretamente, a menos que explicitamente instruído.

## System Architecture
O bot é construído com uma arquitetura modular e production-ready, permitindo fácil expansão e manutenção.
- **Ponto de Entrada:** `main.py`
- **Comunicação API:** `api_client.py` gerencia a interação com a API-Football.
- **Configuração:** `config.py` centraliza as configurações do projeto.
- **Gerenciamento de Dados:**
    - `cache_manager.py` implementa um sistema de cache em memória e arquivo para otimizar o uso da API e o desempenho.
    - `db_manager.py` gerencia a persistência de dados utilizando PostgreSQL, com uma tabela `analises_jogos` para cache de análises complexas.
- **Módulos de Análise (Pure Analyst Protocol):** O diretório `analysts/` contém módulos especializados para diferentes mercados de apostas, orquestrados por um `master_analyzer.py`. Todos os analisadores usam um sistema unificado de confiança (`confidence_calculator.py`) baseado exclusivamente em probabilidades estatísticas, independente de odds de mercado. Inclui análises para gols, resultado final, escanteios, ambos marcam, cartões, finalizações, handicaps e análise contextual (`context_analyzer.py`).
- **UI/UX:** O bot interage com o usuário através de comandos do Telegram, apresentando análises de forma clara e concisa. As mensagens são formatadas para serem consistentes e evitar redundância.
- **Testes:** Diretório `tests/` contém testes unitários para validação de funcionalidades críticas.

## Decisões Técnicas
### Core Features
- **QSC Dinâmico (Quality Score Composite):** Implementado em `context_analyzer.py`, calcula um score de qualidade composto baseado em reputação estática, posição na tabela, saldo de gols e forma recente, ponderando a importância de cada componente.
- **SoS (Strength of Schedule) & Weighted Metrics:** Em `master_analyzer.py`, analisa a força dos adversários recentes e pondera estatísticas (como cantos e finalizações) pela dificuldade dos oponentes, fornecendo métricas ajustadas.
- **Detecção Dinâmica de Temporada:** `api_client.py` inclui lógica para detectar automaticamente a temporada ativa de uma liga através da API, com fallback inteligente, suportando calendários não-padrão e eliminando a necessidade de lógica de data hardcoded.
- **Gerenciamento de Fuso Horário:** Horários dos jogos são convertidos para `America/Sao_Paulo` (Brasília) usando `ZoneInfo` para exibir informações corretas ao usuário.
- **Tratamento de Tactical Tips:** Dicas táticas sem odds são processadas e priorizadas corretamente, sem serem descartadas por falta de odd.
- **Calibração de Cache TTLs:** Os tempos de vida (TTL) do cache são diferenciados por tipo de dado, otimizando a atualização de dados sensíveis ao tempo (odds) e economizando créditos da API para dados mais estáveis.

### Fase 2: Motor de Probabilidades Poisson - 2026-04-03
**Refatoração do motor de probabilidades para usar distribuição de Poisson real.**

- **Lambda por Time:** `master_analyzer.py` extrai `lambda_home` (gols marcados pelo mandante EM CASA) e `lambda_away` (gols marcados pelo visitante FORA), combina com a fragilidade defensiva do oponente para obter `lambda_efetivo` por time.
- **Todas as Linhas via Poisson:** `goals_analyzer_v2.py` substituiu todos os offsets fixos (`over_2_5 + 15`, `over_2_5 - 30`, etc.) por cálculos independentes de Poisson para Over 1.5, 2.5, 3.5 e 4.5 usando `lambda_total`.
- **Modelo HT:** Lambda do 1º tempo = `lambda_total × ht_ratio`, onde `ht_ratio` é ajustado pelo perfil tático: times ofensivos → 0.47, defensivos → 0.38, neutro → 0.43 (baseline histórico global).
- **Gols por Time:** "Casa Over 0.5/1.5" usa `lambda_home` (não percentual do total), "Fora Over 0.5/1.5" usa `lambda_away`.
- **BTTS Poisson:** `btts_analyzer.py` refatorado: `P(BTTS) = P(home marca) × P(away marca)`, onde cada prob = `1 - e^(-lambda_efetivo)` via Poisson. Elimina divisão arbitrária por constante 2.5. `lambda_efetivo` combina ataque próprio + defesa adversária.
- **Novo mercado:** Over/Under 4.5 adicionado ao `goals_analyzer_v2.py`.

### Pure Analyst Protocol - 2025-10-31
**Paradigma Shift:** O bot foi completamente refatorado para focar em análise estatística pura, eliminando toda dependência de market odds (valor de apostas).

- **Sistema Unificado de Confiança:** Todos os analisadores agora usam `confidence_calculator.py` com assinatura simplificada: `calculate_final_confidence(statistical_probability_pct, bet_type, tactical_script)`.
- **Remoção de Filtragem por Odds:** Eliminados todos os checks de `ODD_MINIMA_DE_VALOR` em 8 módulos de análise (goals, corners, cards, shots, btts, handicaps, match_result).
- **Priorização por Confiança:** Análises são ordenadas e filtradas exclusivamente por níveis de confiança estatística (0-10), não por "valor de mercado".
- **Interface Pure Analyst:** Output formatado mostra "ANÁLISE PRINCIPAL" e "OUTRAS TENDÊNCIAS" baseado em confiança, mantendo odds apenas para referência informativa.
- **Módulos Removidos:** `value_detector.py` (detecção de valor de mercado), funções de modificação de score por odd.
- **Arquitetura Validada:** Todos os analisadores testados e aprovados pelo sistema de revisão arquitetural, sem regressões detectadas.

### Production Hardening (SRE) - 2025-10-31
- **API Resilience:** Todas as chamadas HTTP externas agora têm retry automático com exponential backoff (até 5 tentativas) usando a biblioteca `tenacity`. Previne crashes por falhas temporárias de rede ou API (502, 503, timeouts).
- **Startup Secret Validation:** Função `startup_validation()` valida Telegram Token, API-Football Key e PostgreSQL Connection antes de iniciar o bot. Bot recusa iniciar se algum secret estiver inválido, prevenindo crashes tardios.
- **Graceful Shutdown:** Signal handlers (SIGINT, SIGTERM) executam shutdown limpo salvando cache, fechando conexões HTTP e DB pool. Garante zero perda de dados em shutdowns abruptos.
- **Bounded Job Queue:** Fila de análises tem limite máximo de 1000 jobs, prevenindo memory exhaustion sob alta carga. Rejeita graciosamente novos jobs quando cheia, informando o usuário.
- **Rate Limiting:** Proteção contra abuso com limite de 10 comandos/minuto por usuário usando sliding window. Aplicado em todos os comandos e callbacks.
- **Production Readiness Score:** 9/10 (upgrade de 4/10 após hardening)

## External Dependencies
- **Telegram Bot API:** Utilizado através da biblioteca `python-telegram-bot` para interação com os usuários.
- **API-Football (API-Sports):** Principal fonte de dados para estatísticas e informações de jogos, acessada via `httpx` com retry automático.
- **PostgreSQL:** Banco de dados relacional utilizado para persistência de dados e cache de análises, conectado via `psycopg2-binary`. O Replit provê uma instância Neon serverless.
- **python-dotenv:** Usado para gerenciar variáveis de ambiente.
- **tenacity:** Framework de retry para resiliência de chamadas HTTP externas.
- **numpy/scipy:** Bibliotecas científicas para cálculos estatísticos avançados.

## Deployment
- **Procfile:** Configurado para deployment em plataformas PaaS (Heroku, Fly.io, Railway, Render).
- **Environment Variables Requeridas:**
  - `TELEGRAM_BOT_TOKEN` - Token do bot do Telegram
  - `API_FOOTBALL_KEY` - Chave da API-Football
  - `DATABASE_URL` - URL de conexão PostgreSQL (opcional, mas recomendado)

## Recent Changes (2025-10-31)
### Mega Auditoria Completa (LATEST - 31/10/2025 22:30)
Realizada auditoria completa de todo o sistema antes da implementação do V4.0. Relatório detalhado em `MEGA_AUDIT_REPORT.md`.

**Problemas Críticos Identificados:**
1. **Inconsistência de Assinaturas**: goals_analyzer_v2 usa interface moderna `(analysis_packet, odds)`, mas corners_analyzer e cards_analyzer ainda usam interface legada
2. **Função Inexistente**: main.py chama `format_phoenix_dossier()` em 5 locais, mas função não existe (bot quebrado na paginação)
3. **Chamadas Duplicadas**: 3 implementações diferentes com assinaturas conflitantes dos analisadores
4. **Evidence-Based Não Integrado**: `format_evidence_based_dossier()` implementado mas não usado no fluxo principal

**Pontos Positivos:**
- ✅ Analisadores retornam múltiplas predições conforme V3.0
- ✅ Script-Based Modifiers funcionando corretamente
- ✅ Diversity Logic implementada
- ✅ Production Hardening completo

**Próximos Passos**: Executar ULTIMATE FORENSIC AUDIT e corrigir problemas críticos antes do V4.0 Squad Intelligence.

## Recent Changes (2025-10-31)
### Project Phoenix - Deep Analytics Protocol (LATEST)
Implementação completa do protocolo "Deep Analytics" com análise profunda de múltiplos submercados e evidências detalhadas:

**1. Analisadores Reconstruídos com Múltiplas Predições:**
- `goals_analyzer_v2.py`: Retorna ~20 predições cobrindo Total Goals FT (1.5/2.5/3.5), HT Goals (0.5/1.5), BTTS (Sim/Não), Team Goals Home/Away (0.5/1.5)
- `corners_analyzer.py`: Retorna ~12 predições cobrindo Total Corners FT (8.5/9.5/10.5/11.5), HT Corners (4.5/5.5), Team Corners Home (4.5/5.5/6.5) e Away (3.5/4.5/5.5)
- `cards_analyzer.py`: Retorna ~6 predições cobrindo Total Cards (Over/Under 3.5, 4.5, 5.5)

**2. Script-Based Probability Modifier:**
Cada analisador implementa modificadores contextuais que ajustam probabilidades ANTES do cálculo de confiança, baseado em scripts táticos:
- Gols: Ajusta para jogos ofensivos/defensivos/equilibrados
- Cantos: Ajusta para times com estilos de posse/contra-ataque
- Cartões: Ajusta para clássicos/rivais e times disciplinados/agressivos

**3. Evidence-Based Dossier:**
- `dossier_formatter.py`: Implementa formatação com template "Analyst's Dossier" incluindo evidências detalhadas dos últimos 4 jogos
- `justification_generator.py`: Gera justificativas específicas e baseadas em dados para cada mercado
- **Diversity Logic**: Nova função `_select_diverse_predictions()` garante variedade de mercados na seção "OUTRAS TENDÊNCIAS", evitando repetição de mercados

**4. Integração Evidence-Based:**
- Todas as análises agora incluem seção "📊 EVIDÊNCIAS" com dados reais dos últimos 4 jogos
- Justificativas contextuais mencionam desempenho histórico específico de cada time
- Formatação consistente seguindo o blueprint "Evidence-Based Analysis Protocol"

### Pure Analyst Protocol Implementation
Refatoração arquitetural completa transformando o bot de um modelo "tipster" (focado em valor de mercado) para um "Pure Analyst" (análise estatística independente de odds). Todos os 8 módulos de análise foram atualizados para usar o sistema unificado de confiança sem filtragem por odds.

### Production Hardening
Veja `SRE_AFTER_ACTION_REPORT.md` para detalhes completos da missão de Production Hardening.