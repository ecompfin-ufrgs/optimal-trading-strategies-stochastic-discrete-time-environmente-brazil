"""app.principal — orquestrador da esteira pipes-and-filters.

Liga os filtros na ordem da esteira (F10, NF5):

    dal → mercado → agente (+ nucleo) → simulação → resultado

`executar_pipeline` é o único ponto que a camada web chama: ela passa um
`config` e recebe o resultado pronto (carteira ótima, consumo, trajetórias).
Toda a lógica vive nos módulos; aqui só há orquestração.
"""

from __future__ import annotations

import numpy as np

from app.agente import Investidor
from app.mercado import RendaFixa, RendaVariavel
from app import dal, nucleo


def executar_pipeline(config: dict) -> dict:
    """Executa a esteira completa do modelo CRRA. (NF5)

    Fluxo:
      1. DAL: leitura de dados (SQLite ou DataFrame);
      2. Mercado: calibração (μ̂, Σ̂, R_f);
      3. Agente: otimização da carteira e consumo ótimo;
      4. Núcleo: simulação forward da riqueza;
      5. Agregação de métricas e retornos.

    Parameters
    ----------
    config : dict
        Configuração completa da simulação, incluindo:
        - dados de entrada (retornos ou db_path)
        - parâmetros do mercado (ativos, rf_col, cdi_anual)
        - parâmetros do agente (γ, β, W₀, T)
        - parâmetros de simulação (n_scenarios, n_paths, seed)
        - restrições de otimização (allow_short, allow_leverage, alpha_max)

    Returns
    -------
    dict
        Resultado consolidado contendo:
        - alpha_star (carteira ótima)
        - theta (frações de consumo)
        - phi_hat (estatística da política ótima)
        - calibração (μ̂, Σ̂, rf)
        - métricas da simulação (E[W_T], percentis, trajetórias médias)
    """
    ...
