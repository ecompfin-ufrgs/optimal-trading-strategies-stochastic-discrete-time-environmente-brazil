"""Ponto de entrada do pacote: ``python -m app``.

Roda a esteira completa (``app.principal.executar_pipeline``)
e imprime o resultado. Serve para conferir que a aplicação roda de
ponta a ponta sem a camada web.

Em uso real, os retornos vêm do SQLite populado pela DAL (a partir do Yahoo
Finance); aqui foi gerado uma série sintética para a demonstração ser offline e
reprodutível.
"""

from __future__ import annotations

import os

import numpy as np
import pandas as pd

from app.principal import executar_pipeline


def _dados_demo(T: int = 300, seed: int = 7) -> pd.DataFrame:
    """Gera série sintética de retornos mensais (Ibovespa + CDI). (demo)

    Usada apenas quando não existe banco SQLite real disponível.

    Returns
    -------
    DataFrame com:
      - data (YYYY-MM)
      - ibov (retorno sintético de risco)
      - cdi (retorno constante de renda fixa)
    """
    ...


def main() -> None:
    """Executa a esteira completa em modo CLI.

    Fluxo:
      1. verifica existência do banco SQLite;
      2. se existir, usa dados reais da DAL;
      3. caso contrário, gera dados sintéticos;
      4. executa `executar_pipeline`;
      5. imprime resumo da simulação.
    """
    ...


if __name__ == "__main__":
    main()
