# Optimal Trading Strategies in a Stochastic Discrete-Time Environment in Brazil

Código do Trabalho de Conclusão de Curso de Murilo Fiorio Pires (Faculdade de Ciências Econômicas, UFRGS), orientado pelo Prof. Dr. Nelson Seixas dos Santos.

Implementação em Python do modelo de decisão de consumo e portfólio de Samuelson (1969), calibrado com dados reais do Ibovespa e do CDI. O programa calcula a carteira ótima (quanto o investidor deveria deixar em renda variável), as frações da riqueza que ele consome em cada período e simula como a riqueza dele evolui ao longo do tempo. A função de utilidade é a CRRA, que é a usada no projeto do TCC.

O código foi organizado em etapas ligadas em sequência: cada etapa recebe os dados da anterior, transforma e passa adiante, o que é chamado de arquitetura pipes and filters. As classes guardam o estado (os mercados e o investidor) e as contas do modelo ficam separadas, em funções que só recebem números e devolvem números. A explicação completa está em [`docs/project/projeto.md`](docs/project/projeto.md) e a lista de requisitos em [`docs/requisitos/requisitos.md`](docs/requisitos/requisitos.md).

---

## Instalação

É preciso ter o Python 3.12. As versões das bibliotecas estão presas no `requirements.txt`, e vale instalar a partir dele em vez de ir instalando uma por uma.

```bash
git clone https://github.com/ecompfin-ufrgs/optimal-trading-strategies-stochastic-discrete-time-environmente-brazil.git
cd optimal-trading-strategies-stochastic-discrete-time-environmente-brazil
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

Sobre o beta, que é o fator de desconto: ele é informado em termos anuais e o programa converte para o período dos dados. No diário a conta é o beta anual elevado a 1/252, porque o ano tem mais ou menos 252 pregões. Isso parece um detalhe, mas dizer "beta = 0,96" não quer dizer nada se não estiver claro se é por ano, por mês ou por dia. Um beta de 0,96 ao ano é uma coisa; 0,96 por pregão seria um investidor que consome quase tudo já no primeiro ano.

Uma característica do modelo é que o beta não muda a carteira ótima, só as frações de consumo. Ele nem aparece na condição de primeira ordem que resolve o alpha. É justamente por isso que se diz que o investidor é míope: a decisão de quanto colocar em renda variável não depende do horizonte nem da impaciência dele.

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

---

## Figuras dos resultados

```bash
python -m app --diario --graficos
```

Isso escreve nove figuras em `results/`, na mesma execução que faz as contas. As que estão versionadas no repositório são as da base diária. Como os parâmetros das figuras são os mesmos que foram passados na linha de comando, não corre o risco de gerar um gráfico com um gamma e escrever outro valor no texto.

| Figura | O que mostra |
|---|---|
| `foc_G_de_alpha.png` | a curva G(alpha) cruzando o zero, que é onde fica o alpha ótimo |
| `alpha_vs_gamma.png` | o alpha ótimo caindo conforme o gamma sobe (mais ou menos na proporção de 1/gamma) |
| `alpha_vs_mu.png` | o alpha ótimo subindo com o retorno esperado, e passando pelo zero quando ele fica igual ao CDI |
| `alpha_vs_sigma.png` | o alpha ótimo caindo conforme a volatilidade sobe |
| `theta_t.png` | as frações de consumo subindo até chegar em 1 (F13), em escala log |
| `theta_vs_beta.png` | a fração consumida no primeiro período caindo conforme o beta sobe |
| `theta_vs_premio.png` | como a fração consumida no primeiro período reage ao prêmio de risco, com uma curva por gamma: sobe se gamma > 1, cai se gamma < 1 e não muda se gamma = 1 |
| `riqueza_W_t.png` | a riqueza ao longo do tempo, com a faixa entre os percentis 5 e 95 |
| `consumo_por_ano.png` | o consumo somado por ano |

Sem a flag nenhum arquivo é escrito. Isso é de propósito: dá para ficar testando `--gamma`, `--anos` e `--beta-anual` à vontade sem sobrescrever as figuras que o texto do trabalho referencia.

No rodapé de cada figura ficam as informações da rodada que gerou ela: qual base, a janela de datas, o R_f, gamma, beta (ao ano e por período), T, W0, a quantidade de cenários e de trajetórias, a semente e o alpha ótimo que saiu. A ideia é que essas informações acompanhem a imagem quando ela for colada no documento, em vez de ficarem num arquivo de metadados separado, que provavelmente acabaria desatualizado.

Cinco desses gráficos voltam a usar os cenários de Monte Carlo e por isso demoram. O do G(alpha) só reavalia a condição de primeira ordem em 60 pontos; os outros quatro, o do alpha contra gamma, retorno esperado e volatilidade e o do consumo contra o prêmio de risco, refazem a otimização. Os de sensibilidade usam sempre os mesmos cenários, para a diferença entre um ponto e outro vir só do parâmetro que mudou (são a versão em figura dos testes do F12). Na base diária, com os 4 milhões de cenários, a execução com a flag leva cerca de 1 minuto, contra poucos segundos sem ela.

---

## Atualizando a base de dados

A ingestão sobrescreve o banco da frequência pedida, então há dois usos diferentes.

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

---

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
tests/                    19 notebooks, organizados por requisito
requirements.txt          versões das bibliotecas, fixadas
LICENSE                   licença MIT
```

---

## Licença

O código está sob a licença MIT. O texto completo está no arquivo [`LICENSE`](LICENSE).
