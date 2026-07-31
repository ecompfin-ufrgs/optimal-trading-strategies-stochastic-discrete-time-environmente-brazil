"""app.agente — o indivíduo/investidor CRRA.

POO: encapsula as primitivas do agente (γ, β, W₀, T) e orquestra a sua
decisão, delegando a matemática a ``app.nucleo`` (F5, F6, F8, F9).

Fluxo da decisão:
  1. amostra cenários de retorno do mercado (líquidos);
  2. converte para fatores brutos e aplica responsabilidade limitada (R ≥ 0);
  3. resolve a FOC G(α*)=0 (carteira ótima) e guarda α* e Φ̂;
  4. da recorrência A_t deriva as frações de consumo θ_t.
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

    # ── Utilidade CRRA (F5) ─────────────────────────────────────────────────
    def utilidade(self, c):
        """u(c) = c^(1−γ)/(1−γ) (ou ln c se γ=1). (F5)"""
        c = np.asarray(c, dtype=float)
        if np.isclose(self.gamma, 1.0):
            return np.log(c)
        return c ** (1.0 - self.gamma) / (1.0 - self.gamma)

    def utilidade_marginal(self, c):
        """u'(c) = c^(−γ). (F5)"""
        return np.asarray(c, dtype=float) ** (-self.gamma)

    # ── Decisão de portfólio e consumo (F6, F8, F9) ─────────────────────────
    def carteira_otima(self, mercado: RendaVariavel, rf: float, *,
                       n_scenarios: int = 100_000, seed: int | None = 42,
                       **opts) -> np.ndarray:
        """Carteira ótima α* via FOC G(α*)=0. (F6)

        Amostra cenários (líquidos) do mercado e converte para fatores brutos.
        **α é sempre irrestrito** (short e alavancagem permitidos, sem teto),
        fiel ao PDF (§3.1).

        ``opts`` é repassado a ``nucleo.resolver_alpha_otimo`` (``tol``,
        ``maxiter``, ``alpha0``).
        """
        r = mercado.amostrar(n_scenarios, seed=seed)
        rf_bruto = 1.0 + rf
        R = np.maximum(1.0 + r, 0.0)  # resp. limitada do ativo: preço não fica < 0
        alpha = nucleo.resolver_alpha_otimo(R, rf_bruto, self.gamma, **opts)
        self._alpha_star = alpha
        self._phi_hat = nucleo.phi_chapeu(alpha, R, rf_bruto, self.gamma)
        return alpha

    def fracoes_consumo(self) -> np.ndarray:
        """Frações de consumo θ_t = A_t^(−1/γ), t=0..T. (F8, F9)

        Requer ``carteira_otima(...)`` chamado antes (usa o Φ̂ guardado).
        """
        if self._phi_hat is None:
            raise RuntimeError(
                "chame carteira_otima(...) antes de fracoes_consumo() — "
                "θ_t depende de Φ̂, que vem da política ótima."
            )
        A = nucleo.recorrencia_A(self._phi_hat, self.beta, self.gamma, self.horizonte)
        return nucleo.fracoes_consumo(A, self.gamma)

    @property
    def alpha_star(self) -> np.ndarray | None:
        """Última carteira ótima α* calculada (ou None)."""
        return self._alpha_star

    @property
    def phi_hat(self) -> float | None:
        """Φ̂ da última política ótima (ou None)."""
        return self._phi_hat
