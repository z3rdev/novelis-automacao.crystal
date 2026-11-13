# Briefing para o novo frontend — Automação Novelis

## Texto para usar no Lovable

Crie o frontend de um aplicativo chamado **Automação Novelis**, utilizado pela
operação de uma transportadora para controlar CT-es, organizar os documentos
necessários e acompanhar a abertura e o andamento de chamados no portal Novelis.

O produto será usado em computadores Windows e posteriormente empacotado com
Tauri. O backend já existe em Python/FastAPI, com automações Playwright, consulta
SQL e geração de DACTE pelo Crystal Reports. A entrega desta etapa é a interface
React com TypeScript, preparada para integrar os serviços existentes.

### Objetivo operacional

O operador precisa identificar quais CT-es estão pendentes, entender o que falta
em cada um e executar o processamento com acompanhamento claro. A interface deve
reduzir a conferência manual entre planilhas, arquivos PDF/XML, pastas de rede e
relatórios de chamados.

CT-e é o Conhecimento de Transporte Eletrônico. DACTE é sua representação auxiliar
em PDF. Na operação, cada item é identificado por filial, série e número, por
exemplo `2-10-10001`. A chave de acesso de 44 dígitos é um dado separado.

O fluxo principal:

1. Consulta os dados e atualiza a lista de pendências.
2. Cruza documentos existentes e o histórico de processamento.
3. Gera os PDFs de DACTE faltantes usando o banco de dados e o relatório Crystal.
4. Busca os XMLs pela automação da SEFAZ.
5. Localiza guias e comprovantes nas pastas configuradas.
6. Reavalia quais CT-es estão prontos para a etapa de chamados.
7. Executa os chamados Novelis conforme as regras configuradas.
8. Atualiza os resultados e apresenta eventuais pendências ou falhas.

Os PDFs de um lote são gerados em sequência: um CT-e por vez. O estágio PDF e o
estágio XML podem trabalhar simultaneamente. Essa diferença deve ficar clara na
visualização de progresso.

### Estrutura visual

Organize a interface em menu lateral recolhível, cabeçalho com a página atual e
área principal de trabalho. Use visual corporativo limpo, boa legibilidade,
espaçamento consistente, tabelas com cabeçalho fixo e ícones acompanhados de texto.

Priorize o uso em desktop, incluindo resoluções 1366×768 e 1920×1080. Em janelas
menores, permita rolagem das tabelas e reorganização dos painéis.

Use cores de estado consistentes: verde para sucesso, amarelo para pendência,
vermelho para erro e azul para execução. Apresente indicadores de conexão com o
backend e de atualização dos dados. Datas devem usar o padrão brasileiro e valores
monetários, reais. A interface inteira deve estar em português do Brasil.

As telas abaixo reorganizam funcionalidades existentes e propõem visualizações
para o novo frontend. A disponibilidade de cada ação deve respeitar os contratos
reais do backend.

### 1. Visão geral

Apresente indicadores de CT-es na fila, PDFs faltantes, XMLs faltantes, comprovantes
faltantes, itens prontos para chamado e situação da execução atual. Mostre a data
da última atualização e um acesso rápido à consulta e à execução.

Os números devem vir dos dados disponíveis. Estatísticas que ainda não tenham
fonte devem aparecer apenas no modo de demonstração, identificadas como exemplo.

### 2. Execução e lotes

Ofereça seleção do fluxo, botão Iniciar, botão Parar e acompanhamento da execução
atual. Mostre etapa, CT-e atual, quantidade processada e total do lote.

Permita informar CT-es por uma lista, um por linha, ou importar planilhas `.xlsx`,
`.xlsm` e `.csv`. Apresente uma prévia da entrada com quantidade de itens e
indicação de entradas inválidas ou repetidas.

Diferencie claramente a seleção de um único CT-e e uma lista completa. Um campo
de teste individual não deve filtrar silenciosamente os outros itens de um lote.

Na consulta automática, permita informar o período em dias, respeitando os limites
aceitos pelo backend. Na entrada manual, o período não deve aparecer como uma
etapa obrigatória, pois os CT-es são informados diretamente.

Represente visualmente as etapas Consulta, PDF, XML, Comprovantes e Chamados.
Quando PDF e XML estiverem em execução simultânea, exiba seus progressos separados.

Apresente os estados Aguardando, Executando, Parando, Concluída, Falhou e Cancelada.
O resultado de uma operação deve acompanhar a resposta do backend. Impeça envios
duplicados do botão Iniciar enquanto houver uma execução ativa.

### 3. CT-es pendentes

Crie uma tabela pesquisável com CT-e, filial, série, número, situação do PDF,
situação do XML, guia/comprovante e prontidão para chamado.

Use indicadores explícitos como Disponível, Faltando e Não exige. Permita filtrar
as pendências por tipo e consultar os detalhes de um CT-e em um painel lateral.
Disponibilize a exportação para Excel, com opção de todos os itens ou apenas
faltantes, conforme a API existente.

### 4. Documentos e geração de DACTE

Crie uma área para acompanhar a geração dos documentos e visualizar PDFs. Para um
CT-e, mostre os documentos encontrados, as etapas concluídas e os erros relevantes.

A geração de DACTE usa os dados do banco diretamente no backend. O QR Code e o
código de barras são conferidos após a geração do PDF. Apresente essa conferência
como verificação técnica dos códigos, distinta de homologação fiscal.

O caminho principal gera PDF sem depender do XML. Existe também uma alternativa
explícita de geração a partir de XML arquivado, com outro renderizador/layout.
Essas opções devem ser identificadas de forma clara quando disponibilizadas.

Um teste de geração de PDFs e uma execução completa com chamados são operações
diferentes. Deixe o alcance da ação compreensível antes de iniciá-la. No protótipo,
ações ainda sem contrato de API devem ser identificadas como demonstração.

### 5. Chamados Novelis

Mostre os chamados obtidos dos relatórios e dados existentes. A tabela deve
permitir pesquisar CT-e, chamado, responsável, origem e destino.

Preveja as colunas CT-e, data, valor total, abertura Novelis, ID tarifário, chamado,
JDA, andamento, responsável, origem e destino. Apresente indicadores de fila,
solucionados e pendentes a partir da resposta da API.

O histórico de processamento deve ser respeitado pelo fluxo para reduzir
duplicidade de chamados. Exiba claramente quando os dados são de uma consulta ou
relatório e quando correspondem a um resultado de processamento.

### 6. Monitor da automação

Reserve uma área para acompanhar o navegador quando a etapa utilizar automação
web. A integração real poderá usar os recursos de captura/controle existentes ou
a ponte desktop prevista para o Tauri.

Quando a operação atual não precisar de navegador, mostre o andamento da etapa e
os documentos gerados. Uma geração de PDF pelo banco deve ter uma visualização
útil mesmo sem uma página web aberta.

Inclua um painel de eventos em tempo real, com horário, severidade, mensagem e
detalhes técnicos expansíveis. Permita pesquisar e filtrar os eventos.

### 7. Configurações e diagnóstico

Agrupe configurações por banco de dados, documentos, automações e caminhos de
arquivos. Apresente o estado da configuração e das dependências locais, com
mensagens compreensíveis e detalhes técnicos em área avançada.

Campos sensíveis devem ser protegidos. Credenciais reais permanecem sob controle
do backend local; não devem ser gravadas no código do frontend, em dados de
demonstração ou no armazenamento comum do navegador.

A API atual permite consultar a configuração. Formulários de gravação, agenda e
funções nativas adicionais exigem seus respectivos contratos de integração; não
devem simular persistência real quando estiverem apenas no protótipo.

### 8. Área avançada de automação

Preveja uma área separada para passos, pontos de interação, abas, ações, tempos de
espera e capturas usados na manutenção da automação.

Os fluxos e controles antigos do Rodopar foram preservados no projeto e estão
desabilitados. Devem permanecer em uma área de compatibilidade desativada. Falhas
na geração de documentos não podem ativar o Rodopar automaticamente.

### Integração com o backend existente

Use uma camada de serviços TypeScript, com URL base configurável. A API local
atual usa `http://127.0.0.1:8000/api`. Separe os contratos de dados, chamadas HTTP,
eventos e recursos nativos da apresentação visual.

Contratos existentes que devem orientar a integração:

| Finalidade | Rota |
|---|---|
| Estado do backend | `GET /api/health` |
| Fluxos disponíveis | `GET /api/flows` |
| Execução atual | `GET /api/runs/current` |
| Iniciar execução | `POST /api/runs/start` |
| Solicitar parada | `POST /api/runs/stop` |
| Eventos ao vivo | `GET /api/events`, via Server-Sent Events |
| Plano de pendências | `GET /api/pendentes/plan` |
| Exportar pendências | `GET /api/pendentes/plan/export.xlsx?scope=todos` ou `faltantes` |
| Consultar chamados | `GET /api/chamados` |
| Gerar um DACTE pelo Crystal | `POST /api/reports/dacte/pdf` |
| Gerar pela alternativa XML | `POST /api/reports/dacte/pdf-from-xml` |
| Diagnóstico DACTE | `GET /api/reports/dacte/diagnostics` |
| Consultar configurações | `GET /api/config` e `GET /api/config/env` |
| Consultar passos | `GET /api/steps` |
| Editar um passo | `PATCH /api/steps/{number}` |

A geração isolada de um DACTE recebe filial, série e documento. O fluxo principal
recebe o identificador do fluxo e pode receber uma lista no campo `manual_ctes`,
além da planilha de entrada manual. Preserve os nomes e tipos reais dos contratos.

O fluxo principal e a geração isolada de PDF têm efeitos diferentes; cada tela
deve chamar a operação correspondente à ação apresentada ao operador.

### Protótipo e futura embalagem Tauri

Crie um adaptador de demonstração com dados fictícios para permitir revisar as
telas sem acesso ao ambiente local. Esse modo deve ser identificado. Quando o
backend real estiver desconectado, mostre o estado de desconexão e preserve a
distinção entre resultados reais e exemplos.

A arquitetura deve permitir substituir o adaptador de demonstração pelo adaptador
HTTP local. O frontend continua responsável pela interface; SQL, geração Crystal,
Playwright e acesso operacional a arquivos são executados pelos serviços locais.

Prepare interfaces para os recursos desktop que serão conectados posteriormente:
seleção de arquivos/pastas, abertura de documentos, ações da janela e comunicação
com o serviço local. Mantenha essas funções em um adaptador próprio para Tauri.

O projeto já contém uma estrutura inicial de Tauri, mas o ciclo completo de
inicialização do backend, permissões e empacotamento deve ser tratado na etapa de
integração desktop.

### Critérios de entrega do frontend

- Navegação funcional e componentes React/TypeScript reutilizáveis.
- Organização por funcionalidade e módulos com menos de 500 linhas.
- Estados de carregamento, lista vazia, erro, execução e desconexão.
- Entrada de lista com prévia e identificação de itens inválidos/repetidos.
- Acompanhamento do lote e detalhes por CT-e.
- Visualização das pendências, documentos e chamados.
- Identificação do alcance de cada ação e bloqueio de disparos duplicados.
- Integrações reais separadas dos dados de demonstração.
- Comportamento desktop consistente e preparado para a futura integração Tauri.

O objetivo final é uma central operacional em que o usuário consiga consultar os
CT-es, identificar o que falta, executar o lote e acompanhar o resultado de cada
documento e chamado com clareza.
