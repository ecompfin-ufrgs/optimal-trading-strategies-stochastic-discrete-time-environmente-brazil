"""app.principal — orquestrador da esteira pipes-and-filters.

Liga os filtros na ordem da esteira (F10, NF5):

    dal → mercado → agente (+ nucleo) → simulação → resultado

`executar_pipeline` é o **único ponto** que a camada web chama: ela passa um
`config` e recebe o resultado pronto (carteira ótima, consumo, trajetórias).
Toda a lógica vive nos módulos; aqui só há orquestração.
"""

import numpy as np

from app import dal, nucleo
from app.agente import Investidor
from app.mercado import RendaFixa, RendaVariavel


def executar_pipeline(config: dict) -> dict:
    """Executa a esteira de ponta a ponta e devolve os resultados. (NF5)

    Chaves de ``config``:
      Dados (uma das duas):
        ``retornos`` : DataFrame com ``data`` + colunas de ativos; OU
        ``db_path`` (+ ``tabela``, default ``'retornos'``) : lê do SQLite.
      Mercado:
        ``ativos`` : colunas de risco (default: todas menos ``data`` e ``rf_col``);
        ``rf_col`` : coluna da taxa livre de risco nos dados (default ``'cdi'``);
        ``cdi_anual`` : CDI anual p/ ``RendaFixa`` (se ausente, usa a média de ``rf_col``);
        ``periodos_por_ano`` : granularidade p/ converter ``cdi_anual`` (12 mensal, 252 diário).
      Agente: ``gamma`` (5.0), ``beta`` (0.96), ``w0`` (1.0), ``horizonte`` (120).
      Simulação: ``n_scenarios`` (80000), ``n_paths`` (5000), ``seed`` (42).

    Os retornos são sempre Normais e a carteira α* é sempre irrestrita (short e
    alavancagem permitidos, sem teto), fiel ao PDF (§3.1).

    **``n_scenarios`` e a frequência dos dados.** O default de 80 000 serve para
    séries **mensais**. Em séries **diárias**, use ``n_scenarios`` na casa dos milhões.

    Returns
    -------
    dict com ``alpha_star`` (carteira ótima), ``theta``/``consumo_inicial``,
    ``phi_hat``, calibração (``mu_hat``, ``sigma_hat``, ``rf``) e o resumo da
    simulação (``E_W_T``, percentis, trajetórias médias).
    """
    cfg = dict(config)
    coluna_data = cfg.get("coluna_data", "data")
    rf_col = cfg.get("rf_col", "cdi")

    # ── 1. DAL — obter retornos ─────────────────────────────────────────────
    if cfg.get("retornos") is not None:
        retornos = cfg["retornos"]
    elif "db_path" in cfg:
        retornos = dal.ler_sqlite(cfg["db_path"], cfg.get("tabela", "retornos"))
    else:
        raise ValueError("config precisa de 'retornos' (DataFrame) ou 'db_path'.")

    colunas = [c for c in retornos.columns if c != coluna_data]
    ativos = cfg.get("ativos") or [c for c in colunas if c != rf_col]
    if not ativos:
        raise ValueError("nenhum ativo de risco identificado em 'retornos'.")

    # ── 2. Mercado — calibração (Etapa 0) ───────────────────────────────────
    if "cdi_anual" in cfg:
        rf = RendaFixa(cfg["cdi_anual"], cfg.get("periodos_por_ano", 12)).retorno_livre_risco()
    elif rf_col in retornos.columns:
        rf = float(retornos[rf_col].mean())
    else:
        rf = float(cfg.get("rf", 0.0))
    mercado = RendaVariavel(retornos[[coluna_data] + ativos], coluna_data=coluna_data)

    # ── 3. Agente — política ótima (Etapas 1–4) ─────────────────────────────
    inv = Investidor(cfg.get("gamma", 5.0), cfg.get("beta", 0.96),
                     cfg.get("w0", 1.0), cfg.get("horizonte", 120))
    seed = cfg.get("seed", 42)
    alpha = inv.carteira_otima(mercado, rf, n_scenarios=cfg.get("n_scenarios", 80_000), seed=seed)
    theta = inv.fracoes_consumo()

    # ── 4. Simulação forward (Etapas 5–6) ───────────────────────────────────
    T, N = inv.horizonte, len(ativos)
    n_paths = cfg.get("n_paths", 5_000)
    r_paths = mercado.amostrar(n_paths * T, seed=seed + 1)
    R_paths = np.maximum(1.0 + r_paths.reshape(n_paths, T, N), 0.0)
    sim = nucleo.propagar_riqueza(inv.w0, theta, alpha, R_paths, 1.0 + rf)

    # ── 5. Resultado ────────────────────────────────────────────────────────
    W_T = sim["W"][:, -1]
    return {
        "ativos": ativos,
        "rf": rf,
        "mu_hat": mercado.media(),
        "sigma_hat": mercado.covariancia(),
        "alpha_star": alpha,                              # carteira ótima
        "phi_hat": inv.phi_hat,
        "theta": theta,                                   # frações de consumo
        "consumo_inicial": float(theta[0] * inv.w0),      # c_0 = θ_0·W_0
        "horizonte": T,
        "E_W_T": float(W_T.mean()),
        "W_T_p5": float(np.percentile(W_T, 5)),
        "W_T_p95": float(np.percentile(W_T, 95)),
        "trajetoria_W_media": sim["W"].mean(axis=0),
        "trajetoria_c_media": sim["c"].mean(axis=0),
    }
