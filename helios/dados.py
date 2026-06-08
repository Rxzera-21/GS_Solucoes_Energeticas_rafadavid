"""
dados.py
========
Persistencia e leitura dos DADOS SIMULADOS em CSV.

Atende ao requisito "receber, interpretar e exibir dados simulados":
  - 'salvar_csv' grava a telemetria gerada em um arquivo.
  - 'carregar_csv' le esse arquivo de volta e devolve as linhas brutas,
    permitindo que o sistema RECEBA dados de uma fonte externa e os
    INTERPRETE pelo mesmo pipeline de analise.
"""
from __future__ import annotations

import csv
from typing import Iterator

from .modelos import Telemetria


def salvar_csv(historico: list[Telemetria], caminho: str) -> None:
    """Grava o historico de telemetria em um CSV legivel e flat."""
    if not historico:
        return
    ids = [m.id for m in historico[0].modulos]
    colunas = ["passo", "instante_min", "irradiancia_w_m2",
               "sinal_comunicacao_pct", "bateria_soc_pct",
               "geracao_total_w", "consumo_total_w", "balanco_w",
               "fracao_renovavel_pct", "indice_saude", "modo_operacao"]
    for i in ids:
        colunas += [f"{i}_temp_c", f"{i}_potencia_w", f"{i}_status"]

    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(colunas)
        for t in historico:
            linha = [t.passo, t.instante_min, t.irradiancia_w_m2,
                     t.sinal_comunicacao_pct, t.bateria_soc_pct,
                     t.geracao_total_w, t.consumo_total_w, t.balanco_w,
                     t.fracao_renovavel_pct, t.indice_saude,
                     t.modo_operacao.value]
            mapa = {m.id: m for m in t.modulos}
            for i in ids:
                m = mapa[i]
                linha += [round(m.temperatura_c, 1), m.potencia_w, m.status.value]
            w.writerow(linha)


def carregar_csv(caminho: str) -> Iterator[dict]:
    """Le um CSV de telemetria e devolve cada linha como dicionario."""
    with open(caminho, newline="", encoding="utf-8") as f:
        for linha in csv.DictReader(f):
            yield linha
