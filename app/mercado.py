"""app.mercado — mercados de renda fixa (CDI) e variável (Ibovespa).

POO: classes que encapsulam o estado/dados de cada mercado (F2, F3, F4).
Implementa a **Etapa 0 (calibração)** do artigo: a partir dos retornos
históricos, fornece os insumos exógenos do modelo — R_f (renda fixa) e
(μ̂, Σ̂) + amostragem Monte Carlo (renda variável).

As convenções numéricas (conversão composta do rf, covariância amostral
não-viesada, geração de cenários Normal por Cholesky e Student-t com matriz de
escala) são as mesmas do `dp-optimize` de referência, que já está validado.
A matemática de otimização (α*, A_t, …) fica em ``app.nucleo``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


class RendaFixa:
    """Mercado de renda fixa (CDI) — fornece a taxa livre de risco. (F3)"""

    def __init__(
        self,
        cdi_anual: float,
        periodos_por_ano: int = 12,
    ) -> None:
        """Inicializa o mercado de renda fixa.

        Parameters
        ----------
        cdi_anual : taxa CDI anual (decimal)
        periodos_por_ano : número de períodos no ano (default = 12)
        """
        ...

    def retorno_livre_risco(self) -> float:
        """Retorno livre de risco por período (R_f). (F3)

        Conversão composta:

            R_f = (1 + cdi_anual)^(1/periodos_por_ano) − 1

        Retorna taxa em decimal por período.
        """
        ...


class RendaVariavel:
    """Mercado de renda variável (Ibovespa) — distribuição dos retornos. (F4)

    Trabalha diretamente no espaço de retornos líquidos (tabela `retornos`).
    """

    def __init__(
        self,
        retornos: pd.DataFrame,
        coluna_data: str = "data",
    ) -> None:
        """Inicializa o mercado de renda variável.

        Parameters
        ----------
        retornos : DataFrame com colunas de ativos (retornos em decimal)
        coluna_data : coluna de data (ignorada nos cálculos)
        """
        ...

    @property
    def n_ativos(self) -> int:
        """Número de ativos no universo de investimento."""
        ...

    def media(self) -> np.ndarray:
        """Estimativa μ̂ dos retornos médios (vetor N). (F2, F4)"""
        ...

    def covariancia(self) -> np.ndarray:
        """Matriz de covariância amostral Σ̂ (N × N). (F2, F4)

        Estimador não-viesado (ddof=1), consistente com o modelo base.
        """
        ...

    def amostrar(
        self,
        n: int,
        distribuicao: str = "normal",
        nu: float | None = None,
        seed: int | None = None,
    ) -> np.ndarray:
        """Gera cenários Monte Carlo de retornos.

        Retorna matriz (n × N) de retornos simulados a partir de:
          - Normal multivariada via Cholesky, ou
          - Student-t com escala ajustada.

        Parameters
        ----------
        n : número de cenários
        distribuicao : "normal" ou "student_t"
        nu : graus de liberdade (obrigatório se student_t)
        seed : reprodutibilidade do gerador
        """
        ...
