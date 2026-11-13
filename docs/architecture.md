# Arquitetura Inicial

## Backend

O backend e uma API local em FastAPI. Ele centraliza:

- leitura e gravacao da configuracao;
- catalogo de passos;
- controle de execução;
- eventos ao vivo para o frontend;
- integracao Playwright para abrir navegador, capturar tela e executar passos.

## Frontend

O frontend e React com Vite. A primeira tela e operacional, nao uma landing page:

- painel de execução;
- status atual;
- lista de passos;
- editor de passo;
- preview do navegador;
- log ao vivo.

## Fluxo de eventos

O backend publica eventos em memoria e expoe `/api/events` por SSE. Isso evita dependencia extra para o primeiro corte e atende o monitor local.

## Regra de tamanho

Arquivos acima de 500 linhas devem ser quebrados antes de aceitar novas funcionalidades. A verificacao fica em `scripts/check-file-lines.ps1`.
