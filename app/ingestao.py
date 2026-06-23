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

from __future__ import annotations

from app import dal


def montar_base(
    db_path: str = "data/mercado.db",
    inicio: str = "2000-01-01",
    fim: str | None = None,
) -> dict:
    """Baixa Ibovespa (Yahoo) + CDI (Banco Central) e grava o SQLite.

    Fluxo:
      1. baixa Ibovespa via ``dal.baixar_precos``;
      2. baixa CDI via ``dal.baixar_cdi_bcb``;
      3. calcula retornos alinhados;
      4. grava tabelas: ibovespa, cdi e retornos;
      5. retorna metadados do dataset.

    Returns
    -------
    dict com:
      - db_path
      - n_meses
      - periodo (primeiro, último mês)
    """
    ...


def main() -> None:
    """CLI da ingestão.

    Lê argumentos de linha de comando:
      - argv[1] = inicio (opcional)
      - argv[2] = fim (opcional)

    Executa:
      - montagem do banco via ``montar_base``
      - logs simples no stdout
      - tratamento amigável de erro (ex: SSL, internet)
    """
    ...


if __name__ == "__main__":
    main()
