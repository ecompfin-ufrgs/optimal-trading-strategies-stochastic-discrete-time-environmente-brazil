# Documento de requisitos do sistema

<!-- Aqui você vai descrever o problema de pesquisa, que é o que você vai fazer, especificando isto em requisitos funcionais,
isto é, grandezas que você quer quer o software calcule.-->

## Requisitos funcionais
- Requisito F1 - ler as séries históricas de Ibovespa (^BVSP) e CDI e gravá-las/lê-las num banco SQLite
- Requisito F2 - calibrar o modelo (Etapa 0): estimar dos retornos históricos os parâmetros do mercado (mu_chapeu, Sigma_chapeu, R_f) e receber as primitivas do investidor (gamma, beta, T, W_0), que são informadas e não estimadas
- Requisito F3 - representar o mercado de renda fixa (CDI) fornecendo o retorno bruto livre de risco R_f, seja a partir da média da série histórica, seja a partir de um CDI anual informado pelo usuário e convertido para o período
- Requisito F4 - representar o mercado de renda variável (Ibovespa) fornecendo o vetor de retornos R / distribuição calibrada
- Requisito F5 - representar o Investidor com primitivas gamma, beta, W_0, T e utilidade CRRA u(c)=c^{1-gamma}/(1-gamma), incluindo o limite logarítmico u(c)=ln c quando gamma=1 (a fórmula geral é indefinida nesse ponto)
- Requisito F6 - calcular a carteira ótima alpha* resolvendo a FOC G(alpha*)=0 (Etapa 1)
- Requisito F7 - calcular Phi_chapeu = E[R_p^{1-gamma}] do portfólio ótimo (Etapa 2)
- Requisito F8 - calcular a recorrência A_t e as frações de consumo theta_t (Etapas 3 e 4)
- Requisito F9 - calcular o consumo ótimo c_t*=theta_t * W_t e a poupança S_t em cada instante (Etapa 5)
- Requisito F10 - propagar a riqueza W_{t+1}=S_t * R^*_{p,t+1} ao longo de T (simulação para a frente, Etapa 6)
- Requisito F11 - calcular a função valor V_t(W)=A_t * W^{1-gamma}/(1-gamma) (Etapa 7)
- Requisito F12 - validar a miopia: alpha* invariante ao horizonte
- Requisito F13 - validar theta_t estritamente crescente até theta_T = 1
- Requisito F14 - validar a convergência ao Merton contínuo quando Delta t -> 0
- Requisito F15 - receber pela linha de comando os parâmetros do investidor (gamma, beta, W_0, T), o CDI anual da renda fixa e os controles da simulação (cenários, trajetórias, semente) e disparar o cálculo. Os ativos de risco não são parametrizáveis pela linha de comando: a esteira aceita N ativos, mas a interface fixa o Ibovespa
- Requisito F16 - apresentar os resultados: carteira ótima alpha*, trajetória de consumo/riqueza e as figuras, cada uma com a procedência da rodada no rodapé

## Requisitos não funcionais

- Requisito NF1 - O tempo de execução de cada algoritmo do modelo não pode superar 60 segundos. A geração das figuras fica fora desse limite, porque é a apresentação dos resultados e não um algoritmo do modelo: duas das seis refazem a otimização (60 avaliações da FOC e mais 8 reotimizações) sobre os 4 milhões de cenários da base diária e custam sozinhas cerca de 42 segundos. Sobre essa mesma base, a esteira inteira roda em torno de 4,5 segundos.
- Requisito NF2 - a aplicação deve ser executada pela linha de comando, sem precisar editar código para trocar os parâmetros
- Requisito NF3 - rodar em Windows, Linux e macOS (o desenvolvimento é feito no Windows)
- Requisito NF4 - reprodutibilidade: mesma seed + mesmos dados -> resultado idêntico
- Requisito NF5 - arquitetura pipes-and-filter + separação POO (estado) / funcional puro (matemática)
- Requisito NF6 - persistência dos dados em SQLite via DAL
