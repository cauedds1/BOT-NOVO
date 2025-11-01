"""
🧠 ANÁLISE CONTEXTUAL PROFUNDA
================================
Sistema que pensa como um analista humano:
- Compara performance contra times fortes vs fracos
- Analisa bidirecionalmente (ataque vs defesa)
- Ajusta expectativas baseado no oponente de HOJE
- Gera narrativas persuasivas
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass

@dataclass
class ContextualInsight:
    """Representa um insight contextual específico"""
    mercado: str
    expectativa: float
    confianca: float
    narrativa: str
    evidencias: List[str]
    sugestao: Optional[str] = None

class ContextualAnalyzer:
    """
    Analista contextual que entende o CONTEXTO do jogo,
    não apenas médias brutas.
    """
    
    def __init__(self, master_data: Dict[str, Any]):
        """
        Args:
            master_data: Saída completa do Master Analyzer
        """
        self.master = master_data
        self.casa = master_data.get('time_casa', {})
        self.fora = master_data.get('time_fora', {})
        self.roteiro = master_data.get('roteiro_tatico', 'UNKNOWN')
        
    def analisar_cantos_contextual(self) -> ContextualInsight:
        """
        Analisa escanteios de forma CONTEXTUAL:
        - Meu ataque vs defesa deles
        - Ataque deles vs minha defesa
        - Ajusta por força do oponente
        """
        
        casa_nome = self.casa.get('nome', 'Casa')
        fora_nome = self.fora.get('nome', 'Fora')
        
        casa_cantos_feitos = self.casa.get('estatisticas', {}).get('cantos_feitos', 5.0)
        casa_cantos_cedidos = self.casa.get('estatisticas', {}).get('cantos_sofridos', 5.0)
        
        fora_cantos_feitos = self.fora.get('estatisticas', {}).get('cantos_feitos', 5.0)
        fora_cantos_cedidos = self.fora.get('estatisticas', {}).get('cantos_sofridos', 5.0)
        
        ultimos_casa = self.casa.get('ultimos_jogos', [])[:4]
        ultimos_fora = self.fora.get('ultimos_jogos', [])[:4]
        
        evidencias = []
        narrativa_partes = []
        
        casa_ataque_forte = casa_cantos_feitos >= 6.0
        fora_defesa_fraca = fora_cantos_cedidos >= 6.0
        
        if casa_ataque_forte and fora_defesa_fraca:
            narrativa_partes.append(
                f"{casa_nome} tem ataque ofensivo ({casa_cantos_feitos:.1f} cantos/jogo) "
                f"contra defesa que cede espaço ({fora_nome} permite {fora_cantos_cedidos:.1f} cantos/jogo)"
            )
            evidencias.append(f"✅ {casa_nome}: {casa_cantos_feitos:.1f} cantos feitos (ofensivo)")
            evidencias.append(f"⚠️ {fora_nome}: {fora_cantos_cedidos:.1f} cantos cedidos (defesa fraca)")
        
        elif casa_cantos_feitos < 4.5 and fora_cantos_cedidos < 4.5:
            narrativa_partes.append(
                f"{casa_nome} tem pouco volume ofensivo ({casa_cantos_feitos:.1f} cantos/jogo) "
                f"contra defesa sólida ({fora_nome} cede apenas {fora_cantos_cedidos:.1f} cantos/jogo)"
            )
            evidencias.append(f"❌ {casa_nome}: {casa_cantos_feitos:.1f} cantos feitos (baixo)")
            evidencias.append(f"✅ {fora_nome}: {fora_cantos_cedidos:.1f} cantos cedidos (defesa forte)")
        
        else:
            narrativa_partes.append(
                f"{casa_nome} faz {casa_cantos_feitos:.1f} cantos/jogo em média. "
                f"{fora_nome} cede {fora_cantos_cedidos:.1f} cantos/jogo"
            )
            evidencias.append(f"📊 {casa_nome}: {casa_cantos_feitos:.1f} cantos feitos")
            evidencias.append(f"📊 {fora_nome}: {fora_cantos_cedidos:.1f} cantos cedidos")
        
        expectativa_casa = (casa_cantos_feitos + fora_cantos_cedidos) / 2
        expectativa_fora = (fora_cantos_feitos + casa_cantos_cedidos) / 2
        expectativa_total = expectativa_casa + expectativa_fora
        
        if self.roteiro == 'DOMINIO_CASA':
            ajuste = 1.15
            narrativa_partes.append(
                f"\n\n🎬 Roteiro Tático: DOMÍNIO DA CASA\n"
                f"Time mandante deve pressionar muito, aumentando volume de cantos."
            )
            evidencias.append("🎬 Roteiro: Domínio da casa (+15% cantos)")
        elif self.roteiro == 'VISITANTE_FAVORITO':
            ajuste = 1.05
            narrativa_partes.append(
                f"\n\n🎬 Roteiro Tático: VISITANTE FAVORITO\n"
                f"Visitante deve controlar jogo, mas casa pode ter alguns cantos no desespero."
            )
            evidencias.append("🎬 Roteiro: Visitante favorito (+5% cantos)")
        elif self.roteiro == 'JOGO_TRUNCADO':
            ajuste = 0.85
            narrativa_partes.append(
                f"\n\n🎬 Roteiro Tático: JOGO TRUNCADO\n"
                f"Jogo fechado com poucos ataques, volume reduzido de cantos."
            )
            evidencias.append("🎬 Roteiro: Jogo truncado (-15% cantos)")
        else:
            ajuste = 1.0
        
        expectativa_ajustada = expectativa_total * ajuste
        
        narrativa_partes.append(
            f"\n\n💡 Expectativa: {expectativa_ajustada:.1f} cantos no TOTAL"
        )
        
        if expectativa_ajustada >= 10.5:
            sugestao = f"Over 10.5 Cantos Total"
            confianca = min(8.5, 6.0 + (expectativa_ajustada - 10.5) * 0.5)
        elif expectativa_ajustada <= 8.5:
            sugestao = f"Under 9.5 Cantos Total"
            confianca = min(8.5, 6.0 + (9.5 - expectativa_ajustada) * 0.5)
        else:
            sugestao = f"Over/Under 9.5 Cantos (expectativa {expectativa_ajustada:.1f})"
            confianca = 6.5
        
        narrativa_final = "\n".join(narrativa_partes)
        
        return ContextualInsight(
            mercado="cantos",
            expectativa=expectativa_ajustada,
            confianca=confianca,
            narrativa=narrativa_final,
            evidencias=evidencias,
            sugestao=sugestao
        )
    
    def analisar_cartoes_contextual(self) -> ContextualInsight:
        """
        Analisa cartões de forma CONTEXTUAL:
        - Estilo de jogo (faltoso vs disciplinado)
        - Importância da partida
        - Roteiro tático
        """
        
        casa_nome = self.casa.get('nome', 'Casa')
        fora_nome = self.fora.get('nome', 'Fora')
        
        casa_amarelos = self.casa.get('estatisticas', {}).get('cartoes_amarelos', 2.0)
        fora_amarelos = self.fora.get('estatisticas', {}).get('cartoes_amarelos', 2.0)
        
        casa_vermelhos = self.casa.get('estatisticas', {}).get('cartoes_vermelhos', 0.1)
        fora_vermelhos = self.fora.get('estatisticas', {}).get('cartoes_vermelhos', 0.1)
        
        total_casa = casa_amarelos + (casa_vermelhos * 2)
        total_fora = fora_amarelos + (fora_vermelhos * 2)
        
        evidencias = []
        narrativa_partes = []
        
        casa_faltoso = total_casa >= 3.5
        fora_faltoso = total_fora >= 3.5
        
        if casa_faltoso and fora_faltoso:
            narrativa_partes.append(
                f"AMBOS os times têm estilo de jogo físico:\n"
                f"• {casa_nome}: {total_casa:.1f} cartões/jogo\n"
                f"• {fora_nome}: {total_fora:.1f} cartões/jogo"
            )
            evidencias.append(f"⚠️ {casa_nome}: {total_casa:.1f} cartões/jogo (faltoso)")
            evidencias.append(f"⚠️ {fora_nome}: {total_fora:.1f} cartões/jogo (faltoso)")
        elif not casa_faltoso and not fora_faltoso:
            narrativa_partes.append(
                f"Ambos times são disciplinados:\n"
                f"• {casa_nome}: {total_casa:.1f} cartões/jogo\n"
                f"• {fora_nome}: {total_fora:.1f} cartões/jogo"
            )
            evidencias.append(f"✅ {casa_nome}: {total_casa:.1f} cartões/jogo (disciplinado)")
            evidencias.append(f"✅ {fora_nome}: {total_fora:.1f} cartões/jogo (disciplinado)")
        else:
            narrativa_partes.append(
                f"Contraste de estilos:\n"
                f"• {casa_nome}: {total_casa:.1f} cartões/jogo\n"
                f"• {fora_nome}: {total_fora:.1f} cartões/jogo"
            )
            evidencias.append(f"📊 {casa_nome}: {total_casa:.1f} cartões/jogo")
            evidencias.append(f"📊 {fora_nome}: {total_fora:.1f} cartões/jogo")
        
        expectativa_base = total_casa + total_fora
        
        if 'DECISIVO' in self.roteiro or 'MATA_MATA' in self.roteiro:
            ajuste = 1.25
            narrativa_partes.append(
                f"\n\n🎬 Roteiro: Jogo DECISIVO\n"
                f"Partida importante tende a ser mais nervosa e faltosa."
            )
            evidencias.append("🎬 Jogo decisivo (+25% cartões)")
        elif 'RIVALRY' in self.roteiro or 'CLASSICO' in self.roteiro:
            ajuste = 1.20
            narrativa_partes.append(
                f"\n\n🎬 Roteiro: CLÁSSICO/RIVALIDADE\n"
                f"Jogo quente com muito contato físico."
            )
            evidencias.append("🎬 Clássico/rivalidade (+20% cartões)")
        elif 'EQUILIBRADO' in self.roteiro:
            ajuste = 1.10
            narrativa_partes.append(
                f"\n\n🎬 Roteiro: Jogo equilibrado\n"
                f"Ambos buscam vitória, jogo tende a esquentar."
            )
            evidencias.append("🎬 Jogo equilibrado (+10% cartões)")
        else:
            ajuste = 1.0
        
        expectativa_ajustada = expectativa_base * ajuste
        
        narrativa_partes.append(
            f"\n\n💡 Expectativa: {expectativa_ajustada:.1f} cartões no TOTAL"
        )
        
        if expectativa_ajustada >= 5.5:
            sugestao = f"Over 5.5 Cartões Total"
            confianca = min(8.5, 6.0 + (expectativa_ajustada - 5.5) * 0.5)
        elif expectativa_ajustada <= 3.5:
            sugestao = f"Under 4.5 Cartões Total"
            confianca = min(8.5, 6.0 + (4.5 - expectativa_ajustada) * 0.5)
        else:
            sugestao = f"Over/Under 4.5 Cartões (expectativa {expectativa_ajustada:.1f})"
            confianca = 6.5
        
        narrativa_final = "\n".join(narrativa_partes)
        
        return ContextualInsight(
            mercado="cartoes",
            expectativa=expectativa_ajustada,
            confianca=confianca,
            narrativa=narrativa_final,
            evidencias=evidencias,
            sugestao=sugestao
        )
    
    def analisar_gols_contextual(self) -> ContextualInsight:
        """
        Analisa gols de forma CONTEXTUAL usando xG e eficiência
        """
        
        casa_nome = self.casa.get('nome', 'Casa')
        fora_nome = self.fora.get('nome', 'Fora')
        
        casa_gols = self.casa.get('estatisticas', {}).get('gols_marcados', 1.5)
        casa_sofridos = self.casa.get('estatisticas', {}).get('gols_sofridos', 1.5)
        
        fora_gols = self.fora.get('estatisticas', {}).get('gols_marcados', 1.5)
        fora_sofridos = self.fora.get('estatisticas', {}).get('gols_sofridos', 1.5)
        
        evidencias = []
        narrativa_partes = []
        
        casa_ataque_forte = casa_gols >= 2.0
        casa_defesa_fraca = casa_sofridos >= 1.8
        fora_ataque_forte = fora_gols >= 1.5
        fora_defesa_fraca = fora_sofridos >= 1.8
        
        if casa_ataque_forte and fora_defesa_fraca:
            narrativa_partes.append(
                f"✅ {casa_nome} ataca bem ({casa_gols:.1f} gols/jogo) "
                f"contra defesa vulnerável ({fora_nome} sofre {fora_sofridos:.1f} gols/jogo)"
            )
            evidencias.append(f"✅ {casa_nome}: {casa_gols:.1f} gols marcados")
            evidencias.append(f"⚠️ {fora_nome}: {fora_sofridos:.1f} gols sofridos")
        
        if fora_ataque_forte and casa_defesa_fraca:
            narrativa_partes.append(
                f"✅ {fora_nome} ataca bem ({fora_gols:.1f} gols/jogo) "
                f"contra defesa vulnerável ({casa_nome} sofre {casa_sofridos:.1f} gols/jogo)"
            )
            evidencias.append(f"✅ {fora_nome}: {fora_gols:.1f} gols marcados")
            evidencias.append(f"⚠️ {casa_nome}: {casa_sofridos:.1f} gols sofridos")
        
        expectativa_casa = (casa_gols + fora_sofridos) / 2
        expectativa_fora = (fora_gols + casa_sofridos) / 2
        expectativa_total = expectativa_casa + expectativa_fora
        
        if self.roteiro == 'TIME_EM_CHAMAS':
            ajuste = 1.20
            narrativa_partes.append(f"\n\n🎬 Roteiro: TIME EM CHAMAS - Expectativa de muitos gols")
            evidencias.append("🔥 Time em chamas (+20% gols)")
        elif self.roteiro == 'JOGO_TRUNCADO':
            ajuste = 0.80
            narrativa_partes.append(f"\n\n🎬 Roteiro: JOGO TRUNCADO - Poucos gols esperados")
            evidencias.append("🔒 Jogo truncado (-20% gols)")
        else:
            ajuste = 1.0
        
        expectativa_ajustada = expectativa_total * ajuste
        
        narrativa_partes.append(
            f"\n\n💡 Expectativa: {expectativa_ajustada:.1f} gols no TOTAL"
        )
        
        if expectativa_ajustada >= 3.0:
            sugestao = f"Over 2.5 Gols"
            confianca = min(8.5, 6.0 + (expectativa_ajustada - 3.0) * 0.8)
        elif expectativa_ajustada <= 2.0:
            sugestao = f"Under 2.5 Gols"
            confianca = min(8.5, 6.0 + (2.5 - expectativa_ajustada) * 0.8)
        else:
            sugestao = f"Over/Under 2.5 Gols (expectativa {expectativa_ajustada:.1f})"
            confianca = 6.5
        
        narrativa_final = "\n".join(narrativa_partes)
        
        return ContextualInsight(
            mercado="gols",
            expectativa=expectativa_ajustada,
            confianca=confianca,
            narrativa=narrativa_final,
            evidencias=evidencias,
            sugestao=sugestao
        )
