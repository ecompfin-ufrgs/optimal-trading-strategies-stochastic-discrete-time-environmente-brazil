# Documento de requisitos do sistema

<!-- Aqui você vai descrever o problema de pesquisa, que é o que você vai fazer, especificando isto em requisitos funcionais, 
isto é, grandezas que você quer quer o software calcule.-->

## Requisitos funcionais
- Requisito F1 - ler as séries históricas de Ibovespa (^BVSP) e CDI e gravá-las/lê-las num banco SQLite
- Requisito F2 - calibrar os parâmetros (mu_chapeu, Σ̂, R_f, gamma, beta, T, W_0) a partir dos retornos (Etapa 0)
- Requisito F3 - representar o mercado de renda fixa (CDI) fornecendo o retorno bruto livre de risco R_f, seja a partir da média da série histórica, seja a partir de um CDI anual informado pelo usuário e convertido para o período
- Requisito F4 - representar o mercado de renda variável (Ibovespa) fornecendo o vetor de retornos R / distribuição calibrada
- Requisito F5 - representar o Investidor com primitivas gamma, beta, W_0, T e utilidade CRRA u(c)=c^{1−gamma}/(1−gamma)
- Requisito F6 - calcular a carteira ótima alpha* resolvendo a FOC G(alpha*)=0 (Etapa 1)
- Requisito F7 - calcular Phi_chapeu = E[R_p^{1−gamma}] do portfólio ótimo (Etapa 2)
- Requisito F8 - calcular a recorrência A_t e as frações de consumo theta_t (Etapas 3–4)
- Requisito F9 - calcular o consumo ótimo c_t*= theta_t * W_t e a poupança S_t em cada instante (Etapa 5)
- Requisito F10 - propagar a riqueza W_{t+1} = S_t * R*_{p,t+1} ao longo de T (forward pass, Etapa 6)
- Requisito F11 - calcular a função valor V_t(W)=A_t * W^{1−gamma}/(1−gamma) (Etapa 7)
- Requisito F12 - validar a miopia: alpha* invariante ao horizonte
- Requisito F13 - validar theta_t estritamente crescente até theta_T = 1
- Requisito F14 - validar a convergência ao Merton contínuo quando delta_t -> 0
- Requisito F15 - receber pela linha de comando os parâmetros do investidor (gamma, beta, W_0, T), o CDI anual da renda fixa e os controles da simulação (cenários, trajetórias, semente) e disparar o cálculo. Os ativos de risco não são parametrizáveis pela linha de comando: a esteira aceita N ativos, mas a interface fixa o Ibovespa
- Requisito F16 - apresentar os resultados: carteira ótima alpha*, trajetória de consumo/riqueza e as figuras, cada uma com a procedência da rodada no rodapé

## Requisitos não funcionais

- Requisito NF1 - O tempo de execução de cada algoritmo não pode superar 30 segundos.
- Requisito NF2 - a aplicação deve ser executada pela linha de comando, sem precisar editar código para trocar os parâmetros
- Requisito NF3 - rodar em Windows, Linux e macOS (o desenvolvimento é feito no Windows)
- Requisito NF4 - reprodutibilidade: mesma seed + mesmos dados → resultado idêntico
- Requisito NF5 - arquitetura pipes-and-filter + separação POO (estado) / funcional puro (matemática)
- Requisito NF6 - persistência dos dados em SQLite via DAL
