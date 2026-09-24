"""app.dal: a camada de acesso a dados (F1, NF6).

E aqui que acontece:
  - o download das series historicas (Yahoo Finance e Banco Central);
  - a gravacao e a leitura das tabelas no SQLite;
  - o calculo dos retornos a partir dos precos.

Este e o unico modulo que sabe que existe banco e disco. As outras etapas so
recebem e devolvem DataFrame, e nunca abrem o SQLite direto. E tambem quem cria
o esquema das tabelas, com as restricoes de integridade do projeto (ESQUEMAS),
seguindo a secao "Projeto de dados" do docs/project/projeto.md.
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

# O esquema das tres tabelas do projeto, com as restricoes da secao "Regras de
# integridade" do docs/project/projeto.md: a data e chave primaria (AAAA-MM tem
# 7 caracteres e AAAA-MM-DD tem 10), nenhuma coluna aceita nulo, o fechamento e
# positivo e o CDI nao e negativo.
ESQUEMAS: dict[str, tuple[str, ...]] = {
    "ibovespa": (
        "data TEXT PRIMARY KEY NOT NULL CHECK (length(data) IN (7, 10))",
        "fechamento REAL NOT NULL CHECK (fechamento > 0)",
    ),
    "cdi": (
        "data TEXT PRIMARY KEY NOT NULL CHECK (length(data) IN (7, 10))",
        "cdi REAL NOT NULL CHECK (cdi >= 0)",
    ),
    "retornos": (
        "data TEXT PRIMARY KEY NOT NULL CHECK (length(data) IN (7, 10))",
        "ibov REAL NOT NULL",
        "cdi REAL NOT NULL",
    ),
}


def _formato_data(frequencia: str) -> str:
    """Formato da coluna data para a frequencia pedida (valida o argumento)."""
    try:
        return FORMATO_DATA[frequencia]
    except KeyError:
        raise ValueError(
            f"frequencia desconhecida: {frequencia!r} (use {sorted(FORMATO_DATA)})."
        ) from None


def baixar_precos(
    ativos: Sequence[str],
    inicio: str,
    fim: str | None = None,
    frequencia: str = "1mo",
) -> pd.DataFrame:
    """
    Baixa os precos de fechamento no Yahoo Finance. (F1)

    Recebe a lista de tickers (por exemplo ["^BVSP"]), a data inicial e a
    final no formato AAAA-MM-DD (se a final vier None, usa hoje) e a
    frequencia, "1mo" pra mensal ou "1d" pra diario.

    Devolve um DataFrame com a coluna data na frente, no formato AAAA-MM ou
    AAAA-MM-DD conforme a frequencia, e uma coluna por ticker.

    O campo lido e o 'close' da API, o fechamento sem ajuste. Para o ^BVSP da
    no mesmo, porque indice de pontos nao paga dividendo nem desdobra.

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
            resposta = json.load(resp)
        resultado = (resposta.get("chart") or {}).get("result")
        if not resultado:
            raise ValueError(f"Yahoo nao retornou dados para {tk!r}.")
        res = resultado[0]
        ts = res.get("timestamp") or []
        close = res["indicators"]["quote"][0].get("close") or []
        datas = [datetime.fromtimestamp(t, tz=timezone.utc).strftime(fmt) for t in ts]
        series[tk] = pd.Series(close, index=datas, name=tk)

    df = pd.DataFrame(series).dropna(how="any")
    df = df[~df.index.duplicated(keep="last")]
    return df.reset_index().rename(columns={"index": "data"})


def calcular_retornos(precos: pd.DataFrame, coluna_data: str = "data") -> pd.DataFrame:
    """Converte precos/niveis em retornos simples por periodo. (F1)

    A primeira observacao e descartada, porque nao ha retorno anterior, entao
    sobram T - 1 linhas. Toda coluna que nao seja a coluna_data e tratada como
    serie de preco.

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

    Se a tabela for uma das tres do projeto, ela e criada a partir do
    ESQUEMAS, com chave primaria na data, NOT NULL em tudo e os CHECK de
    dominio. Data repetida, celula vazia ou fechamento negativo param aqui,
    com IntegrityError. Qualquer outra tabela cai no caminho normal do pandas,
    sem restricao nenhuma.

    A gravacao e tudo ou nada. O "replace" monta a tabela nova ao lado da
    antiga e so troca as duas no fim, entao uma linha que bata num CHECK deixa
    a base que ja estava no banco intacta.
    """
    _validar_identificador(tabela)
    colunas = ESQUEMAS.get(tabela)
    with closing(sqlite3.connect(db_path)) as con:
        try:
            if colunas is None:
                df.to_sql(tabela, con, if_exists=if_exists, index=False)
                con.commit()
                return
            if if_exists == "fail" and _tabela_existe(con, tabela):
                raise ValueError(f"a tabela {tabela!r} ja existe em {db_path}.")
            if if_exists != "replace":
                con.execute(f"CREATE TABLE IF NOT EXISTS {tabela} ({', '.join(colunas)})")
                df.to_sql(tabela, con, if_exists="append", index=False)
                con.commit()
                return

            provisoria = f"{tabela}__novo"
            con.execute(f"DROP TABLE IF EXISTS {provisoria}")
            con.execute(f"CREATE TABLE {provisoria} ({', '.join(colunas)})")
            try:
                df.to_sql(provisoria, con, if_exists="append", index=False)
                con.execute(f"DROP TABLE IF EXISTS {tabela}")
                con.execute(f"ALTER TABLE {provisoria} RENAME TO {tabela}")
                con.commit()
            except Exception:
                con.rollback()
                con.execute(f"DROP TABLE IF EXISTS {provisoria}")
                con.commit()
                raise
        except Exception as exc:
            _erro_original_sqlite(exc)


def _erro_original_sqlite(exc: Exception) -> None:
    """Devolve o erro original do SQLite, que o pandas esconde dentro do dele."""
    if isinstance(exc.__cause__, sqlite3.Error):
        raise exc.__cause__ from None
    raise exc


def _tabela_existe(con: sqlite3.Connection, tabela: str) -> bool:
    """Diz se a tabela ja existe no banco aberto em con."""
    achou = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (tabela,)
    ).fetchone()
    return achou is not None


def ler_sqlite(db_path: str, tabela: str) -> pd.DataFrame:
    """Le uma tabela do banco SQLite para um DataFrame. (F1, NF6)"""
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
        raise ValueError("BCB nao retornou CDI para o periodo pedido.")

    df = pd.DataFrame(partes)
    df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y").dt.strftime(fmt)
    df["cdi"] = df["valor"].astype(float) / 100.0   # % por periodo -> decimal
    # Janelas consecutivas podem repetir a data de fronteira.
    return df[["data", "cdi"]].drop_duplicates(subset="data").reset_index(drop=True)


def _janelas(inicio: pd.Timestamp, fim: pd.Timestamp, limite_anos: int | None):
    """Corta o periodo em pedacos de no maximo limite_anos.

    Com limite_anos None devolve um pedaco so.
    """
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
        raise ValueError(f"nome de tabela invalido: {nome!r}")
