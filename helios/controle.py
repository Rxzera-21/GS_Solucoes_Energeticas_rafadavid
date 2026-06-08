"""
controle.py
===========
Orquestrador central da missao (Centro de Controle HELIOS).

Conecta todos os componentes em um pipeline claro, executado a cada passo:

    simulador  ->  energia  ->  IA  ->  alertas  ->  decisao
       (dados)    (calculo)   (previsao) (regras)   (resposta)

Produz, a cada passo, um snapshot 'Telemetria' com TUDO ja interpretado,
pronto para ser exibido pelo painel (CLI ou web).
"""
from __future__ import annotations

from .alertas import MotorAlertas
from .decisao import MotorDecisao
from .energia import AnalisadorEnergia
from .ia_monitor import MonitorIA
from .modelos import Severidade, Telemetria
from .simulador import Simulador, frota_padrao


class ControleMissao:
    """Cola todos os modulos e gera os snapshots de telemetria."""

    def __init__(self, cenario: str = "nominal", seed: int = 42,
                 passo_min: float = 1.0):
        self.modulos = frota_padrao()
        self.simulador = Simulador(self.modulos, cenario=cenario, seed=seed)
        self.energia = AnalisadorEnergia(passo_min=passo_min)
        self.ia = MonitorIA()
        self.alertas = MotorAlertas()
        self.decisao = MotorDecisao()
        self.passo_min = passo_min

    def passo(self, n: int) -> Telemetria:
        """Executa um passo completo do pipeline e devolve a telemetria."""
        # 1) DADOS — simulador atualiza modulos in-place
        irradiancia, sinal = self.simulador.passo(n)

        # 2) ENERGIA — calcula potencia, energia, bateria e sustentabilidade
        en = self.energia.analisar(self.modulos)

        # 3) IA — anomalias e previsao de tempo ate SoC critico
        anomalias = self.ia.detectar_anomalias(self.modulos, sinal)
        previsao = self.ia.prever_tempo_critico(en["bateria_soc_pct"], self.passo_min)

        # 4) ALERTAS — regras de seguranca (tambem define status dos modulos)
        alertas = self.alertas.avaliar(
            self.modulos, en["bateria_soc_pct"], en["balanco_w"],
            sinal, en["autonomia_min"], anomalias)

        # 5) DECISAO — respostas automatizadas (alteram os modulos)
        acoes, modo = self.decisao.decidir(
            self.modulos, en["bateria_soc_pct"], alertas, en["autonomia_min"])

        n_criticos = sum(1 for a in alertas if a.severidade == Severidade.CRITICO)
        saude = self.ia.indice_saude(
            en["bateria_soc_pct"], en["fracao_renovavel_pct"], sinal, n_criticos)

        return Telemetria(
            passo=n,
            instante_min=round(n * self.passo_min, 1),
            irradiancia_w_m2=irradiancia,
            sinal_comunicacao_pct=sinal,
            modulos=[m.snapshot() for m in self.modulos],
            anomalias=anomalias,
            previsao_soc_min=previsao,
            alertas=alertas,
            acoes=acoes,
            modo_operacao=modo,
            indice_saude=saude,
            **en,
        )

    def executar(self, passos: int) -> list[Telemetria]:
        """Roda a missao inteira e retorna a lista de snapshots."""
        return [self.passo(n) for n in range(passos)]
