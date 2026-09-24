# Documento de requisitos do sistema

<!-- Aqui você vai descrever o problema de pesquisa, que é o que você vai fazer, especificando isto em requisitos funcionais,
isto é, grandezas que você quer quer o software calcule.-->

## Requisitos funcionais
- Requisito F1 - ler as séries históricas de Ibovespa (^BVSP) e CDI e gravá-las/lê-las num banco SQLite
- Requisito F2 - calibrar o modelo (Etapa 0): estimar dos retornos históricos os parâmetros do mercado (mu_chapeu, Sigma_chapeu, R_f) e receber as primitivas do investidor (gamma, beta, T, W_0), que são informadas e não estimadas
- Requisito F3 - representar o mercado de renda fixa (CDI) fornecendo a taxa livre de risco R_f por período (líquida; nas contas do modelo entra o fator bruto 1 + R_f), seja a partir da média da série histórica, seja a partir de um CDI anual informado pelo usuário e convertido para o período
- Requisito F4 - representar o mercado de renda variável (Ibovespa) fornecendo o vetor de retornos R / distribuição calibrada
- Requisito F5 - representar o Investidor com primitivas gamma, beta, W_0, T e utilidade CRRA u(c)=c^{1-gamma}/(1-gamma), incluindo o limite logarítmico u(c)=ln c quando gamma=1 (a fórmula geral é indefinida nesse ponto)
- Requisito F6 - calcular a carteira ótima alpha* resolvendo a FOC G(alpha*)=0 (Etapa 1)
- Requisito F7 - calcular Phi_chapeu = E[R_p^{1-gamma}] do portfólio ótimo (Etapa 2)
- Requisito F8 - calcular a recorrência A_t e as frações de consumo theta_t (Etapas 3 e 4)
- Requisito F9 - calcular o consumo ótimo c_t*=theta_t * W_t e a poupança S_t em cada instante (Etapa 5)
- Requisito F10 - propagar a riqueza W_{t+1}=S_t * R^*_{p,t+1} ao longo de T (simulação para a frente, Etapa 6)
- Requisito F11 - calcular a função valor V_t(W_t)=A_t * W_t^{1-gamma}/(1-gamma) nas trajetórias simuladas (com o termo B_t no caso gamma=1) e conferir que a política simulada entrega V_0(W_0) (Etapa 7)
- Requisito F12 - validar as respostas monotônicas da solução aos parâmetros: alpha* decrescente em gamma, crescente em mu e decrescente em sigma, theta_t decrescente em beta, e theta_0 respondendo ao prêmio de risco com sinal que depende de gamma (crescente se gamma > 1, decrescente se gamma < 1, constante se gamma = 1)
- Requisito F13 - validar theta_t estritamente crescente até theta_T = 1
- Requisito F14 - receber pela linha de comando os parâmetros do investidor (gamma, beta ao ano, W_0 e o horizonte T em anos, convertidos para o período dos dados), o CDI anual da renda fixa, a base de dados (mensal por padrão, ou diária com --diario), a geração das figuras (--graficos) e os controles da simulação (cenários, trajetórias, semente) e disparar o cálculo. Os ativos de risco não são parametrizáveis pela linha de comando: a esteira aceita N ativos, mas a interface fixa o Ibovespa
- Requisito F15 - apresentar os resultados: carteira ótima alpha*, trajetória de consumo/riqueza e as figuras, cada uma com a procedência da rodada no rodapé

## Requisitos não funcionais

- Requisito NF1 - O tempo de execução de cada algoritmo do modelo não pode superar 60 segundos. A geração das figuras fica fora desse limite, porque é a apresentação dos resultados e não um algoritmo do modelo: cinco das nove voltam a usar os 4 milhões de cenários da base diária (a do G(alpha) reavalia a FOC em 60 pontos e as outras quatro fazem, juntas, 40 reotimizações), e a geração das figuras leva cerca de 1 minuto. Sobre essa mesma base, a esteira inteira roda em poucos segundos. Não há notebook que teste este requisito; ele é conferido medindo o tempo de execução.
- Requisito NF2 - a aplicação deve ser executada pela linha de comando, sem precisar editar código para trocar os parâmetros
- Requisito NF3 - rodar em Windows, Linux e macOS. O desenvolvimento e os testes locais são feitos no Windows, e a integração contínua executa os testes no Linux (Ubuntu); no macOS a aplicação ainda não foi testada
- Requisito NF4 - reprodutibilidade: mesma seed + mesmos dados -> resultado idêntico. Pelo mesmo motivo, as versões das bibliotecas ficam fixadas no requirements.txt. Não há notebook dedicado a este requisito; ele foi conferido executando a esteira duas vezes com a mesma semente, com resultados idênticos
- Requisito NF5 - arquitetura pipes-and-filters + separação POO (estado) / funcional puro (matemática)
- Requisito NF6 - persistência dos dados em SQLite via DAL
