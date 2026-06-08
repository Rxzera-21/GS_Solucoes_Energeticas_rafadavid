"""
alertas.py
==========
GERACAO AUTOMATICA DE ALERTAS.

O motor de alertas avalia o estado atual da missao contra limiares de
seguranca e emite alertas classificados por severidade (INFO, ATENCAO,
CRITICO). Tambem promove o estado de cada modulo (NOMINAL -> ATENCAO ->
CRITICO) com base na sua temperatura, atendendo ao requisito de
"interpretar e exibir" as condicoes operacionais.
"""
from __future__ import annotations

from .modelos import Alerta, Modulo, Severidade, Status, TipoModulo

# Limiares globais de energia/comunicacao
SOC_ATENCAO = 30.0
SOC_CRITICO = 15.0
SINAL_ATENCAO = 60.0
SINAL_CRITICO = 35.0


class MotorAlertas:
    """Avalia limiares e produz a lista de alertas do passo."""

    def avaliar(self, modulos: list[Modulo], soc_pct: float,
                balanco_w: float, sinal: float, autonomia_min: float,
                anomalias: list[str]) -> list[Alerta]:
        alertas: list[Alerta] = []

        # 1) Temperatura por modulo -> tambem define o status do modulo
        for m in modulos:
            if not m.ligado:
                m.status = Status.OFFLINE
                continue
            if m.temperatura_c >= m.temp_max_c:
                m.status = Status.CRITICO
                alertas.append(Alerta(
                    Severidade.CRITICO, m.id,
                    f"{m.nome}: superaquecimento ({m.temperatura_c:.1f}°C ≥ "
                    f"{m.temp_max_c:.0f}°C)",
                    "Reduzir carga / acionar controle térmico"))
            elif m.temperatura_c <= m.temp_min_c:
                m.status = Status.CRITICO
                alertas.append(Alerta(
                    Severidade.CRITICO, m.id,
                    f"{m.nome}: temperatura muito baixa "
                    f"({m.temperatura_c:.1f}°C ≤ {m.temp_min_c:.0f}°C)",
                    "Acionar aquecimento do módulo"))
            elif m.temperatura_c >= m.temp_ideal_c + 0.7 * (m.temp_max_c - m.temp_ideal_c):
                m.status = Status.ATENCAO
                alertas.append(Alerta(
                    Severidade.ATENCAO, m.id,
                    f"{m.nome}: temperatura elevada ({m.temperatura_c:.1f}°C)",
                    "Monitorar tendência térmica"))
            else:
                m.status = Status.NOMINAL

        # 2) Bateria / estado de carga
        if soc_pct <= SOC_CRITICO:
            alertas.append(Alerta(
                Severidade.CRITICO, "BATT",
                f"Carga da bateria crítica ({soc_pct:.1f}%)",
                "Cortar cargas não essenciais imediatamente"))
        elif soc_pct <= SOC_ATENCAO:
            alertas.append(Alerta(
                Severidade.ATENCAO, "BATT",
                f"Carga da bateria baixa ({soc_pct:.1f}%)",
                "Iniciar economia de energia"))

        # 3) Balanco energetico negativo (consumindo mais do que gera)
        if balanco_w < 0 and soc_pct <= SOC_ATENCAO:
            alertas.append(Alerta(
                Severidade.ATENCAO, "ENERGIA",
                f"Déficit energético de {abs(balanco_w):.0f} W com bateria baixa",
                "Reduzir consumo até equilibrar o balanço"))

        # 4) Autonomia projetada curta
        if autonomia_min != float("inf") and autonomia_min < 20:
            alertas.append(Alerta(
                Severidade.CRITICO, "ENERGIA",
                f"Autonomia projetada de apenas {autonomia_min:.0f} min",
                "Entrar em modo seguro"))

        # 5) Comunicacao
        if sinal <= SINAL_CRITICO:
            alertas.append(Alerta(
                Severidade.CRITICO, "COMM",
                f"Sinal de comunicação crítico ({sinal:.0f}%)",
                "Reorientar antena / aguardar janela de contato"))
        elif sinal <= SINAL_ATENCAO:
            alertas.append(Alerta(
                Severidade.ATENCAO, "COMM",
                f"Sinal de comunicação degradado ({sinal:.0f}%)",
                "Reduzir taxa de transmissão"))

        # 6) Anomalias detectadas pela IA viram alertas informativos
        for texto in anomalias:
            alertas.append(Alerta(
                Severidade.ATENCAO, "IA",
                f"Anomalia detectada: {texto}",
                "Investigar comportamento do sensor"))

        return alertas
