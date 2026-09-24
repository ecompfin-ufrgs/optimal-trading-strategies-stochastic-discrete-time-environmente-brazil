"""app.graficos: as figuras dos resultados do modelo (F15).

Gera em results/ as ilustracoes usadas no documento. Este modulo fica fora da
esteira: o app.principal nao importa ele, entao quem so quer o resultado
numerico nao paga o custo de carregar o matplotlib.

Cada figura leva no rodape a procedencia, em duas linhas: de onde vieram os
numeros (a serie, se a base e real ou sintetica, a janela e o R_f) e com que
parametros a rodada foi feita.

Uso: python -m app --graficos (os parametros sao os da propria execucao).
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

# os graficos de mu e de sigma refazem a otimizacao nos mesmos cenarios,
# O de theta_0 usa esses betas anuais.
DESLOCAMENTOS_MU_ANUAL = (-0.06, -0.04, -0.02, 0.0, 0.02, 0.04, 0.06)
ESCALAS_SIGMA = (0.5, 0.75, 1.0, 1.25, 1.5)
BETAS_ANUAIS = (0.86, 0.88, 0.90, 0.92, 0.94, 0.96, 0.98)

# o grafico do consumo contra o premio de risco usa esses premios (mu - R_f,
# ao ano) e esses valores de gamma
PREMIOS_ANUAIS = (0.0, 0.02, 0.04, 0.06, 0.08)
GAMMAS_CONSUMO = (0.5, 1.0, 2.0, 5.0)


def _rodape(fig, texto: str) -> None:
    """Escreve as duas linhas de informacoes no rodape da figura."""
    fig.text(0.5, 0.012, texto, ha="center", va="bottom", fontsize=6.5,
             color="0.45", linespacing=1.5)
    fig.subplots_adjust(bottom=0.26)


def _salvar(fig, destino: str, nome: str, rodape: str) -> str:
    _rodape(fig, rodape)
    caminho = os.path.join(destino, nome)
    fig.savefig(caminho, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return caminho


def montar_rodape(res: dict, cfg: dict, periodo: tuple[str, str], n_obs: int,
                  beta_anual: float, anos: float, unidade: str,
                  dados_reais: bool = True) -> str:
    """Texto de procedencia impresso em todas as figuras."""
    rf_anual = (1.0 + res["rf"]) ** cfg["periodos_por_ano"] - 1.0
    origem_rf = "informado" if cfg.get("cdi_anual") is not None else "série CDI"
    fonte = "dados reais" if dados_reais else "dados SINTÉTICOS"
    cenarios = f"{cfg['n_scenarios']:,}".replace(",", ".")
    trajetorias = f"{cfg['n_paths']:,}".replace(",", ".")

    periodo_beta = "pregão" if cfg["periodos_por_ano"] == 252 else "mês"
    return (f"Ibovespa {unidade} ({fonte}) · {periodo[0]} a {periodo[1]} "
            f"({n_obs} obs) · R_f={rf_anual:.2%} a.a. ({origem_rf})\n"
            f"γ={cfg['gamma']:g} · β={beta_anual:g} a.a. "
            f"({res['beta']:.6f} por {periodo_beta}) · T={anos:g} anos · "
            f"W₀={cfg['w0']:g} · {cenarios} cenários · "
            f"{trajetorias} trajetórias · seed {cfg['seed']} · "
            f"α*={res['alpha_star'][0]:.4f}")


def gerar(res: dict, mercado, rf: float, cfg: dict, rodape: str,
          destino: str = DESTINO_PADRAO) -> list[str]:
    """Faz as nove figuras e devolve os caminhos dos arquivos escritos.

    O res e o que o executar_pipeline devolveu. O mercado e o rf so sao
    necessarios para os cinco graficos que voltam a usar os cenarios: quatro
    refazem a otimizacao e o do G(alpha) so reavalia a FOC. O consumo somado
    por ano ja vem pronto em res["consumo_por_ano"], entao a figura e a linha
    de comando leem o mesmo numero.
    """
    os.makedirs(destino, exist_ok=True)
    g = float(cfg["gamma"])
    Rf = 1.0 + rf
    T = res["horizonte"]
    escritos = []

    ppa = cfg["periodos_por_ano"]
    r = mercado.amostrar(cfg["n_scenarios"], seed=cfg["seed"])
    R = np.maximum(1.0 + r, 0.0)

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

    # 2. alpha contra gamma
    alphas = [nucleo.resolver_alpha_otimo(R, Rf, gi)[0] for gi in GRADE_GAMMA]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(GRADE_GAMMA, alphas, "o-", color="#1f77b4")
    ax.axvline(g, color="0.7", ls="--", lw=0.8)
    ax.set_xlabel("γ (aversão relativa ao risco)"); ax.set_ylabel("α*")
    ax.set_title("Sensibilidade da carteira ótima à aversão ao risco")
    escritos.append(_salvar(fig, destino, "alpha_vs_gamma.png", rodape))

    # 3. alpha contra mu
    mu = float(res["mu_hat"][0])
    mu_anual = (1.0 + mu) ** ppa - 1.0
    medias = mu_anual + np.array(DESLOCAMENTOS_MU_ANUAL)
    alphas_mu = [nucleo.resolver_alpha_otimo(
                     np.maximum(1.0 + r + (1.0 + m) ** (1.0 / ppa) - 1.0 - mu, 0.0), Rf, g)[0]
                 for m in medias]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.axhline(0, color="0.7", lw=0.8)
    ax.plot(100 * medias, alphas_mu, "o-", color="#1f77b4")
    ax.axvline(100 * mu_anual, color="0.7", ls="--", lw=0.8)
    ax.set_xlabel(r"$\mu$ (retorno esperado, % a.a.)"); ax.set_ylabel(r"$\alpha^*$")
    ax.set_title("Sensibilidade da carteira ótima ao retorno esperado")
    escritos.append(_salvar(fig, destino, "alpha_vs_mu.png", rodape))

    # 4. alpha contra sigma
    media_r = r.mean(axis=0)
    sigma_anual = float(np.sqrt(res["sigma_hat"][0, 0] * ppa))
    alphas_sigma = [nucleo.resolver_alpha_otimo(
                        np.maximum(1.0 + media_r + (r - media_r) * k, 0.0), Rf, g)[0]
                    for k in ESCALAS_SIGMA]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(100 * sigma_anual * np.array(ESCALAS_SIGMA), alphas_sigma, "o-", color="#1f77b4")
    ax.axvline(100 * sigma_anual, color="0.7", ls="--", lw=0.8)
    ax.set_xlabel(r"$\sigma$ (volatilidade, % a.a.)"); ax.set_ylabel(r"$\alpha^*$")
    ax.set_title("Sensibilidade da carteira ótima à volatilidade")
    escritos.append(_salvar(fig, destino, "alpha_vs_sigma.png", rodape))

    # 5. as fracoes de consumo ao longo do tempo (F13)
    theta = res["theta"]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(np.arange(len(theta)), theta, color="#1f77b4")
    ax.set_yscale("log") 
    ax.set_xlabel("t (períodos)"); ax.set_ylabel(r"$\theta_t$ (escala log)")
    ax.set_title(r"Fração de consumo $\theta_t$ (crescente até $\theta_T = 1$)")
    escritos.append(_salvar(fig, destino, "theta_t.png", rodape))

    # 6. theta_0 contra beta.
    theta_0 = [nucleo.fracoes_consumo(
                   nucleo.recorrencia_A(res["phi_hat"], b ** (1.0 / ppa), g, T), g)[0]
               for b in BETAS_ANUAIS]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(BETAS_ANUAIS, theta_0, "o-", color="#1f77b4")
    ax.axvline(res["beta"] ** ppa, color="0.7", ls="--", lw=0.8)
    ax.set_xlabel(r"$\beta$ (fator de desconto, ao ano)")
    ax.set_ylabel(r"$\theta_0$ (fração consumida em t = 0)")
    ax.set_title("Sensibilidade da fração de consumo ao fator de desconto")
    escritos.append(_salvar(fig, destino, "theta_vs_beta.png", rodape))

    # 7. theta_0 contra o premio de risco, uma curva por gamma.
    rf_anual = (1.0 + rf) ** ppa - 1.0
    media_amostra = float(r.mean())
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.axhline(0, color="0.7", lw=0.8)
    for gi in GAMMAS_CONSUMO:
        theta_p = []
        for p in PREMIOS_ANUAIS:
            cenarios = np.maximum(1.0 + r + (1.0 + rf_anual + p) ** (1.0 / ppa) - 1.0 - media_amostra, 0.0)
            a = nucleo.resolver_alpha_otimo(cenarios, Rf, gi)
            A_p = nucleo.recorrencia_A(nucleo.phi_chapeu(a, cenarios, Rf, gi), res["beta"], gi, T)
            theta_p.append(nucleo.fracoes_consumo(A_p, gi)[0])
        ax.plot(100 * np.array(PREMIOS_ANUAIS), 100 * (np.array(theta_p) / theta_p[0] - 1.0),
                "o-", label=rf"$\gamma$ = {gi:g}")
    ax.set_xlabel(r"prêmio de risco $\mu - R_f$ (p.p. ao ano)")
    ax.set_ylabel(r"variação de $\theta_0$ desde o prêmio zero (%)", fontsize=9)
    ax.set_title("Efeito do prêmio de risco sobre a fração de consumo")
    ax.legend()
    escritos.append(_salvar(fig, destino, "theta_vs_premio.png", rodape))

    # 8. a riqueza com a faixa entre os percentis 5 e 95
    t = np.arange(T + 1)
    media, p5, p95 = (res["trajetoria_W_media"], res["trajetoria_W_p5"],
                      res["trajetoria_W_p95"])
    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(7, 5.4), sharex=True,
                                  gridspec_kw={"height_ratios": [3, 1]})
    ax.fill_between(t, p5, p95, color="#1f77b4", alpha=0.3, label="P5-P95")
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

    # 9. consumo somado por ano
    por_ano = res["consumo_por_ano"]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(np.arange(1, len(por_ano) + 1), por_ano, color="#ff7f0e")
    ax.set_xlabel("ano"); ax.set_ylabel(r"consumo (fração de $W_0$)")
    ax.set_title("Consumo agregado por ano")
    escritos.append(_salvar(fig, destino, "consumo_por_ano.png", rodape))

    return escritos
