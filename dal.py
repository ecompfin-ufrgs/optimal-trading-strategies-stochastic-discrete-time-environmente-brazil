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
from __future__ import annotations

import sqlite3
from contextlib import closing
from typing import Sequence

import pandas as pd


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
    frequencia : intervalo do yfinance (``"1mo"`` = mensal).

    Returns
    -------
    DataFrame com a coluna ``data`` (``AAAA-MM``) na primeira posição e uma
    coluna por ticker (preço de fechamento ajustado).

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
        meses = [datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m") for t in ts]
        series[tk] = pd.Series(close, index=meses, name=tk)

    df = pd.DataFrame(series).dropna(how="any")
    return df.reset_index().rename(columns={"index": "data"})


def calcular_retornos(precos: pd.DataFrame, coluna_data: str = "data") -> pd.DataFrame:
    """Converte preços/níveis em retornos simples mensais. (F1)

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
    """Grava um DataFrame numa tabela do banco SQLite. (F1, NF6)

    Usa ``contextlib.closing`` porque ``with sqlite3.connect(...)`` apenas
    gerencia a transação — **não fecha** a conexão; sem fechar, o arquivo do
    banco fica travado no Windows (NF3).
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


def baixar_cdi_bcb(inicio: str, fim: str | None = None) -> pd.DataFrame:
    """Baixa o CDI mensal da API SGS do Banco Central. (F1)

    Série 4391 = 'Taxa de juros - CDI acumulada no mês' (% a.m.). Devolve um
    DataFrame com ``data`` (AAAA-MM) e ``cdi`` (decimal por mês, ex.: 0.0034).
    Fonte oficial, gratuita e sem cadastro; requer internet.

    Notes
    -----
    Imports tardios (``json``/``urllib``, stdlib) e nenhuma dependência nova.
    """
    import json
    from datetime import date as _date
    from urllib.request import urlopen

    di = pd.to_datetime(inicio).strftime("%d/%m/%Y")
    dfim = pd.to_datetime(fim or _date.today().isoformat()).strftime("%d/%m/%Y")
    url = ("https://api.bcb.gov.br/dados/serie/bcdata.sgs.4391/dados"
           f"?formato=json&dataInicial={di}&dataFinal={dfim}")
    with urlopen(url, timeout=30) as resp:
        dados = json.load(resp)
    if not dados:
        raise ValueError("BCB não retornou CDI para o período pedido.")
    df = pd.DataFrame(dados)
    df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y").dt.strftime("%Y-%m")
    df["cdi"] = df["valor"].astype(float) / 100.0   # % a.m. -> decimal
    return df[["data", "cdi"]]


def _validar_identificador(nome: str) -> None:
    """Impede nomes de tabela inválidos/injeção (o nome vem do código, mas
    validar mantém o contrato explícito)."""
    if not nome.isidentifier():
        raise ValueError(f"nome de tabela inválido: {nome!r}")
