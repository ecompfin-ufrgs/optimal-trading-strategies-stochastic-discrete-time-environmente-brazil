"""app.ingestao — monta o banco de dados REAL (Ibovespa + CDI).

Passo de ingestão da esteira (F1, NF6): baixa as séries de mercado, calcula os
retornos alinhados e grava as três tabelas do `projeto.md` num SQLite:

    ibovespa(data, fechamento) · cdi(data, cdi) · retornos(data, ibov, cdi)

Uso (linha de comando):

    python -m app.ingestao                      # 2000-01-01 até hoje
    python -m app.ingestao 2010-01-01           # início custom
    python -m app.ingestao 2010-01-01 2020-12-31

Depois, ``python -m app`` usa esse banco automaticamente.
"""

import os

from app import dal


def montar_base(db_path: str = "data/mercado.db",
                inicio: str = "2000-01-01", fim: str | None = None) -> dict:
    """Baixa Ibovespa (Yahoo) + CDI (Banco Central) e grava o SQLite.

    Returns
    -------
    dict com ``db_path``, ``n_meses`` e ``periodo`` (primeiro, último mês).
    """
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

    # 1. Ibovespa — níveis mensais (tabela 'ibovespa').
    precos = dal.baixar_precos(["^BVSP"], inicio, fim)
    precos = precos.rename(columns={precos.columns[1]: "fechamento"})
    dal.gravar_sqlite(precos, db_path, "ibovespa")

    # 2. CDI — taxa mensal (tabela 'cdi').
    cdi = dal.baixar_cdi_bcb(inicio, fim)
    dal.gravar_sqlite(cdi, db_path, "cdi")

    # 3. Retornos alinhados por data (tabela 'retornos').
    ret_ibov = dal.calcular_retornos(precos.rename(columns={"fechamento": "ibov"}))
    retornos = ret_ibov.merge(cdi, on="data", how="inner")
    if retornos.empty:
        raise ValueError("Sem datas em comum entre Ibovespa e CDI — verifique o período.")
    dal.gravar_sqlite(retornos, db_path, "retornos")

    return {"db_path": db_path, "n_meses": len(retornos),
            "periodo": (retornos["data"].iloc[0], retornos["data"].iloc[-1])}


def main() -> None:
    import sys

    inicio = sys.argv[1] if len(sys.argv) > 1 else "2000-01-01"
    fim = sys.argv[2] if len(sys.argv) > 2 else None
    print(f"Baixando Ibovespa (Yahoo Finance) e CDI (Banco Central) "
          f"de {inicio} ate {fim or 'hoje'}...")
    try:
        info = montar_base(inicio=inicio, fim=fim)
    except Exception as exc:  # noqa: BLE001 — mensagem amigável p/ o usuário
        print(f"\nERRO ao baixar os dados: {type(exc).__name__}: {exc}")
        raise SystemExit(1)
    print(f"OK! Banco criado em: {info['db_path']}")
    print(f"  {info['n_meses']} meses de dados, periodo {info['periodo'][0]} a {info['periodo'][1]}")
    print("Agora rode:  python -m app")


if __name__ == "__main__":
    main()

