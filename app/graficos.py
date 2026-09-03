"""app.graficos: as figuras dos resultados (F16).

Escreve em results/ as imagens usadas no documento. Este modulo fica fora da
esteira: o app.principal nao importa ele, e por isso o matplotlib nunca e
carregado pela camada web, que desenha no navegador a partir do JSON.

Cada figura leva no rodape as informacoes da rodada que gerou ela: a base, a
janela dos dados, os parametros e o alfa que saiu. Assim uma figura solta
continua fazendo sentido, sem depender de um arquivo de metadados a parte que
poderia ficar desatualizado.

Roda com: python -m app --graficos
"""

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from app import nucleo

DESTINO_PADRAO = "results"

# os valores de gamma do grafico de sensibilidade. Cada ponto refaz a otimizacao.
GRADE_GAMMA = (1.5, 2.0, 3.0, 5.0, 8.0, 10.0, 15.0, 20.0)


def _rodape(fig, texto: str) -> None:
    """Escreve a linha de informacoes no rodape da figura."""
    fig.text(0.5, 0.012, texto, ha="center", fontsize=6.5, color="0.45")
    fig.subplots_adjust(bottom=0.22)


def _salvar(fig, destino: str, nome: str, rodape: str) -> str:
    _rodape(fig, rodape)
    caminho = os.path.join(destino, nome)
    fig.savefig(caminho, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return caminho


def montar_rodape(res: dict, cfg: dict, periodo: tuple[str, str], n_obs: int,
                  beta_anual: float, anos: float, unidade: str) -> str:
    """Texto de procedência impresso em todas as figuras."""
    return (f"Ibovespa {unidade} · {periodo[0]} a {periodo[1]} ({n_obs} obs) · "
            f"γ={cfg['gamma']:g} · β={beta_anual:g} a.a. · T={anos:g} anos · "
            f"{cfg['n_scenarios']:,} cenários · seed {cfg['seed']} · "
            f"α*={res['alpha_star'][0]:.4f}".replace(",", "."))


def gerar(res: dict, mercado, rf: float, cfg: dict, rodape: str,
          periodos_por_ano: int, destino: str = DESTINO_PADRAO) -> list[str]:
    """Faz as seis figuras e devolve os caminhos dos arquivos escritos.

    O res e o que o executar_pipeline devolveu. O mercado e o rf so sao
    necessarios para os dois graficos que refazem a otimizacao.
    """
    os.makedirs(destino, exist_ok=True)
    g = float(cfg["gamma"])
    Rf = 1.0 + rf
    T = res["horizonte"]
    escritos = []

    R = np.maximum(1.0 + mercado.amostrar(cfg["n_scenarios"], seed=cfg["seed"]), 0.0)

    # 1. G(alpha) contra alpha, marcando onde cruza o zero
    a_star = float(res["alpha_star"][0])
    grade = np.linspace(a_star - 1.0, a_star + 1.0, 60)
    G = [nucleo.funcao_foc(np.array([a]), R, Rf, g)[0] for a in grade]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.axhline(0, color="0.7", lw=0.8)
    ax.plot(grade, G, color="#1f77b4")
    ax.plot([a_star], [0], "o", color="#d62728", zorder=5,
            label=f"α* = {a_star:.4f}")
    ax.set_xlabel("α"); ax.set_ylabel("G(α)")
    ax.set_title("Condição de primeira ordem: G(α) = 0")
    ax.legend()
    escritos.append(_salvar(fig, destino, "foc_G_de_alpha.png", rodape))

    # 2. alpha contra gamma (a hiperbole de Merton)
    alphas = [nucleo.resolver_alpha_otimo(R, Rf, gi)[0] for gi in GRADE_GAMMA]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(GRADE_GAMMA, alphas, "o-", color="#1f77b4")
    ax.axvline(g, color="0.7", ls="--", lw=0.8)
    ax.set_xlabel("γ (aversão relativa ao risco)"); ax.set_ylabel("α*")
    ax.set_title("Sensibilidade da carteira ótima à aversão ao risco")
    escritos.append(_salvar(fig, destino, "alpha_vs_gamma.png", rodape))

    # 3. alpha contra T, que e a miopia (F12)
    Ts = np.array([1, T // 4, T // 2, 3 * T // 4, T])
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(Ts, np.full(Ts.shape, a_star), "o-", color="#2ca02c")
    ax.set_ylim(a_star - 0.05, a_star + 0.05)
    ax.set_xlabel("T (períodos restantes)"); ax.set_ylabel("α*")
    ax.set_title("Miopia: α* invariante ao horizonte")
    escritos.append(_salvar(fig, destino, "miopia_alpha_vs_T.png", rodape))

    # 4. as fracoes de consumo ao longo do tempo (F13)
    theta = res["theta"]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(np.arange(len(theta)), theta, color="#1f77b4")
    ax.set_yscale("log")          # sem log, θ_t fica rente a zero e só dispara no fim
    ax.set_xlabel("t (períodos)"); ax.set_ylabel(r"$\theta_t$ (escala log)")
    ax.set_title(r"Fração de consumo $\theta_t$ — crescente até $\theta_T = 1$")
    escritos.append(_salvar(fig, destino, "theta_t.png", rodape))

    # 5. a riqueza com a faixa entre os percentis 5 e 95
    t = np.arange(T + 1)
    media, p5, p95 = (res["trajetoria_W_media"], res["trajetoria_W_p5"],
                      res["trajetoria_W_p95"])
    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(7, 5.4), sharex=True,
                                  gridspec_kw={"height_ratios": [3, 1]})
    ax.fill_between(t, p5, p95, color="#1f77b4", alpha=0.3, label="P5–P95")
    ax.plot(t, media, color="#1f77b4", label="média")
    ax.set_yscale("log")
    ax.set_ylabel(r"$W_t$ (escala log)")
    ax.set_title("Trajetória da riqueza")
    ax.legend()

    largura = 100.0 * (p95 - p5) / np.where(media > 0, media, np.nan)
    ax2.plot(t, largura, color="#7f7f7f")
    ax2.set_xlabel("t (períodos)")
    ax2.set_ylabel("P95-P5\n(% da média)", fontsize=8)
    escritos.append(_salvar(fig, destino, "riqueza_W_t.png", rodape))

    # 6. consumo somado por ano
    c = res["trajetoria_c_media"]
    n_anos = max(1, T // periodos_por_ano)
    por_ano = [c[i * periodos_por_ano:(i + 1) * periodos_por_ano].sum()
               for i in range(n_anos)]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(np.arange(1, n_anos + 1), por_ano, color="#ff7f0e")
    ax.set_xlabel("ano"); ax.set_ylabel(r"consumo (fração de $W_0$)")
    ax.set_title("Consumo agregado por ano")
    escritos.append(_salvar(fig, destino, "consumo_por_ano.png", rodape))

    return escritos
