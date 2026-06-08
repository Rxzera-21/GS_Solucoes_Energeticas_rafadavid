"""
dashboard.py
============
Painel web (dashboard) do HELIOS, construido com Streamlit.

Complementa o painel de terminal (main.py) oferecendo uma VISUALIZACAO
grafica e interativa dos dados da missao — atendendo diretamente ao
criterio de Usabilidade e ao requisito "Visualizacao dos Dados".

Como executar:
    streamlit run dashboard.py

O usuario escolhe o cenario e o numero de passos na barra lateral; o
sistema roda a simulacao completa pelo MESMO pipeline do HELIOS
(ControleMissao) e exibe graficos de energia/potencia, status dos modulos,
metricas de sustentabilidade, alertas e o log de decisoes automatizadas.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from helios.controle import ControleMissao
from helios.modelos import Severidade, Status

# ---------------------------------------------------------------------------
# Configuracao geral da pagina
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="HELIOS — Monitoramento de Missão Espacial",
    page_icon="🛰️",
    layout="wide",
)

CENARIOS = {
    "nominal": "Operação Nominal",
    "falha_painel": "Falha nos Painéis Solares",
    "eclipse_prolongado": "Eclipse Prolongado",
    "superaquecimento": "Superaquecimento de Módulo",
    "tempestade_solar": "Tempestade Solar (comunicação)",
}

COR_STATUS = {
    Status.NOMINAL: "🟢",
    Status.ATENCAO: "🟡",
    Status.CRITICO: "🔴",
    Status.OFFLINE: "⚫",
}


# ---------------------------------------------------------------------------
# Simulacao (cacheada para nao recalcular a cada interacao)
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="Executando simulação da missão...")
def rodar(cenario: str, passos: int, seed: int):
    """Roda a missao e devolve (historico, dataframe de series temporais)."""
    controle = ControleMissao(cenario=cenario, seed=seed)
    hist = controle.executar(passos)

    linhas = []
    for t in hist:
        linhas.append({
            "Passo": t.passo,
            "Tempo (min)": t.instante_min,
            "Bateria (%)": round(t.bateria_soc_pct, 1),
            "Geração (W)": round(t.geracao_total_w, 1),
            "Consumo (W)": round(t.consumo_total_w, 1),
            "Balanço (W)": round(t.balanco_w, 1),
            "Renovável (%)": round(t.fracao_renovavel_pct, 1),
            "Sinal (%)": round(t.sinal_comunicacao_pct, 1),
            "Saúde": round(t.indice_saude, 1),
        })
    return hist, pd.DataFrame(linhas).set_index("Tempo (min)")


# ---------------------------------------------------------------------------
# Barra lateral (controles)
# ---------------------------------------------------------------------------
st.sidebar.title("🛰️ HELIOS")
st.sidebar.caption("Centro de Controle de Missão")

cenario = st.sidebar.selectbox(
    "Cenário da missão",
    options=list(CENARIOS.keys()),
    format_func=lambda c: CENARIOS[c],
)
passos = st.sidebar.slider("Passos de simulação (min)", 30, 300, 120, step=10)
seed = st.sidebar.number_input("Semente (reprodutibilidade)", value=42, step=1)

st.sidebar.markdown("---")
st.sidebar.markdown(
    "Sistema inteligente de monitoramento energético para missões "
    "espaciais experimentais. Aplica conceitos de **energia**, **potência**, "
    "**energias renováveis** e **sustentabilidade**."
)

hist, df = rodar(cenario, int(passos), int(seed))
final = hist[-1]


# ---------------------------------------------------------------------------
# Cabecalho + indicadores principais
# ---------------------------------------------------------------------------
st.title("Painel de Monitoramento da Missão")
st.caption(f"Cenário: **{CENARIOS[cenario]}**  ·  {passos} passos simulados")

modo = final.modo_operacao.value
cor_modo = {"NORMAL": "🟢", "ECONOMIA DE ENERGIA": "🟡", "MODO SEGURO": "🔴"}
st.subheader(f"Modo de operação atual: {cor_modo.get(modo, '')} {modo}")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Bateria (SoC)", f"{final.bateria_soc_pct:.0f}%")
c2.metric("Índice de Saúde", f"{final.indice_saude:.0f}/100")
c3.metric("Fração Renovável", f"{final.fracao_renovavel_pct:.0f}%")
c4.metric("CO₂ Evitado", f"{final.co2_evitado_kg:.1f} kg")
auton = "∞" if final.autonomia_min == float("inf") else f"{final.autonomia_min:.0f} min"
c5.metric("Autonomia", auton)

st.markdown("---")


# ---------------------------------------------------------------------------
# Graficos de series temporais
# ---------------------------------------------------------------------------
g1, g2 = st.columns(2)

with g1:
    st.markdown("#### 🔋 Carga da bateria ao longo do tempo")
    st.line_chart(df[["Bateria (%)"]], height=260)

with g2:
    st.markdown("#### ⚡ Geração × Consumo (potência)")
    st.line_chart(df[["Geração (W)", "Consumo (W)"]], height=260)

g3, g4 = st.columns(2)

with g3:
    st.markdown("#### ♻️ Fração renovável e índice de saúde")
    st.line_chart(df[["Renovável (%)", "Saúde"]], height=260)

with g4:
    st.markdown("#### 📡 Sinal de comunicação")
    st.area_chart(df[["Sinal (%)"]], height=260)

st.markdown("---")


# ---------------------------------------------------------------------------
# Status dos modulos (no instante final)
# ---------------------------------------------------------------------------
st.markdown("#### 🧩 Status dos módulos da operação")
linhas_mod = []
for m in final.modulos:
    linhas_mod.append({
        "": COR_STATUS.get(m.status, ""),
        "Módulo": m.nome,
        "Tipo": m.tipo.value,
        "Status": m.status.value,
        "Ligado": "Sim" if m.ligado else "Não",
        "Temperatura (°C)": round(m.temperatura_c, 1),
        "Potência (W)": round(m.potencia_w, 1),
        "Crítico": "Sim" if m.critico else "Não",
    })
st.dataframe(pd.DataFrame(linhas_mod), use_container_width=True, hide_index=True)

st.markdown("---")


# ---------------------------------------------------------------------------
# Alertas e decisoes (agregados de toda a missao)
# ---------------------------------------------------------------------------
col_a, col_d = st.columns(2)

with col_a:
    st.markdown("#### 🚨 Alertas gerados na missão")
    alertas = [(t, a) for t in hist for a in t.alertas]
    n_crit = sum(1 for _, a in alertas if a.severidade == Severidade.CRITICO)
    n_aten = sum(1 for _, a in alertas if a.severidade == Severidade.ATENCAO)
    st.write(f"Total: **{len(alertas)}**  ·  🔴 Críticos: **{n_crit}**  ·  🟡 Atenção: **{n_aten}**")
    if alertas:
        tabela_al = [{
            "Passo": t.passo,
            "Nível": a.severidade.value,
            "Origem": a.origem,
            "Mensagem": a.mensagem,
        } for t, a in alertas[-40:]]
        st.dataframe(pd.DataFrame(tabela_al), use_container_width=True,
                     hide_index=True, height=320)
    else:
        st.success("Nenhum alerta gerado — missão em operação nominal.")

with col_d:
    st.markdown("#### 🤖 Decisões automatizadas")
    acoes = [(t, ac) for t in hist for ac in t.acoes]
    st.write(f"Total de respostas automatizadas: **{len(acoes)}**")
    if acoes:
        tabela_ac = [{
            "Passo": t.passo,
            "Ação": ac.descricao,
            "Alvo": ac.alvo,
            "Justificativa": ac.justificativa,
        } for t, ac in acoes]
        st.dataframe(pd.DataFrame(tabela_ac), use_container_width=True,
                     hide_index=True, height=320)
    else:
        st.info("Nenhuma intervenção automática foi necessária neste cenário.")

st.markdown("---")
st.caption(
    "HELIOS · pipeline: simulador → energia → IA → alertas → decisão. "
    "Os mesmos dados podem ser acompanhados em tempo real no terminal via "
    "`python main.py`."
)
