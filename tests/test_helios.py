"""
test_helios.py
==============
Testes automatizados do HELIOS (pytest).

Cobrem as quatro responsabilidades centrais do sistema:
  1. Monitoramento de dados simulados  (simulador + energia)
  2. Geração de alertas                (alertas)
  3. Tomada de decisão automatizada    (decisao)
  4. IA introdutória                   (anomalias + previsão + saúde)
Além de um teste de ponta a ponta (pipeline completo via ControleMissao)
e da persistência em CSV.

Executar:
    pytest -v
"""
from __future__ import annotations

import math

import pytest

from helios.alertas import MotorAlertas
from helios.controle import ControleMissao
from helios.dados import carregar_csv, salvar_csv
from helios.decisao import MotorDecisao
from helios.energia import CAPACIDADE_BATERIA_WH, AnalisadorEnergia
from helios.ia_monitor import MonitorIA
from helios.modelos import ModoOperacao, Severidade, Status, TipoModulo
from helios.simulador import Simulador, frota_padrao


# ---------------------------------------------------------------------------
# 1. Frota e simulador (monitoramento de dados simulados)
# ---------------------------------------------------------------------------
def test_frota_padrao_tem_subsistemas_essenciais():
    frota = frota_padrao()
    tipos = {m.tipo for m in frota}
    assert TipoModulo.GERACAO in tipos
    assert TipoModulo.ARMAZENAMENTO in tipos
    assert TipoModulo.SUPORTE_VIDA in tipos
    # ids unicos
    ids = [m.id for m in frota]
    assert len(ids) == len(set(ids))


def test_simulador_e_deterministico_com_mesma_seed():
    f1, f2 = frota_padrao(), frota_padrao()
    s1 = Simulador(f1, cenario="nominal", seed=7)
    s2 = Simulador(f2, cenario="nominal", seed=7)
    for n in range(30):
        assert s1.passo(n) == pytest.approx(s2.passo(n))


def test_irradiancia_cai_no_eclipse():
    """Durante a sombra orbital a irradiância deve zerar em algum momento."""
    sim = Simulador(frota_padrao(), cenario="nominal", seed=1)
    irradiancias = [sim.passo(n)[0] for n in range(90)]
    assert min(irradiancias) <= 1.0          # houve eclipse
    assert max(irradiancias) > 500.0         # houve pleno sol


# ---------------------------------------------------------------------------
# 2. Energia / potência / sustentabilidade
# ---------------------------------------------------------------------------
def test_balanco_energia_e_consistente():
    frota = frota_padrao()
    Simulador(frota, cenario="nominal", seed=1).passo(0)
    en = AnalisadorEnergia().analisar(frota)
    assert en["balanco_w"] == pytest.approx(
        en["geracao_total_w"] - en["consumo_total_w"], abs=1e-6)
    assert 0.0 <= en["bateria_soc_pct"] <= 100.0
    assert 0.0 <= en["fracao_renovavel_pct"] <= 100.0


def test_soc_nunca_sai_dos_limites_fisicos():
    """Em falha de painel a bateria descarrega, mas nunca abaixo de 0%."""
    ctrl = ControleMissao(cenario="falha_painel", seed=42)
    for t in ctrl.executar(120):
        assert 0.0 <= t.bateria_soc_pct <= 100.0
        assert t.bateria_energia_wh <= CAPACIDADE_BATERIA_WH + 1e-6


def test_co2_evitado_e_monotonico():
    """O CO2 evitado é acumulado: nunca diminui ao longo da missão."""
    tels = ControleMissao(cenario="nominal", seed=3).executar(60)
    valores = [t.co2_evitado_kg for t in tels]
    assert all(b >= a - 1e-9 for a, b in zip(valores, valores[1:]))


# ---------------------------------------------------------------------------
# 3. Alertas
# ---------------------------------------------------------------------------
def test_alerta_critico_quando_soc_muito_baixo():
    motor = MotorAlertas()
    frota = frota_padrao()
    alertas = motor.avaliar(frota, soc_pct=10.0, balanco_w=-100.0,
                            sinal=90.0, autonomia_min=120.0, anomalias=[])
    assert any(a.severidade == Severidade.CRITICO for a in alertas)


def test_sem_alerta_critico_em_condicao_saudavel():
    motor = MotorAlertas()
    frota = frota_padrao()
    Simulador(frota, cenario="nominal", seed=1).passo(2)
    alertas = motor.avaliar(frota, soc_pct=95.0, balanco_w=200.0,
                            sinal=95.0, autonomia_min=float("inf"),
                            anomalias=[])
    assert not any(a.severidade == Severidade.CRITICO for a in alertas)


def test_sinal_fraco_gera_alerta_de_comunicacao():
    motor = MotorAlertas()
    frota = frota_padrao()
    alertas = motor.avaliar(frota, soc_pct=80.0, balanco_w=0.0,
                            sinal=20.0, autonomia_min=200.0, anomalias=[])
    assert any("comunica" in a.mensagem.lower() or a.origem == "COMM"
               for a in alertas)


# ---------------------------------------------------------------------------
# 4. Decisão automatizada
# ---------------------------------------------------------------------------
def test_economia_desliga_modulo_nao_critico():
    frota = frota_padrao()
    Simulador(frota, cenario="nominal", seed=1).passo(0)
    motor = MotorDecisao()
    acoes, modo = motor.decidir(frota, soc_pct=25.0, alertas=[],
                                autonomia_min=200.0)
    sci = next(m for m in frota if m.id == "SCI")
    assert sci.ligado is False                       # experimento foi cortado
    assert modo in (ModoOperacao.ECONOMIA, ModoOperacao.SEGURO)


def test_modulo_critico_nunca_e_desligado():
    frota = frota_padrao()
    Simulador(frota, cenario="nominal", seed=1).passo(0)
    motor = MotorDecisao()
    # SoC catastrófico: ainda assim suporte à vida permanece ligado
    motor.decidir(frota, soc_pct=5.0, alertas=[], autonomia_min=10.0)
    life = next(m for m in frota if m.id == "LIFE")
    assert life.ligado is True


def test_religamento_quando_bateria_recupera():
    frota = frota_padrao()
    Simulador(frota, cenario="nominal", seed=1).passo(0)
    motor = MotorDecisao()
    motor.decidir(frota, soc_pct=25.0, alertas=[], autonomia_min=200.0)  # corta
    motor.decidir(frota, soc_pct=70.0, alertas=[], autonomia_min=300.0)  # religa
    sci = next(m for m in frota if m.id == "SCI")
    assert sci.ligado is True


# ---------------------------------------------------------------------------
# 5. IA introdutória
# ---------------------------------------------------------------------------
def test_indice_saude_no_intervalo():
    ia = MonitorIA()
    s = ia.indice_saude(soc_pct=80.0, fracao_renovavel=70.0,
                        sinal=90.0, n_alertas_criticos=0)
    assert 0.0 <= s <= 100.0


def test_saude_cai_com_alertas_criticos():
    ia = MonitorIA()
    boa = ia.indice_saude(80.0, 70.0, 90.0, n_alertas_criticos=0)
    ruim = ia.indice_saude(80.0, 70.0, 90.0, n_alertas_criticos=3)
    assert ruim < boa


def test_previsao_detecta_descarga():
    """Alimentando SoC em queda, a IA deve prever tempo finito até o crítico."""
    ia = MonitorIA()
    previsao = None
    for soc in [90, 80, 70, 60, 50, 40, 30, 25]:
        previsao = ia.prever_tempo_critico(float(soc), passo_min=1.0)
    assert previsao is not None and previsao >= 0.0


# ---------------------------------------------------------------------------
# 6. Pipeline completo (ponta a ponta) + persistência
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("cenario", [
    "nominal", "falha_painel", "eclipse_prolongado",
    "superaquecimento", "tempestade_solar",
])
def test_pipeline_completo_roda_todos_cenarios(cenario):
    tels = ControleMissao(cenario=cenario, seed=42).executar(60)
    assert len(tels) == 60
    for t in tels:
        assert t.modulos                                  # há módulos
        assert math.isfinite(t.indice_saude)
        assert isinstance(t.modo_operacao, ModoOperacao)


def test_nominal_e_estavel():
    """Cenário nominal não deve entrar em modo seguro nem zerar a bateria."""
    tels = ControleMissao(cenario="nominal", seed=42).executar(120)
    assert all(t.modo_operacao != ModoOperacao.SEGURO for t in tels)
    assert min(t.bateria_soc_pct for t in tels) > 30.0


def test_falha_painel_dispara_resposta():
    """A falha de painel deve gerar alertas críticos e ao menos uma ação."""
    tels = ControleMissao(cenario="falha_painel", seed=42).executar(120)
    n_crit = sum(1 for t in tels for a in t.alertas
                 if a.severidade == Severidade.CRITICO)
    n_acoes = sum(len(t.acoes) for t in tels)
    assert n_crit > 0 and n_acoes > 0


def test_persistencia_csv_ida_e_volta(tmp_path):
    tels = ControleMissao(cenario="nominal", seed=42).executar(20)
    caminho = tmp_path / "telemetria.csv"
    salvar_csv(tels, str(caminho))
    linhas = list(carregar_csv(str(caminho)))
    assert len(linhas) == 20
    assert "bateria_soc_pct" in linhas[0]
    # o SoC lido bate com o simulado (tolerância de arredondamento)
    assert float(linhas[0]["bateria_soc_pct"]) == pytest.approx(
        tels[0].bateria_soc_pct, abs=0.2)
