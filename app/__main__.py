"""Ponto de entrada do pacote: ``python -m app``.

Roda a esteira completa (``app.principal.executar_pipeline``) e imprime o
resultado. Serve para conferir que a aplicação roda de ponta a ponta sem a
camada web, e para experimentar parâmetros sem editar código:

    python -m app                                   # base diária, defaults
    python -m app --anos 20 --beta-anual 0.90
    python -m app --mensal --anos 10
    python -m app --graficos                        # + figuras em results/
    python -m app --help                            # lista tudo

Se o banco não existir, uma série sintética na frequência pedida mantém a
demonstração offline e reprodutível.

**Convenção de β.** O desconto é escolhido em termos **anuais** e convertido para
o período dos dados: ``β_período = β_anual^(1/períodos_por_ano)``. β é
adimensional e não afeta α* (a CPO da carteira não contém β — daí a miopia); ele
governa apenas a recorrência A_t e, portanto, as frações de consumo θ_t. Declarar
o valor anual evita a ambiguidade de "β = 0.96" sem dizer a que período se refere.
"""

import argparse
import os
import sys

import numpy as np
import pandas as pd

from app.principal import executar_pipeline

# Períodos por ano, banco e n_scenarios default de cada frequência.

PERFIS = {
    "1d":  {"periodos_por_ano": 252, "db": os.path.join("data", "mercado_diario.db"),
            "n_scenarios": 4_000_000, "unidade": "pregao",
            "mu": 0.0007, "sigma": 0.011, "cdi": 0.00049, "freq_pandas": "B"},
    "1mo": {"periodos_por_ano": 12,  "db": os.path.join("data", "mercado.db"),
            "n_scenarios": 200_000, "unidade": "mes",
            "mu": 0.015, "sigma": 0.06, "cdi": 0.008, "freq_pandas": "MS"},
}

BETA_ANUAL = 0.96
GAMMA = 5.0
ANOS = 5
W0 = 1.0


def _dados_demo(perfil: dict, n: int = 1_050, seed: int = 7) -> pd.DataFrame:
    """
    Série sintética de retornos (Ibovespa + CDI) na frequência do perfil.
    """
    
    rng = np.random.default_rng(seed)
    ruido = rng.normal(0.0, perfil["sigma"], n)
    ruido -= ruido.mean()                       # média exatamente 0
    datas = pd.date_range("2022-05-24", periods=n, freq=perfil["freq_pandas"])
    fmt = "%Y-%m-%d" if perfil["periodos_por_ano"] == 252 else "%Y-%m"
    return pd.DataFrame({
        "data": datas.strftime(fmt),
        "ibov": perfil["mu"] + ruido,
        "cdi": np.full(n, perfil["cdi"]),
    })


def _analisar(argv) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="python -m app",
        description="Roda a esteira de Samuelson (1969) sobre Ibovespa + CDI.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--mensal", action="store_true",
                   help="usa a base mensal em vez da diária")
    p.add_argument("--anos", type=float, default=ANOS,
                   help="horizonte de planejamento T, em anos")
    p.add_argument("--beta-anual", type=float, default=BETA_ANUAL,
                   help="fator de desconto ANUAL (convertido para o período)")
    p.add_argument("--gamma", type=float, default=GAMMA,
                   help="coeficiente de aversao relativa ao risco")
    p.add_argument("--w0", type=float, default=W0, help="riqueza inicial")
    p.add_argument("--n-scenarios", type=int, default=0,
                   help="cenarios de Monte Carlo; 0 = automatico por frequencia "
                        "(4M diario, 200k mensal)")
    p.add_argument("--n-paths", type=int, default=3_000,
                   help="trajetorias simuladas no forward pass")
    p.add_argument("--seed", type=int, default=1, help="semente (reprodutibilidade)")
    p.add_argument("--graficos", action="store_true",
                   help="alem de imprimir, escreve as figuras em results/")
    return p.parse_args(argv)


def main(argv=()) -> None:
    """Executa a esteira. ``argv``."""
    args = _analisar(list(argv))
    perfil = PERFIS["1mo" if args.mensal else "1d"]
    ppa = perfil["periodos_por_ano"]
    unid = perfil["unidade"]
    T = int(round(ppa * args.anos))
    n_scenarios = args.n_scenarios or perfil["n_scenarios"]

    comum = {"ativos": ["ibov"], "periodos_por_ano": ppa, "gamma": args.gamma,
             "beta_anual": args.beta_anual, "w0": args.w0,
             "horizonte": T, "n_scenarios": n_scenarios,
             "n_paths": args.n_paths, "seed": args.seed}
    if os.path.exists(perfil["db"]):
        print(f"(dados REAIS: {perfil['db']} - R_f vem da serie real do CDI)")
        config = {"db_path": perfil["db"], "tabela": "retornos", **comum}
    else:
        alvo = "--diario" if ppa == 252 else ""
        print("(SEM banco real -> dados SINTETICOS de demonstracao)")
        print(f"  para baixar dados reais:  python -m app.ingestao 2022-05-22 {alvo}".rstrip())
        config = {"retornos": _dados_demo(perfil), **comum}
    res = executar_pipeline(config)

    rf_a = (1 + res["rf"]) ** ppa - 1
    mu_a = (1 + res["mu_hat"][0]) ** ppa - 1

    print(f"=== Esteira DP-CRRA-IID (Samuelson 1969) — base {'mensal' if args.mensal else 'diaria'} ===")
    print(f"Ativos de risco      : {res['ativos']}")
    print(f"R_f ({unid})         : {res['rf']:.8f}   ({rf_a:.2%} a.a.)")
    print(f"mu_hat ({unid})      : {res['mu_hat'][0]:.8f}   ({mu_a:.2%} a.a.)")
    print(f"gamma                : {args.gamma}")
    print(f"Carteira otima a*   : {np.round(res['alpha_star'], 4)}")
    print(f"Phi_hat              : {res['phi_hat']:.6f}")
    print(f"beta                 : {res['beta']:.6f} por {unid}  ({args.beta_anual:.4g} a.a.)")
    print(f"theta_0 ({unid})     : {res['theta'][0]:.6f}")
    print(f"theta_T (terminal)   : {res['theta'][-1]:.4f}")

    c = res["trajetoria_c_media"]
    print(f"Consumo por ano (frac. de W_0), horizonte de {args.anos:g} anos:")
    for ano in range(int(args.anos)):
        fatia = c[ano * ppa:(ano + 1) * ppa]
        print(f"   ano {ano + 1}: {fatia.sum():.4f}")
    print(f"E[W_T] (T={res['horizonte']})      : {res['E_W_T']:.6f}  "
          f"[P5={res['W_T_p5']:.6f}, P95={res['W_T_p95']:.6f}]")

    if args.graficos:
        from app import graficos
        from app.mercado import RendaVariavel
        ret = config.get("retornos")
        if ret is None:
            from app import dal
            ret = dal.ler_sqlite(config["db_path"], config["tabela"])
        mercado = RendaVariavel(ret[["data"] + config["ativos"]])
        rodape = graficos.montar_rodape(
            res, comum, (ret["data"].iloc[0], ret["data"].iloc[-1]), len(ret),
            args.beta_anual, args.anos, "diario" if ppa == 252 else "mensal")
        escritos = graficos.gerar(res, mercado, res["rf"], comum, rodape, ppa)
        print(f"Figuras escritas em {graficos.DESTINO_PADRAO}/:")
        for c in escritos:
            print(f"   {os.path.basename(c)}")


if __name__ == "__main__":
    main(sys.argv[1:])
