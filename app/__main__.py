"""Ponto de entrada do pacote: ``python -m app``.

Roda a esteira completa (``app.principal.executar_pipeline``) num exemplo
autocontido e imprime o resultado. Serve para conferir que a aplicação roda de
ponta a ponta sem a camada web.

Em uso real, os retornos vêm do SQLite populado pela DAL (a partir do Yahoo
Finance); aqui gerarei uma série sintética para a demonstração ser offline e
reprodutível.
"""

import os

import numpy as np
import pandas as pd

from app.principal import executar_pipeline

def _dados_demo(T: int = 300, seed: int = 7) -> pd.DataFrame:
    """Série sintética de retornos mensais (Ibovespa + CDI) para a demo."""
    rng = np.random.default_rng(seed)
    ruido = rng.normal(0.0, 0.06, T)
    ruido -= ruido.mean()                       # média exatamente 0
    return pd.DataFrame({
        "data": pd.date_range("2000-01", periods=T, freq="MS").strftime("%Y-%m"),
        "ibov": 0.015 + ruido,                  # prêmio positivo ⇒ α* interior
        "cdi": np.full(T, 0.008),
    })


def main() -> None:
    db = os.path.join("data", "mercado.db")
    comum = {"ativos": ["ibov"], "gamma": 5.0, "beta": 0.96, "w0": 1.0,
             "horizonte": 60, "n_scenarios": 60_000, "n_paths": 3_000, "seed": 1}
    if os.path.exists(db):
        print(f"(dados REAIS: {db} - R_f vem da serie real do CDI)")
        config = {"db_path": db, "tabela": "retornos", **comum}
    else:
        print("(SEM banco real -> dados SINTETICOS de demonstracao)")
        print("  para baixar dados reais:  python -m app.ingestao")
        config = {"retornos": _dados_demo(), "cdi_anual": 0.10, **comum}
    res = executar_pipeline(config)

    print("=== Esteira DP-CRRA-IID (Samuelson 1969) ===")
    print(f"Ativos de risco      : {res['ativos']}")
    print(f"R_f (mensal)         : {res['rf']:.6f}")
    print(f"mu_hat               : {np.round(res['mu_hat'], 5)}")
    print(f"Carteira otima a*   : {np.round(res['alpha_star'], 4)}")
    print(f"Phi_hat              : {res['phi_hat']:.6f}")
    print(f"Consumo inicial c_0  : {res['consumo_inicial']:.4f}  (theta_0={res['theta'][0]:.4f})")
    print(f"theta_T (terminal)   : {res['theta'][-1]:.4f}")
    print(f"E[W_T] (T={res['horizonte']})        : {res['E_W_T']:.4f}  "
          f"[P5={res['W_T_p5']:.4f}, P95={res['W_T_p95']:.4f}]")


if __name__ == "__main__":
    main()
