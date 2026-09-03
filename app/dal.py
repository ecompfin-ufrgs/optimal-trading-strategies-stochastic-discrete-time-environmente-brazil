"""app.dal: a camada de acesso a dados (F1, NF6).

E aqui que acontece:
  - o download das series historicas (Yahoo Finance e Banco Central);
  - a gravacao e a leitura das tabelas no SQLite;
  - o calculo dos retornos a partir dos precos.

Este e o unico modulo que sabe que existe banco e disco. As outras etapas so
recebem e devolvem DataFrame, e nunca abrem o SQLite direto. O que esta aqui
segue a secao "Projeto de dados" do docs/project/projeto.md.
"""

import sqlite3
from contextlib import closing
from typing import Sequence

import pandas as pd

# frequencias que a ingestao aceita. O formato da coluna data acompanha:
# AAAA-MM no mensal e AAAA-MM-DD no diario.
FORMATO_DATA = {"1mo": "%Y-%m", "1d": "%Y-%m-%d"}

# qual serie do CDI pedir pra API do Banco Central em cada frequencia.
# A 4391 e o CDI acumulado no mes; a 12 e o CDI do dia.
_SERIE_CDI = {"1mo": 4391, "1d": 12}

# a API recusa pedido de serie diaria com mais de 10 anos (responde 406).
# No mensal nao tem esse limite. Periodo maior que isso e baixado em pedacos.
_LIMITE_ANOS_SGS = {"1mo": None, "1d": 10}

# essa API demora bastante em janela diaria grande (ja levou 19 segundos pra
# uns 2500 registros), entao o tempo de espera aqui e bem maior que o do Yahoo.
_TIMEOUT_SGS = 90


def _formato_data(frequencia: str) -> str:
    """Formato da coluna data para a frequência pedida (valida o argumento)."""
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
    """
    Baixa os precos de fechamento ajustado no Yahoo Finance. (F1)

    Recebe a lista de tickers (por exemplo ["^BVSP"]), a data inicial e a
    final no formato AAAA-MM-DD (se a final vier None, usa hoje) e a
    frequencia, "1mo" pra mensal ou "1d" pra diario.

    Devolve um DataFrame com a coluna data na frente, no formato AAAA-MM ou
    AAAA-MM-DD conforme a frequencia, e uma coluna por ticker.

    Usa a API publica de graficos do Yahoo com o urllib, que ja vem no Python.
    Cheguei aqui porque o yfinance e o curl_cffi davam erro de certificado SSL
    no Windows. Os imports ficam dentro da funcao pra que os testes de banco e
    de retorno continuem rodando sem internet.
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
    T_efetivo = T − 1. Todas as colunas que não sejam coluna_data são
    tratadas como séries de preço.

    O CDI nao passa por aqui, porque ele ja e um retorno e nao um preco. Ele
    vai direto pra coluna cdi da tabela retornos.
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
    """Grava um DataFrame numa tabela do SQLite. (F1, NF6)
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
    """
    Baixa o CDI da API do Banco Central. (F1)

    No mensal pede a serie 4391, que e o CDI acumulado no mes; no diario pede a
    serie 12, que e o CDI do dia. Devolve um DataFrame com data e cdi, com o
    cdi ja em decimal e por periodo (uns 0.0034 no mensal e 0.00047 no diario).
    A fonte e oficial e de graca, nao precisa cadastro, mas precisa internet.

    Os imports ficam dentro da funcao e sao todos da biblioteca padrao. A serie
    diaria vem em pedacos de 10 anos, que e o limite da API, e depois eles sao
    juntados.
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
    """Corta o periodo em pedacos de no maximo limite_anos. Se for None, devolve um pedaco so."""
    if limite_anos is None or fim <= inicio + pd.DateOffset(years=limite_anos):
        return [(inicio, fim)]
    partes, atual = [], inicio
    while atual <= fim:
        prox = min(atual + pd.DateOffset(years=limite_anos), fim)
        partes.append((atual, prox))
        atual = prox + pd.Timedelta(days=1)
    return partes


def _validar_identificador(nome: str) -> None:
    """Confere se o nome da tabela e valido antes de montar o SQL."""
    if not nome.isidentifier():
        raise ValueError(f"nome de tabela inválido: {nome!r}")

