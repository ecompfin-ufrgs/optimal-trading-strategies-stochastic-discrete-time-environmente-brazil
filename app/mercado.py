"""app.mercado: a renda fixa (CDI) e a renda variavel (Ibovespa).

Cada classe guarda os dados de um mercado (F2, F3, F4). E aqui que acontece a
Etapa 0 do artigo, a calibracao: a partir dos retornos historicos saem a taxa
livre de risco, a media, a matriz de covariancia e o sorteio dos cenarios.

A parte de otimizacao (o alpha, o A_t) fica no app.nucleo.
"""

import numpy as np
import pandas as pd


class RendaFixa:
    """Mercado de renda fixa (CDI) — fornece a taxa livre de risco. (F3)"""

    def __init__(self, cdi_anual: float, periodos_por_ano: int = 12) -> None:
        """
        Recebe o CDI anual em decimal (0.10 para 10% ao ano) e em quantos
        periodos o ano e dividido: 12 se a base for mensal, 252 se for diaria.
        """
        self.cdi_anual = float(cdi_anual)
        self.periodos_por_ano = int(periodos_por_ano)

    def retorno_livre_risco(self) -> float:
        """A taxa livre de risco de um periodo, liquida. (F3)

        A conversao de ano pra periodo e composta, e nao dividindo por 12:

            R_f = (1 + cdi_anual) ** (1 / periodos_por_ano) - 1

        Por exemplo, 10% ao ano no mensal da (1.10) ** (1/12) - 1, que e mais
        ou menos 0.007974. Na hora de propagar a riqueza usa-se 1 + R_f.
        """
        return (1.0 + self.cdi_anual) ** (1.0 / self.periodos_por_ano) - 1.0


class RendaVariavel:
    """Mercado de renda variavel (Ibovespa): a distribuicao dos retornos. (F4)

    Trabalha com retornos liquidos, do mesmo jeito que estao na tabela
    retornos do banco. A diferenca R - R_f e montada depois, no agente.
    """

    def __init__(self, retornos: pd.DataFrame, coluna_data: str = "data") -> None:
        """
        Recebe o DataFrame de retornos, com uma coluna por ativo em decimal
        e sem valor faltando. A coluna de data e opcional; se existir, o nome
        dela vem em coluna_data e ela fica de fora das contas.
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
        """Vetor de retornos esperados estimado mu_chapeu, shape (N,). (F2, F4)"""
        return self._R.mean(axis=0)

    def covariancia(self) -> np.ndarray:
        """A matriz de covariancia amostral, com ddof=1. (F2, F4)

        E o np.cov mesmo, com atleast_2d por cima pra garantir que o resultado
        seja bidimensional quando tem um ativo so.
        """
        return np.atleast_2d(np.cov(self._R.T, ddof=1))

    def amostrar(self, n: int, seed: int | None = None) -> np.ndarray:
        """
        Sorteia n cenarios de retorno de uma normal com a media e a
        covariancia estimadas.

        E o que alimenta o Monte Carlo da Etapa 1. Passando a mesma semente sai
        sempre o mesmo resultado, que e o que o NF4 pede.
        """
        rng = np.random.default_rng(seed)
        mu = self.media()
        # R = μ + z·cholᵀ,  z ~ N(0, I)   ⇒  Cov(R) = Σ
        chol = np.linalg.cholesky(self.covariancia())
        z = rng.standard_normal((n, mu.shape[0]))
        return mu[None, :] + z @ chol.T
