# Novelis Cargo Hub

Crie o frontend de um aplicativo chamado **Automação Novelis**, utilizado pela operação de uma transportadora para controlar CT-es, organizar os documentos necessários e acompanhar a abertura e o andamento de chamados no portal Novelis.

O produto será usado em computadores Windows e posteriormente empacotado com Tauri. O backend já existe em Python/FastAPI, com automações Playwright, consulta SQL e geração de DACTE pelo Crystal Reports. A entrega desta etapa é a interface React com TypeScript, preparada para integrar os serviços existentes.

### Objetivo operacional
O operador precisa identificar quais CT-es estão pendentes, entender o que falta em cada um e executar o processamento com acompanhamento claro. A interface deve reduzir a conferência manual entre planilhas, arquivos PDF/XML, pastas de rede e relatórios de chamados.

CT-e é o Conhecimento de Transporte Eletrônico. DACTE é sua representação auxiliar em PDF. Na operação, cada item é identificado por filial, série e número, por exemplo `2-10-10001`. A chave de acesso de 44 dígitos é um dado separado.

O fluxo principal:
1. Consulta os dados e atualiza a lista de pendências.
2. Cruza documentos existentes e o histórico de processamento.
3. Gera os PDFs de DACTE faltantes usando o banco de dados e o relatório Crystal.
4. Busca os XMLs pela automação da SEFAZ.
5. Localiza guias e comprovantes nas pastas configuradas.
6. Reavalia quais CT-es estão prontos para a etapa de chamados.
7. Executa os chamados Novelis conforme as regras configuradas.
8. Atualiza os resultados e apresenta eventuais pendências ou falhas.

Os PDFs de um lote são gerados em sequência: um CT-e por vez. O estágio PDF e o estágio XML podem trabalhar simultaneamente. Essa diferença deve ficar clara na visualização de progresso.

### Estrutura visual
Organize a interface em menu lateral recolhível, cabeçalho com a página atual e área principal de trabalho. Use visual corporativo limpo, boa legibilidade, espaçamento consistente, tabelas com cabeçalho fixo e ícones acompanhados de texto.

Priorize o uso em desktop, incluindo resoluções 1366×768 e 1920×1080. Em janelas menores, permita rolagem das tabelas e reorganização dos painéis.

Use cores de estado consistentes: verde para sucesso, amarelo para pendência, vermelho para erro e azul para execução. Apresente indicadores de conexão com o backend e de atualização dos dados. Datas devem usar o padrão brasileiro e valores monetários, reais. A interface inteira deve estar em português do Brasil.

### Telas do sistema:
1. **Visão geral**: Indicadores de CT-es na fila, PDFs faltantes, XMLs faltantes, comprovantes faltantes, itens prontos para chamado e situação da execução atual. Data da última atualização e acesso rápido à consulta e execução.
2. **Execução e lotes**: Seleção do fluxo, botão Iniciar, botão Parar, acompanhamento da execução atual (etapa, CT-e atual, processados vs total do lote). Entrada manual de CT-es (um por linha) ou importação (.xlsx, .xlsm, .csv) com validação e detecção de duplicados. Consulta automática com período em dias. Etapas visuais: Consulta, PDF, XML, Comprovantes, Chamados (com progresso separado para PDF e XML quando simultâneos). Estados: Aguardando, Executando, Parando, Concluída, Falhou, Cancelada. Bloqueio de envio duplicado.
3. **CT-es pendentes**: Tabela pesquisável com CT-e (filial-série-número), situação do PDF, XML, guia/comprovante e prontidão para chamado (status: Disponível, Faltando, Não exige). Filtros por tipo de pendência, painel lateral de detalhes e exportação para Excel (todos ou apenas faltantes).
4. **Documentos e geração de DACTE**: Acompanhamento de geração e visualizador de PDFs/DACTE. Documentos encontrados, etapas e erros. Conferência técnica de QR Code e código de barras. Opções claras: geração via banco/Crystal ou via XML arquivado.
5. **Chamados Novelis**: Tabela com CT-e, data, valor total, abertura Novelis, ID tarifário, chamado, JDA, andamento, responsável, origem e destino. Indicadores de fila, solucionados e pendentes.
6. **Monitor da automação**: Área de acompanhamento da automação web / navegador (ou andamento da etapa quando sem navegador), com painel de eventos e logs em tempo real (horário, severidade, mensagem, detalhes técnicos pesquisáveis/filtráveis).
7. **Configurações e diagnóstico**: Agrupamento por banco de dados, documentos, automações e caminhos de arquivos. Indicadores de saúde e diagnóstico das dependências locais. Proteção de campos sensíveis.
8. **Área avançada de automação**: Passos da automação, pontos de interação, abas, ações, timeouts, capturas. Área de compatibilidade desativada para fluxos antigos Rodopar.

### Integração e Modo Demonstração:
- Camada de serviços TypeScript modularizada com URL base configurável (`http://127.0.0.1:8000/api`).
- Adaptador de demonstração (mock data) realista e completo que permite testar toda a interface de imediato, com alternador/indicador claro entre modo Demonstração e Backend Local.
- Preparado para Tauri com interfaces isoladas para recursos desktop.

This project was built with [Lovable](https://lovable.dev).

## Build with Lovable

Continue developing this project in the [Lovable editor](https://lovable.dev/projects/7c130ec7-7f90-491c-a9a8-0c591a54f7a8).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```
