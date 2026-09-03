# Documento de projeto de software

## Projeto de dados

<!--Modelo de dados: fontes, formato dos arquivos e esquema do banco.-->

### Fontes

São duas séries históricas, uma para cada mercado. A frequência pode ser mensal, que é o padrão, ou diária:

- Renda variável: o Ibovespa (`^BVSP`), usando o nível do índice. Os dados vêm do Yahoo Finance, pela API pública de gráficos, acessada com o `urllib`.
- Renda fixa: o CDI, que faz o papel da taxa livre de risco `R_f`. Os dados vêm da API do Banco Central. Quando a base é mensal usa-se a série SGS 4391, que já vem acumulada no mês em % ao mês; quando é diária, a série 12, em % ao dia.

### Fluxo (transformação) dos dados

O sistema começa obtendo os **dados brutos** do Ibovespa e do CDI. Em seguida, esses dados são transformados em **retornos por período**, que mostram quanto cada mercado ganhou ou perdeu em cada período (mês ou dia, conforme a frequência da ingestão). A partir desses retornos, o sistema calcula os **parâmetros estatísticos** necessários para o modelo, como retorno esperado, risco etc. Por fim, esses parâmetros são usados para gerar as **trajetórias simuladas** de riqueza e consumo do investidor ao longo do tempo, produzindo os resultados finais da aplicação. A informação muda de forma ao longo da esteira:

```
   dados brutos          retornos por periodo       parametros          trajetorias
 (ibovespa, cdi)   ->        (retornos)        ->  (parametros)  ->    (em memoria)
                                                                        [resultado]
```

Os dados brutos e os derivados ficam guardados de forma permanente em SQLite (NF6), e quem cuida disso é a camada DAL (Data Access Layer). O resto da sequência de etapas de processamento, o pipeline, lê do banco e não refaz o download a cada execução.

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
              +-------+--------+
                      |  calibracao (Etapa 0): media, covariancia, R_f
                      v
              +----------------+
              |   parametros   |
              +----------------+
              | chave TEXT PK  |
              | valor REAL     |
              +----------------+
```

A ligação entre `ibovespa`/`cdi` e `retornos` é feita pela data, já que as três tabelas usam a mesma chave `data`. Isto é, as tabelas de dados do Ibovespa e do CDI estão conectadas às "retornos" apenas pelo fato de usarem o mesmo identificador de tempo (a coluna de data), mas sem uma ligação fixa dentro do banco de dados. O sistema pega os dados brutos dessas duas fontes e calcula uma nova tabela chamada "retornos", que mostra a variação de cada mês. Assim, essa tabela não é uma fonte original de dados nem depende diretamente de outra dentro do banco, ela é gerada automaticamente a partir das outras duas sempre que necessário.

#### Dicionário de dados

| Tabela | Campo | Tipo | Restrições | Descrição | Exemplo |
|---|---|---|---|---|---|
| `ibovespa` | `data` | TEXT | PK, `AAAA-MM`\|`AAAA-MM-DD`, não nulo | período da observação | `2000-01` |
| `ibovespa` | `fechamento` | REAL | > 0, não nulo | nível do índice (pontos) | `17092.0` |
| `cdi` | `data` | TEXT | PK, `AAAA-MM`\|`AAAA-MM-DD`, não nulo | período da observação | `2000-01` |
| `cdi` | `cdi` | REAL | ≥ 0, não nulo | taxa CDI do período (decimal) = `R_f` | `0.0149` |
| `retornos` | `data` | TEXT | PK, `AAAA-MM`\|`AAAA-MM-DD`, não nulo | período da observação | `2000-02` |
| `retornos` | `ibov` | REAL | não nulo | retorno do Ibovespa no período (decimal) | `-0.0315` |
| `retornos` | `cdi` | REAL | não nulo | retorno livre de risco do período (decimal) | `0.0149` |
| `parametros` | `chave` | TEXT | PK, não nulo | nome do parâmetro calibrado | `mu_ibov` |
| `parametros` | `valor` | REAL | não nulo | valor do parâmetro | `0.0107` |

O formato da coluna `data` muda junto com a frequência da ingestão: fica `AAAA-MM` no mensal, que é o padrão, e `AAAA-MM-DD` no diário. As duas frequências ficam em bancos separados, e nunca na mesma tabela.

### Formato dos arquivos (CSV)

Os arquivos CSV de entrada e de saída seguem o mesmo formato do framework de referência: a coluna `data` vem primeiro, no formato `AAAA-MM`, e depois uma coluna para cada ativo. Os valores ficam sempre em decimal (`0.0213`, e não `2,13%`) e não pode haver célula vazia.

```csv
data,ibov,cdi
2000-01,0.0213,0.0152
2000-02,-0.0315,0.0149
```

### Regras de integridade

- A coluna `data` é única dentro de cada tabela, porque é a chave primária. O formato é `AAAA-MM` no mensal e `AAAA-MM-DD` no diário, com uma frequência por banco.
- Não pode haver valor faltando (NaN) nas colunas de retorno.
- Os valores ficam sempre em decimal, nunca em porcentagem.
- A tabela `retornos` só tem as datas que aparecem nas duas tabelas brutas ao mesmo tempo, isto é, a interseção entre `ibovespa` e `cdi`. Assim o alinhamento não fica com buracos.

### Dados em trânsito (pipes)

Entre uma etapa e outra os dados ficam só na memória. As séries de preços e de retornos andam como `pandas.DataFrame` e o resto (as médias, a matriz de covariância, os cenários e as trajetórias de riqueza e consumo) como `numpy.ndarray`. Só as pontas da esteira encostam no disco: a DAL de um lado e o relatório ou a web do outro.

---

## Projeto de arquitetura

<!--Liste os módulos e pacotes e apresente uma figura com a estrutura que os liga-->

A aplicação segue o modelo arquitetural conhecido como pipes and filters. A ideia é que os dados passem por uma esteira de etapas de processamento, que são os filtros, ligadas pelos dados que saem de uma etapa e entram na próxima, que são os pipes. Cada filtro tem uma responsabilidade só: recebe dados, transforma e repassa adiante.

A camada de apresentação, que é a interface web, usa um padrão diferente, o MVC (Model-View-Controller). Enquanto o núcleo de cálculo é pipes and filters, a apresentação separa três papéis. O Model é o pacote `app`, acessado pela função `app.principal.executar_pipeline`, e é onde ficam os dados e a lógica de negócio. O Controller recebe os parâmetros que o usuário digitou, monta o `config` e chama o Model. A View mostra os resultados: a carteira ótima, as trajetórias e os gráficos. Dessa forma o núcleo fica isolado da interface.

O requisito NF5 pede também a separação de paradigmas, que ficou assim:

- A parte orientada a objetos guarda o estado. As classes `RendaFixa`, `RendaVariavel` e `Investidor` carregam os dados e o comportamento das entidades econômicas.
- A parte funcional faz a matemática. O módulo `nucleo` tem as equações do modelo (a função G(alpha), o Phi, a recorrência A_t e a função valor) escritas como funções que só recebem números e arrays e devolvem números, sem depender de nada de fora. Isso deixa cada equação fácil de testar sozinha.

### Módulos e pacotes

| Módulo / pacote | Papel | Requisitos |
|---|---|---|
| `app.dal` | DAL, o acesso a dados: download, gravação e leitura no SQLite | F1, NF6 |
| `app.ingestao` | ingestão: baixa Ibovespa e CDI e enche o SQLite (`montar_base`) | F1, NF6 |
| `app.mercado` | os mercados: `RendaFixa` (CDI) e `RendaVariavel` (Ibovespa) | F2, F3, F4 |
| `app.agente` | o indivíduo: a classe `Investidor` (gamma, beta, W0, T, CRRA) | F5, F6, F8, F9 |
| `app.nucleo` | as funções puras com a matemática do modelo | F6–F11 |
| `app.principal` | o orquestrador, que liga as etapas na ordem | F10, NF5 |
| `app.graficos` | as figuras dos resultados em `results/`, fora da esteira | F16 |
| `app.__main__` | o ponto de entrada `python -m app`, que roda a base diária usando o banco real se ele existir | NF5 |
| `web` (à parte) | a interface web em cima do módulo principal | F15, F16, NF2 |

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
| Investidor; alfa*, A_t,     |
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
      |  resultados
      v
+-----------------------------+
| Interface Web (a parte)     |   (F15, F16, NF2)
+-----------------------------+
```

Quem liga tudo isso na ordem certa é o módulo principal (`app.principal`, NF5). A validação (F12 a F14) fica nos testes, que conferem o alfa ótimo, as frações de consumo e a convergência a Merton. A ingestão (`app.ingestao`) é o passo que baixa Ibovespa e CDI e enche o SQLite que aparece lá no topo do desenho.

---

## Projeto de módulos e pacotes

<!--Dizer o que cada módulo e pacote faz, incluindo a assinatura das funções e/ou classes-->

### `app.dal`: Data Access Layer (F1, NF6)

Faz a leitura das fontes externas e guarda tudo no SQLite. É o único módulo que sabe que existe um banco e um disco.

```python
def baixar_precos(ativos: list[str], inicio: str, fim: str,
                  frequencia: str = "1mo") -> "DataFrame":
    """Baixa preços de fechamento (ex.: ^BVSP) do Yahoo Finance, via urllib. (F1)"""

def baixar_cdi_bcb(inicio: str, fim: str, frequencia: str = "1mo") -> "DataFrame":
    """Baixa o CDI da API do Banco Central — SGS 4391 (% a.m.) se mensal,
    SGS 12 (% a.d.) se diário. (F1)"""

def gravar_sqlite(df: "DataFrame", db_path: str, tabela: str) -> None:
    """Grava um DataFrame em uma tabela do banco SQLite. (F1, NF6)"""

def ler_sqlite(db_path: str, tabela: str) -> "DataFrame":
    """Lê uma tabela do banco SQLite para um DataFrame. (F1, NF6)"""

def calcular_retornos(precos: "DataFrame") -> "DataFrame":
    """Converte preços em retornos por período, alinhados por data."""
```

O parâmetro `frequencia` muda mais coisas do que parece. Com `"1mo"`, que é o padrão, a coluna `data` sai no formato `AAAA-MM`; com `"1d"` sai como `AAAA-MM-DD`. Muda também de onde vem o CDI: a série 4391, acumulada no mês, contra a série 12, que é diária. E tem um detalhe da API do Banco Central: ela recusa pedidos de série diária com mais de 10 anos e responde com HTTP 406. Por causa disso a DAL corta o período em janelas de 10 anos, faz um pedido para cada uma e depois junta tudo, tomando o cuidado de jogar fora a data repetida na emenda.

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

### `app.mercado`: Mercados (F2, F3, F4)

Cada classe representa um mercado e entrega o que o agente precisa. Isso corresponde à Etapa 0 do artigo, que é a calibração da média, da matriz de covariância e da taxa livre de risco.

```python
class RendaFixa:
    """Mercado de renda fixa (CDI) — fornece a taxa livre de risco. (F3)"""
    def __init__(self, cdi_anual: float) -> None: ...
    def retorno_livre_risco(self) -> float:
        """Taxa livre de risco R_f por período (líquida; o fator bruto é 1+R_f). (F3)"""

class RendaVariavel:
    """Mercado de renda variável (Ibovespa) — distribuição dos retornos. (F4)"""
    def __init__(self, retornos: "DataFrame") -> None: ...
    def media(self) -> "ndarray":
        """Vetor de retornos esperados estimado mu_chapeu. (F2, F4)"""
    def covariancia(self) -> "ndarray":
        """Matriz de covariância estimada sigma_chapeu. (F2, F4)"""
    def amostrar(self, n: int, seed: int | None = None) -> "ndarray":
        """Gera n cenários de retorno R normalmente distribuido para o Monte Carlo."""
```

### `app.agente`: Indivíduo / Investidor (F5, F6, F8, F9)

Guarda as características do agente (aversão ao risco, impaciência, riqueza inicial e horizonte) e conduz a decisão dele, deixando as contas em si por conta do `nucleo`.

```python
class Investidor:
    """Agente CRRA com decisão de consumo e portfólio. (F5)"""
    def __init__(self, gamma: float, beta: float,
                 w0: float, horizonte: int) -> None: ...
    def utilidade(self, c: float) -> float:
        """u(c) = c^(1−γ)/(1−γ). (F5)"""
    def utilidade_marginal(self, c: float) -> float:
        """u'(c) = c^(−γ). (F5)"""
    def carteira_otima(self, mercado: "RendaVariavel", rf: float,
                       **opts) -> "ndarray":
        """Carteira ótima alpha* via FOC G(alpha*)=0; alpha sempre irrestrito. (F6)"""
    def fracoes_consumo(self) -> "ndarray":
        """Frações de consumo theta_t = A_t^(−1/γ), t=0..T. (F8, F9)"""
```

Vale explicar como o beta se relaciona com a frequência dos dados. O beta é um número sem unidade e, com a hipótese de retornos independentes e identicamente distribuídos, ele nem aparece na condição de primeira ordem que resolve o alpha. É exatamente por isso que a carteira ótima não muda com o tempo e a miopia acontece. Isso foi conferido no número: variando o beta de 0,90 até 0,9999 na base diária, o alfa ótimo e o Phi ficam iguais. O que o beta governa é a recorrência `A_t` e, por consequência, as frações de consumo.

O problema é que o beta entra elevado a `t`, e `t` conta períodos, então o mesmo número descreve investidores completamente diferentes conforme a frequência dos dados. Um beta de 0,96 ao mês equivale a 0,613 ao ano, mas um beta de 0,96 por pregão equivale a 3,4 × 10⁻⁵ ao ano, o que seria um investidor que consome 92% da riqueza logo no primeiro ano. Para não cair nessa confusão, o `app.__main__` fixa o desconto em termos anuais (`BETA_ANUAL = 0.96`) e converte para o período: no diário fica `beta_pregao = beta_anual^(1/252) = 0,999838`. Ao reportar um resultado é bom sempre dizer as duas formas.

### `app.nucleo`: Funções puras / matemática do modelo (F6–F11)

Cada função é uma equação do artigo e dá para testar isolada das outras.

```python
def funcao_foc(alpha, R, rf, gamma):
    """G(alpha) = E[(R − rf·1)/(rf + alpha^T(R − rf·1))^γ]. (F6)"""

def resolver_alpha_otimo(R, rf, gamma, *, tol=1e-10, maxiter=200, alpha0=None):
    """Resolve G(alpha*)=0 — alpha pertence a R^N irrestrito (ver nota abaixo);
    SLSQP para N≥2, brentq para N=1. (F6)"""

def phi_chapeu(alpha, R, rf, gamma):
    """Phi_chapeu = E[R_p^(1−γ)] do portfólio ótimo. (F7)"""

def recorrencia_A(phi, beta, gamma, T):
    """A_T=1; A_t=[1+(beta·A_{t+1}·Phi_chapeu)^(1/γ)]^γ, t=T−1..0. (F8)"""

def fracoes_consumo(A, gamma):
    """theta_t = A_t^(−1/γ). (F8)"""

def propagar_riqueza(w0, theta, alpha, R, rf):
    """Forward pass: W_{t+1}=S_t·R*_{p,t+1}; devolve W_t, c_t*, S_t. (F9, F10)"""

def funcao_valor(A, W, gamma):
    """V_t(W) = A_t·W^(1−γ)/(1−γ). (F11)"""
```

Uma observação sobre o domínio dos pesos. A função `resolver_alpha_otimo` é sempre irrestrita, ou seja, o alfa pode ser qualquer número real, o que admite venda a descoberto (alfa negativo) e alavancagem (a soma dos pesos passando de 1), sem nenhum teto. Não existe opção para exigir carteira só comprada nem para impor limites. No caso de um ativo só, o `brentq` começa procurando no intervalo de −20 a 20 e vai dobrando esse intervalo até a função G trocar de sinal. Se ela nunca trocar, quer dizer que não existe nenhum cenário com o retorno do ativo abaixo da taxa livre de risco. Nesse caso não há alpha ótimo finito e a função levanta um `RuntimeError` em vez de devolver um valor qualquer.

### `app.principal`: Orquestrador (F10, NF5)

Liga os filtros na ordem da esteira. É a função que a web chama.

```python
def executar_pipeline(config: dict) -> dict:
    """DAL → mercado → agente → simulação; devolve o resultado (alpha*, theta_t, trajetórias, métricas) que a web consome. (NF5)"""
```

O número de cenários (`n_scenarios`) precisa de atenção, porque depende da frequência dos dados. O padrão de 80 000 serve bem para séries mensais. Quem chama a função precisa escolher o `n_scenarios` de acordo com a base. O `app.__main__` usa 4 milhões no diário e 200 mil no mensal.

### `app.graficos`: Figuras dos resultados (F16)

Gera em `results/` as seis figuras usadas no documento: a curva G(alpha) com a raiz marcada, o alfa ótimo contra gamma (a hipérbole de Merton), o alfa ótimo contra o horizonte T (que fica reto, mostrando a miopia), as frações de consumo, a trajetória da riqueza com a faixa entre os percentis 5 e 95, e o consumo somado por ano.

```python
def gerar(res, mercado, rf, cfg, rodape, periodos_por_ano,
          destino="results") -> list[str]:
    """Escreve as figuras e devolve os caminhos."""
```

O módulo é acionado por `python -m app --graficos`, na mesma execução que faz as contas, então os parâmetros das figuras são os mesmos da linha de comando e não há como um divergir do outro.

O matplotlib fica isolado de propósito. O `app.principal` não importa este módulo, e no `__main__` o import só acontece se a flag for usada. Sem a flag o matplotlib nem chega a ser carregado. Isso importa para a camada web, que consome só o `executar_pipeline` e desenha no navegador a partir do JSON.

Cada PNG leva no rodapé as informações da rodada que o gerou: a base, a janela dos dados, gamma, beta anual, T, o `n_scenarios`, a semente e o alfa ótimo. A alternativa seria guardar isso num arquivo de metadados separado, mas aí seria fácil o arquivo ficar para trás; do jeito que está, a legenda acompanha a imagem quando ela vai para dentro do documento. As figuras ficam versionadas no repositório, porque o texto se refere a elas.

Dois desses gráficos refazem a otimização e por isso custam tempo: o G(alpha) avalia a condição de primeira ordem em 60 pontos e o alpha contra gamma refaz a otimização em 8 valores. Já o gráfico do alpha contra T sai de graça, porque o alfa não depende de T, e é justamente esse achatamento que o gráfico serve para mostrar.

### `web` (à parte): Interface (F15, F16, NF2)

A camada de apresentação usa o padrão MVC (Model-View-Controller) em cima do módulo principal:

- Model: o pacote `app`, que é a esteira pipes and filters, acessado pela função `app.principal.executar_pipeline`. É onde ficam os dados e a lógica de negócio, e ele não sabe nada sobre a web.
- Controller: recebe os parâmetros do investidor (gamma, beta, W0, T e os ativos), monta o `config`, chama o Model e entrega o resultado para a View (F15).
- View: mostra a saída, ou seja, a carteira ótima, as trajetórias de consumo e de riqueza e os gráficos (F16).

Essa parte vive em um projeto separado. A vantagem da separação em MVC é poder trocar a interface, seja outra tela web ou outro tipo de interface, sem precisar mexer no Model, que é o núcleo de cálculo.

---

## Projeto de algoritmos

<!--Descrever o algoritmo implementado em cada função-->

Situação atual: os algoritmos das Etapas 0 a 6 estão implementados e testados (tarefas 4 a 7, com um notebook por requisito dentro de `tests/`). A integração com o QuantEcon (tarefa 8) está no `tests/19_algoritmo_quantecon.ipynb`, que refaz a solução por programação dinâmica com quadratura (`qnwnorm` mais `brentq`) e confirma a miopia.

1. Calibração (Etapa 0). As funções `media` e `covariancia` calculam os estimadores amostrais em cima dos retornos, e a taxa livre de risco vem do CDI.
2. Carteira ótima (Etapa 1). A função `resolver_alpha_otimo` maximiza J(alpha) = E[u(R_p)] resolvendo a condição de primeira ordem G(alpha) = 0. Para dois ativos ou mais usa o SLSQP; para um ativo só usa o `brentq`. As esperanças são calculadas por Monte Carlo sobre cenários sorteados de uma normal com a média e a covariância estimadas. O alpha é sempre irrestrito, admitindo venda a descoberto e alavancagem, sem teto. Isso é resolvido uma vez só, por causa da miopia.
3. Phi (Etapa 2). A função `phi_chapeu` calcula a esperança E[R_p^(1−gamma)] do portfólio ótimo, também uma vez só, e o valor é reaproveitado depois.
4. Coeficientes A_t e frações de consumo (Etapas 3 e 4). As funções `recorrencia_A` e `fracoes_consumo` fazem a indução retroativa, de t = T até t = 0. Essa parte é pura álgebra, não tem otimização nenhuma.
5. Simulação para a frente (Etapas 5 e 6). A função `propagar_riqueza` faz, em cada período, o consumo `c_t* = theta_t · W_t`, investe o que sobrou seguindo o alpha ótimo e propaga a riqueza para o período seguinte.
6. Validação (Etapas 7 e 8). A função `funcao_valor` confere a consistência de Bellman, e o teste de miopia verifica que a distância entre os alphas obtidos com horizontes diferentes é menor que um epsilon (F12 a F14).

As Etapas 3 e 7 também aparecem no resultado final: os coeficientes `A_t` da recorrência e o `valor_V`, que é a função valor avaliada na riqueza inicial (requisito F11). Antes esses dois ficavam escondidos dentro do agente e eram descartados no fim. A simulação devolve, além da média, os percentis período a período (`trajetoria_W_p5`, `_mediana` e `_p95`), que são necessários para desenhar a banda de confiança, tanto nas figuras de `results/` quanto na web.
