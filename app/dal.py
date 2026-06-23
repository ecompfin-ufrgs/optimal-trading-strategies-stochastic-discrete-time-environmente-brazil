"""app.dal — Data Access Layer (camada de acesso a dados).

Responsável por (F1, NF6):
  * baixar séries históricas (Yahoo Finance);
  * gravar e ler tabelas no banco SQLite;
  * calcular retornos a partir de preços/níveis.

É o único módulo que conhece o banco e o disco. As demais etapas da esteira
(pipes-and-filters) recebem/devolvem ``DataFrame`` e nunca tocam o SQLite
diretamente. Implementa o contrato definido na seção "Projeto de dados" de
``docs/project/projeto.md``.
"""

from __future__ import annotations

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
    pass


def calcular_retornos(
    precos: pd.DataFrame,
    coluna_data: str = "data",
) -> pd.DataFrame:
    """Converte preços/níveis em retornos simples mensais. (F1)

    A primeira observação é descartada (não há retorno anterior), portanto
    ``T_efetivo = T − 1``. Todas as colunas que não sejam ``coluna_data`` são
    tratadas como séries de preço.

    Notes
    -----
    A taxa CDI, por **já ser** um retorno (não um preço), não passa por aqui:
    ela entra direto na coluna ``cdi`` da tabela ``retornos``.
    """
    pass


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
    pass


def ler_sqlite(
    db_path: str,
    tabela: str,
) -> pd.DataFrame:
    """Lê uma tabela do banco SQLite para um DataFrame. (F1, NF6)"""
    pass


def baixar_cdi_bcb(
    inicio: str,
    fim: str | None = None,
) -> pd.DataFrame:
    """Baixa o CDI mensal da API SGS do Banco Central. (F1)

    Série 4391 = 'Taxa de juros - CDI acumulada no mês' (% a.m.). Devolve um
    DataFrame com ``data`` (AAAA-MM) e ``cdi`` (decimal por mês, ex.: 0.0034).
    Fonte oficial, gratuita e sem cadastro; requer internet.

    Notes
    -----
    Imports tardios (``json``/``urllib``, stdlib) e nenhuma dependência nova.
    """
    pass


def _validar_identificador(nome: str) -> None:
    """Impede nomes de tabela inválidos/injeção (o nome vem do código, mas
    validar mantém o contrato explícito)."""
    pass
