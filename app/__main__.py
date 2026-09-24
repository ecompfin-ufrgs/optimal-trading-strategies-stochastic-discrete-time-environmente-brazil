"""Ponto de entrada do pacote: ``python -m app`` (F14, NF2, NF5).

Roda a esteira completa (``app.principal.executar_pipeline``) e imprime o
resultado. Serve pra conferir que a aplicacao roda de ponta a ponta e pra
experimentar parametros sem editar codigo:

    python -m app                                   # base mensal, defaults
    python -m app --diario                          # base diaria (252 pregoes)
    python -m app --anos 20 --beta-anual 0.90
    python -m app --cdi-anual 0.08                  # R_f hipotetico, 8% a.a.
    python -m app --graficos                        # + figuras em results/
    python -m app --help                            # lista tudo

A frequencia padrao e a mensal, a mesma da ingestao: ``python -m app.ingestao``
enche ``data/mercado.db`` e ``python -m app`` le de la. Para a base diaria sao
``python -m app.ingestao <inicio> --diario`` e ``python -m app --diario``.

Se o banco da frequencia pedida nao existir, uma serie sintetica mantem a
demonstracao rodando sem rede. As figuras dessa rodada saem marcadas como
sinteticas no rodape e vao para results/sinteticos/.

Este modulo so le parametros, escolhe a fonte de dados e formata a saida. As
contas do modelo estao todas na esteira. A unica excecao e a serie sintetica
aqui embaixo, que acompanha a interface porque existe so pra demonstracao.
"""

import argparse
import os
import sys

import numpy as np
import pandas as pd

from app.principal import executar_pipeline

# Periodos por ano, banco, n_scenarios e a serie sintetica de cada frequencia.
# A mensal vem primeiro por ser o padrao.

PERFIS = {
    "1mo": {"periodos_por_ano": 12,  "db": os.path.join("data", "mercado.db"),
            "n_scenarios": 200_000, "unidade": "mes",
            "mu": 0.015, "sigma": 0.06, "cdi": 0.008, "freq_pandas": "MS"},
    "1d":  {"periodos_por_ano": 252, "db": os.path.join("data", "mercado_diario.db"),
            "n_scenarios": 4_000_000, "unidade": "pregao",
            "mu": 0.0007, "sigma": 0.011, "cdi": 0.00049, "freq_pandas": "B"},
}

BETA_ANUAL = 0.96
GAMMA = 5.0
ANOS = 5
W0 = 1.0


def _dados_demo(perfil: dict, n: int = 1_050, seed: int = 7) -> pd.DataFrame:
    """Serie inventada de retornos, na frequencia do perfil escolhido."""

    rng = np.random.default_rng(seed)
    ruido = rng.normal(0.0, perfil["sigma"], n)
    ruido -= ruido.mean()                       # media exatamente 0
    datas = pd.date_range("2022-05-24", periods=n, freq=perfil["freq_pandas"])
    fmt = "%Y-%m-%d" if perfil["periodos_por_ano"] == 252 else "%Y-%m"
    return pd.DataFrame({
        "data": datas.strftime(fmt),
        "ibov": perfil["mu"] + ruido,
        "cdi": np.full(n, perfil["cdi"]),
    })


def _comando_ingestao(periodos_por_ano: int) -> str:
    """A linha de ingestao que enche o banco da frequencia pedida."""
    if periodos_por_ano == 252:
        return "python -m app.ingestao 2022-05-22 --diario"
    return "python -m app.ingestao"


def _analisar(argv) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="python -m app",
        description="Roda a esteira de Samuelson (1969) sobre Ibovespa + CDI.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--diario", action="store_true",
                   help="usa a base diaria (252 pregoes) no lugar da mensal")
    p.add_argument("--anos", type=float, default=ANOS,
                   help="horizonte de planejamento T, em anos")
    p.add_argument("--beta-anual", type=float, default=BETA_ANUAL,
                   help="fator de desconto ANUAL (convertido para o periodo)")
    p.add_argument("--gamma", type=float, default=GAMMA,
                   help="coeficiente de aversao relativa ao risco")
    p.add_argument("--cdi-anual", type=float, default=None,
                   help="CDI ANUAL em decimal (0.13 = 13%% a.a.), convertido "
                        "para o periodo; se omitido, usa a media da serie de "
                        "CDI dos dados")
    p.add_argument("--w0", type=float, default=W0, help="riqueza inicial")
    p.add_argument("--n-scenarios", type=int, default=0,
                   help="cenarios de Monte Carlo; 0 = automatico por frequencia "
                        "(200k mensal, 4M diario)")
    p.add_argument("--n-paths", type=int, default=3_000,
                   help="trajetorias simuladas na propagacao pra frente")
    p.add_argument("--seed", type=int, default=1, help="semente (reprodutibilidade)")
    p.add_argument("--graficos", action="store_true",
                   help="alem de imprimir, escreve as figuras em results/")
    args = p.parse_args(argv)
    if args.cdi_anual is not None and not -0.5 < args.cdi_anual < 1.0:
        p.error(f"--cdi-anual e em decimal e deve ficar entre -0.5 e 1.0; veio "
                f"{args.cdi_anual:g}. Para 13% ao ano use 0.13, e nao 13.")
    if args.anos <= 0:
        p.error(f"--anos deve ser positivo; veio {args.anos:g}.")
    return args


def main(argv=()) -> None:
    """Executa a esteira com os parametros de ``argv`` e imprime o resultado."""
    args = _analisar(list(argv))
    perfil = PERFIS["1d" if args.diario else "1mo"]
    ppa = perfil["periodos_por_ano"]
    unid = perfil["unidade"]
    T = int(round(ppa * args.anos))
    n_scenarios = args.n_scenarios or perfil["n_scenarios"]

    comum = {"ativos": ["ibov"], "periodos_por_ano": ppa, "gamma": args.gamma,
             "beta_anual": args.beta_anual, "w0": args.w0,
             "horizonte": T, "n_scenarios": n_scenarios,
             "n_paths": args.n_paths, "seed": args.seed}
    if args.cdi_anual is not None:
        comum["cdi_anual"] = args.cdi_anual

    origem_rf = ("do --cdi-anual" if args.cdi_anual is not None
                 else "da serie de CDI dos dados")
    dados_reais = os.path.exists(perfil["db"])
    if dados_reais:
        print(f"(dados REAIS: {perfil['db']} - R_f vem {origem_rf})")
        config = {"db_path": perfil["db"], "tabela": "retornos", **comum}
    else:
        print(f"(SEM banco real -> dados SINTETICOS de demonstracao; "
              f"R_f vem {origem_rf})")
        print(f"  para baixar dados reais:  {_comando_ingestao(ppa)}")
        config = {"retornos": _dados_demo(perfil), **comum}
    res = executar_pipeline(config)

    rf_a = (1 + res["rf"]) ** ppa - 1
    mu_a = (1 + res["mu_hat"][0]) ** ppa - 1

    def linha(rotulo: str, valor: str) -> None:
        """Mantem a coluna dos valores alinhada, com 'mes' ou com 'pregao'."""
        print(f"{rotulo:<22}: {valor}")

    print(f"=== Esteira DP-CRRA-IID (Samuelson 1969) - base "
          f"{'diaria' if args.diario else 'mensal'} ===")
    linha("Ativos de risco", f"{res['ativos']}")
    linha(f"R_f ({unid})", f"{res['rf']:.8f}   ({rf_a:.2%} a.a.)")
    linha(f"mu_hat ({unid})", f"{res['mu_hat'][0]:.8f}   ({mu_a:.2%} a.a.)")
    linha("gamma", f"{args.gamma}")
    linha("Carteira otima a*", f"{np.round(res['alpha_star'], 4)}")
    linha("Phi_hat", f"{res['phi_hat']:.6f}")
    linha("beta", f"{res['beta']:.6f} por {unid}  ({args.beta_anual:.4g} a.a.)")
    linha(f"theta_0 ({unid})", f"{res['theta'][0]:.6f}")
    linha("theta_T (terminal)", f"{res['theta'][-1]:.4f}")

    por_ano = res["consumo_por_ano"]
    print(f"Consumo por ano (frac. de W_0), horizonte de {args.anos:g} anos:")
    for i, total in enumerate(por_ano, start=1):
        parcial = " (ano parcial)" if i == len(por_ano) and T % ppa else ""
        print(f"   ano {i}: {total:.4f}{parcial}")
    linha(f"E[W_T] (T={res['horizonte']})",
          f"{res['E_W_T']:.6f}  [P5={res['W_T_p5']:.6f}, P95={res['W_T_p95']:.6f}]")

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
            args.beta_anual, args.anos, "diario" if ppa == 252 else "mensal",
            dados_reais=dados_reais)
        destino = (graficos.DESTINO_PADRAO if dados_reais
                   else os.path.join(graficos.DESTINO_PADRAO, "sinteticos"))
        escritos = graficos.gerar(res, mercado, res["rf"], comum, rodape,
                                  destino=destino)
        print(f"Figuras escritas em {destino}/:")
        for caminho in escritos:
            print(f"   {os.path.basename(caminho)}")


if __name__ == "__main__":
    main(sys.argv[1:])
