"""
simulador.py
============
Gera os DADOS SIMULADOS da missao espacial.

O simulador modela uma orbita baixa (LEO) onde a nave alterna entre periodos
iluminados pelo Sol e periodos de eclipse (sombra da Terra). Isso afeta
diretamente a geracao de energia renovavel (paineis solares) e, portanto, o
balanco energetico e o estado da bateria.

Conceitos de fisica/energia aplicados:
  - Irradiancia solar no espaco ~ 1361 W/m^2 (constante solar).
  - Potencia gerada = irradiancia (W/m^2) x area (m^2) x eficiencia.
  - Durante o eclipse a geracao cai a zero -> a missao depende da bateria.
"""
from __future__ import annotations

import math
import random

from .modelos import Modulo, Status, TipoModulo

# Constante solar aproximada no espaco proximo da Terra (W/m^2)
CONSTANTE_SOLAR = 1361.0


def frota_padrao() -> list[Modulo]:
    """Cria a configuracao padrao dos modulos da missao."""
    return [
        Modulo("PSOL", "Painéis Solares", TipoModulo.GERACAO,
               critico=False, consumo_nominal_w=0.0,
               temp_ideal_c=60, temp_max_c=120, temp_min_c=-100),
        Modulo("BATT", "Banco de Baterias", TipoModulo.ARMAZENAMENTO,
               critico=True, consumo_nominal_w=50.0,
               temp_ideal_c=25, temp_max_c=45, temp_min_c=0),
        Modulo("LIFE", "Suporte à Vida", TipoModulo.SUPORTE_VIDA,
               critico=True, consumo_nominal_w=800.0,
               temp_ideal_c=22, temp_max_c=30, temp_min_c=15),
        Modulo("OBC", "Computador de Bordo", TipoModulo.COMPUTADOR,
               critico=True, consumo_nominal_w=300.0,
               temp_ideal_c=30, temp_max_c=70, temp_min_c=-10),
        Modulo("COMM", "Comunicação", TipoModulo.COMUNICACAO,
               critico=False, consumo_nominal_w=500.0,
               temp_ideal_c=35, temp_max_c=75, temp_min_c=-20),
        Modulo("TERM", "Controle Térmico", TipoModulo.TERMICO,
               critico=True, consumo_nominal_w=450.0,
               temp_ideal_c=25, temp_max_c=60, temp_min_c=-5),
        Modulo("SCI", "Experimentos Científicos", TipoModulo.CIENTIFICO,
               critico=False, consumo_nominal_w=700.0,
               temp_ideal_c=20, temp_max_c=55, temp_min_c=-15),
    ]


class Simulador:
    """
    Produz leituras de telemetria passo a passo.

    Cada passo equivale a 1 minuto de missao. A classe nao calcula energia
    acumulada nem bateria (isso e feito pelo analisador) -- ela apenas entrega
    os "sensores brutos": irradiancia, sinal de comunicacao, temperaturas e
    potencias instantaneas de cada modulo.
    """

    PERIODO_ORBITAL_MIN = 90      # duracao de uma orbita completa (min)
    FRACAO_ECLIPSE = 0.38         # ~38% da orbita na sombra da Terra
    AREA_PAINEL_M2 = 12.0         # area total dos paineis
    EFICIENCIA_PAINEL = 0.30      # eficiencia dos paineis solares

    VIES_SOLAR_C = 1.5            # variacao termica entre sol e sombra (C)

    def __init__(self, modulos: list[Modulo], cenario: str = "nominal", seed: int = 42):
        self.modulos = modulos
        self.cenario = cenario
        self.rng = random.Random(seed)
        # fatores que cenarios podem alterar ao longo do tempo
        self._eficiencia_painel = self.EFICIENCIA_PAINEL
        # modulo com falha de refrigeracao (aquecimento descontrolado)
        self._falha_termica_id = "SCI" if cenario == "superaquecimento" else None
        self._inicio_falha_termica = 10

    # -- modelo orbital --------------------------------------------------
    def _irradiancia(self, passo: int) -> float:
        """Irradiancia solar (W/m^2) em funcao da fase orbital."""
        fase = (passo % self.PERIODO_ORBITAL_MIN) / self.PERIODO_ORBITAL_MIN
        eclipse = self.FRACAO_ECLIPSE
        # cenario de eclipse prolongado aumenta o tempo de sombra
        if self.cenario == "eclipse_prolongado":
            eclipse = 0.55
        if fase > (1 - eclipse):
            return 0.0  # nave na sombra da Terra
        # leve variacao do angulo de incidencia ao longo do trecho iluminado
        angulo = math.sin(math.pi * fase / (1 - eclipse))
        return CONSTANTE_SOLAR * (0.85 + 0.15 * angulo)

    def _aplicar_cenario(self, passo: int) -> None:
        """Injeta eventos criticos conforme o cenario escolhido."""
        if self.cenario == "falha_painel" and passo == 8:
            # degradacao subita dos paineis (perda de ~90% da eficiencia)
            self._eficiencia_painel = self.EFICIENCIA_PAINEL * 0.10

    # -- passo de simulacao ---------------------------------------------
    def passo(self, passo: int) -> tuple[float, float]:
        """
        Avanca a simulacao em um passo, atualizando 'self.modulos' in-place.

        Retorna (irradiancia_w_m2, sinal_comunicacao_pct).
        """
        self._aplicar_cenario(passo)
        irradiancia = self._irradiancia(passo)
        ensolarado = irradiancia > 0

        # 1) Geracao solar (potencia positiva no modulo de paineis)
        geracao = irradiancia * self.AREA_PAINEL_M2 * self._eficiencia_painel

        # 2) Sinal de comunicacao (queda em tempestade solar)
        sinal = 92 + self.rng.uniform(-4, 4)
        if self.cenario == "tempestade_solar" and 20 <= passo <= 45:
            sinal = 28 + self.rng.uniform(-8, 8)

        # 3) Atualiza cada modulo
        for m in self.modulos:
            if m.tipo == TipoModulo.GERACAO:
                m.temperatura_c = (75 if ensolarado else -65) + self.rng.uniform(-5, 5)
                m.potencia_w = round(geracao, 1)
                m.ligado = True
                continue

            if not m.ligado:
                m.potencia_w = 0.0
                # modulo desligado tende a temperatura ambiente do espaco
                m.temperatura_c += (m.temp_min_c - m.temperatura_c) * 0.1
                continue

            # consumo com pequena flutuacao realista (+-8%)
            consumo = m.consumo_nominal_w * (1 + self.rng.uniform(-0.08, 0.08))
            m.potencia_w = -round(consumo, 1)

            # --- temperatura ---
            if m.id == self._falha_termica_id and passo >= self._inicio_falha_termica:
                # falha de refrigeracao: temperatura sobe de forma descontrolada
                m.temperatura_c += 3.2 + self.rng.uniform(-0.5, 0.5)
            else:
                # operacao normal: temperatura tende ao ideal, com leve
                # influencia do Sol e ruido de sensor
                vies = self.VIES_SOLAR_C if ensolarado else -self.VIES_SOLAR_C
                alvo = m.temp_ideal_c + vies
                m.temperatura_c += (alvo - m.temperatura_c) * 0.3 + self.rng.uniform(-0.8, 0.8)

            # tempestade solar aquece a eletronica exposta
            if self.cenario == "tempestade_solar" and 20 <= passo <= 45 and m.id in ("COMM", "OBC"):
                m.temperatura_c += 3.0

        return round(irradiancia, 1), round(max(0.0, min(100.0, sinal)), 1)
