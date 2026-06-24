# Documento de projeto de software

## Projeto de dados

<!--Modelo de dados: fontes, formato dos arquivos e esquema do banco.-->

### Fontes

Duas séries históricas mensais, uma por mercado:

- **Renda variável** — Ibovespa (`^BVSP`), nível do índice, obtido do Yahoo Finance (chart API pública, via `urllib`).
- **Renda fixa** — CDI, taxa mensal (a taxa livre de risco `R_f`), da API do Banco Central (SGS, série 4391).

### Fluxo (transformação) dos dados

O sistema começa obtendo os **dados brutos** do Ibovespa e do CDI. Em seguida, esses dados são transformados em **retornos mensais**, que mostram quanto cada mercado ganhou ou perdeu em cada período. A partir desses retornos, o sistema calcula os **parâmetros estatísticos** necessários para o modelo, como retorno esperado, risco etc. Por fim, esses parâmetros são usados para gerar as **trajetórias simuladas** de riqueza e consumo do investidor ao longo do tempo, produzindo os resultados finais da aplicação. A informação muda de forma ao longo da esteira:

```
   dados brutos            retornos mensais          parâmetros           trajetórias
 (ibovespa, cdi)       →      (retornos)       →    (parametros)    →    (em memória)
                                                                          [resultado]
```

Os dados brutos e derivados são guardados de forma permanente em **SQLite** (NF6) pela camada DAL (Data Access Layer); o restante da sequência de etapas de processamento dos dados, o pipeline, lê do banco e não refaz o download a cada execução.

### Modelo de dados (esquema SQLite)

Optou-se por **uma tabela de dados brutos por mercado** e uma tabela de **retornos** já alinhados por data, consumida pela calibração.

#### Diagrama

```
┌────────────────┐          ┌────────────────┐
│   ibovespa     │          │      cdi       │
├────────────────┤          ├────────────────┤
│ data  TEXT PK  │          │ data  TEXT PK  │
│ fechamento REAL│          │ cdi   REAL     │
└───────┬────────┘          └───────┬────────┘
        │ retorno do índice         │ cdi = R_f
        │ (alinhado por data)       │ (alinhado por data)
        └─────────────┬─────────────┘
                      ▼
             ┌────────────────┐
             │    retornos    │
             ├────────────────┤
             │ data  TEXT PK  │
             │ ibov  REAL     │
             │ cdi   REAL     │
             └───────┬────────┘
                     │ calibração (Etapa 0): μ̂, Σ̂, R_f
                     ▼
             ┌────────────────┐
             │   parametros   │
             ├────────────────┤
             │ chave TEXT PK  │
             │ valor REAL     │
             └────────────────┘
```

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

## Projeto de arquitetura

<!--Liste os módulos e pacotes e apresente uma figura com a estrutura que os liga-->

A aplicação usa o modelo arquitetural **"pipes and filters"**: os dados percorrem uma esteira de etapas de processamento (os *filtros*), ligadas por *pipes* (os dados que saem de uma etapa e entram na próxima). Cada filtro tem uma única responsabilidade, recebe dados, transforma e os repassa adiante.

A **camada de apresentação** (a interface web) segue um padrão diferente e complementar: **MVC (Model-View-Controller)**. Enquanto o núcleo de cálculo usa *pipes-and-filters*, a apresentação separa **Model** (o pacote `app`, acessado por `app.principal.executar_pipeline` — os dados e a lógica de negócio), **Controller** (recebe os parâmetros do usuário, monta o `config` e chama o Model) e **View** (renderiza os resultados: carteira ótima, trajetórias, gráficos). Assim, o núcleo fica isolado da interface.

Adota-se a separação de paradigmas (NF5):

- **POO guarda o estado** — as classes `RendaFixa`, `RendaVariavel` e `Investidor` encapsulam dados e comportamento das entidades econômicas.
- **Funções puras fazem a matemática** — o módulo `nucleo` implementa as equações do modelo (G(α), Φ̂, recorrência A_t, função valor) como funções que só recebem números/arrays e devolvem números, sem estado externo — fáceis de testar isoladamente.

### Módulos e pacotes

| Módulo / pacote | Papel | Requisitos |
|---|---|---|
| `app.dal` | **DAL** — acesso a dados (download, gravação/leitura SQLite) | F1, NF6 |
| `app.ingestao` | **ingestão** — baixa Ibovespa+CDI e popula o SQLite (`montar_base`) | F1, NF6 |
| `app.mercado` | mercados: `RendaFixa` (CDI) e `RendaVariavel` (Ibovespa) | F2, F3, F4 |
| `app.agente` | indivíduo: classe `Investidor` (γ, β, W₀, T, CRRA) | F5, F6, F8, F9 |
| `app.nucleo` | funções puras com a matemática do modelo | F6–F11 |
| `app.principal` | **orquestrador** da esteira pipes-and-filters | F10, NF5 |
| `app.__main__` | ponto de entrada `python -m app` | NF5 |
| `web` (à parte) | interface web sobre o módulo principal | F15, F16, NF2 |

### Figura — esteira do pipeline

```
[ SQLite / CSV ]
      │  preços
      ▼
┌──────────────────────────┐
│ DAL — acesso a dados      │   (F1, NF6)
│ baixar · gravar · ler     │
└────────────┬─────────────┘
             │  retornos (Ibovespa, CDI)
             ▼
┌──────────────────────────┐
│ Mercado                   │   (F2, F3, F4)
│ RendaFixa     → R_f       │
│ RendaVariavel → μ̂, Σ̂, R  │
└────────────┬─────────────┘
             │  parâmetros do modelo
             ▼
┌──────────────────────────┐
│ Agente + Núcleo           │   (F5–F8, F11)
│ Investidor; α*, A_t, θ_t  │
└────────────┬─────────────┘
             │  política ótima (α*, θ_t)
             ▼
┌──────────────────────────┐
│ Simulação forward         │   (F9, F10)
│ W_t, c_t*, S_t            │
└────────────┬─────────────┘
             │  trajetórias + métricas
             ▼
┌──────────────────────────┐
│ Relatório (tabelas/graf)  │   (F16)
└────────────┬─────────────┘
             │  resultados
             ▼
┌──────────────────────────┐
│ Interface Web (à parte)   │   (F15, F16, NF2)
└──────────────────────────┘

Orquestração de toda a esteira: módulo principal (app.principal, NF5)
Validação (F12–F14): testes sobre α*, θ_t e a convergência a Merton
Ingestão (app.ingestao): baixa Ibovespa+CDI e popula o [SQLite] do topo da esteira
```

---

## Projeto de módulos e pacotes

<!--Dizer o que cada módulo e pacote faz, incluindo a assinatura das funções e/ou classes-->

### `app.dal` — Data Access Layer (F1, NF6)

Leitura das fontes externas e persistência no SQLite. É o único módulo que conhece o banco e o disco.

```python
def baixar_precos(ativos: list[str], inicio: str, fim: str) -> "DataFrame":
    """Baixa preços de fechamento (ex.: ^BVSP) do Yahoo Finance, via urllib. (F1)"""

def baixar_cdi_bcb(inicio: str, fim: str) -> "DataFrame":
    """Baixa o CDI mensal da API do Banco Central (SGS, série 4391). (F1)"""

def gravar_sqlite(df: "DataFrame", db_path: str, tabela: str) -> None:
    """Grava um DataFrame em uma tabela do banco SQLite. (F1, NF6)"""

def ler_sqlite(db_path: str, tabela: str) -> "DataFrame":
    """Lê uma tabela do banco SQLite para um DataFrame. (F1, NF6)"""

def calcular_retornos(precos: "DataFrame") -> "DataFrame":
    """Converte preços em retornos mensais alinhados por data."""
```

### `app.ingestao` — Ingestão da base real (F1, NF6)

Passo operacional que **popula** o banco: baixa Ibovespa (Yahoo) + CDI (Banco Central), calcula os retornos alinhados e grava as tabelas `ibovespa`/`cdi`/`retornos`. Rodado uma vez (`python -m app.ingestao`); depois o pipeline lê do SQLite.

```python
def montar_base(db_path: str = "data/mercado.db",
                inicio: str = "2000-01-01", fim: str | None = None) -> dict:
    """Baixa Ibovespa+CDI, calcula retornos e grava as 3 tabelas. (F1, NF6)"""
```

### `app.mercado` — Mercados (F2, F3, F4)

Encapsula cada mercado e expõe os insumos que o agente precisa (Etapa 0 do artigo: calibração de μ̂, Σ̂, R_f).

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
        """Vetor de retornos esperados estimado μ̂. (F2, F4)"""
    def covariancia(self) -> "ndarray":
        """Matriz de covariância estimada Σ̂. (F2, F4)"""
    def amostrar(self, n: int, distribuicao: str = "normal") -> "ndarray":
        """Gera n cenários de retorno R ~ (μ̂, Σ̂) para o Monte Carlo."""
```

### `app.agente` — Indivíduo / Investidor (F5, F6, F8, F9)

Encapsula as primitivas do agente e orquestra sua decisão (delega a matemática ao `nucleo`).

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
        """Carteira ótima α* via FOC G(α*)=0; sem restrição por padrão.
        Repassa allow_short/allow_leverage/alpha_max ao núcleo. (F6)"""
    def fracoes_consumo(self) -> "ndarray":
        """Frações de consumo θ_t = A_t^(−1/γ), t=0..T. (F8, F9)"""
```

### `app.nucleo` — Funções puras / matemática do modelo (F6–F11)

Sem estado. Cada função implementa uma equação do artigo e é testável isolada.

```python
def funcao_foc(alpha, R, rf, gamma):
    """G(α) = E[(R − rf·1)/(rf + αᵀ(R − rf·1))^γ]. (F6)"""

def resolver_alpha_otimo(R, rf, gamma, *, allow_short=True,
                         allow_leverage=True, alpha_max=np.inf):
    """Resolve G(α*)=0 — α ∈ ℝ^N irrestrito por padrão (ver nota abaixo);
    SLSQP para N≥2, brentq para N=1. (F6)"""

def phi_chapeu(alpha, R, rf, gamma):
    """Φ̂ = E[R_p^(1−γ)] do portfólio ótimo. (F7)"""

def recorrencia_A(phi, beta, gamma, T):
    """A_T=1; A_t=[1+(β·A_{t+1}·Φ̂)^(1/γ)]^γ, t=T−1..0. (F8)"""

def fracoes_consumo(A, gamma):
    """θ_t = A_t^(−1/γ). (F8)"""

def propagar_riqueza(w0, theta, alpha, R, rf):
    """Forward pass: W_{t+1}=S_t·R*_{p,t+1}; devolve W_t, c_t*, S_t. (F9, F10)"""

def funcao_valor(A, W, gamma):
    """V_t(W) = A_t·W^(1−γ)/(1−γ). (F11)"""
```

> **Restrição sobre os pesos α (domínio).** `resolver_alpha_otimo` é **irrestrito por padrão**: `α ∈ ℝ^N`, admitindo **short** (α<0) e **alavancagem** (Σα>1). Os flags `allow_short=False`, `allow_leverage=False` e `alpha_max` impõem long-only/limites quando desejado.

### `app.principal` — Orquestrador (F10, NF5)

Liga os filtros na ordem da esteira; é o ponto de entrada chamado pela web.

```python
def executar_pipeline(config: dict) -> dict:
    """DAL → mercado → agente → simulação; devolve o resultado (α*, θ_t,
    trajetórias, métricas) que a web consome. (NF5)"""
```

### `web` (à parte) — Interface (F15, F16, NF2)

A camada de apresentação segue o padrão **MVC (Model-View-Controller)**, sobre o módulo principal:

- **Model** — o pacote `app` (a esteira *pipes-and-filters*), acessado por `app.principal.executar_pipeline`. Concentra os dados e a lógica de negócio; não conhece a web.
- **Controller** — recebe os parâmetros do investidor (γ, β, W₀, T, ativos), monta o `config`, chama o Model e repassa o resultado à View (**F15**).
- **View** — renderiza a saída: carteira ótima α*, trajetórias de consumo/riqueza e gráficos (**F16**).

Vive em projeto separado. A separação MVC permite trocar a interface (web ou outra UI) sem tocar no Model (o núcleo de cálculo).

---

## Projeto de algoritmos

<!--Descrever o algoritmo implementado em cada função-->

> **Estado:** os algoritmos das Etapas 0–6 estão **implementados e testados** (tarefas 4–7, um notebook por requisito em `tests/`). A integração com o QuantEcon (tarefa 8) e o pseudocódigo detalhado ficam para depois.

1. **Calibração (Etapa 0)** — `media`/`covariancia`: estimadores amostrais de μ̂ e Σ̂ sobre os retornos; R_f vem do CDI.
2. **Carteira ótima α\* (Etapa 1)** — `resolver_alpha_otimo`: maximiza J(α)=E[u(R_p)] resolvendo a FOC `G(α)=0` via **SLSQP** (N≥2) ou **brentq** (N=1), com `G`/J avaliados por **Monte Carlo** sobre cenários R ~ (μ̂, Σ̂). **α irrestrito por padrão** (short e alavancagem; §3.1). Resolvida **uma única vez** (miopia).
3. **Φ̂ (Etapa 2)** — `phi_chapeu`: esperança `E[R_p^(1−γ)]` do portfólio ótimo, calculada **uma vez** e reutilizada.
4. **Coeficientes A_t e frações θ_t (Etapas 3–4)** — `recorrencia_A` / `fracoes_consumo`: **indução retroativa** de `t=T` até `t=0` (backward pass), puramente algébrica, sem otimização.
5. **Simulação forward (Etapas 5–6)** — `propagar_riqueza`: a cada t consome `c_t*=θ_t·W_t`, investe a poupança em α* e propaga a riqueza (forward pass).
6. **Validação (Etapas 7–8)** — `funcao_valor` (consistência de Bellman) e o teste de miopia `‖α*_T − α*_{T'}‖ < ε` (F12–F14).
