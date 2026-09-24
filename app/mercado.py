"""app.mercado: a renda fixa (CDI) e a renda variavel (Ibovespa).

Cada classe guarda os dados de um mercado (F2, F3, F4). E aqui que acontece a
maior parte da Etapa 0 do projeto do TCC, a calibracao: a RendaVariavel estima
a media e a matriz de covariancia dos retornos historicos e sorteia os
cenarios, e a RendaFixa converte um CDI anual informado em taxa por periodo.
Quando nenhum CDI anual e informado, o app.principal usa a media da serie do
CDI dos dados.

A parte de otimizacao (o alpha, o A_t) fica no app.nucleo.
"""

import numpy as np
import pandas as pd


class RendaFixa:
    """Mercado de renda fixa (CDI): fornece a taxa livre de risco. (F3)"""

    def __init__(self, cdi_anual: float, periodos_por_ano: int = 12) -> None:
        """
        Recebe o CDI anual em decimal (0.10 para 10% ao ano) e em quantos
        periodos o ano e dividido: 12 se a base for mensal, 252 se for diaria.

        O cdi_anual tem que ser maior que -1 e o periodos_por_ano, pelo menos
        1; fora disso a conversao do retorno_livre_risco nao esta definida.
        """
        cdi_anual = float(cdi_anual)
        periodos_por_ano = int(periodos_por_ano)
        if cdi_anual <= -1.0:
            raise ValueError(
                f"cdi_anual deve ser > -1; veio {cdi_anual:g}. A conversao "
                "eleva (1 + cdi_anual) a 1/periodos_por_ano, e com a base "
                "negativa o resultado sai complexo."
            )
        if periodos_por_ano < 1:
            raise ValueError(
                f"periodos_por_ano deve ser >= 1; veio {periodos_por_ano}."
            )
        self.cdi_anual = cdi_anual
        self.periodos_por_ano = periodos_por_ano

    def retorno_livre_risco(self) -> float:
        """A taxa livre de risco de um periodo, liquida. (F3)

        A conversao de ano pra periodo e composta (nao e dividir por 12):

            R_f = (1 + cdi_anual) ** (1 / periodos_por_ano) - 1

        Por exemplo, 10% ao ano no mensal da (1.10) ** (1/12) - 1, que e mais
        ou menos 0.007974. Na hora de propagar a riqueza usa-se 1 + R_f.
        """
        return (1.0 + self.cdi_anual) ** (1.0 / self.periodos_por_ano) - 1.0


class RendaVariavel:
    """Mercado de renda variavel (Ibovespa): a distribuicao dos retornos. (F4)

    Trabalha com retornos liquidos, do mesmo jeito que estao na tabela
    retornos do banco. A diferenca R - R_f e montada depois, no nucleo.
    """

    def __init__(self, retornos: pd.DataFrame, coluna_data: str = "data") -> None:
        """
        Recebe o DataFrame de retornos, com uma coluna por ativo em decimal
        e sem valor faltando. A coluna de data e opcional; se existir, o nome
        dela vem em coluna_data e ela fica de fora das contas.
        """
        df = retornos.drop(columns=[coluna_data]) if coluna_data in retornos.columns else retornos.copy()

        if df.shape[1] == 0:
            raise ValueError("retornos deve conter ao menos uma coluna de ativo.")
        if df.shape[0] < 2:
            raise ValueError("sao necessarias ao menos 2 observacoes de retorno.")
        nao_numericas = [c for c in df.columns
                         if not pd.api.types.is_numeric_dtype(df[c])]
        if nao_numericas:
            raise ValueError(
                f"colunas nao numericas em retornos: {nao_numericas}. Informe "
                f"o nome da coluna de data em coluna_data (veio {coluna_data!r})."
            )

        self.ativos: list[str] = list(df.columns)
        self._R: np.ndarray = df.to_numpy(dtype=np.float64)

        if np.isnan(self._R).any():
            raise ValueError("retornos nao pode conter NaN.")

    @property
    def n_ativos(self) -> int:
        return self._R.shape[1]

    def media(self) -> np.ndarray:
        """Vetor de retornos esperados estimado mu_chapeu, um por ativo. (F2, F4)"""
        return self._R.mean(axis=0)

    def covariancia(self) -> np.ndarray:
        """A matriz de covariancia amostral, com ddof=1. (F2, F4)

        E o np.cov mesmo; o atleast_2d forca o resultado a sair como matriz
        tambem quando tem um ativo so.
        """
        return np.atleast_2d(np.cov(self._R.T, ddof=1))

    def amostrar(self, n: int, seed: int | None = None) -> np.ndarray:
        """
        Sorteia n cenarios de retorno de uma normal com a media e a
        covariancia estimadas.

        E o que alimenta o Monte Carlo da Etapa 1, a simulacao pra frente e os
        graficos que refazem a otimizacao. Passando a mesma semente sai sempre
        o mesmo resultado, que e o que o NF4 pede.
        """
        rng = np.random.default_rng(seed)
        mu = self.media()
        # R = media + z * chol.T, com z normal padrao, pra covariancia sair certa.
        chol = np.linalg.cholesky(self.covariancia())
        z = rng.standard_normal((n, mu.shape[0]))
        return mu[None, :] + z @ chol.T
