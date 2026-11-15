# Relatórios diários de chamados e exportação HTTP Novelis

Prévia de 14/11/2026. Nenhum instalador, executável nativo ou release foi compilado/publicado nesta etapa.

## Download do relatório do portal

O JavaScript real do portal (`/scripts/custom/relatorio_cte_xml.js`) configura o formulário para enviar um POST a `/custom/relatorio_cte_xml_excel`. O novo cliente utiliza esse mesmo endpoint, com autenticação da conta Novelis configurada no backend, cookies/CSRF e os campos `de`, `ate` e `tipo=date`.

O padrão `NOVELIS_RELATORIO_CTE_XML_TRANSPORT=http` não inicia navegador para essa exportação. `auto` permite o fluxo anterior no navegador quando o HTTP falhar; `browser` mantém explicitamente o fluxo anterior. Os demais passos da automação conservam suas próprias necessidades de navegador e certificado.

O cliente aceita somente HTTPS no host oficial, rejeita redirecionamentos de exportação/login para outro host e exige um XLSX com os cabeçalhos reconhecidos de CT-e antes de substituir o arquivo anterior. O download é gravado primeiro em arquivo temporário, com limite de 50 MB. Credenciais, cookies e conteúdo do login não são incluídos em logs.

**Teste real:** exportação HTTP 200 e leitura de **11.331 registros**, sem navegador e sem substituir os arquivos compartilhados existentes. Evidência local: `runtime/dev-preview/http-report-export.json`.

## Relatório diário de chamados

O fluxo completo e o fluxo de abertura de chamados registram o operador no início. Ao finalizar, suas aberturas confirmadas atualizam um único Excel por data, reunindo todos os operadores e computadores que usam o banco compartilhado. A data corresponde à confirmação da abertura em `America/Sao_Paulo`. Uma execução que atravessa a meia-noite pode atualizar dois dias.

- Só entram em **Chamados abertos** os eventos `novelis.save` com confirmação positiva e sem indicação de duplicidade. O evento recebe apenas os campos comerciais necessários, sem copiar a linha SQL inteira.
- A coleta de eventos usa o UUID exato da execução e não tem o limite de 1.000 eventos aplicado à visualização dos logs. A consolidação elimina repetições pelo número do chamado e preserva sua primeira confirmação. Quando registros antigos não possuem esse horário, usa a finalização da execução.
- As aberturas confirmadas antes de falha ou cancelamento também entram no dia correspondente. Consultas isoladas, simulações, tentativas e chamados apenas encontrados como existentes não aumentam esse total.
- O Excel inclui resumo diário, CT-e, número/link do chamado, rota, TON, ID tarifário, frete, total, conferência, operador, computador e execução de origem. Textos externos são células de texto.
- Os registros de relatório que ficaram em geração e já possuem execução terminal podem ser recuperados pelo publicador após reinício.

Os relatórios por execução já armazenados são consolidados automaticamente na nova lista. Os registros de origem e links UUID antigos continuam disponíveis para rastreabilidade. Dias sem aberturas confirmadas não geram uma linha vazia.

## Compartilhamento

Os registros de origem permanecem em `execution_reports`. O catálogo diário fica em `execution_daily_reports`, no SQLite operacional compartilhado já configurado. O cache consolidado fica em `logs/relatorios-execucoes/daily/AAAA-MM-DD.xlsx`, ao lado desse banco.

O arquivo também é enviado ao bucket `z3-releases`, prefixo privado:

`cargo-hub/reports/daily/AAAA/MM/DD/report.xlsx`

Novas aberturas atualizam o mesmo arquivo do dia. Uma trava por data coordena geração, envio e download entre processos e computadores. O catálogo é atualizado após a confirmação de integridade do objeto, evitando que publicações concorrentes sobrescrevam um resultado mais recente. O nome sugerido para download é `CargoHub-Chamados-AAAA-MM-DD.xlsx`.

A política lida no servidor durante a verificação permite leitura pública apenas de manifesto, feed de notificações e pacotes. O prefixo de relatórios não está nessa permissão. O publicador recusa o envio se detectar uma permissão anônima de GetObject para o objeto. Não foi alterada a política do bucket.

O backend usa uma URL assinada para atender ao download; essa URL não é enviada na API de listagem/detalhes. O Excel chega à interface como Blob autenticado pela sessão do operador e é salvo pela integração desktop. Leitores não precisam de credenciais de publicação. O conteúdo recebido é conferido por SHA-256; o cache de rede continua disponível durante indisponibilidade do MinIO.

As URLs assinadas têm validade de sete dias e o publicador renova as que estiverem a menos de um dia do vencimento. Um publicador ativo consulta pendências a cada minuto. Há também **Sincronizar pendentes** na nova tela. O envio ocorrido no final da execução não depende de esperar esse minuto.

## Perfil do publicador

Para implantação normal, configurar `EXECUTION_REPORT_S3_CREDENTIALS_FILE` no perfil privado do backend publicador. O JSON segue o formato local existente (`url`, `accessKey`, `secretKey` e `region` opcional); seus valores não devem entrar em código, logs, commits ou frontend.

O perfil deve permitir GetBucketPolicy no bucket e PutObject/GetObject somente em `cargo-hub/reports/*`, com acesso de leitura ao cache compartilhado. Pode haver um publicador central ou perfis restritos nos computadores autorizados. Os leitores usam o catálogo compartilhado e as URLs assinadas; não recebem esse arquivo de credenciais.

Na máquina de desenvolvimento, o mecanismo também utiliza o perfil já existente quando `CONFIG.dev` e `credentials.json` habilitam o modo DEV. Essa alternativa não instala nem distribui essas credenciais para os operadores. Enquanto não houver publicador ativo/autorizado, o relatório permanece **Envio pendente**, com Excel disponível pelo cache compartilhado.

## Tela e API

- Página **Relatórios diários**, no menu Operação.
- Lista paginada por data, quantidade de aberturas, operadores, execuções de origem e atualização.
- Painel lateral com os chamados novos e link direto ao portal; download Excel na lista e no painel.
- `GET /api/hub/execution-reports`, `GET /api/hub/execution-reports/<UUID>` e `GET /api/hub/execution-reports/<UUID>/file` exigem sessão de operador.
- `POST /api/hub/execution-reports/sync` solicita nova tentativa de envio das pendências.

## Evidências e limites

### Consolidação diária de 14/11/2026

O catálogo existente foi consolidado em um relatório de 14/11/2026 com 22 aberturas confirmadas, provenientes de seis execuções. O Excel foi enviado ao MinIO e lido novamente. A contagem de linhas foi 22 e o SHA-256 remoto correspondeu ao catálogo. A evidência local está em `runtime/dev-preview/daily-reports-real-validation.json`.

Os testes direcionados incluem vários operadores, cancelamento/falha com resultados parciais, deduplicação, virada de dia em Brasília, atualização do mesmo objeto no MinIO, publicação concorrente entre dois backends, autenticação e nome do arquivo por data. As evidências anteriores abaixo correspondem à implementação inicial por execução.

Arquivos locais em `runtime/dev-preview/`:

- `report-endpoint-inspection.json`: formulário/endpoint e política observados, sem credenciais.
- `http-report-export.json`: exportação real do portal e quantidade de registros lidos.
- `report-minio-roundtrip.json`: upload real de planilha **vazia e identificada como validação**, download por leitor sem credenciais de publicação, SHA-256 igual e HTTP 403 para acesso anônimo. O catálogo de teste é isolado do operacional; nenhuma execução de negócio foi simulada na lista compartilhada.
- `backend-execution-reports-tests.log`: regressão geral — 484 aprovados e 4 ignorados antes dos últimos casos adicionais de regressão.
- `execution-reports-focused-tests.log`: casos finais direcionados de exportação, confirmação, parcial, privacidade, operador e recuperação de falha S3.
- `execution-reports-final-tests.log`: 26 casos direcionados aprovados, incluindo a preparação real do fluxo e a regressão da variável `numero_cte`.
- `frontend-execution-reports-tests.log`: 52 testes aprovados.
- `execution-reports-typecheck.log`: TypeScript sem emissão de build.
- `execution-reports-ui.json`: API local e revisão de interface. Exemplos visuais, quando usados, ficam apenas no navegador de teste e são identificados como exemplos.

O agente não iniciou execução fiscal nem fez teste em outro computador. Durante a revisão, o usuário iniciou a execução `61f1de39-377a-41c5-b7a4-4920351dee7e`: ela terminou com falha antes das confirmações de chamado, por uma referência indefinida a `numero_cte` na preparação do overlay. A referência foi corrigida e coberta por regressão.

O relatório dessa execução foi gerado com **zero aberturas confirmadas**, situação **Falhou**, enviado de verdade ao MinIO e baixado pela API autenticada com contagem Excel igual à do catálogo. Evidência: `actual-execution-report.json`. Contadores de progresso e tentativas não foram reinterpretados como chamados abertos.

A geração com aberturas confirmadas foi exercitada com coordenador de teste; ainda falta observar o término bem-sucedido de uma execução real após a correção e provisionar o perfil restrito do publicador para a implantação nos operadores. O perfil DEV atual comprova o envio nesta máquina, sem distribuir credenciais aos demais computadores.

## Painel de chamados do dia — revisão de 15/11/2026

O painel lateral tem cabeçalho fixo com data, contagem de chamados/execuções e download do Excel. Somente a lista rola. Horários ficam à esquerda; CT-e, número do chamado, rota, valor, tonelagem, tarifa, operador e computador são apresentados em linhas alinhadas. O número do chamado mantém o acesso ao portal pelo serviço nativo existente.

A busca local aceita CT-e, chamado, origem/destino, operador, computador e tarifa, ignorando acentos. A ordem inicial é de mais recentes para mais antigos, com opção inversa. O rodapé informa a quantidade visível e a última atualização. Filtrar a visualização não limita o Excel: o download permanece sendo o relatório completo da data.

Quatro testes direcionados aprovados, TypeScript e ESLint aprovados. A conferência visual usou **dados controlados de 23 chamados**, nos temas claro e escuro e nas larguras 1440, 1024, 695 e 390 px. Cabeçalho/download permaneceram visíveis ao rolar; não houve transbordamento horizontal do painel nem erros JavaScript. Não foram consultados/exportados documentos fiscais nem publicados objetos no MinIO nesta revisão de interface.

Componentes: `FRONTEND-HUB/src/components/app/reports/`. Evidências locais: `runtime/dev-preview/daily-report-design-validation.json`, `daily-report-light.png`, `daily-report-dark.png` e `daily-report-mobile.png`. Mudanças disponíveis na prévia; nenhum instalador foi gerado.
