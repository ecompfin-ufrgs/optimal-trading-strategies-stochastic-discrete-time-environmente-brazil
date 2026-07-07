"""Pacote `app` — aplicação de otimização de portfólio (Samuelson 1969).

Arquitetura *pipes-and-filters*. A esteira liga os módulos na ordem:

    dal  →  mercado  →  agente (+ nucleo)  →  principal

Ver o desenho completo em ``docs/project/projeto.md``.
"""
