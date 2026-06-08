"""
modelos.py
==========
Estruturas de dados centrais do HELIOS (enums e dataclasses).

Aqui ficam apenas as "formas" dos dados que circulam pelo sistema, sem
nenhuma regra de negocio. Isso mantem o codigo organizado: cada arquivo do
pacote tem uma responsabilidade clara.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Enumeracoes (categorias fixas usadas em todo o sistema)
# ---------------------------------------------------------------------------
class TipoModulo(str, Enum):
    """Funcao de cada modulo da missao espacial."""
    GERACAO = "Geração Solar"
    ARMAZENAMENTO = "Armazenamento"
    SUPORTE_VIDA = "Suporte à Vida"
    COMUNICACAO = "Comunicação"
    TERMICO = "Controle Térmico"
    COMPUTADOR = "Computador de Bordo"
    CIENTIFICO = "Experimentos Científicos"
    PROPULSAO = "Propulsão"


class Status(str, Enum):
    """Estado operacional de um modulo (ordem = gravidade crescente)."""
    NOMINAL = "NOMINAL"
    ATENCAO = "ATENÇÃO"
    CRITICO = "CRÍTICO"
    OFFLINE = "OFFLINE"


class Severidade(str, Enum):
    """Nivel de um alerta."""
    INFO = "INFO"
    ATENCAO = "ATENÇÃO"
    CRITICO = "CRÍTICO"


class ModoOperacao(str, Enum):
    """Modo global da missao, definido pelo motor de decisao."""
    NORMAL = "NORMAL"
    ECONOMIA = "ECONOMIA DE ENERGIA"
    SEGURO = "MODO SEGURO"


# ---------------------------------------------------------------------------
# Modulo da missao
# ---------------------------------------------------------------------------
@dataclass
class Modulo:
    """
    Representa um subsistema da nave (paineis solares, suporte a vida, etc.).

    Campos de configuracao (fixos) e campos dinamicos (atualizados a cada
    leitura de telemetria) ficam juntos para facilitar o snapshot.
    """
    id: str
    nome: str
    tipo: TipoModulo
    # 'critico=True' -> nunca pode ser desligado automaticamente (ex.: suporte a vida)
    critico: bool
    consumo_nominal_w: float       # consumo medio quando ligado (W)
    temp_ideal_c: float            # temperatura de operacao ideal (C)
    temp_max_c: float              # acima disso -> superaquecimento
    temp_min_c: float              # abaixo disso -> frio critico

    # --- estado dinamico ---
    ligado: bool = True
    status: Status = Status.NOMINAL
    temperatura_c: float = 20.0
    # potencia instantanea: positiva = geracao, negativa = consumo
    potencia_w: float = 0.0

    def snapshot(self) -> "Modulo":
        """Retorna uma copia imutavel do estado atual (para o historico)."""
        return replace(self)


# ---------------------------------------------------------------------------
# Alertas e acoes automatizadas
# ---------------------------------------------------------------------------
@dataclass
class Alerta:
    """Alerta gerado pelo motor de regras ou pela deteccao de anomalias."""
    severidade: Severidade
    origem: str            # id do modulo ou subsistema afetado
    mensagem: str
    recomendacao: str = ""


@dataclass
class Acao:
    """Resposta automatizada decidida pelo sistema diante de uma situacao."""
    descricao: str
    alvo: str              # modulo/subsistema afetado
    justificativa: str


# ---------------------------------------------------------------------------
# Snapshot de telemetria (estado completo em um instante)
# ---------------------------------------------------------------------------
@dataclass
class Telemetria:
    """
    "Fotografia" da missao em um passo de tempo. Tudo que o painel precisa
    exibir esta aqui dentro, ja calculado e interpretado.
    """
    passo: int
    instante_min: float
    irradiancia_w_m2: float
    sinal_comunicacao_pct: float
    modulos: list[Modulo]

    # bloco de energia / potencia / sustentabilidade
    geracao_total_w: float = 0.0
    consumo_total_w: float = 0.0
    balanco_w: float = 0.0
    bateria_soc_pct: float = 100.0
    bateria_energia_wh: float = 0.0
    autonomia_min: float = float("inf")
    fracao_renovavel_pct: float = 100.0
    energia_gerada_acum_wh: float = 0.0
    energia_consumida_acum_wh: float = 0.0
    co2_evitado_kg: float = 0.0
    indice_saude: float = 100.0

    # bloco de IA introdutoria
    anomalias: list[str] = field(default_factory=list)
    previsao_soc_min: Optional[float] = None  # minutos ate SoC critico (ou None)

    # bloco operacional
    alertas: list[Alerta] = field(default_factory=list)
    acoes: list[Acao] = field(default_factory=list)
    modo_operacao: ModoOperacao = ModoOperacao.NORMAL
