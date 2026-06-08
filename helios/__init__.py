"""
HELIOS — Sistema Inteligente de Monitoramento Energético para Missões Espaciais.

Pacote principal. Expõe os componentes mais usados para facilitar o import.
"""
from .controle import ControleMissao
from .modelos import (
    Acao, Alerta, ModoOperacao, Modulo, Severidade, Status, Telemetria,
    TipoModulo,
)

__all__ = [
    "ControleMissao", "Telemetria", "Modulo", "Alerta", "Acao",
    "Status", "Severidade", "TipoModulo", "ModoOperacao",
]
__version__ = "1.0.0"
