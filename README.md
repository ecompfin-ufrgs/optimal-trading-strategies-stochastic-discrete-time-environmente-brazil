# Optimal Trading Strategies in a Stochastic Discrete-Time Environment in Brazil

Código do Trabalho de Conclusão de Curso de Murilo Fiorio Pires (Faculdade de Ciências Econômicas, UFRGS), orientado pelo Prof. Dr. Nelson Seixas dos Santos.

Implementação em Python do modelo de decisão de consumo e portfólio de Samuelson (1969), calibrado com dados reais do Ibovespa e do CDI. O programa calcula a carteira ótima (quanto o investidor deveria deixar em renda variável), as frações da riqueza que ele consome em cada período e simula como a riqueza dele evolui ao longo do tempo. A função de utilidade é a CRRA, que é a usada no projeto do TCC.

O código é uma esteira de etapas, no estilo *pipes and filters*, em que cada etapa recebe o resultado da anterior. As classes guardam o estado (os mercados e o investidor), e as contas do modelo ficam em funções que só recebem números e devolvem números. A explicação completa está em [`docs/project/projeto.md`](docs/project/projeto.md) e a lista de requisitos em [`docs/requisitos/requisitos.md`](docs/requisitos/requisitos.md).

## Instalação

É preciso ter o Python 3.12. As versões das bibliotecas estão presas no `requirements.txt`, e vale instalar a partir dele em vez de ir instalando uma por uma.

```bash
git clone https://github.com/ecompfin-ufrgs/optimal-trading-strategies-stochastic-discrete-time-environmente-brazil.git
cd optimal-trading-strategies-stochastic-discrete-time-environmente-brazil
```

```bash
pip install -r requirements.txt
```

## Rodando o modelo

```bash
python -m app
```

Sem opções, o programa usa a base mensal, `data/mercado.db`. Com `--diario` ele usa a base diária, `data/mercado_diario.db`, que é a usada no trabalho. Os dois bancos têm dados reais do Ibovespa e do CDI; se o da frequência pedida não existir, o programa gera uma série sintética só para a demonstração continuar funcionando.

Os parâmetros do investidor entram pela linha de comando, então dá para testar valores diferentes sem precisar editar o código. O `python -m app --help` mostra a lista completa:

```bash
python -m app --anos 20 --beta-anual 0.90 --gamma 3.0
python -m app --diario --anos 10
python -m app --diario --graficos        # + figuras em results/
```

O beta, fator de desconto, é informado ao ano, e o programa converte para o período dos dados: no diário, é o beta anual elevado a 1/252, porque o ano tem cerca de 252 pregões. Um beta de 0,96 por pregão, em vez de ao ano, descreveria um investidor que consome quase tudo já no primeiro ano.

O beta não muda a carteira ótima, só as frações de consumo: ele não entra na condição de primeira ordem do alpha. O horizonte restante também não entra nela, e por isso a decisão é míope, ou seja, a parcela em renda variável não depende de quantos períodos faltam.

Saída típica de `python -m app --diario`:

```
=== Esteira DP-CRRA-IID (Samuelson 1969) - base diaria ===
Ativos de risco       : ['ibov']
R_f (pregao)          : 0.00048924   (13.12% a.a.)
mu_hat (pregao)       : 0.00051104   (13.74% a.a.)
gamma                 : 5.0
Carteira otima a*     : [0.0584]
Phi_hat               : 0.998042
beta                  : 0.999838 por pregao  (0.96 a.a.)
theta_0 (pregao)      : 0.001024
theta_T (terminal)    : 1.0000
Consumo por ano (frac. de W_0), horizonte de 5 anos:
   ano 1: 0.2602
   ano 2: 0.2646
   ano 3: 0.2691
   ano 4: 0.2736
   ano 5: 0.2783
E[W_T] (T=1260)       : 0.001113  [P5=0.001074, P95=0.001155]
```

O consumo sai somado por ano. Na base diária cada fração de consumo fica na casa de 0,001 por pregão, e imprimir 1260 números desse tamanho não ajudaria muito a entender o resultado. Somando dentro de cada ano dá para ver a fração de W0 que foi consumida, que é o número que costuma ser reportado.

Essa saída usa os 4 milhões de cenários do padrão. Os números e as figuras do artigo vêm de uma rodada com 40 milhões, em que a carteira ótima sai 0,0430:

```bash
python -m app --diario --n-scenarios 40000000 --graficos
```

O motivo de usar tantos cenários está no fim da seção sobre a base de dados.

## Figuras dos resultados

```bash
python -m app --diario --graficos
```

Isso escreve nove figuras em `results/`, na mesma execução do modelo. As que estão versionadas no repositório são as da base diária, geradas com os 40 milhões de cenários do artigo. Como os parâmetros das figuras são os mesmos que foram passados na linha de comando, não corre o risco de gerar um gráfico com um gamma e escrever outro valor no texto.

| Figura | O que mostra |
|---|---|
| `foc_G_de_alpha.png` | a curva G(alfa) cruzando o zero, que é onde fica o alfa ótimo |
| `alpha_vs_gamma.png` | o alfa ótimo caindo conforme o gamma sobe (mais ou menos na proporção de 1/gamma) |
| `alpha_vs_mu.png` | o alfa ótimo subindo com o retorno esperado, e passando pelo zero quando ele fica igual ao CDI |
| `alpha_vs_sigma.png` | o alfa ótimo caindo conforme a volatilidade sobe |
| `theta_t.png` | as frações de consumo subindo até chegar em 1 (F13), em escala log |
| `theta_vs_beta.png` | a fração consumida no primeiro período caindo conforme o beta sobe |
| `theta_vs_premio.png` | como a fração consumida no primeiro período reage ao prêmio de risco, com uma curva por gamma: sobe se gamma > 1, cai se gamma < 1 e não muda se gamma = 1 |
| `riqueza_W_t.png` | a riqueza ao longo do tempo, com a faixa entre os percentis 5 e 95 |
| `consumo_por_ano.png` | o consumo somado por ano |

Sem a flag nenhum arquivo é escrito. Isso é de propósito: dá para ficar testando `--gamma`, `--anos` e `--beta-anual` à vontade sem sobrescrever as figuras que o texto do trabalho referencia.

No rodapé de cada figura ficam as informações da rodada que gerou ela: qual base, a janela de datas, o R_f, gamma, beta (ao ano e por período), T, W0, a quantidade de cenários e de trajetórias, a semente e o alfa ótimo que saiu.

Cinco dessas figuras refazem contas sobre os cenários de Monte Carlo, e o [`projeto.md`](docs/project/projeto.md) explica quais. Na base diária, com os 4 milhões de cenários, a execução com a flag leva cerca de 1 minuto, contra poucos segundos sem ela; com os 40 milhões do artigo, uns dez vezes mais.

## Atualizando a base de dados

Os bancos que já estão no repositório bastam para rodar tudo. Os retornos do mensal, `data/mercado.db`, vão de 2015-02 a 2024-12, e os do diário, `data/mercado_diario.db`, de 2022-05-24 a 2026-08-05. As fontes são o Yahoo Finance, para o Ibovespa, e a API SGS do Banco Central, para o CDI (série 4391 no mensal e série 12 no diário). A ingestão sobrescreve o banco da frequência pedida, então há dois usos diferentes.

Para refazer os bancos versionados, com as mesmas janelas:

```bash
python -m app.ingestao 2015-01-01 2024-12-31
python -m app.ingestao 2022-05-22 2026-08-06 --diario
```

O primeiro recria o `data/mercado.db` e o segundo, o `data/mercado_diario.db`. A tabela `retornos`, que é a que o modelo usa, sai igual à versionada. A única diferença aparece na tabela `cdi` do diário, que ganha o dia 2026-08-06: a API do Banco Central inclui a data final pedida e a do Yahoo não, e por isso esse dia fica sem retorno do Ibovespa para casar.

Para baixar dados mais novos, basta não passar a data final, e a ingestão vai até hoje:

```bash
python -m app.ingestao
python -m app.ingestao 2022-05-22 --diario
```

Sem nenhuma data, o mensal começa em 2000-01-01. Nos dois casos os resultados passam a ser os da janela nova, e não mais os do texto do trabalho.

## Estrutura

```
app/                      pacote da aplicação
  dal.py                  acesso a dados: download, SQLite, retornos (F1, NF6)
  ingestao.py             popula o banco a partir das fontes reais (F1, NF6)
  mercado.py              RendaFixa (CDI) e RendaVariavel (Ibovespa) (F2–F4)
  agente.py               Investidor CRRA (F5, F6, F8, F9)
  nucleo.py               as contas do modelo, em funções separadas (F6–F11)
  principal.py            liga as etapas na ordem (F10, NF5)
  graficos.py             figuras dos resultados, fora da sequência (F15)
  __main__.py             a linha de comando, python -m app (F14, NF2, NF5)
data/                     bancos SQLite versionados (mensal e diário)
results/                  figuras geradas por --graficos (versionadas)
docs/                     documento de projeto e de requisitos
tests/                    20 notebooks, organizados por requisito
requirements.txt          versões das bibliotecas, fixadas
LICENSE                   licença MIT
```

## Licença

O código está sob a licença MIT. O texto completo está no arquivo
[`LICENSE`](LICENSE).
