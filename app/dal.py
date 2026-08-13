"""app.dal — Data Access Layer (camada de acesso a dados).

Responsável por (F1, NF6):
  * baixar séries históricas (Yahoo Finance);
  * gravar e ler tabelas no banco SQLite;
  * calcular retornos a partir de preços/níveis.

É o **único** módulo que conhece o banco e o disco. As demais etapas da esteira
(pipes-and-filters) recebem/devolvem ``DataFrame`` e nunca tocam o SQLite
diretamente. Implementa o contrato definido na seção "Projeto de dados" de
``docs/project/projeto.md``.
"""

import sqlite3
from contextlib import closing
from typing import Sequence

import pandas as pd

# Frequências suportadas na ingestão. A granularidade da coluna ``data`` segue a
# frequência: mensal usa ``AAAA-MM``; diária, ``AAAA-MM-DD``.
FORMATO_DATA = {"1mo": "%Y-%m", "1d": "%Y-%m-%d"}

# Série do CDI na API SGS do Banco Central, por frequência.
#   4391 = CDI acumulada no mês (% a.m.) · 12 = CDI (% a.d.)
_SERIE_CDI = {"1mo": 4391, "1d": 12}

# A SGS recusa (HTTP 406) séries **diárias** de mais de 10 anos por requisição;
# a mensal não tem esse limite. Janelas maiores são baixadas em partes.
_LIMITE_ANOS_SGS = {"1mo": None, "1d": 10}

# A SGS é lenta e irregular em janelas diárias largas (medido: 0,4s a 19s para
# ~2500 registros), então o timeout é bem mais folgado que o do Yahoo.
_TIMEOUT_SGS = 90


def _formato_data(frequencia: str) -> str:
    """Formato da coluna ``data`` para a frequência pedida (valida o argumento)."""
    try:
        return FORMATO_DATA[frequencia]
    except KeyError:
        raise ValueError(
            f"frequência desconhecida: {frequencia!r} (use {sorted(FORMATO_DATA)})."
        ) from None


def baixar_precos(
    ativos: Sequence[str],
    inicio: str,
    fim: str | None = None,
    frequencia: str = "1mo",
) -> pd.DataFrame:
    """Baixa preços de fechamento (ajustado) do Yahoo Finance. (F1)

    Parameters
    ----------
    ativos : sequência de tickers, ex.: ``["^BVSP"]``.
    inicio : data inicial ``AAAA-MM-DD``.
    fim : data final ``AAAA-MM-DD`` (``None`` => hoje).
    frequencia : ``"1mo"`` (mensal) ou ``"1d"`` (diário).

    Returns
    -------
    DataFrame com a coluna ``data`` na primeira posição — ``AAAA-MM`` se mensal,
    ``AAAA-MM-DD`` se diário — e uma coluna por ticker (fechamento ajustado).

    Notes
    -----
    Usa a *chart API* pública do Yahoo via ``urllib`` (stdlib) — **sem**
    ``yfinance``/``curl_cffi``, que sofriam de erro de certificado SSL no
    Windows. Imports tardios mantêm os testes de banco/retorno offline (NF4).
    """
    import json
    from datetime import datetime, timezone
    from urllib.parse import quote
    from urllib.request import Request, urlopen

    fmt = _formato_data(frequencia)

    def _epoch(d: str) -> int:
        return int(pd.Timestamp(d, tz="UTC").timestamp())

    p1 = _epoch(inicio)
    p2 = _epoch(fim or datetime.now(timezone.utc).strftime("%Y-%m-%d"))

    series: dict[str, pd.Series] = {}
    for tk in ativos:
        url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(tk)}"
               f"?period1={p1}&period2={p2}&interval={frequencia}")
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=30) as resp:
            payload = json.load(resp)
        resultado = (payload.get("chart") or {}).get("result")
        if not resultado:
            raise ValueError(f"Yahoo não retornou dados para {tk!r}.")
        res = resultado[0]
        ts = res.get("timestamp") or []
        close = res["indicators"]["quote"][0].get("close") or []
        datas = [datetime.fromtimestamp(t, tz=timezone.utc).strftime(fmt) for t in ts]
        series[tk] = pd.Series(close, index=datas, name=tk)

    df = pd.DataFrame(series).dropna(how="any")
    return df.reset_index().rename(columns={"index": "data"})


def calcular_retornos(precos: pd.DataFrame, coluna_data: str = "data") -> pd.DataFrame:
    """Converte preços/níveis em retornos simples por período. (F1)

    A primeira observação é descartada (não há retorno anterior), portanto
    ``T_efetivo = T − 1``. Todas as colunas que não sejam ``coluna_data`` são
    tratadas como séries de preço.

    Notes
    -----
    A taxa CDI, por **já ser** um retorno (não um preço), não passa por aqui:
    ela entra direto na coluna ``cdi`` da tabela ``retornos``.
    """
    if coluna_data not in precos.columns:
        raise KeyError(f"coluna '{coluna_data}' ausente em precos.")

    datas = precos[coluna_data].iloc[1:].to_numpy()
    numericas = precos.drop(columns=[coluna_data])
    ret = numericas.pct_change(fill_method=None).iloc[1:].reset_index(drop=True)
    ret.insert(0, coluna_data, datas)
    return ret


def gravar_sqlite(
    df: pd.DataFrame,
    db_path: str,
    tabela: str,
    if_exists: str = "replace",
) -> None:
    """
    Grava um DataFrame numa tabela do banco SQLite. (F1, NF6)
    """
 
    _validar_identificador(tabela)
    with closing(sqlite3.connect(db_path)) as con:
        df.to_sql(tabela, con, if_exists=if_exists, index=False)
        con.commit()


def ler_sqlite(db_path: str, tabela: str) -> pd.DataFrame:
    """Lê uma tabela do banco SQLite para um DataFrame. (F1, NF6)"""
    _validar_identificador(tabela)
    with closing(sqlite3.connect(db_path)) as con:
        return pd.read_sql(f"SELECT * FROM {tabela}", con)


def baixar_cdi_bcb(inicio: str, fim: str | None = None,
                   frequencia: str = "1mo") -> pd.DataFrame:
    """Baixa o CDI da API SGS do Banco Central. (F1)

    Série 4391 = 'CDI acumulada no mês' (% a.m.) para ``frequencia="1mo"``;
    série 12 = 'CDI' (% a.d.) para ``"1d"``. Devolve um DataFrame com ``data``
    (``AAAA-MM`` ou ``AAAA-MM-DD``) e ``cdi`` (decimal **por período**, ex.:
    0.0034 no mensal, 0.00047 no diário). Fonte oficial, gratuita e sem
    cadastro; requer internet.

    Notes
    -----
    Imports tardios (``json``/``urllib``, stdlib) e nenhuma dependência nova.
    A série diária é baixada em janelas de 10 anos (limite da SGS) e
    concatenada.
    """
    import json
    from datetime import date as _date
    from urllib.request import urlopen

    fmt = _formato_data(frequencia)
    serie = _SERIE_CDI[frequencia]
    ini = pd.to_datetime(inicio)
    dfim = pd.to_datetime(fim or _date.today().isoformat())

    partes = []
    for janela_ini, janela_fim in _janelas(ini, dfim, _LIMITE_ANOS_SGS[frequencia]):
        url = (f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados"
               f"?formato=json&dataInicial={janela_ini.strftime('%d/%m/%Y')}"
               f"&dataFinal={janela_fim.strftime('%d/%m/%Y')}")
        with urlopen(url, timeout=_TIMEOUT_SGS) as resp:
            partes.extend(json.load(resp))
    if not partes:
        raise ValueError("BCB não retornou CDI para o período pedido.")

    df = pd.DataFrame(partes)
    df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y").dt.strftime(fmt)
    df["cdi"] = df["valor"].astype(float) / 100.0   # % por período -> decimal
    # Janelas consecutivas podem repetir a data de fronteira.
    return df[["data", "cdi"]].drop_duplicates(subset="data").reset_index(drop=True)


def _janelas(inicio: pd.Timestamp, fim: pd.Timestamp, limite_anos: int | None):
    """Fatia [inicio, fim] em janelas de no máximo ``limite_anos`` (None = 1 só)."""
    if limite_anos is None or fim <= inicio + pd.DateOffset(years=limite_anos):
        return [(inicio, fim)]
    partes, atual = [], inicio
    while atual <= fim:
        prox = min(atual + pd.DateOffset(years=limite_anos), fim)
        partes.append((atual, prox))
        atual = prox + pd.Timedelta(days=1)
    return partes


def _validar_identificador(nome: str) -> None:
    """Impede nomes de tabela inválidos/injeção (o nome vem do código, mas
    validar mantém o contrato explícito)."""
    if not nome.isidentifier():
        raise ValueError(f"nome de tabela inválido: {nome!r}")

