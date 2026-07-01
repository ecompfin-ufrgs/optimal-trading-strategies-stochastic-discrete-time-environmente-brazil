"""Ponto de entrada do pacote: ``python -m app``.

Roda a esteira completa (``app.principal.executar_pipeline``)
e imprime o resultado. Serve para conferir que a aplicação roda de
ponta a ponta sem a camada web.

Em uso real, os retornos vêm do SQLite populado pela DAL (a partir do Yahoo
Finance);
"""

from __future__ import annotations

import os

import numpy as np
import pandas as pd

from app.principal import executar_pipeline

def main() -> None:
    """Executa a esteira completa em modo CLI.

    Fluxo:
      1. verifica existência do banco SQLite;
      2. usa dados reais da DAL;
      4. executa `executar_pipeline`;
      5. imprime resumo da simulação.
    """
    ...


if __name__ == "__main__":
    main()
