"""
main.py
=======
Painel de monitoramento da missao em tempo real (interface de terminal).

Uso:
    python main.py                         # cenario nominal, 120 passos
    python main.py --cenario falha_painel  # simula falha nos paineis solares
    python main.py --cenario superaquecimento
    python main.py --cenario tempestade_solar
    python main.py --cenario eclipse_prolongado
    python main.py --passos 90 --velocidade 0.08
    python main.py --gerar-csv data/telemetria_exemplo.csv   # gera dataset
    python main.py --fonte csv --arquivo data/telemetria_exemplo.csv  # le dataset

Cenarios disponiveis:
    nominal | falha_painel | eclipse_prolongado | superaquecimento | tempestade_solar
"""
from __future__ import annotations

import argparse
import time

from rich.align import Align
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from helios import ControleMissao, ModoOperacao, Severidade, Status, Telemetria
from helios.dados import carregar_csv, salvar_csv

console = Console()

CORES_STATUS = {
    Status.NOMINAL: "bright_green",
    Status.ATENCAO: "yellow",
    Status.CRITICO: "bright_red",
    Status.OFFLINE: "grey50",
}
CORES_SEVERIDADE = {
    Severidade.INFO: "cyan",
    Severidade.ATENCAO: "yellow",
    Severidade.CRITICO: "bright_red",
}
CORES_MODO = {
    ModoOperacao.NORMAL: "bright_green",
    ModoOperacao.ECONOMIA: "yellow",
    ModoOperacao.SEGURO: "bright_red",
}


def barra(pct: float, largura: int = 18) -> Text:
    """Desenha uma barra de progresso textual colorida."""
    pct = max(0.0, min(100.0, pct))
    cheio = int(round(pct / 100 * largura))
    cor = "bright_green" if pct > 50 else "yellow" if pct > 25 else "bright_red"
    t = Text()
    t.append("█" * cheio, style=cor)
    t.append("░" * (largura - cheio), style="grey42")
    t.append(f" {pct:5.1f}%", style=cor)
    return t


def cabecalho(t: Telemetria) -> Panel:
    sol = "☀ SOL" if t.irradiancia_w_m2 > 0 else "🌑 ECLIPSE"
    cor_modo = CORES_MODO[t.modo_operacao]
    txt = Text()
    txt.append("  HELIOS ", style="bold white on blue")
    txt.append(f"  Missão Espacial Experimental    ", style="bold")
    txt.append(f"T+{t.instante_min:>6.0f} min", style="cyan")
    txt.append(f"   |   {sol}", style="bold yellow")
    txt.append(f"   |   MODO: ", style="bold")
    txt.append(t.modo_operacao.value, style=f"bold {cor_modo}")
    txt.append(f"   |   Saúde: ", style="bold")
    cor_s = "bright_green" if t.indice_saude > 60 else "yellow" if t.indice_saude > 35 else "bright_red"
    txt.append(f"{t.indice_saude:.0f}/100", style=f"bold {cor_s}")
    return Panel(Align.center(txt), border_style=cor_modo)


def tabela_modulos(t: Telemetria) -> Panel:
    tab = Table(expand=True, show_edge=False, header_style="bold cyan")
    tab.add_column("Módulo")
    tab.add_column("Status", justify="center")
    tab.add_column("Temp °C", justify="right")
    tab.add_column("Potência W", justify="right")
    for m in t.modulos:
        cor = CORES_STATUS[m.status]
        pot = f"{m.potencia_w:+.0f}"
        pot_estilo = "bright_green" if m.potencia_w > 0 else "white"
        estado = m.status.value if m.ligado else "OFFLINE"
        tab.add_row(
            Text(m.nome, style="bold" if m.critico else ""),
            Text(estado, style=cor),
            Text(f"{m.temperatura_c:.1f}", style=cor),
            Text(pot, style=pot_estilo),
        )
    return Panel(tab, title="[bold]Módulos da Operação", border_style="blue")


def painel_energia(t: Telemetria) -> Panel:
    g = Table.grid(padding=(0, 1))
    g.add_column(justify="left")
    g.add_column(justify="left")
    g.add_row("Bateria (SoC):", barra(t.bateria_soc_pct))
    g.add_row("Geração solar:", Text(f"{t.geracao_total_w:>8.0f} W", style="bright_green"))
    g.add_row("Consumo total:", Text(f"{t.consumo_total_w:>8.0f} W", style="white"))
    cor_b = "bright_green" if t.balanco_w >= 0 else "bright_red"
    g.add_row("Balanço:", Text(f"{t.balanco_w:>+8.0f} W", style=cor_b))
    aut = "∞" if t.autonomia_min == float("inf") else f"{t.autonomia_min:.0f} min"
    g.add_row("Autonomia:", Text(aut, style="cyan"))
    g.add_row("% Renovável:", Text(f"{t.fracao_renovavel_pct:.0f}%", style="bright_green"))
    g.add_row("CO₂ evitado:", Text(f"{t.co2_evitado_kg:.2f} kg", style="bright_green"))
    return Panel(g, title="[bold]Energia & Sustentabilidade", border_style="green")


def painel_ia(t: Telemetria) -> Panel:
    linhas = []
    if t.previsao_soc_min is not None:
        cor = "bright_red" if t.previsao_soc_min < 30 else "yellow"
        linhas.append(Text(f"⏳ Previsão: bateria crítica em ~{t.previsao_soc_min:.0f} min",
                           style=cor))
    else:
        linhas.append(Text("✓ Bateria estável / em recarga", style="bright_green"))
    if t.anomalias:
        for a in t.anomalias[:4]:
            linhas.append(Text(f"⚠ {a}", style="magenta"))
    else:
        linhas.append(Text("✓ Nenhuma anomalia detectada", style="grey62"))
    return Panel(Group(*linhas), title="[bold]IA — Anomalias & Previsão", border_style="magenta")


def painel_alertas(t: Telemetria) -> Panel:
    if not t.alertas:
        corpo = Align.center(Text("✓ Sem alertas ativos", style="bright_green"))
    else:
        tab = Table.grid(padding=(0, 1))
        tab.add_column()
        tab.add_column()
        for a in sorted(t.alertas, key=lambda x: list(Severidade).index(x.severidade), reverse=True)[:6]:
            cor = CORES_SEVERIDADE[a.severidade]
            tab.add_row(Text(f"[{a.severidade.value}]", style=f"bold {cor}"),
                        Text(a.mensagem, style=cor))
        corpo = tab
    return Panel(corpo, title=f"[bold]Alertas ({len(t.alertas)})", border_style="red")


def painel_acoes(t: Telemetria) -> Panel:
    if not t.acoes:
        corpo = Align.center(Text("— nenhuma ação automática neste instante —", style="grey50"))
    else:
        tab = Table.grid(padding=(0, 1))
        tab.add_column()
        for a in t.acoes:
            tab.add_row(Text(f"▶ {a.descricao}", style="bold cyan"))
            tab.add_row(Text(f"   ↳ {a.justificativa}", style="grey62"))
        corpo = tab
    return Panel(corpo, title="[bold]Decisões Automatizadas", border_style="cyan")


def montar(t: Telemetria) -> Group:
    topo = Table.grid(expand=True)
    topo.add_column(ratio=3)
    topo.add_column(ratio=2)
    topo.add_row(tabela_modulos(t), painel_energia(t))
    meio = Table.grid(expand=True)
    meio.add_column(ratio=1)
    meio.add_column(ratio=1)
    meio.add_row(painel_alertas(t), painel_ia(t))
    return Group(cabecalho(t), topo, meio, painel_acoes(t))


def resumo_final(historico: list[Telemetria]) -> None:
    crit = sum(1 for t in historico for a in t.alertas if a.severidade == Severidade.CRITICO)
    aten = sum(1 for t in historico for a in t.alertas if a.severidade == Severidade.ATENCAO)
    acoes = sum(len(t.acoes) for t in historico)
    ult = historico[-1]
    tab = Table(title="Resumo da Missão", border_style="blue", show_header=False)
    tab.add_column(style="bold")
    tab.add_column()
    tab.add_row("Passos simulados", str(len(historico)))
    tab.add_row("Alertas críticos / atenção", f"{crit} / {aten}")
    tab.add_row("Ações automatizadas", str(acoes))
    tab.add_row("Energia renovável gerada", f"{ult.energia_gerada_acum_wh/1000:.2f} kWh")
    tab.add_row("Energia consumida", f"{ult.energia_consumida_acum_wh/1000:.2f} kWh")
    tab.add_row("CO₂ evitado (vs. diesel)", f"{ult.co2_evitado_kg:.2f} kg")
    tab.add_row("SoC final da bateria", f"{ult.bateria_soc_pct:.1f}%")
    tab.add_row("Modo final", ult.modo_operacao.value)
    console.print(tab)


# ---------------------------------------------------------------------------
# Execucao
# ---------------------------------------------------------------------------
def rodar_simulador(args) -> list[Telemetria]:
    cm = ControleMissao(cenario=args.cenario, seed=args.seed)
    historico: list[Telemetria] = []
    with Live(console=console, refresh_per_second=20, screen=False) as live:
        for n in range(args.passos):
            t = cm.passo(n)
            historico.append(t)
            live.update(montar(t))
            time.sleep(args.velocidade)
    return historico


def rodar_csv(args) -> None:
    """Le um CSV de telemetria e exibe as leituras interpretadas."""
    console.print(f"[bold cyan]Lendo telemetria de {args.arquivo}[/]\n")
    tab = Table(title="Telemetria recebida (CSV)", border_style="blue")
    for col in ["Passo", "T+min", "Irrad.", "Sinal%", "SoC%", "Ger.W", "Cons.W", "Modo"]:
        tab.add_column(col, justify="right")
    linhas = list(carregar_csv(args.arquivo))
    for r in linhas:
        soc = float(r["bateria_soc_pct"])
        cor = "bright_green" if soc > 50 else "yellow" if soc > 25 else "bright_red"
        tab.add_row(r["passo"], r["instante_min"], r["irradiancia_w_m2"],
                    r["sinal_comunicacao_pct"], Text(f"{soc:.1f}", style=cor),
                    r["geracao_total_w"], r["consumo_total_w"], r["modo_operacao"])
    console.print(tab)
    console.print(f"\n[green]{len(linhas)} leituras interpretadas e exibidas.[/]")


def main() -> None:
    p = argparse.ArgumentParser(description="HELIOS — Monitoramento Energético de Missão Espacial")
    p.add_argument("--cenario", default="nominal",
                   choices=["nominal", "falha_painel", "eclipse_prolongado",
                            "superaquecimento", "tempestade_solar"])
    p.add_argument("--passos", type=int, default=120)
    p.add_argument("--velocidade", type=float, default=0.06, help="segundos entre passos")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--fonte", default="simulador", choices=["simulador", "csv"])
    p.add_argument("--arquivo", default="data/telemetria_exemplo.csv")
    p.add_argument("--gerar-csv", metavar="CAMINHO",
                   help="gera um CSV de telemetria e encerra")
    args = p.parse_args()

    if args.gerar_csv:
        cm = ControleMissao(cenario=args.cenario, seed=args.seed)
        hist = cm.executar(args.passos)
        salvar_csv(hist, args.gerar_csv)
        console.print(f"[green]CSV gerado:[/] {args.gerar_csv} ({len(hist)} leituras)")
        return

    if args.fonte == "csv":
        rodar_csv(args)
        return

    console.print(f"[bold]Iniciando monitoramento — cenário: [cyan]{args.cenario}[/][/]\n")
    historico = rodar_simulador(args)
    console.print()
    resumo_final(historico)


if __name__ == "__main__":
    main()
