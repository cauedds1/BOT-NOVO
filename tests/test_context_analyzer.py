"""
Testes unitários básicos para o módulo de análise contextual.
Garante que funções críticas do sistema funcionam corretamente.
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from analysts.context_analyzer import get_quality_scores


class TestContextAnalyzer(unittest.TestCase):
    """Testes para o módulo context_analyzer"""
    
    def test_get_quality_scores_basic(self):
        """Testa cálculo básico de Quality Score"""
        stats_casa = {
            'games_played': 10,
            'wins': 7,
            'draws': 2,
            'losses': 1,
            'goals_for': 20,
            'goals_against': 8
        }
        
        stats_fora = {
            'games_played': 10,
            'wins': 4,
            'draws': 3,
            'losses': 3,
            'goals_for': 12,
            'goals_against': 12
        }
        
        liga_id = 39  # Premier League
        
        qsc_casa, qsc_fora = get_quality_scores(
            stats_casa=stats_casa,
            stats_fora=stats_fora,
            posicao_casa=3,
            posicao_fora=8,
            total_times=20,
            liga_id=liga_id
        )
        
        # Time da casa deve ter QSC maior (melhor posição, mais vitórias, melhor saldo de gols)
        self.assertGreater(qsc_casa, qsc_fora, 
                          "Time da casa deve ter Quality Score maior")
        
        # QSC deve estar entre 0 e 100
        self.assertGreaterEqual(qsc_casa, 0)
        self.assertLessEqual(qsc_casa, 100)
        self.assertGreaterEqual(qsc_fora, 0)
        self.assertLessEqual(qsc_fora, 100)
    
    def test_get_quality_scores_returns_tuple(self):
        """Testa se retorna tupla de 2 valores"""
        stats_casa = {'games_played': 5, 'wins': 3, 'draws': 1, 'losses': 1, 
                     'goals_for': 8, 'goals_against': 4}
        stats_fora = {'games_played': 5, 'wins': 2, 'draws': 2, 'losses': 1, 
                     'goals_for': 6, 'goals_against': 5}
        
        result = get_quality_scores(stats_casa, stats_fora, 5, 10, 20, 39)
        
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], (int, float))
        self.assertIsInstance(result[1], (int, float))


if __name__ == '__main__':
    unittest.main()
