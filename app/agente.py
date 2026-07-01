"""app.agente — o indivíduo/investidor CRRA.

POO: encapsula as primitivas do agente (γ, β, W₀, T) e orquestra a sua
decisão, delegando a matemática a ``app.nucleo`` (F5, F6, F8, F9).

Fluxo da decisão:
  1. amostra cenários de retorno do mercado (líquidos);
  2. converte para fatores brutos e aplica responsabilidade limitada (R ≥ 0);
  3. resolve a FOC G(α*)=0 (carteira ótima) e guarda α* e Φ̂;
  4. da recorrência A_t deriva as frações de consumo θ_t.
"""

from __future__ import annotations

import numpy as np

from app.mercado import RendaVariavel


class Investidor:
    """Agente CRRA com decisão de consumo e portfólio. (F5)"""

    def __init__(
        self,
        gamma: float,
        beta: float,
        w0: float,
        horizonte: int,
    ) -> None:
        """Inicializa o agente CRRA.

        Parameters
        ----------
        gamma : aversão ao risco (γ > 0)
        beta : fator de desconto (0 < β < 1)
        w0 : riqueza inicial (W₀ > 0)
        horizonte : horizonte de decisão T (≥ 1)
        """
        ...

    # ── Utilidade CRRA (F5) ────────────────────────────────────────────────
    def utilidade(self, c) -> np.ndarray:
        """u(c) = c^(1−γ)/(1−γ) (ou ln c se γ = 1). (F5)"""
        ...

    def utilidade_marginal(self, c) -> np.ndarray:
        """u'(c) = c^(−γ). (F5)"""
        ...

    # ── Decisão de portfólio e consumo (F6, F8, F9) ────────────────────────
    def carteira_otima(
        self,
        mercado: RendaVariavel,
        rf: float,
        n_scenarios: int = 100_000,
        distribuicao: str = "normal",
        nu: float | None = None,
        seed: int | None = 42,
    ) -> np.ndarray:
        """Calcula a carteira ótima α* via FOC G(α*) = 0. (F6)

        O método:
          - amostra cenários de retorno do mercado;
          - converte retornos líquidos em fatores brutos;
          - aplica responsabilidade limitada (R ≥ 0);
          - resolve o problema via ``nucleo.resolver_alpha_otimo``;
          - armazena α* e Φ̂ internamente para uso posterior.

        Parameters adicionais são repassados ao solver do núcleo.
        """
        ...

    def fracoes_consumo(self) -> np.ndarray:
        """Retorna frações de consumo θ_t = A_t^(−1/γ), t = 0..T.

        Requer que ``carteira_otima`` tenha sido chamada previamente.
        """
        ...

    def alpha_star(self) -> np.ndarray | None:
        """Última carteira ótima α* calculada."""
        ...

    def phi_hat(self) -> float | None:
        """Valor de Φ̂ associado à última solução ótima."""
        ...
