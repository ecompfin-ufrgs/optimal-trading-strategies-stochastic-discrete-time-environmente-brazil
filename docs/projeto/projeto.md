# Documento de projeto de software

## Projeto de dados

### Fontes

Duas séries históricas mensais, uma por mercado:

- **Renda variável** — Ibovespa (`^BVSP`), nível do índice, obtido do Yahoo Finance (chart API pública, via `urllib`).
- **Renda fixa** — CDI, taxa mensal (a taxa livre de risco `R_f`), da API do Banco Central (SGS, série 4391).

### Fluxo (transformação) dos dados

O sistema começa obtendo os **dados brutos** do Ibovespa e do CDI. Em seguida, esses dados são transformados em **retornos mensais**, que mostram quanto cada mercado ganhou ou perdeu em cada período. A partir desses retornos, o sistema calcula os **parâmetros estatísticos** necessários para o modelo, como retorno esperado, risco etc. Por fim, esses parâmetros são usados para gerar as **trajetórias simuladas** de riqueza e consumo do investidor ao longo do tempo, produzindo os resultados finais da aplicação. 

Os dados brutos e derivados são guardados de forma permanente em **SQLite** (NF6) pela camada DAL (Data Access Layer); o restante da sequência de etapas de processamento dos dados, o pipeline, lê do banco e não refaz o download a cada execução.

### Modelo de dados (esquema SQLite)

Optou-se por **uma tabela de dados brutos por mercado** e uma tabela de **retornos** já alinhados por data, consumida pela calibração.

> A ligação entre `ibovespa`/`cdi` e `retornos` é **por data** (mesma chave `data`): `retornos` é uma tabela *derivada* (calculada pela DAL a partir das brutas), não uma referência relacional. Isto é, as tabelas de dados do Ibovespa e do CDI estão conectadas às "retornos" apenas pelo fato de usarem o mesmo identificador de tempo (a coluna de data), mas sem uma ligação fixa dentro do banco de dados. O sistema pega os dados brutos dessas duas fontes e calcula uma nova tabela chamada "retornos", que mostra a variação de cada mês. Assim, essa tabela não é uma fonte original de dados nem depende diretamente de outra dentro do banco, ela é gerada automaticamente a partir das outras duas sempre que necessário.

#### Dicionário de dados

| Tabela | Campo | Tipo | Restrições | Descrição | Exemplo |
|---|---|---|---|---|---|
| `ibovespa` | `data` | TEXT | PK, `AAAA-MM`, não nulo | mês da observação | `2000-01` |
| `ibovespa` | `fechamento` | REAL | > 0, não nulo | nível do índice (pontos) | `17092.0` |
| `cdi` | `data` | TEXT | PK, `AAAA-MM`, não nulo | mês da observação | `2000-01` |
| `cdi` | `cdi` | REAL | ≥ 0, não nulo | taxa CDI do mês (decimal) = `R_f` | `0.0149` |
| `retornos` | `data` | TEXT | PK, `AAAA-MM`, não nulo | mês da observação | `2000-02` |
| `retornos` | `ibov` | REAL | não nulo | retorno mensal do Ibovespa (decimal) | `-0.0315` |
| `retornos` | `cdi` | REAL | não nulo | retorno livre de risco do mês (decimal) | `0.0149` |
| `parametros` | `chave` | TEXT | PK, não nulo | nome do parâmetro calibrado | `mu_ibov` |
| `parametros` | `valor` | REAL | não nulo | valor do parâmetro | `0.0107` |


### Formato dos arquivos (CSV)

Entrada/saída em CSV espelha o framework de referência: coluna `data` na primeira posição (formato `AAAA-MM`), uma coluna por ativo, valores em **decimal** (ex.: `0.0213`, não `2,13%`), **sem células vazias** (NaN).

```csv
data,ibov,cdi
2000-01,0.0213,0.0152
2000-02,-0.0315,0.0149
```

### Regras de integridade

- `data` única por tabela (chave primária) e no formato mensal `AAAA-MM`.
- Sem valores ausentes (NaN) nas colunas de retorno.
- Valores sempre em **decimal**, nunca em porcentagem.
- `retornos` cobre apenas as datas presentes em **ambas** as tabelas brutas
  `ibovespa` e `cdi` (interseção por data — alinhamento sem buracos).

### Dados em trânsito (pipes)

Entre os filtros, os dados trafegam em memória como `pandas.DataFrame` (séries de preços/retornos) e `numpy.ndarray` (μ̂, Σ̂, cenários `R`, trajetórias `W_t`/`c_t*`). Apenas as pontas da esteira (DAL e relatório/web) tocam o disco/banco.

---


## Projeto de arquiitetura
A aplicação usa  modelo arquitetural misto: "pipes and filters" para o pipeline de dados e MVC para a camada de apresentação.

<!--Liste os módulos e pacotes e apresente uma figura com a estrutura que os liga-->

## Projeto de módulos e pacotes

<!--Dizer o que cada módulo e pacote faz, incluindo a assinatura das funções e/ou classes-->


## Projeto de algoritmos

<!--Descrever o algoritmo implementado em cada função-->
