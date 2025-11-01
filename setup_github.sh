
#!/bin/bash

echo "🔧 Configurando repositório Git..."

# Inicializar repositório se ainda não existe
if [ ! -d .git ]; then
    git init
    echo "✅ Repositório Git inicializado"
else
    echo "✅ Repositório Git já existe"
fi

# Verificar se há mudanças para commitar
if [ -n "$(git status --porcelain)" ]; then
    echo "📦 Adicionando arquivos ao Git..."
    git add .
    
    echo "💾 Criando commit..."
    git commit -m "feat: Upload completo do Bot de Análise de Apostas Esportivas

- Sistema de análise estatística avançada
- Integração com API-Football
- Cache inteligente com PostgreSQL
- Pure Analyst Protocol implementado
- Production-ready com SRE hardening (9/10 score)
- Multiple analyzers: Goals, Corners, BTTS, Cards, Handicaps, Shots
- Evidence-based dossier formatting
- Telegram bot interface completa"
    
    echo "✅ Commit criado com sucesso!"
else
    echo "ℹ️ Nenhuma mudança para commitar"
fi

echo ""
echo "📋 Próximos passos:"
echo ""
echo "1. Crie um novo repositório no GitHub: https://github.com/new"
echo "2. NÃO inicialize com README, .gitignore ou licença"
echo "3. Copie a URL do repositório (formato: https://github.com/seu-usuario/nome-repo.git)"
echo "4. Execute os comandos abaixo:"
echo ""
echo "   git remote add origin https://github.com/SEU-USUARIO/NOME-REPO.git"
echo "   git branch -M main"
echo "   git push -u origin main"
echo ""
echo "💡 Dica: Para autenticar, use um Personal Access Token ao invés de senha"
echo "   Crie um token em: https://github.com/settings/tokens"
echo ""
