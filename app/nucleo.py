"""app.nucleo: as contas do modelo de Samuelson (1969).

Aqui nao tem estado nenhum. Cada funcao e uma equacao do artigo e da pra
testar sozinha (F6 a F11). E a parte "funcional" da separacao pedida no NF5.

Uma convencao importante: R e rf sao fatores de retorno BRUTO (1.02, 1.008),
e nao a variacao. Assim o retorno bruto da carteira fica

    R_p = rf + alfa * (R - rf)        e o excesso e (R - rf).

Quem faz a conversao e o app.agente: ele pega os retornos liquidos do mercado,
soma 1 e corta em zero (a acao nao pode valer menos que nada) antes de chamar
estas funcoes.
"""

import numpy as np
from scipy import optimize

# piso de seguranca pro R_p, pra ele nunca ficar zero ou negativo na potencia
_TOL_FALENCIA = 1e-12

# intervalo onde o brentq comeca procurando a raiz (caso de 1 ativo so).
# Com dados mensais o alfa fica bem longe de 20, mas se G nao trocar de sinal
# dentro do intervalo ele vai sendo dobrado ate 8 vezes.
_BRACKET_INICIAL = 20.0
_MAX_EXPANSOES = 8


def funcao_foc(alpha, R, rf, gamma):
    """G(alpha) = E[(R − rf·1) / R_p^γ], com R_p = rf + αᵀ(R − rf·1). Shape (N,). (F6)"""
    alpha = np.asarray(alpha, dtype=float)
    excesso = R - rf                                    # (n, N)
    R_p = np.maximum(rf + excesso @ alpha, _TOL_FALENCIA)  # (n,)
    pesos = R_p ** (-gamma)
    return (excesso.T @ pesos) / R.shape[0]


def _objetivo_J(alpha, R, rf, gamma):
    """J(alfa) = E[u(R_p)]. E esta funcao que o solver maximiza; a derivada dela e o G."""
    excesso = R - rf
    R_p = np.maximum(rf + excesso @ alpha, _TOL_FALENCIA)
    if np.isclose(gamma, 1.0):
        u = np.log(R_p)
    else:
        u = R_p ** (1.0 - gamma) / (1.0 - gamma)
    return float(u.mean())


def resolver_alpha_otimo(R, rf, gamma, *, tol=1e-10, maxiter=200, alpha0=None):
    """Acha o alfa que zera a condicao de primeira ordem, G(alfa)=0. (F6)

    Como no artigo, o alfa pode ser qualquer numero: pode ficar negativo
    (venda a descoberto) e pode passar de 1 (alavancagem), sem limite.
    Com 2 ativos ou mais usa o SLSQP; com 1 ativo so usa o brentq.
    """
    
    R = np.asarray(R, dtype=float)
    N = R.shape[1]
    if alpha0 is None:
        alpha0 = np.full(N, 1.0 / N)

    if N >= 2:
        res = optimize.minimize(
            lambda a: -_objetivo_J(a, R, rf, gamma), np.asarray(alpha0, float),
            jac=lambda a: -funcao_foc(a, R, rf, gamma),
            method="SLSQP",
            options={"ftol": tol, "maxiter": int(maxiter), "disp": False})
        return res.x.copy()

    # caso de 1 ativo, com brentq. O G so cai, entao procuro G(lo) > 0 > G(hi).
    g = lambda a: float(funcao_foc(np.array([a]), R, rf, gamma)[0])
    lo = -_BRACKET_INICIAL
    hi = _BRACKET_INICIAL
    for _ in range(_MAX_EXPANSOES):
        if g(lo) > 0 > g(hi):
            return np.array([optimize.brentq(g, lo, hi, xtol=tol)])
        lo *= 2.0
        hi *= 2.0
    raise RuntimeError(
        f"FOC sem troca de sinal em α ∈ [{lo / 2:.0f}, {hi / 2:.0f}]: não há α* "
        "finito. Verifique se a amostra de R contém cenários acima e abaixo de rf."
    )


def phi_chapeu(alpha, R, rf, gamma):
    """Phi_chapeu = E[R_p^(1−γ)] do portfólio ótimo (ou E[ln R_p] se γ=1). (F7)"""
    alpha = np.asarray(alpha, dtype=float)
    excesso = R - rf
    R_p = np.maximum(rf + excesso @ alpha, _TOL_FALENCIA)
    if np.isclose(gamma, 1.0):
        return float(np.mean(np.log(R_p)))
    return float(np.mean(R_p ** (1.0 - gamma)))


def recorrencia_A(phi, beta, gamma, T):
    """A_T=1; A_t=[1 + (beta·A_{t+1}·Phi_chapeu)^(1/γ)]^γ, t=T−1..0. Shape (T+1,). (F8)"""
    A = np.empty(T + 1)
    if np.isclose(gamma, 1.0):
        # caso gamma=1 (utilidade log): A_t = (1-beta^(T-t+1))/(1-beta), nao usa o phi
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
    """theta_t = A_t^(−1/γ) (ou 1/A_t se γ=1). (F8)"""
    A = np.asarray(A, dtype=float)
    if np.isclose(gamma, 1.0):
        return 1.0 / A
    return A ** (-1.0 / gamma)


def funcao_valor(A, W, gamma):
    """V_t(W) = A_t·W^(1−γ)/(1−γ) (γ diferente de 1) ou A_t·ln(W) (γ=1). (F11)"""
    A = np.asarray(A, dtype=float)
    if np.isclose(gamma, 1.0):
        return A * np.log(W)
    return A * W ** (1.0 - gamma) / (1.0 - gamma)


def propagar_riqueza(w0, theta, alpha, R, rf):
    """Simula pra frente (Etapas 5 e 6). Em cada periodo consome theta*W,
    investe o que sobrou no alfa otimo e calcula a riqueza do periodo seguinte,
    W = poupanca * R_p. (F9, F10)

    Recebe: w0 (riqueza inicial), theta (as fracoes de consumo, T+1 valores),
    alpha (a carteira otima), R (os retornos brutos sorteados, um por periodo
    e por caminho) e rf (o fator livre de risco bruto).

    Devolve um dicionario com W (riqueza), c (consumo) e S (poupanca), cada um
    com uma linha por caminho e uma coluna por periodo.
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
    # Condição terminal: consome toda a riqueza (theta_T = 1).
    c[:, T] = theta[T] * W[:, T]
    S[:, T] = W[:, T] - c[:, T]
    return {"W": W, "c": c, "S": S}
