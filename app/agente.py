"""app.agente: o investidor.

Esta e a parte orientada a objetos. A classe guarda as caracteristicas do
investidor (aversao ao risco, impaciencia, riqueza inicial e horizonte) e
conduz a decisao dele, deixando as contas por conta do app.nucleo
(F5, F6, F8, F9).

A decisao acontece nesta ordem:
  1. sorteia cenarios de retorno do mercado (liquidos);
  2. converte pra fator bruto e corta em zero;
  3. acha a carteira otima e guarda o alfa e o phi;
  4. usa a recorrencia A_t pra chegar nas fracoes de consumo.
"""

import numpy as np

from app import nucleo
from app.mercado import RendaVariavel


class Investidor:
    """Agente CRRA com decisão de consumo e portfólio. (F5)"""

    def __init__(self, gamma: float, beta: float, w0: float, horizonte: int) -> None:
        if gamma <= 0:
            raise ValueError("γ (aversão ao risco) deve ser > 0.")
        if not 0.0 < beta < 1.0:
            raise ValueError("β (fator de desconto) deve estar em (0, 1).")
        if w0 <= 0:
            raise ValueError("W₀ (riqueza inicial) deve ser > 0.")
        if horizonte < 1:
            raise ValueError("horizonte T deve ser ≥ 1.")
        self.gamma = float(gamma)
        self.beta = float(beta)
        self.w0 = float(w0)
        self.horizonte = int(horizonte)
        self._alpha_star: np.ndarray | None = None
        self._phi_hat: float | None = None
        self._A: np.ndarray | None = None

    # utilidade CRRA (F5)
    def utilidade(self, c):
        """u(c) = c^(1−γ)/(1−γ) (ou ln c se γ=1). (F5)"""
        c = np.asarray(c, dtype=float)
        if np.isclose(self.gamma, 1.0):
            return np.log(c)
        return c ** (1.0 - self.gamma) / (1.0 - self.gamma)

    def utilidade_marginal(self, c):
        """u'(c) = c^(−γ). (F5)"""
        return np.asarray(c, dtype=float) ** (-self.gamma)

    # decisao de carteira e de consumo (F6, F8, F9)
    def carteira_otima(self, mercado: RendaVariavel, rf: float, *,
                       n_scenarios: int = 100_000, seed: int | None = 42,
                       **opts) -> np.ndarray:
        """Carteira otima, resolvendo G(alpha)=0. (F6)

        Sorteia os cenarios do mercado (que vem liquidos) e converte pra fator
        bruto. O alpha e sempre livre, pode ser negativo e pode passar de 1.

        O que vier em opts vai direto pro nucleo.resolver_alpha_otimo
        (tol, maxiter, alpha0).
        """
        r = mercado.amostrar(n_scenarios, seed=seed)
        rf_bruto = 1.0 + rf
        R = np.maximum(1.0 + r, 0.0)  # resp. limitada do ativo: preço não fica < 0
        alpha = nucleo.resolver_alpha_otimo(R, rf_bruto, self.gamma, **opts)
        self._alpha_star = alpha
        self._phi_hat = nucleo.phi_chapeu(alpha, R, rf_bruto, self.gamma)
        return alpha

    def fracoes_consumo(self) -> np.ndarray:
        """Frações de consumo theta_t = A_t^(−1/γ), t=0..T. (F8, F9)

        Requer carteira_otima(...) chamado antes (usa o Phi_chapeu guardado).
        """
        if self._phi_hat is None:
            raise RuntimeError(
                "chame carteira_otima() antes de fracoes_consumo(): "
                "as fracoes de consumo dependem do phi, que sai da carteira."
            )
        self._A = nucleo.recorrencia_A(self._phi_hat, self.beta, self.gamma, self.horizonte)
        return nucleo.fracoes_consumo(self._A, self.gamma)

    @property
    def alpha_star(self) -> np.ndarray | None:
        """Última carteira ótima alpha* calculada (ou None)."""
        return self._alpha_star

    @property
    def phi_hat(self) -> float | None:
        """Phi_chapeu da última política ótima (ou None)."""
        return self._phi_hat

    @property
    def coeficientes_A(self) -> np.ndarray | None:
        """Os coeficientes A_t da ultima recorrencia (Etapa 3), ou None.

        Ficam guardados porque a funcao valor (F11) precisa deles, e sem isso
        eles teriam que ser calculados de novo la na frente.
        """
        return self._A
