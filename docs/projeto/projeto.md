# Documento de projeto de software

## Projeto de dados

<!--Modelo de dados: fontes, formato dos arquivos e esquema do banco.-->

### Fontes

São duas séries históricas, uma para cada mercado. A frequência pode ser mensal, que é o padrão tanto da ingestão (`python -m app.ingestao`) quanto da execução (`python -m app`), ou diária, pedida com `--diario` nas duas pontas. Cada frequência tem o seu banco, e a execução lê o banco da frequência que foi pedida:

- Renda variável: o Ibovespa (`^BVSP`), usando o nível do índice. Os dados vêm do Yahoo Finance, pela API pública de gráficos, acessada com o `urllib`.
- Renda fixa: o CDI, que faz o papel da taxa livre de risco `R_f`. Os dados vêm da API do Banco Central. Quando a base é mensal usa-se a série SGS 4391, que já vem acumulada no mês em % ao mês; quando é diária, a série 12, em % ao dia.

### Fluxo (transformação) dos dados

O sistema começa obtendo os **dados brutos** do Ibovespa e do CDI. Em seguida, esses dados são transformados em **retornos por período**, que mostram quanto cada mercado ganhou ou perdeu em cada período (mês ou dia, conforme a frequência da ingestão). A partir desses retornos, o sistema calcula os **parâmetros estatísticos** necessários para o modelo, como retorno esperado, risco etc. Por fim, esses parâmetros são usados para gerar as **trajetórias simuladas** de riqueza e consumo do investidor ao longo do tempo, produzindo os resultados finais da aplicação. A informação muda de forma ao longo da esteira:

```
   dados brutos          retornos por periodo       parametros          trajetorias
 (ibovespa, cdi)   ->        (retornos)        ->  (em memoria)  ->    (em memoria)
                                                                        [resultado]
```

Os dados brutos e os retornos derivados deles ficam guardados de forma permanente em SQLite (NF6), e quem cuida disso é a camada DAL (Data Access Layer). O resto da sequência de etapas de processamento, o pipeline, lê do banco e não refaz o download a cada execução.

### Modelo de dados (esquema SQLite)

A escolha foi ter uma tabela de dados brutos para cada mercado e mais uma tabela com os retornos já alinhados por data, que é a tabela que a calibração usa.

#### Diagrama

```
  +----------------+          +----------------+
  |   ibovespa     |          |      cdi       |
  +----------------+          +----------------+
  | data  TEXT PK  |          | data  TEXT PK  |
  | fechamento REAL|          | cdi   REAL     |
  +-------+--------+          +-------+--------+
          |  retorno do indice        |  cdi = R_f
          |  (alinhado por data)      |  (alinhado por data)
          +------------+--------------+
                       |
                       v
              +----------------+
              |    retornos    |
              +----------------+
              | data  TEXT PK  |
              | ibov  REAL     |
              | cdi   REAL     |
              +----------------+
```

A ligação entre `ibovespa`/`cdi` e `retornos` é feita pela data, já que as três tabelas usam a mesma chave `data`. Isto é, as tabelas de dados do Ibovespa e do CDI estão conectadas às "retornos" apenas pelo fato de usarem o mesmo identificador de tempo (a coluna de data), mas sem uma ligação fixa dentro do banco de dados. O sistema pega os dados brutos dessas duas fontes e calcula uma nova tabela chamada `retornos`, que mostra a variação de cada mês. Assim, essa tabela não é uma fonte original de dados nem depende diretamente de outra dentro do banco, ela é gerada automaticamente a partir das outras duas sempre que necessário.

#### Dicionário de dados

| Tabela | Campo | Tipo | Restrições | Descrição | Exemplo |
|---|---|---|---|---|---|
| `ibovespa` | `data` | TEXT | PK, `AAAA-MM`\|`AAAA-MM-DD`, não nulo | período da observação | `2000-01` |
| `ibovespa` | `fechamento` | REAL | > 0, não nulo | nível do índice (pontos) | `17092.0` |
| `cdi` | `data` | TEXT | PK, `AAAA-MM`\|`AAAA-MM-DD`, não nulo | período da observação | `2000-01` |
| `cdi` | `cdi` | REAL | >= 0, não nulo | taxa CDI do período (decimal) = `R_f` | `0.0149` |
| `retornos` | `data` | TEXT | PK, `AAAA-MM`\|`AAAA-MM-DD`, não nulo | período da observação | `2000-02` |
| `retornos` | `ibov` | REAL | não nulo | retorno do Ibovespa no período (decimal) | `-0.0315` |
| `retornos` | `cdi` | REAL | não nulo | retorno livre de risco do período (decimal) | `0.0149` |

São três tabelas. Os parâmetros calibrados, ou seja, a média, a matriz de covariância e o R_f, não ficam guardados no banco: eles são recalculados a cada execução a partir da tabela `retornos` e vivem só em memória.

O formato da coluna `data` muda junto com a frequência da ingestão: fica `AAAA-MM` no mensal, que é o padrão, e `AAAA-MM-DD` no diário. As duas frequências ficam em bancos separados, e nunca na mesma tabela.

### Formato tabular

A aplicação não lê nem escreve CSV: a entrada é o SQLite, que a ingestão enche, e a saída são as figuras em `results/`. Mas o layout da tabela `retornos` segue o mesmo formato do framework de referência, de modo que exportá-la para CSV é uma questão de `to_csv` e nada mais precisa mudar de forma. A coluna `data` vem primeiro, e depois uma coluna para cada ativo. Os valores ficam sempre em decimal (`0.0213`, e não `2,13%`) e não pode haver célula vazia.

```csv
data,ibov,cdi
2000-01,0.0213,0.0152
2000-02,-0.0315,0.0149
```

### Regras de integridade

- A coluna `data` é única dentro de cada tabela, porque é a chave primária. O formato é `AAAA-MM` no mensal e `AAAA-MM-DD` no diário, com uma frequência por banco.
- Não pode haver valor faltando (NaN) nas colunas de retorno.
- O `fechamento` do Ibovespa é positivo e o `cdi` não é negativo. O retorno do Ibovespa fica sem essa exigência, porque pode ser negativo mesmo.
- Os valores ficam sempre em decimal, nunca em porcentagem.
- A tabela `retornos` só tem as datas que aparecem nas duas tabelas brutas ao mesmo tempo, isto é, a interseção entre `ibovespa` e `cdi`. Assim o alinhamento não fica com buracos.

As quatro primeiras dessas regras ficam declaradas no próprio banco, no dicionário `ESQUEMAS` do `app.dal`, e não apenas no código que baixa os dados. É a `gravar_sqlite` que cria as tabelas a partir dele:

```sql
CREATE TABLE ibovespa (
  data       TEXT PRIMARY KEY NOT NULL CHECK (length(data) IN (7, 10)),
  fechamento REAL NOT NULL CHECK (fechamento > 0)
);
CREATE TABLE cdi (
  data TEXT PRIMARY KEY NOT NULL CHECK (length(data) IN (7, 10)),
  cdi  REAL NOT NULL CHECK (cdi >= 0)
);
CREATE TABLE retornos (
  data TEXT PRIMARY KEY NOT NULL CHECK (length(data) IN (7, 10)),
  ibov REAL NOT NULL,
  cdi  REAL NOT NULL
);
```

O `CHECK` no comprimento da data é o que separa os dois formatos aceitos: `AAAA-MM` tem sete caracteres e `AAAA-MM-DD` tem dez. Com as regras declaradas no banco, uma data repetida ou uma célula vazia param a ingestão com `IntegrityError` logo na gravação, antes de chegarem à calibração. A validação de domínio da `RendaFixa`, mais adiante, segue a mesma ideia.

### Dados em trânsito (pipes)

Entre uma etapa e outra, os dados ficam só na memória. As séries de preços e de retornos andam como `pandas.DataFrame` e o resto (as médias, a matriz de covariância, os cenários e as trajetórias de riqueza e consumo) como `numpy.ndarray`. Só as pontas da esteira encostam no disco: a DAL de um lado e as figuras dos resultados do outro.

---

## Projeto de arquitetura

<!--Liste os módulos e pacotes e apresente uma figura com a estrutura que os liga-->

A aplicação segue o modelo arquitetural conhecido como pipes and filters. A ideia é que os dados passem por uma esteira de etapas de processamento, que são os filtros, ligadas pelos dados que saem de uma etapa e entram na próxima, que são os pipes. Cada filtro tem uma responsabilidade só: recebe dados, transforma e repassa adiante.

A interface da aplicação é a linha de comando, no `app.__main__`. Ela não resolve nada do modelo: lê os parâmetros que o usuário passou, monta o `config`, chama uma única função do núcleo e formata o que voltou, sem refazer conta alguma por cima do resultado. Até o consumo somado por ano, que ela imprime e a figura desenha, já vem pronto da esteira, então os dois sempre mostram o mesmo número. A única coisa que ela produz sozinha é a série sintética de demonstração, que acompanha a interface porque existe só para a aplicação rodar sem rede. Essa função é a `app.principal.executar_pipeline`, que recebe um dicionário e devolve outro, e é a única porta de entrada da esteira. Concentrar tudo nela deixa o núcleo de cálculo sem saber quem está chamando, então dá para ligar outra interface depois sem mexer em nada do que está aqui dentro.

O requisito NF5 pede também a separação de paradigmas, que ficou assim:

- A parte orientada a objetos guarda o estado. As classes `RendaFixa`, `RendaVariavel` e `Investidor` carregam os dados e o comportamento das entidades econômicas.
- A parte funcional faz a matemática. O módulo `nucleo` tem as equações do modelo (a função G(alpha), o Phi, a recorrência A_t e a função valor) escritas como funções que só recebem números e arrays e devolvem números, sem depender de nada de fora. Isso deixa cada equação fácil de testar sozinha.

### Módulos e pacotes

| Módulo / pacote | Papel | Requisitos |
|---|---|---|
| `app.dal` | DAL, o acesso a dados: download, esquema das tabelas, gravação e leitura no SQLite | F1, NF6 |
| `app.ingestao` | ingestão: baixa Ibovespa e CDI e enche o SQLite (`montar_base`) | F1, NF6 |
| `app.mercado` | os mercados: `RendaFixa` (CDI) e `RendaVariavel` (Ibovespa) | F2, F3, F4 |
| `app.agente` | o indivíduo: a classe `Investidor` (gamma, beta, W0, T, CRRA) | F5, F6, F8, F9 |
| `app.nucleo` | as funções que só fazem as contas do modelo | F6 a F11 |
| `app.principal` | liga as etapas da esteira na ordem | F10, NF5 |
| `app.graficos` | as figuras dos resultados em `results/`, fora da esteira | F16 |
| `app.__main__` | a porta de entrada `python -m app`, que recebe os parâmetros e roda a base mensal (ou a diária, com `--diario`), usando o banco real daquela frequência se ele existir | F15, NF5 |

### Figura: esteira do pipeline

```
[ SQLite / CSV ]
      |  precos
      v
+-----------------------------+
| DAL - acesso a dados        |   (F1, NF6)
| baixar, gravar, ler         |
+-----------------------------+
      |  retornos (Ibovespa, CDI)
      v
+-----------------------------+
| Mercado                     |   (F2, F3, F4)
| RendaFixa     -> R_f        |
| RendaVariavel -> media,     |
|                  covariancia|
+-----------------------------+
      |  parametros do modelo
      v
+-----------------------------+
| Agente + Nucleo             |   (F5-F8, F11)
| Investidor; alpha*, A_t,     |
| theta_t                     |
+-----------------------------+
      |  politica otima (alfa*, theta_t)
      v
+-----------------------------+
| Simulacao forward           |   (F9, F10)
| W_t, c_t*, S_t              |
+-----------------------------+
      |  trajetorias + metricas
      v
+-----------------------------+
| Relatorio (tabelas/graficos)|   (F16)
+-----------------------------+
```

Quem liga tudo isso na ordem certa é o módulo principal (`app.principal`, NF5). A validação (F12 a F14) fica nos testes, que conferem o alpha ótimo, as frações de consumo e a convergência a Merton. A ingestão (`app.ingestao`) é o passo que baixa Ibovespa e CDI e enche o SQLite que aparece lá no topo do desenho.

---

## Projeto de módulos e pacotes

<!--Dizer o que cada módulo e pacote faz, incluindo a assinatura das funções e/ou classes-->

### `app.dal`: Data Access Layer (F1, NF6)

Faz a leitura das fontes externas e guarda tudo no SQLite. É o único módulo que sabe que existe um banco e um disco.

```python
ESQUEMAS: dict[str, tuple[str, ...]]

def baixar_precos(ativos: Sequence[str], inicio: str, fim: str | None = None,
                  frequencia: str = "1mo") -> "DataFrame":
    """Baixa preços de fechamento (ex.: ^BVSP) do Yahoo Finance, via urllib.
    Se fim vier None, usa hoje. (F1)"""

def baixar_cdi_bcb(inicio: str, fim: str | None = None,
                   frequencia: str = "1mo") -> "DataFrame":
    """Baixa o CDI da API do Banco Central: SGS 4391 (% a.m.) se mensal,
    SGS 12 (% a.d.) se diário. (F1)"""

def gravar_sqlite(df: "DataFrame", db_path: str, tabela: str,
                  if_exists: str = "replace") -> None:
    """Grava um DataFrame em uma tabela do banco SQLite, criando-a a partir do
    ESQUEMAS quando ela é uma das três do projeto. (F1, NF6)"""

def ler_sqlite(db_path: str, tabela: str) -> "DataFrame":
    """Lê uma tabela do banco SQLite para um DataFrame. (F1, NF6)"""

def calcular_retornos(precos: "DataFrame",
                      coluna_data: str = "data") -> "DataFrame":
    """Converte preços em retornos por período, alinhados por data."""
```

O parâmetro `frequencia` muda mais coisas do que parece. Com `"1mo"`, que é o padrão, a coluna `data` sai no formato `AAAA-MM`; com `"1d"` sai como `AAAA-MM-DD`. Muda também de onde vem o CDI: a série 4391, acumulada no mês, contra a série 12, que é diária. E tem um detalhe da API do Banco Central: ela recusa pedidos de série diária com mais de 10 anos e responde com HTTP 406. Por causa disso a DAL corta o período em janelas de 10 anos, faz um pedido para cada uma e depois junta tudo. As janelas não se sobrepõem, porque a seguinte começa um dia depois do fim da anterior; o `drop_duplicates` que vem em seguida é só uma garantia a mais, para o caso de a API devolver a data de fronteira nos dois pedidos.

A `gravar_sqlite` é a única porta de escrita do banco, e é ela que aplica o `ESQUEMAS` descrito lá em cima: chave primária na data, `NOT NULL` em tudo e os `CHECK` de domínio, com a substituição feita de forma que uma gravação interrompida não deixe uma tabela vazia no lugar de uma boa. Uma tabela que não esteja no `ESQUEMAS` (as dos notebooks de teste, por exemplo) cai no caminho genérico do pandas, sem restrição.

### `app.ingestao`: Ingestão da base real (F1, NF6)

É o passo que enche o banco. Ele baixa o Ibovespa no Yahoo e o CDI no Banco Central, calcula os retornos alinhados e grava as tabelas `ibovespa`, `cdi` e `retornos`. Roda uma vez, com `python -m app.ingestao`, e daí em diante o pipeline só lê do SQLite.

```python
BANCO_PADRAO = {"1mo": "data/mercado.db", "1d": "data/mercado_diario.db"}

def montar_base(db_path: str | None = None, inicio: str = "2000-01-01",
                fim: str | None = None, frequencia: str = "1mo") -> dict:
    """Baixa Ibovespa+CDI, calcula retornos e grava as 3 tabelas. (F1, NF6)"""
```

Cada frequência tem o seu próprio banco, para que uma ingestão não apague a outra:

```
python -m app.ingestao                      # mensal  -> data/mercado.db
python -m app.ingestao 2022-05-22 --diario  # diário  -> data/mercado_diario.db
```

E cada banco é lido pela execução da mesma frequência: `python -m app` lê o mensal e `python -m app --diario` lê o diário. Se o banco da frequência pedida não existir, a execução não para: cai numa série sintética de demonstração e avisa isso na saída e no rodapé das figuras.

### `app.mercado`: Mercados (F2, F3, F4)

Cada classe representa um mercado e entrega o que o agente precisa. Isso corresponde à Etapa 0 do artigo, que é a calibração da média, da matriz de covariância e da taxa livre de risco.

```python
class RendaFixa:
    """Mercado de renda fixa (CDI): fornece a taxa livre de risco. (F3)"""
    def __init__(self, cdi_anual: float, periodos_por_ano: int = 12) -> None:
        """Valida cdi_anual > -1 e periodos_por_ano >= 1 (domínio da conversão)."""
    def retorno_livre_risco(self) -> float:
        """Taxa livre de risco R_f por período (líquida; o fator bruto é 1+R_f). (F3)"""

class RendaVariavel:
    """Mercado de renda variável (Ibovespa): distribuição dos retornos. (F4)"""
    def __init__(self, retornos: "DataFrame",
                 coluna_data: str = "data") -> None:
        """Valida o formato antes de converter para ndarray, para que uma
        coluna de texto esquecida dê a mensagem do projeto, e não a do numpy."""
    def media(self) -> "ndarray":
        """Vetor de retornos esperados estimado mu_chapeu. (F2, F4)"""
    def covariancia(self) -> "ndarray":
        """Matriz de covariância estimada sigma_chapeu. (F2, F4)"""
    def amostrar(self, n: int, seed: int | None = None) -> "ndarray":
        """Gera n cenários de retorno R normalmente distribuido para o Monte Carlo."""
```

O `periodos_por_ano` da `RendaFixa` é o que faz a conversão de ano para período, e a conversão é composta: `R_f = (1 + cdi_anual)^(1/periodos_por_ano) - 1`. Dizer só "CDI de 13%" não basta, porque o mesmo número vira `0.000489` por pregão ou `0.01024` por mês.

A classe valida as duas entradas no construtor, como as outras entidades do projeto fazem com as suas: o `cdi_anual` tem que ser maior que -1 e o `periodos_por_ano`, pelo menos 1. O motivo é que a conversão eleva `(1 + cdi_anual)` a um expoente fracionário, e com a base negativa o resultado sai **complexo**. Isso não interrompe a execução: o numpy descarta a parte imaginária mais adiante, o R_f fica errado e a esteira devolve um alpha\* de aparência normal. Por isso a checagem fica logo na entrada.

Essa checagem é de domínio. Quem recusa valores apenas implausíveis (um CDI de 300% ao ano, por exemplo, quase sempre é `3` digitado no lugar de `0.03`) é a interface de linha de comando, que limita o `--cdi-anual` à faixa de -0,5 a 1,0. São responsabilidades diferentes: o limite matemático vale para qualquer chamador, inclusive os notebooks que usam `executar_pipeline` direto.

A taxa livre de risco pode entrar por dois caminhos, e quem decide entre eles é o `app.principal`:

1. **`cdi_anual` no config** (que é o que a flag `--cdi-anual` preenche): o valor é declarado ao ano e convertido pela `RendaFixa`. Serve para cenários contrafactuais, do tipo "e se o CDI fosse 8%?", e nesse caso a coluna `cdi` dos dados é ignorada.
2. **A coluna `cdi` dos dados** (o padrão): usa-se a média da série, que já vem na frequência da base. É a média aritmética das taxas por período; a diferença para a média geométrica aparece só na oitava casa decimal, porque o CDI diário varia pouco.

Se nenhum dos dois existir, sobra um `rf` avulso no config, que por padrão é zero. Pela linha de comando esse terceiro caso não acontece, porque a base sintética de demonstração também traz uma coluna `cdi`.

### `app.agente`: Indivíduo / Investidor (F5, F6, F8, F9)

Guarda as características do agente (aversão ao risco, impaciência, riqueza inicial e horizonte) e conduz a decisão dele, deixando as contas em si por conta do `nucleo`.

```python
class Investidor:
    """Agente CRRA com decisao de consumo e portfolio. (F5)"""
    def __init__(self, gamma: float, beta: float,
                 w0: float, horizonte: int) -> None: ...
    def utilidade(self, c: float) -> float:
        """u(c) = c^(1-gamma)/(1-gamma), ou ln c quando gamma=1. (F5)"""
    def utilidade_marginal(self, c: float) -> float:
        """u'(c) = c^(-gamma). (F5)"""
    def carteira_otima(self, mercado: "RendaVariavel", rf: float, *,
                       n_scenarios: int = 200_000, seed: int | None = 42,
                       **opts) -> "ndarray":
        """Carteira ótima alpha* via FOC G(alpha*)=0; alpha sempre irrestrito. (F6)"""
    def fracoes_consumo(self) -> "ndarray":
        """Frações de consumo theta_t = A_t^(-1/gamma), t=0..T. (F8, F9)"""
```

O beta é um número sem unidade e, com a hipótese de retornos independentes e identicamente distribuídos, ele nem aparece na condição de primeira ordem que resolve o alpha. É exatamente por isso que a carteira ótima não muda com o tempo e a miopia acontece. Isso foi conferido no número: variando o beta de 0,90 até 0,9999 na base diária, o alpha ótimo e o Phi ficam iguais. O que o beta governa é a recorrência `A_t` e, por consequência, as frações de consumo.

O problema é que o beta entra elevado a `t`, e `t` conta períodos, então o mesmo número descreve investidores completamente diferentes conforme a frequência dos dados. Um beta de 0,96 ao mês equivale a 0,613 ao ano, mas um beta de 0,96 por pregão equivale a 3,4*10^-5 ao ano, o que seria um investidor que consome 92% da riqueza logo no primeiro ano. Para não cair nessa confusão, o `app.__main__` fixa o desconto em termos anuais (`BETA_ANUAL = 0.96`) e converte para o período: no diário fica `beta_pregao = beta_anual^(1/252) = 0,999838`. Ao reportar um resultado é bom sempre dizer as duas formas.

### `app.nucleo`: as funções de cálculo do modelo (F6 a F11)

Cada função é uma equação do artigo e dá para testar isolada das outras.

```python
def funcao_foc(alpha, R, rf, gamma):
    """G(alpha) = E[(R - rf * 1)/(rf + alpha^T(R - rf * 1))^gamma]. (F6)"""

def resolver_alpha_otimo(R, rf, gamma, *, tol=1e-10, maxiter=200, alpha0=None):
    """Resolve G(alpha*)=0; alpha pertence a R^N irrestrito (ver nota abaixo).
    SLSQP para N >= 2, brentq para N=1. (F6)"""

def phi_chapeu(alpha, R, rf, gamma):
    """Phi_chapeu = E[R_p^(1-gamma)] do portfólio ótimo. (F7)"""

def recorrencia_A(phi, beta, gamma, T):
    """A_T=1; A_t=[1+(beta * A_{t+1} * Phi_chapeu)^(1/gamma)]^gamma, t=T-1..0. (F8)"""

def fracoes_consumo(A, gamma):
    """theta_t = A_t^(-1/gamma), ou 1/A_t quando gamma=1. (F8)"""

def propagar_riqueza(w0, theta, alpha, R, rf):
    """Simulação para a frente: W_{t+1}=S_t * R*_{p,t+1}; devolve W_t, c_t*, S_t. (F9, F10)"""

def funcao_valor(A, W, gamma):
    """V_t(W) = A_t * W^(1-gamma)/(1-gamma). (F11)"""
```

Um caso à parte é o do gamma=1. A utilidade CRRA `c^(1-gamma)/(1-gamma)` é indefinida nesse ponto, e o limite dela é o logaritmo. As seis funções do módulo tratam isso explicitamente: a utilidade e o objetivo J viram `ln`, o Phi vira `E[ln R_p]`, a recorrência ganha a forma fechada `A_t = (1 - beta^(T-t+1))/(1 - beta)`, que não usa o Phi, porque com log-utilidade o consumo não depende do retorno da carteira; as frações viram `1/A_t` e a função valor vira `A_t * ln W`. O teste é `np.isclose(gamma, 1.0)`, e não `gamma == 1.0`, para pegar também um gamma que tenha chegado de uma conta em ponto flutuante.

Na recorrência há ainda um ramo para `beta * A * Phi <= 0`, que devolve `A_t = 1`. Ele não acontece quando o Phi vem do `phi_chapeu`, porque lá o `R_p` tem piso em `_TOL_FALENCIA`; existe só para um Phi entregue na mão, e nesse caso o termo de continuação não tem raiz real e o período vale apenas o consumo.

Sobre o domínio dos pesos: a função `resolver_alpha_otimo` é sempre irrestrita, ou seja, o alpha pode ser qualquer número real, o que admite venda a descoberto (alpha negativo) e alavancagem (a soma dos pesos passando de 1), sem nenhum teto. Não existe opção para exigir carteira só comprada nem para impor limites. No caso de um ativo só, o `brentq` começa procurando no intervalo de -20 a 20 e vai dobrando esse intervalo até a função G trocar de sinal. Se ela nunca trocar, quer dizer que não existe nenhum cenário com o retorno do ativo abaixo da taxa livre de risco, então não há alpha ótimo finito e a função levanta um `RuntimeError`.

O caminho de dois ativos ou mais faz o mesmo: se o SLSQP não convergir, a função levanta `RuntimeError` com a mensagem do otimizador e não devolve o último ponto visitado. Um alpha que não resolve a FOC seguiria pela esteira sem nenhum aviso, e o erro só apareceria no resultado final.

### `app.principal`: Orquestrador (F10, NF5)

Liga os filtros na ordem da esteira. É a função que o `python -m app` chama.

```python
def executar_pipeline(config: dict) -> dict:
    """DAL -> mercado -> agente -> simulação; devolve o resultado (alpha*, theta_t, trajetórias, métricas). (NF5)"""
```

Além do `n_scenarios`, dois outros controles da simulação têm valor padrão: o `n_paths`, que é o número de trajetórias da simulação para a frente, vale 5000 na esteira e 3000 na linha de comando, e a `seed`, que vale 42. A semente vale para os dois sorteios, mas com valores diferentes: os cenários que resolvem o alpha usam `seed` e os caminhos da simulação usam `seed + 1`, para que a política ótima não seja conferida nos mesmos números que a produziram. Mesma semente e mesmos dados dão sempre o mesmo resultado, que é o que o NF4 pede.

O resultado traz também o `consumo_por_ano`, com o consumo médio já somado dentro de cada ano do horizonte. A soma fica na esteira, e não em quem exibe, para que a linha de comando e a figura leiam o mesmo número. O consumo terminal `c_T` fica fora dela: ele é a liquidação de toda a riqueza que sobrou (Phi_T = 1), e não um fluxo anual comparável com os outros. Quando o horizonte não fecha um número inteiro de anos, o último balde sai parcial.

O número de cenários (`n_scenarios`) precisa de atenção, porque depende da frequência dos dados. Quando ele não vem no config, o padrão sai da própria frequência: 200 mil para séries mensais e 4 milhões para séries diárias. A base diária precisa de muito mais porque o excesso de retorno de um pregão é pequeno perto do seu desvio-padrão, e com poucos cenários o alpha* oscila bastante de uma rodada para outra. O `app.__main__` usa esses mesmos valores.

### `app.graficos`: Figuras dos resultados (F16)

Gera em `results/` as seis figuras usadas no documento: a curva G(alpha) com a raiz marcada, o alpha ótimo contra gamma, o alpha ótimo contra o horizonte T (que fica reto, mostrando a miopia), as frações de consumo, a trajetória da riqueza e o consumo somado por ano. A da riqueza tem dois painéis: em cima a média com a faixa entre os percentis 5 e 95, e embaixo a largura dessa faixa em porcentagem da média, que é o que mostra a dispersão crescendo. No painel de cima, em escala log, ela passaria despercebida.

```python
def montar_rodape(res, cfg, periodo, n_obs, beta_anual, anos, unidade,
                  dados_reais=True) -> str:
    """Texto de procedência (duas linhas) impresso em todas as figuras."""

def gerar(res, mercado, rf, cfg, rodape,
          destino="results") -> list[str]:
    """Escreve as figuras e devolve os caminhos."""
```

O módulo é acionado por `python -m app --graficos`, na mesma execução que faz as contas, então os parâmetros das figuras são os mesmos da linha de comando e não há como um divergir do outro.

O matplotlib fica isolado. O `app.principal` não importa este módulo, e no `__main__` o import só acontece se a flag for usada; sem a flag, ele nem chega a ser carregado. Quem só quer o resultado numérico não paga o tempo de inicialização de uma biblioteca de gráficos inteira, e o núcleo de cálculo continua sem depender dela.

Cada PNG leva no rodapé as informações da rodada que o gerou, em duas linhas. A de cima diz de onde vieram os números: a série, se a base é real ou sintética, a janela e o número de observações, e o R_f anualizado com a sua origem (`série CDI` ou `informado`, conforme a flag `--cdi-anual` tenha sido usada ou não). A de baixo traz os parâmetros: gamma, beta anual, T, W_0, o `n_scenarios`, o `n_paths` e a semente, terminando no alpha ótimo. Com isso a figura sozinha basta para refazer a rodada.

A quebra em duas linhas tem um motivo prático. Em uma linha só o texto passava de 7 polegadas, que é a largura das figuras, e como o `savefig` usa `bbox_inches="tight"` o excesso não era cortado: o PNG saía mais largo, e cada figura acabava com uma dimensão diferente.

Marcar se a base é real ou sintética importa porque a série de demonstração usa datas plausíveis; sem essa marca, uma figura gerada sem banco ficaria indistinguível de uma gerada com dados do Yahoo e do Banco Central. Só que o rodapé sozinho não basta: como o nome do arquivo é o mesmo nos dois casos, uma rodada sem banco sobrescreveria as figuras de dados reais que o texto referencia. Por isso o destino também muda, com as figuras de dados reais indo para `results/` e as da base sintética para `results/sinteticos/`. Guardar a procedência num arquivo de metadados separado seria outra saída, mas aí seria fácil o arquivo ficar para trás; com a legenda na própria imagem, ela acompanha a figura quando vai para dentro do documento. As figuras ficam versionadas no repositório, porque o texto se refere a elas.

Dois desses gráficos refazem a otimização e por isso custam tempo: o G(alpha) avalia a condição de primeira ordem em 60 pontos e o alpha contra gamma refaz a otimização em 8 valores. Sobre os 4 milhões de cenários da base diária isso dá cerca de 32 segundos, contra os 6 segundos da esteira inteira sem figuras; na base mensal, com 200 mil cenários, o custo é uma fração disso. É essa a etapa mais cara da aplicação, e é ela que fixa o limite de 40 segundos do NF1. Já o gráfico do alpha contra T sai de graça, porque o alpha não depende de T, e é esse achatamento que ele serve para mostrar. A reta é desenhada a partir do alpha único, e não de uma otimização por horizonte: a verificação numérica da miopia (F12) é a do notebook de teste, e a figura só ilustra o resultado.

---

## Projeto de algoritmos

<!--Descrever o algoritmo implementado em cada função-->

Situação atual: os algoritmos das Etapas 0 a 6 estão implementados e testados (tarefas 4 a 7, com um notebook por requisito dentro de `tests/`). A integração com o QuantEcon (tarefa 8) está no `tests/19_algoritmo_quantecon.ipynb`, que refaz a solução por programação dinâmica com quadratura (`qnwnorm` mais `brentq`) e confirma a miopia.

1. Calibração (Etapa 0). As funções `media` e `covariancia` calculam os estimadores amostrais em cima dos retornos. A taxa livre de risco vem do CDI: por padrão, da média da coluna `cdi` dos dados, que já está na frequência da base; se o usuário informar um CDI anual (`--cdi-anual`), é esse valor que vale, convertido para o período pela `RendaFixa`.
2. Carteira ótima (Etapa 1). A função `resolver_alpha_otimo` maximiza J(alpha) = E[u(R_p)] resolvendo a condição de primeira ordem G(alpha) = 0. Para dois ativos ou mais usa o SLSQP; para um ativo só usa o `brentq`. As esperanças são calculadas por Monte Carlo sobre cenários sorteados de uma normal com a média e a covariância estimadas. O alpha é sempre irrestrito, admitindo venda a descoberto e alavancagem, sem teto. Isso é resolvido uma vez só, por causa da miopia.
3. Phi (Etapa 2). A função `phi_chapeu` calcula a esperança E[R_p^(1-gamma)] do portfólio ótimo, também uma vez só, e o valor é reaproveitado depois.
4. Coeficientes A_t e frações de consumo (Etapas 3 e 4). As funções `recorrencia_A` e `fracoes_consumo` fazem a indução retroativa, de t = T até t = 0. Essa parte é pura álgebra, não tem otimização nenhuma.
5. Simulação para a frente (Etapas 5 e 6). A função `propagar_riqueza` faz, em cada período, o consumo `c_t* = theta_t * W_t`, investe o que sobrou seguindo o alpha ótimo e propaga a riqueza para o período seguinte.
6. Validação (Etapas 7 e 8). A função `funcao_valor` confere a consistência de Bellman, e o teste de miopia verifica que a distância entre os alphas obtidos com horizontes diferentes é menor que um epsilon (F12 a F14).

As Etapas 3 e 7 também aparecem no resultado final: os coeficientes `A_t` da recorrência e o `valor_V`, que é a função valor avaliada na riqueza inicial (requisito F11). Antes esses dois ficavam escondidos dentro do agente e eram descartados no fim. A simulação devolve, além da média, os percentis período a período (`trajetoria_W_p5`, `_mediana` e `_p95`), que são necessários para desenhar a banda de confiança nas figuras de `results/`, e o `consumo_por_ano`, que a linha de comando imprime e a figura de barras desenha a partir do mesmo número.
