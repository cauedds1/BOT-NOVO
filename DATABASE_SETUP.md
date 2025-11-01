# 🔧 Configuração do Banco de Dados PostgreSQL

Este projeto requer um banco de dados PostgreSQL para funcionar completamente.

## Opções de Configuração

### Opção 1: Usar Replit Database (Recomendado)
1. No painel do Replit, vá em "Tools" → "Database"
2. Clique em "Create Database" e escolha PostgreSQL
3. Aguarde a provisão do banco de dados
4. A variável de ambiente `DATABASE_URL` será automaticamente configurada

### Opção 2: Banco de Dados Externo
1. Obtenha uma URL de conexão PostgreSQL (ex: de Neon, Supabase, etc.)
2. Adicione a variável de ambiente `DATABASE_URL` nos Secrets do Replit
3. Format: `postgresql://user:password@host:port/database`

## Após Configurar o DATABASE_URL

Execute o script SQL para criar as tabelas necessárias:

```bash
# Conecte-se ao seu banco de dados e execute:
psql $DATABASE_URL -f schema.sql
```

Ou copie e cole o conteúdo de `schema.sql` diretamente no console SQL do seu provedor de banco de dados.

## Tabelas Criadas

- **analises_jogos**: Cache de análises completas (otimiza uso da API)
- **daily_analyses**: Análises processadas em batch pelo sistema de fila assíncrona

## Verificação

Após criar as tabelas, reinicie o bot. Você deve ver a mensagem:
✅ `DATABASE_URL encontrado. Cache de análises habilitado.`

Se ver:
⚠️ `DATABASE_URL não encontrado. Cache de análises desabilitado.`

Significa que a variável de ambiente não está configurada corretamente.
