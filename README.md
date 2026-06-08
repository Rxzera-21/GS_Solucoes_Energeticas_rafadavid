# 🛰️ HELIOS — Sistema Inteligente de Monitoramento Energético para Missões Espaciais

> **Global Solution — Soluções em Energias Renováveis e Sustentáveis**
> FIAP · Ciência da Computação · Turma 1CC

O **HELIOS** é uma plataforma computacional que **recebe, interpreta e exibe**
dados simulados de uma missão espacial experimental, aplicando conceitos de
**energia, potência, energias renováveis e sustentabilidade** ao monitoramento
dos módulos da operação. O sistema gera **alertas automáticos**, toma
**decisões automatizadas** diante de situações críticas e oferece **duas
formas de visualização**: um painel em tempo real no terminal e um dashboard
web interativo.

---

## 🎯 Por que isso importa (tema da disciplina)

Uma nave depende quase inteiramente de **energia renovável** (painéis solares)
e de um **banco de baterias** para sobreviver aos eclipses orbitais. Gerir essa
energia com eficiência é, ao mesmo tempo, uma questão de **sobrevivência** e de
**sustentabilidade**: cada watt gerado pelo Sol é um watt que não precisa vir de
uma fonte poluente. O HELIOS quantifica isso o tempo todo — fração de energia
renovável, autonomia da bateria e **CO₂ evitado** em relação a um gerador a
diesel equivalente.

---

## ✅ Requisitos do desafio × como o HELIOS atende

| Requisito mínimo | Onde está implementado |
|---|---|
| **Monitoramento de dados simulados** (temperatura, comunicação, energia, status) | `helios/simulador.py` gera os dados; `helios/energia.py` os interpreta; `Telemetria` (`helios/modelos.py`) consolida tudo |
| **Geração automática de alertas** | `helios/alertas.py` — regras de temperatura, SoC, balanço, autonomia e comunicação + alertas vindos da IA |
| **Tomada de decisão / respostas automatizadas** | `helios/decisao.py` — corte térmico, economia de energia, modo seguro e religamento |
| **Visualização clara dos dados** | `main.py` (painel no terminal com `rich`) e `dashboard.py` (dashboard web com `streamlit`) |
| **IA introdutória** | `helios/ia_monitor.py` — detecção de anomalias (z-score), previsão de tempo até SoC crítico (regressão linear) e índice de saúde |

---

## ⚡ Conceitos de energia aplicados

- **Potência (W):** cada módulo tem consumo instantâneo; os painéis geram
  potência proporcional à irradiância solar (`P = irradiância × área ×
  eficiência`).
- **Energia (Wh):** integrada no tempo (`E = P × t`) para atualizar a carga da
  bateria a cada passo.
- **Energias renováveis:** a geração é 100% solar. O sistema calcula a
  **fração renovável** do consumo atendida diretamente pelo Sol.
- **Sustentabilidade:** a energia limpa acumulada é convertida em **CO₂
  evitado** (fator de um gerador a diesel), tornando o impacto ambiental
  mensurável.
- **Modelo orbital:** período de ~90 min com fase de **eclipse** (~38% da
  órbita), em que a geração some e a missão passa a depender da bateria — o
  cenário clássico de gestão energética espacial.

---

## 🧩 Arquitetura

O sistema é um **pipeline** claro, executado a cada passo de tempo (1 min):

```
simulador  →  energia  →  IA  →  alertas  →  decisão
 (dados)     (cálculo)  (previsão) (regras)  (resposta)
```

Cada passo produz um objeto `Telemetria` — uma "fotografia" completa da missão,
já calculada e interpretada, que alimenta as duas interfaces de visualização.

```
helios-monitor/
├── helios/                 # pacote principal
│   ├── modelos.py          # estruturas de dados (enums e dataclasses)
│   ├── simulador.py        # gera os dados simulados (modelo orbital + cenários)
│   ├── energia.py          # potência, energia, bateria e sustentabilidade
│   ├── ia_monitor.py       # IA: anomalias, previsão e índice de saúde
│   ├── alertas.py          # motor de alertas automáticos
│   ├── decisao.py          # respostas automatizadas / modos de operação
│   ├── controle.py         # orquestra o pipeline (Centro de Controle)
│   └── dados.py            # persistência/leitura de telemetria em CSV
├── main.py                 # painel de monitoramento no TERMINAL (rich)
├── dashboard.py            # DASHBOARD web interativo (streamlit)
├── tests/test_helios.py    # 23 testes automatizados (pytest)
├── data/telemetria_exemplo.csv
├── requirements.txt
└── README.md
```

---

## 🚀 Como executar

### 1. Instalar dependências

```bash
pip install -r requirements.txt
```

### 2. Painel no terminal (tempo real)

```bash
python main.py                          # cenário nominal
python main.py --cenario falha_painel   # outro cenário
```

Opções principais:

| Argumento | Padrão | Descrição |
|---|---|---|
| `--cenario` | `nominal` | cenário a simular (lista abaixo) |
| `--passos` | `120` | número de passos (minutos) |
| `--velocidade` | `0.06` | segundos entre passos (animação) |
| `--seed` | `42` | semente para reprodutibilidade |
| `--fonte` | `simulador` | `simulador` ou `csv` (lê dados externos) |
| `--gerar-csv CAMINHO` | — | gera um CSV de telemetria e encerra |

### 3. Dashboard web

```bash
streamlit run dashboard.py
```

Selecione o cenário e o número de passos na barra lateral e explore os
gráficos de bateria, potência, sustentabilidade e comunicação, além das
tabelas de alertas e decisões.

### 4. Rodar os testes

```bash
pytest -v
```

---

## 🎬 Cenários simulados

| Cenário | O que acontece | Resposta esperada do sistema |
|---|---|---|
| `nominal` | Operação saudável | Modo NORMAL, bateria estável, quase nenhum alerta |
| `falha_painel` | Eficiência dos painéis despenca | Bateria descarrega → ECONOMIA → corte de módulos não críticos |
| `eclipse_prolongado` | Sombra orbital mais longa | Ciclagem da bateria mais profunda, porém controlada |
| `superaquecimento` | Falha térmica em um módulo | Alerta crítico de temperatura → corte/redução do módulo |
| `tempestade_solar` | Degradação da comunicação | Vários alertas críticos de sinal de comunicação |

---

## 🤖 Inteligência artificial introdutória

- **Detecção de anomalias:** z-score em janela móvel sobre as temperaturas dos
  módulos — sinaliza desvios estatisticamente improváveis sem depender de
  limiares fixos.
- **Previsão:** regressão linear sobre o histórico recente de carga da bateria
  estima **em quantos minutos** o SoC chegaria ao nível crítico, antecipando a
  decisão.
- **Índice de saúde (0–100):** combina carga da bateria, fração renovável,
  qualidade da comunicação e penalidades por alertas críticos em um único
  indicador de fácil leitura.

---

## 🧠 Decisões automatizadas

Diante de situações críticas, o HELIOS responde sozinho, **sempre preservando
os módulos críticos** (suporte à vida, computador de bordo, controle térmico):

- **Corte térmico:** desliga (ou reduz a potência de) um módulo em
  superaquecimento.
- **Economia de energia:** com bateria baixa, desliga módulos não essenciais
  por ordem de prioridade.
- **Modo seguro:** acionado diante de múltiplos alertas críticos ou autonomia
  muito curta.
- **Religamento:** restabelece os módulos quando a bateria se recupera.

---

## 📊 Critérios de avaliação atendidos

- **Técnica (60):** código modular, com responsabilidades separadas,
  documentado e coberto por **23 testes automatizados**; alertas claros e
  organizados.
- **Inovação (30):** IA introdutória (anomalias + previsão + índice de saúde),
  modelo orbital com eclipse, motor de decisão com estado e métrica de
  sustentabilidade (**CO₂ evitado**).
- **Usabilidade (10):** duas interfaces de visualização (terminal animado e
  dashboard web interativo), com cores, ícones e organização clara.

---

## 👥 Integrantes

- Rafael Marinucci Peres — RM569729
- David dos Reis Cardoso — RM568938

## 📄 Licença

Distribuído sob a licença MIT. Veja o arquivo `LICENSE`.
