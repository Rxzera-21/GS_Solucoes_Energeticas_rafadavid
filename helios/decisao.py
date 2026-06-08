"""
decisao.py
==========
TOMADA DE DECISAO BASICA e RESPOSTAS AUTOMATIZADAS.

A partir dos alertas e do estado energetico, o motor de decisao aplica regras
logicas para responder automaticamente a situacoes criticas. As acoes
fecham o ciclo de controle: elas alteram o estado dos modulos (desligando
cargas nao essenciais, por exemplo), o que afeta a proxima leitura.

Estrategias implementadas:
  - Economia de energia: desliga modulos NAO criticos quando a bateria cai.
  - Modo seguro: diante de multiplas falhas criticas, mantem apenas os
    sistemas essenciais (suporte a vida, computador, controle termico).
  - Resposta termica: alivia carga de modulos em superaquecimento.
  - Religamento: ao normalizar a energia, religa cargas que foram cortadas.
"""
from __future__ import annotations

from .modelos import Acao, Modulo, ModoOperacao, Severidade, Status

SOC_CORTAR = 30.0       # abaixo disso, comeca o corte de cargas
SOC_RELIGAR = 55.0      # acima disso, religa cargas cortadas
# ordem de corte: cargas menos essenciais primeiro
PRIORIDADE_CORTE = ["SCI", "COMM"]


class MotorDecisao:
    """Decide e aplica respostas automatizadas sobre os modulos."""

    def __init__(self):
        # modulos desligados por falha termica nao devem ser religados
        # automaticamente pela regra de energia (evita reincidencia da falha).
        self.desligado_termico: set[str] = set()

    def decidir(self, modulos: list[Modulo], soc_pct: float,
                alertas: list, autonomia_min: float) -> tuple[list[Acao], ModoOperacao]:
        acoes: list[Acao] = []
        por_id = {m.id: m for m in modulos}
        criticos = [a for a in alertas if a.severidade == Severidade.CRITICO]

        # 1) Resposta termica: modulo em estado CRITICO por temperatura alta
        for m in modulos:
            if m.ligado and m.status == Status.CRITICO and m.temperatura_c >= m.temp_max_c:
                if not m.critico:
                    m.ligado = False
                    self.desligado_termico.add(m.id)
                    acoes.append(Acao(
                        f"Desligar {m.nome} por superaquecimento",
                        m.id, "Temperatura acima do limite máximo"))
                else:
                    # modulo essencial: reduz consumo em vez de desligar
                    m.consumo_nominal_w *= 0.85
                    acoes.append(Acao(
                        f"Reduzir carga de {m.nome} em 15%",
                        m.id, "Aliviar geração de calor sem desligar sistema essencial"))

        # 2) Decisao energetica baseada no SoC
        modo = ModoOperacao.NORMAL
        if soc_pct <= SOC_CORTAR:
            modo = ModoOperacao.ECONOMIA
            for mid in PRIORIDADE_CORTE:
                m = por_id.get(mid)
                if m and m.ligado and not m.critico:
                    m.ligado = False
                    acoes.append(Acao(
                        f"Desligar {m.nome} (corte de carga)",
                        mid, f"Bateria em {soc_pct:.0f}% — preservar energia"))

        # 3) Modo seguro: muitas falhas criticas ou autonomia muito curta
        autonomia_curta = autonomia_min != float("inf") and autonomia_min < 20
        if len(criticos) >= 3 or autonomia_curta:
            modo = ModoOperacao.SEGURO
            for m in modulos:
                if m.ligado and not m.critico:
                    m.ligado = False
                    acoes.append(Acao(
                        f"Desligar {m.nome} (modo seguro)",
                        m.id, "Múltiplas condições críticas — preservar sistemas essenciais"))

        # 4) Religamento quando a energia se normaliza
        if soc_pct >= SOC_RELIGAR and modo == ModoOperacao.NORMAL:
            for m in modulos:
                if not m.ligado and not m.critico and m.id not in self.desligado_termico:
                    m.ligado = True
                    acoes.append(Acao(
                        f"Religar {m.nome}",
                        m.id, f"Bateria recuperada ({soc_pct:.0f}%) — retomar operação"))

        return acoes, modo
