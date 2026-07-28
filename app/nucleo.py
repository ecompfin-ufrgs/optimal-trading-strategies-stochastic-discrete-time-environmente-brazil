"""app.nucleo — funções puras com a matemática do modelo (Samuelson 1969).

Sem estado: cada função implementa uma equação do artigo e é testável
isoladamente (F6–F11). Metade "funcional pura" da separação de paradigmas
da Seção 3.5.1 (NF5).

**Convenção — fatores brutos.** R e rf são *fatores* de retorno bruto
(ex.: 1.02, 1.008), de modo que o retorno bruto do portfólio é

    R_p = rf + αᵀ(R − rf·1)            e o excesso é (R − rf·1).

O agente converte os retornos *líquidos* do mercado (r, rf_líq) em brutos
(1+r, 1+rf_líq) e aplica a **responsabilidade limitada** (R ≥ 0) antes de
chamar estas funções (ver ``app.agente``).
"""

import numpy as np
from scipy import optimize

# Piso numérico de R_p (rede de segurança) — evita R_p ≤ 0 nas potências.
_TOL_FALENCIA = 1e-12

def funcao_foc(alpha, R, rf, gamma):
    """G(α) = E[(R − rf·1) / R_p^γ], com R_p = rf + αᵀ(R − rf·1). (F6)

    Retorna vetor gradiente da condição de primeira ordem.
    """
    ...


def _objetivo_J(alpha, R, rf, gamma):
    """J(α) = E[u(R_p(α))].

    Função objetivo cujo gradiente é a FOC G(α).
    """
    ...


def resolver_alpha_otimo(
    R,
    rf,
    gamma,
    *,
    allow_short: bool = True,
    allow_leverage: bool = True,
    alpha_max=np.inf,
    tol: float = 1e-10,
    maxiter: int = 200,
    alpha0=None,
):
    """Resolve a FOC G(α*) = 0 via otimização numérica. (F6)

    Casos:
      - N ≥ 2 → SLSQP
      - N = 1 → Brent (root-finding com KKT implícito)

    Por padrão permite solução irrestrita (short + leverage).
    """
    ...


def phi_chapeu(alpha, R, rf, gamma):
    """Φ̂ = E[R_p^(1−γ)] do portfólio ótimo (ou E[ln R_p] se γ=1). (F7)"""
    alpha = np.asarray(alpha, dtype=float)
    excesso = R - rf
    R_p = np.maximum(rf + excesso @ alpha, _TOL_FALENCIA)
    if np.isclose(gamma, 1.0):
        return float(np.mean(np.log(R_p)))
    return float(np.mean(R_p ** (1.0 - gamma)))


def recorrencia_A(phi, beta, gamma, T):
    """A_T = 1; A_t = f(A_{t+1}, β, Φ̂, γ). (F8)

    Gera sequência backward para horizonte T.
    """
    ...


def fracoes_consumo(A, gamma):
    """θ_t = A_t^(−1/γ). (F8)"""
    ...


def funcao_valor(A, W, gamma):
    """V_t(W) = A_t·u(W). (F11)

    Função valor fechada da solução CRRA.
    """
    ...


def propagar_riqueza(w0, theta, alpha, R, rf):
    """Forward pass da dinâmica de riqueza. (F9–F10)

    Simula:
      c_t = θ_t W_t
      W_{t+1} = (W_t − c_t) · R_p(α, R_t)

    Retorna trajetórias de W, consumo e poupança.
    """
    ...
