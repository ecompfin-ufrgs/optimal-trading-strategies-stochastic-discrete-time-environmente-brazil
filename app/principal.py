"""app.principal: liga as etapas da esteira na ordem.

A ordem e esta (F10, NF5):

    dal -> mercado -> agente (+ nucleo) -> simulacao -> resultado

O executar_pipeline e a unica porta de entrada da esteira: recebe um config e
devolve o resultado pronto, com a carteira otima, o consumo e as trajetorias.
Ficou assim para que desse para ligar outra interface depois sem mexer nos
modulos de calculo. As contas do modelo ficam nos outros modulos; aqui ficam
so a ligacao entre as etapas e o que vai em volta dela: passar o beta e o
CDI pro periodo, cortar os retornos em zero e resumir a simulacao (medias,
percentis e o consumo por ano).
"""

import numpy as np

from app import dal, nucleo
from app.agente import Investidor
from app.mercado import RendaFixa, RendaVariavel

# Fator de desconto ANUAL padrao.
# Fica declarado ao ano porque "beta = 0.96" sozinho nao diz a que periodo se
# refere. Lido como valor por pregao, vira 0.96 elevado a 252, quase zero, e o
# investidor consumiria quase tudo no primeiro ano.
BETA_ANUAL_PADRAO = 0.96


def _n_scenarios_padrao(periodos_por_ano: int) -> int:
    """Cenarios de Monte Carlo adequados a frequencia dos dados.

    A base diaria precisa de muito mais, porque o excesso de retorno de um
    pregao e pequeno perto do desvio-padrao dele e com poucos cenarios o
    alpha* oscila de uma rodada pra outra.
    """
    return 200_000 if periodos_por_ano <= 12 else 4_000_000


def _consumo_por_ano(c_medio: np.ndarray, periodos_por_ano: int, T: int) -> np.ndarray:
    """Soma o consumo medio dentro de cada ano do horizonte."""
    n_anos = max(1, int(np.ceil(T / periodos_por_ano)))
    fluxo = np.asarray(c_medio, dtype=float)[:T]
    return np.array([fluxo[i * periodos_por_ano:(i + 1) * periodos_por_ano].sum()
                     for i in range(n_anos)])


def executar_pipeline(config: dict) -> dict:
    """Roda a esteira inteira e devolve os resultados. (NF5)

    O que pode vir no config:

    periodos_por_ano: 12 se a base for mensal, 252 se for diaria. E
        obrigatorio: sem ele nao da pra converter o cdi_anual nem o
        beta_anual, que sao declarados ao ano.
    retornos ou db_path: ou o DataFrame ja pronto, com a coluna data mais uma
        coluna por ativo, ou o caminho do banco pra ler do SQLite (nesse caso
        da pra passar tambem tabela, que por padrao e 'retornos').
    ativos: quais colunas sao de risco. Por padrao, todas menos a data e a
        coluna do rf.
    rf_col: nome da coluna da taxa livre de risco nos dados, por padrao 'cdi'.
    cdi_anual: o CDI ao ano, convertido pro periodo aqui dentro. Se nao vier,
        usa a media da coluna do rf, que o dal ja grava por periodo.
    gamma (5.0), w0 (1.0) e horizonte, que e o T em periodos e tambem e
        obrigatorio.
    beta_anual (0.96, convertido pro periodo) ou beta, pra quem ja tiver o
        valor por periodo. Passar os dois da erro.
    n_scenarios (200 mil no mensal, 4 milhoes no diario), n_paths (5000, mas a
        linha de comando pede 3000) e seed (42).

    O que volta: um dicionario com alpha_star (a carteira otima), theta e
    consumo_inicial, phi_hat, A_t (Etapa 3), a calibracao (mu_hat, sigma_hat e
    rf) e o resumo da simulacao, com E_W_T, os percentis de W_T (W_T_p5 e
    W_T_p95) e as trajetorias
    trajetoria_W_media, _mediana, _p5, _p95 e trajetoria_c_media, mais o
    consumo_por_ano ja somado dentro de cada ano e dividido por w0, que e a
    fracao da riqueza inicial consumida no ano.
    """
    cfg = dict(config)
    coluna_data = cfg.get("coluna_data", "data")
    rf_col = cfg.get("rf_col", "cdi")

    # 0. a frequencia, que da a unidade de tempo de todo o resto
    if "periodos_por_ano" not in cfg:
        raise ValueError(
            "falta 'periodos_por_ano' no config (12 se mensal, 252 se diario). "
            "Sem ele nao da pra converter 'cdi_anual' e 'beta_anual', que sao "
            "declarados ao ano."
        )
    ppa = int(cfg["periodos_por_ano"])
    if ppa <= 0:
        raise ValueError(f"'periodos_por_ano' deve ser positivo; veio {ppa!r}.")

    # 1. dal: pegar os retornos
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

    # 2. mercado: a calibracao (Etapa 0)
    if "cdi_anual" in cfg:
        rf = RendaFixa(cfg["cdi_anual"], ppa).retorno_livre_risco()
    elif rf_col in retornos.columns:
        rf = float(retornos[rf_col].mean())
    else:
        rf = float(cfg.get("rf", 0.0))
    mercado = RendaVariavel(retornos[[coluna_data] + ativos], coluna_data=coluna_data)

    # 3. agente: a politica otima (Etapas 1 a 4)
    if "horizonte" not in cfg:
        raise ValueError(
            "falta 'horizonte' no config (o T, contado em periodos). Nao tem "
            "padrao porque 60 periodos e 5 anos no mensal e uns 3 meses no diario."
        )
    if "beta" in cfg and "beta_anual" in cfg:
        raise ValueError("use 'beta' (por periodo) OU 'beta_anual', nao os dois.")
    beta = (float(cfg["beta"]) if "beta" in cfg
            else float(cfg.get("beta_anual", BETA_ANUAL_PADRAO)) ** (1.0 / ppa))
    inv = Investidor(cfg.get("gamma", 5.0), beta,
                     cfg.get("w0", 1.0), cfg["horizonte"])
    seed = cfg.get("seed", 42)
    n_scenarios = cfg.get("n_scenarios") or _n_scenarios_padrao(ppa)
    alpha = inv.carteira_otima(mercado, rf, n_scenarios=n_scenarios, seed=seed)
    theta = inv.fracoes_consumo()

    # 4. simulacao pra frente (Etapas 5 e 6)
    T, N = inv.horizonte, len(ativos)
    n_paths = cfg.get("n_paths", 5_000)
    r_paths = mercado.amostrar(n_paths * T, seed=seed + 1)
    R_paths = np.maximum(1.0 + r_paths.reshape(n_paths, T, N), 0.0)
    sim = nucleo.propagar_riqueza(inv.w0, theta, alpha, R_paths, 1.0 + rf)

    # 5. o resultado
    W_T = sim["W"][:, -1]
    A_t = inv.coeficientes_A
    B_t = (nucleo.recorrencia_B(A_t, inv.phi_hat, beta)
           if np.isclose(inv.gamma, 1.0) else None)
    V = nucleo.funcao_valor(A_t, sim["W"], inv.gamma, B=B_t)
    W_p5, W_p50, W_p95 = np.percentile(sim["W"], [5, 50, 95], axis=0)
    return {
        "ativos": ativos,
        "periodos_por_ano": ppa,
        "rf": rf,
        "beta": beta,
        "mu_hat": mercado.media(),
        "sigma_hat": mercado.covariancia(),
        "alpha_star": alpha,
        "phi_hat": inv.phi_hat,
        "theta": theta,
        "consumo_inicial": float(theta[0] * inv.w0),
        "horizonte": T,
        "E_W_T": float(W_T.mean()),
        "W_T_p5": float(np.percentile(W_T, 5)),
        "W_T_p95": float(np.percentile(W_T, 95)),
        "A_t": A_t,
        "trajetoria_W_media": sim["W"].mean(axis=0),
        "trajetoria_W_mediana": W_p50,
        "trajetoria_W_p5": W_p5,
        "trajetoria_W_p95": W_p95,
        "trajetoria_c_media": sim["c"].mean(axis=0),
        "trajetoria_V_media": V.mean(axis=0),
        "trajetoria_u_media": inv.utilidade(sim["c"]).mean(axis=0),
        "consumo_por_ano": _consumo_por_ano(sim["c"].mean(axis=0) / inv.w0, ppa, T),
    }
