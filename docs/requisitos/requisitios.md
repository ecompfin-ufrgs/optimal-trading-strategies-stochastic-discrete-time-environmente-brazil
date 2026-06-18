# Documento de requisitos do sistema

<!-- Aqui você vai descrever o problema de pesquisa, que é o que você vai fazer, especificando isto em requisitos funcionais, 
isto é, grandezas que você quer quer o software calcule.-->

## Requisitos funcionais
- Requisito F1 - ler as séries históricas de Ibovespa (^BVSP) e CDI e gravá-las/lê-las num banco SQLite
- Requisito F2 - calibrar os parâmetros (μ̂, Σ̂, R_f, γ, β, T, W₀) a partir dos retornos (Etapa 0)
- Requisito F3 - representar o mercado de renda fixa (CDI) fornecendo o retorno bruto livre de risco R_f
- Requisito F4 - representar o mercado de renda variável (Ibovespa) fornecendo o vetor de retornos R / distribuição calibrada
- Requisito F5 - representar o Investidor com primitivas γ, β, W₀, T e utilidade CRRA u(c)=c^{1−γ}/(1−γ)
- Requisito F6 - calcular a carteira ótima α* resolvendo a FOC G(α*)=0 (Etapa 1)
- Requisito F7 - calcular Φ̂ = E[R_p^{1−γ}] do portfólio ótimo (Etapa 2)
- Requisito F8 - calcular a recorrência A_t e as frações de consumo θ_t (Etapas 3–4)
- Requisito F9 - calcular o consumo ótimo c_t*=θ_t·W_t e a poupança S_t em cada instante (Etapa 5)
- Requisito F10 - propagar a riqueza W_{t+1}=S_t·R*_{p,t+1} ao longo de T (forward pass, Etapa 6)
- Requisito F11 - calcular a função valor V_t(W)=A_t·W^{1−γ}/(1−γ) (Etapa 7)
- Requisito F12 - validar a miopia: α* invariante ao horizonte
- Requisito F13 - validar θ_t estritamente crescente até θ_T = 1
- Requisito F14 - validar a convergência ao Merton contínuo quando Δt→0
- Requisito F15 - a interface web deve receber os parâmetros do investidor (γ, β, W₀, T, ativos) e disparar o cálculo
- Requisito F16 - a interface web deve exibir os resultados — carteira ótima α*, trajetória de consumo/riqueza e gráficos

## Requisitos não funcionais

- Requisito NF1 - O tempo de execução de cada algoritmo não pode superar 30 segundos.
- Requisito NF2 - a aplicação deve ser executada na Web (acesso via navegador)
- Requisito NF3 - rodar em Windows, Linux e macOS (o servidor deve subir nos três)
- Requisito NF4 - reprodutibilidade: mesma seed + mesmos dados → resultado idêntico
- Requisito NF5 - arquitetura pipes-and-filter + separação POO (estado) / funcional puro (matemática), com a camada web sobre o módulo principal
- Requisito NF6 - persistência dos dados em SQLite via DAL

