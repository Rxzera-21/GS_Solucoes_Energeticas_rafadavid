"""
ia_monitor.py
=============
INTELIGENCIA ARTIFICIAL INTRODUTORIA.

Aqui aplicamos duas tecnicas simples, porem genuinas, de IA/estatistica:

1) Deteccao de anomalias por escore-z (z-score) sobre janela movel:
   para cada sensor, mantemos uma janela das ultimas leituras e medimos
   quao distante (em desvios-padrao) o valor atual esta da media recente.
   Se |z| ultrapassa um limiar, o comportamento e considerado anomalo.
   E uma forma de deteccao NAO supervisionada de outliers.

2) Previsao por regressao linear (minimos quadrados):
   ajustamos uma reta ao historico recente do estado de carga da bateria
   (SoC) para PREVER em quanto tempo ela atingira o nivel critico. Isso
   permite uma resposta proativa, antes da falha acontecer.

3) Indice de saude da missao: combinacao ponderada de indicadores que
   resume a "saude" geral em um numero de 0 a 100.
"""
from __future__ import annotations

from collections import deque
from typing import Optional

import numpy as np

from .modelos import Modulo, TipoModulo


class MonitorIA:
    """Detector de anomalias + previsor de tendencia da bateria."""

    def __init__(self, janela: int = 16, limiar_z: float = 4.5,
                 soc_critico_pct: float = 15.0):
        self.janela = janela
        self.limiar_z = limiar_z
        self.soc_critico = soc_critico_pct
        # historicos por sensor (uma fila por chave)
        self._hist: dict[str, deque] = {}
        self._hist_soc: deque = deque(maxlen=janela)

    # -- deteccao de anomalias ------------------------------------------
    def _registrar(self, chave: str, valor: float) -> Optional[float]:
        """Adiciona valor ao historico e devolve o escore-z (ou None)."""
        fila = self._hist.setdefault(chave, deque(maxlen=self.janela))
        z = None
        if len(fila) >= max(5, self.janela // 2):
            arr = np.array(fila, dtype=float)
            media, desvio = arr.mean(), arr.std()
            if desvio > 1e-6:
                z = (valor - media) / desvio
        fila.append(valor)
        return z

    def detectar_anomalias(self, modulos: list[Modulo],
                           sinal_comunicacao: float) -> list[str]:
        """Verifica todos os sensores e retorna mensagens de anomalia."""
        anomalias: list[str] = []

        # temperaturas de cada modulo
        for m in modulos:
            # o painel solar oscila naturalmente entre sol e eclipse:
            # essa variacao e esperada e nao deve gerar anomalia.
            if m.tipo == TipoModulo.GERACAO:
                continue
            z = self._registrar(f"temp_{m.id}", m.temperatura_c)
            if z is not None and abs(z) > self.limiar_z:
                tendencia = "alta" if z > 0 else "baixa"
                anomalias.append(
                    f"Temperatura anômala em {m.nome} "
                    f"(desvio {z:+.1f}σ, tendência de {tendencia})"
                )
            # consumo (apenas modulos que consomem)
            if m.potencia_w < 0:
                z_c = self._registrar(f"pot_{m.id}", abs(m.potencia_w))
                if z_c is not None and abs(z_c) > self.limiar_z:
                    anomalias.append(
                        f"Consumo anômalo em {m.nome} (desvio {z_c:+.1f}σ)"
                    )

        # sinal de comunicacao
        z_s = self._registrar("sinal", sinal_comunicacao)
        if z_s is not None and z_s < -self.limiar_z:
            anomalias.append(
                f"Queda anômala no sinal de comunicação (desvio {z_s:+.1f}σ)"
            )
        return anomalias

    # -- previsao da bateria --------------------------------------------
    def prever_tempo_critico(self, soc_pct: float,
                             passo_min: float) -> Optional[float]:
        """
        Ajusta uma reta (minimos quadrados) ao SoC recente e estima em
        quantos minutos ele atingira o nivel critico. Retorna None se a
        bateria nao estiver descarregando.
        """
        self._hist_soc.append(soc_pct)
        if len(self._hist_soc) < 5:
            return None

        y = np.array(self._hist_soc, dtype=float)
        x = np.arange(len(y), dtype=float)
        # regressao linear: y = a*x + b (coef[0]=a inclinacao, coef[1]=b)
        coef = np.polyfit(x, y, 1)
        inclinacao = coef[0]  # variacao de SoC por passo

        if inclinacao >= -1e-3:   # estavel ou carregando -> sem risco
            return None
        passos_ate_critico = (self.soc_critico - soc_pct) / inclinacao
        if passos_ate_critico <= 0:
            return 0.0
        return round(passos_ate_critico * passo_min, 1)

    # -- indice de saude -------------------------------------------------
    @staticmethod
    def indice_saude(soc_pct: float, fracao_renovavel: float,
                     sinal: float, n_alertas_criticos: int) -> float:
        """
        Combina indicadores em um escore 0-100 (quanto maior, melhor).
        Pesos: bateria 40%, renovavel 25%, comunicacao 20%, penalidade por
        alertas criticos.
        """
        base = (0.40 * soc_pct
                + 0.25 * fracao_renovavel
                + 0.20 * sinal
                + 0.15 * 100)        # margem operacional base
        penalidade = 18.0 * n_alertas_criticos
        return round(max(0.0, min(100.0, base - penalidade)), 1)
