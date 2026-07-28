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
    """A_T=1; A_t=[1 + (β·A_{t+1}·Φ̂)^(1/γ)]^γ, t=T−1..0. Shape (T+1,). (F8)"""
    A = np.empty(T + 1)
    if np.isclose(gamma, 1.0):
        # Limite log: A_t = (1−β^{T−t+1})/(1−β) — independe de Φ̂.
        for t in range(T + 1):
            A[t] = (T - t + 1) if np.isclose(beta, 1.0) else (1 - beta ** (T - t + 1)) / (1 - beta)
        return A
    A[T] = 1.0
    inv_g = 1.0 / gamma
    for t in range(T - 1, -1, -1):
        inner = beta * A[t + 1] * phi
        A[t] = (1.0 + inner ** inv_g) ** gamma if inner > 0 else 1.0
    return A


def fracoes_consumo(A, gamma):
    """θ_t = A_t^(−1/γ) (ou 1/A_t se γ=1). (F8)"""
    A = np.asarray(A, dtype=float)
    if np.isclose(gamma, 1.0):
        return 1.0 / A
    return A ** (-1.0 / gamma)


def funcao_valor(A, W, gamma):
    """V_t(W) = A_t·W^(1−γ)/(1−γ) (γ≠1) ou A_t·ln(W) (γ=1). (F11)"""
    A = np.asarray(A, dtype=float)
    if np.isclose(gamma, 1.0):
        return A * np.log(W)
    return A * W ** (1.0 - gamma) / (1.0 - gamma)


def propagar_riqueza(w0, theta, alpha, R, rf):
    """Forward pass (Etapas 5–6): consome c_t=θ_t·W_t, investe a poupança em α*
    e propaga W_{t+1}=S_t·R_p. (F9, F10)

    Parameters
    ----------
    w0 : riqueza inicial W₀.
    theta : (T+1,) frações de consumo θ_t.
    alpha : (N,) carteira ótima α*.
    R : (n_paths, T, N) retornos brutos amostrados (um por período e caminho).
    rf : fator livre de risco bruto.

    Returns
    -------
    dict com ``W``, ``c``, ``S`` — cada um shape (n_paths, T+1).
    """
    R = np.asarray(R, dtype=float)
    alpha = np.asarray(alpha, dtype=float)
    theta = np.asarray(theta, dtype=float)
    n_paths, T, _ = R.shape
    W = np.empty((n_paths, T + 1))
    c = np.empty((n_paths, T + 1))
    S = np.empty((n_paths, T + 1))
    W[:, 0] = w0
    for t in range(T):
        c[:, t] = theta[t] * W[:, t]
        S[:, t] = W[:, t] - c[:, t]
        R_p = rf + (R[:, t, :] - rf) @ alpha           # (n_paths,)
        W[:, t + 1] = S[:, t] * R_p
    # Condição terminal: consome toda a riqueza (θ_T = 1).
    c[:, T] = theta[T] * W[:, T]
    S[:, T] = W[:, T] - c[:, T]
    return {"W": W, "c": c, "S": S}
