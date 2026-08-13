"""app.ingestao — monta o banco de dados REAL (Ibovespa + CDI).

Passo de ingestão da esteira (F1, NF6): baixa as séries de mercado, calcula os
retornos alinhados e grava as três tabelas do `projeto.md` num SQLite:

    ibovespa(data, fechamento) · cdi(data, cdi) · retornos(data, ibov, cdi)

Uso (linha de comando):

    python -m app.ingestao                      # mensal, 2000-01-01 até hoje
    python -m app.ingestao 2010-01-01           # início custom
    python -m app.ingestao 2010-01-01 2020-12-31
    python -m app.ingestao 2022-05-22 --diario  # série diária

No mensal a coluna ``data`` é ``AAAA-MM``; no diário, ``AAAA-MM-DD``. Cada
frequência tem seu banco (``data/mercado.db`` e ``data/mercado_diario.db``),
para que uma ingestão não sobrescreva a outra.

Depois, ``python -m app`` usa o banco mensal automaticamente.
"""

import os

from app import dal


BANCO_PADRAO = {"1mo": "data/mercado.db", "1d": "data/mercado_diario.db"}


def montar_base(db_path: str | None = None, inicio: str = "2000-01-01",
                fim: str | None = None, frequencia: str = "1mo") -> dict:
    """Baixa Ibovespa (Yahoo) + CDI (Banco Central) e grava o SQLite.

    Parameters
    ----------
    db_path : caminho do banco (``None`` => o padrão da frequência).
    frequencia : ``"1mo"`` (mensal) ou ``"1d"`` (diário).

    Returns
    -------
    dict com ``db_path``, ``frequencia``, ``n_periodos`` e ``periodo``
    (primeira e última data).
    """
    if db_path is None:
        db_path = BANCO_PADRAO[frequencia]
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

    # 1. Ibovespa — níveis (tabela 'ibovespa').
    precos = dal.baixar_precos(["^BVSP"], inicio, fim, frequencia=frequencia)
    precos = precos.rename(columns={precos.columns[1]: "fechamento"})
    dal.gravar_sqlite(precos, db_path, "ibovespa")

    # 2. CDI — taxa por período (tabela 'cdi').
    cdi = dal.baixar_cdi_bcb(inicio, fim, frequencia=frequencia)
    dal.gravar_sqlite(cdi, db_path, "cdi")

    # 3. Retornos alinhados por data (tabela 'retornos'). O merge interno
    #    descarta feriado de bolsa que não é feriado bancário, e vice-versa.
    ret_ibov = dal.calcular_retornos(precos.rename(columns={"fechamento": "ibov"}))
    retornos = ret_ibov.merge(cdi, on="data", how="inner")
    if retornos.empty:
        raise ValueError("Sem datas em comum entre Ibovespa e CDI — verifique o período.")
    dal.gravar_sqlite(retornos, db_path, "retornos")

    return {"db_path": db_path, "frequencia": frequencia, "n_periodos": len(retornos),
            "periodo": (retornos["data"].iloc[0], retornos["data"].iloc[-1])}


def main() -> None:
    import sys

    args = [a for a in sys.argv[1:] if a != "--diario"]
    frequencia = "1d" if "--diario" in sys.argv[1:] else "1mo"
    inicio = args[0] if args else "2000-01-01"
    fim = args[1] if len(args) > 1 else None
    unidade = "dias" if frequencia == "1d" else "meses"
    print(f"Baixando Ibovespa (Yahoo Finance) e CDI (Banco Central) "
          f"de {inicio} ate {fim or 'hoje'} ({unidade})...")
    try:
        info = montar_base(inicio=inicio, fim=fim, frequencia=frequencia)
    except Exception as exc:  # noqa: BLE001 — mensagem amigável p/ o usuário
        print(f"\nERRO ao baixar os dados: {type(exc).__name__}: {exc}")
        raise SystemExit(1)
    print(f"OK! Banco criado em: {info['db_path']}")
    print(f"  {info['n_periodos']} {unidade} de dados, "
          f"periodo {info['periodo'][0]} a {info['periodo'][1]}")
    if frequencia == "1mo":
        print("Agora rode:  python -m app")
    else:
        print(f"Use no pipeline:  executar_pipeline({{'db_path': '{info['db_path']}', ...}})")


if __name__ == "__main__":
    main()
