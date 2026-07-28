"""app.mercado — mercados de renda fixa (CDI) e variável (Ibovespa).

POO: classes que encapsulam o estado/dados de cada mercado (F2, F3, F4).
Implementa a **Etapa 0 (calibração)** do artigo: a partir dos retornos
históricos, fornece os insumos exógenos do modelo — R_f (renda fixa) e
(μ̂, Σ̂) + amostragem Monte Carlo (renda variável).

A matemática de otimização (α*, A_t, …) fica em ``app.nucleo``.
"""

import numpy as np
import pandas as pd


class RendaFixa:
    """Mercado de renda fixa (CDI) — fornece a taxa livre de risco. (F3)"""

    def __init__(self, cdi_anual: float, periodos_por_ano: int = 12) -> None:
        """
        Parameters
        ----------
        cdi_anual : taxa CDI anual em decimal (ex.: 0.10 para 10% a.a.).
        periodos_por_ano : 12 para dados mensais (default).
        """
        self.cdi_anual = float(cdi_anual)
        self.periodos_por_ano = int(periodos_por_ano)

    def retorno_livre_risco(self) -> float:
        """Taxa livre de risco R_f por período (líquida). (F3)

        Conversão **composta** anual → período:

            R_f = (1 + cdi_anual)^(1/periodos_por_ano) − 1

        Ex.: 10% a.a. mensal ⇒ (1.10)^(1/12) − 1 ≈ 0.007974. O fator *bruto*
        usado ao propagar a riqueza é ``1 + R_f``.
        """
        return (1.0 + self.cdi_anual) ** (1.0 / self.periodos_por_ano) - 1.0


class RendaVariavel:
    """Mercado de renda variável (Ibovespa) — distribuição dos retornos. (F4)

    Opera no **espaço de retornos líquidos** (a mesma forma da tabela
    ``retornos``); o excesso ``R − R_f`` é formado depois, no agente/núcleo.
    """

    def __init__(self, retornos: pd.DataFrame, coluna_data: str = "data") -> None:
        """
        Parameters
        ----------
        retornos : DataFrame com (opcionalmente) a coluna ``data`` + uma coluna
            de retorno por ativo (decimal, sem NaN).
        coluna_data : nome da coluna de data a ignorar nos cálculos.
        """
        df = retornos.drop(columns=[coluna_data]) if coluna_data in retornos.columns else retornos.copy()
        self.ativos: list[str] = list(df.columns)
        self._R: np.ndarray = df.to_numpy(dtype=np.float64)  # (T, N)

        if self._R.ndim != 2 or self._R.shape[1] == 0:
            raise ValueError("retornos deve conter ao menos uma coluna de ativo.")
        if self._R.shape[0] < 2:
            raise ValueError("são necessárias ao menos 2 observações de retorno.")
        if np.isnan(self._R).any():
            raise ValueError("retornos não pode conter NaN.")

    @property
    def n_ativos(self) -> int:
        return self._R.shape[1]

    def media(self) -> np.ndarray:
        """Vetor de retornos esperados estimado μ̂, shape (N,). (F2, F4)"""
        return self._R.mean(axis=0)

    def covariancia(self) -> np.ndarray:
        """Matriz de covariância amostral não-viesada Σ̂, shape (N, N). (F2, F4)

        ``np.cov(R.T, ddof=1)`` + ``atleast_2d`` (idêntico ao estimador de
        referência ``estimate_sample_cov``).
        """
        return np.atleast_2d(np.cov(self._R.T, ddof=1))

    def amostrar(self, n: int, seed: int | None = None) -> np.ndarray:
        """Gera ``n`` cenários de retorno R ~ Normal(μ̂, Σ̂), shape (n, N).

        Usado pelo Monte Carlo da FOC (Etapa 1). Reprodutível via ``seed`` (NF4).

        Parameters
        ----------
        n : número de cenários.
        seed : semente do gerador (reprodutibilidade).
        """
        rng = np.random.default_rng(seed)
        mu = self.media()
        # R = μ + z·cholᵀ,  z ~ N(0, I)   ⇒  Cov(R) = Σ
        chol = np.linalg.cholesky(self.covariancia())
        z = rng.standard_normal((n, mu.shape[0]))
        return mu[None, :] + z @ chol.T
