"""
energia.py
==========
Analise de ENERGIA, POTENCIA, ENERGIAS RENOVAVEIS e SUSTENTABILIDADE.

Este modulo concentra os conceitos de fisica da disciplina e e o coracao da
aderencia ao tema "Solucoes em Energias Renovaveis e Sustentaveis".

Formulas usadas:
  - Potencia (W): valor instantaneo medido em cada modulo.
  - Energia (Wh): E = P x t  -> potencia integrada no tempo.
  - Balanco energetico: geracao - consumo. Se negativo, a bateria descarrega.
  - Estado de carga da bateria (SoC): atualizado pela energia liquida.
  - Fracao renovavel: % do consumo atendido diretamente pela geracao solar.
  - CO2 evitado: comparacao com um gerador a diesel equivalente.
"""
from __future__ import annotations

from .modelos import Modulo, TipoModulo

# Parametros fisicos da bateria
CAPACIDADE_BATERIA_WH = 4500.0
# Fator de emissao de um gerador a diesel equivalente (kg de CO2 por kWh)
FATOR_CO2_DIESEL = 0.85


class AnalisadorEnergia:
    """
    Recebe o estado dos modulos a cada passo e calcula todos os indicadores
    energeticos e de sustentabilidade, mantendo os acumulados da missao.
    """

    def __init__(self, passo_min: float = 1.0, soc_inicial_pct: float = 95.0):
        self.passo_min = passo_min                  # duracao de cada passo (min)
        self.passo_h = passo_min / 60.0             # em horas (para Wh)
        self.soc_pct = soc_inicial_pct
        self.energia_gerada_acum_wh = 0.0
        self.energia_consumida_acum_wh = 0.0

    @property
    def energia_bateria_wh(self) -> float:
        return self.soc_pct / 100.0 * CAPACIDADE_BATERIA_WH

    def analisar(self, modulos: list[Modulo]) -> dict:
        """Calcula os indicadores energeticos para o passo atual."""
        geracao = sum(m.potencia_w for m in modulos if m.potencia_w > 0)
        consumo = sum(-m.potencia_w for m in modulos if m.potencia_w < 0)
        balanco = geracao - consumo  # positivo = sobra (carrega bateria)

        # Energia (Wh) movimentada neste passo: E = P x t
        energia_gerada_wh = geracao * self.passo_h
        energia_consumida_wh = consumo * self.passo_h
        self.energia_gerada_acum_wh += energia_gerada_wh
        self.energia_consumida_acum_wh += energia_consumida_wh

        # Atualiza o estado de carga da bateria (SoC) pela energia liquida
        energia_liquida_wh = balanco * self.passo_h
        nova_energia = self.energia_bateria_wh + energia_liquida_wh
        nova_energia = max(0.0, min(CAPACIDADE_BATERIA_WH, nova_energia))
        self.soc_pct = nova_energia / CAPACIDADE_BATERIA_WH * 100.0

        # Autonomia: por quanto tempo a bateria sustenta o consumo atual
        # se nao houver geracao (cenario de eclipse).
        if consumo > 0:
            autonomia_h = self.energia_bateria_wh / consumo
            autonomia_min = autonomia_h * 60.0
        else:
            autonomia_min = float("inf")

        # Fracao renovavel: parte do consumo atendida direto pelo Sol.
        if consumo > 0:
            fracao_renovavel = min(geracao, consumo) / consumo * 100.0
        else:
            fracao_renovavel = 100.0

        # Sustentabilidade: toda energia gerada e renovavel (solar). Comparamos
        # com um gerador a diesel para estimar o CO2 evitado.
        co2_evitado = self.energia_gerada_acum_wh / 1000.0 * FATOR_CO2_DIESEL

        return {
            "geracao_total_w": round(geracao, 1),
            "consumo_total_w": round(consumo, 1),
            "balanco_w": round(balanco, 1),
            "bateria_soc_pct": round(self.soc_pct, 1),
            "bateria_energia_wh": round(self.energia_bateria_wh, 1),
            "autonomia_min": autonomia_min,
            "fracao_renovavel_pct": round(fracao_renovavel, 1),
            "energia_gerada_acum_wh": round(self.energia_gerada_acum_wh, 1),
            "energia_consumida_acum_wh": round(self.energia_consumida_acum_wh, 1),
            "co2_evitado_kg": round(co2_evitado, 3),
        }
