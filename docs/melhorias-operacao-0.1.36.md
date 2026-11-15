# Cargo Hub 0.1.36 — operação, comunicação e instalação

Implementação de 14/11/2026. O pacote 0.1.35 foi preservado. Esta entrega é privada, para validação interna, e não foi publicada no MinIO nem homologada como instalação limpa.

## Alterações de operação

| Recurso | Comportamento |
| --- | --- |
| Mensagens dos chamados | Nova tela para título, assinatura, texto normal e complementar, com prévia fictícia. Variáveis restritas; não executa expressões. |
| Ausência de comprovante | Permissão explícita na mesma tela, desativada por padrão. PDF e XML permanecem obrigatórios. A regra é registrada nas preferências e aplicada nas próximas execuções. |
| Notificações | Avisos novos abrem o modal, inclusive depois de fechar um aviso anterior. Consulta periódica habilitada em segundo plano. Publicar ou fechar não equivale a ler. Leitura individual, leitura de todas e horário da confirmação. |
| Agendamentos | Consulta, PDF, XML, comprovantes, atualização do relatório de chamados ou fluxo completo. A atualização do relatório lê o histórico Novelis; não abre chamados. |
| Período personalizado | Disponível na visão geral, pendentes e execução. Início/fim inclusivos, entre hoje e 30 dias atrás. Validação na interface e no backend. |
| Limpeza semanal | Remove apenas PDF/XML de cópias locais geradas pelo aplicativo antes da segunda-feira, 00:00, da semana atual. Não remove arquivos compartilhados, unidades de rede mapeadas, links ou arquivos de outros tipos. Só executa quando a automação está ociosa. |
| Layout | Menu com largura reservada, conteúdo isolado e cabeçalhos de tabela contidos na área de rolagem. |
| Ajuda integrada | Nova tela “Ajuda e primeiros passos”, com navegação por etapas e exemplo interativo dos requisitos de documentos. Não executa trabalhos reais. |

Variáveis de mensagem: `{cte}`, `{percurso}`, `{ton}`, `{id}`, `{idTarifario}`, `{rota}`, `{cteOrigem}`, `{chamadoOrigem}` e `{assinatura}`. O portal continua responsável pelas próprias exigências de anexos e validações.

O agendamento requer computador ligado, rede disponível e Cargo Hub aberto, inclusive na bandeja. Não executa com a aplicação totalmente encerrada.

## Chamados centralizados em PostgreSQL

O histórico da tela deixou de depender da releitura e transferência integral de JSON a cada quatro segundos. O backend importa alterações das fontes existentes para:

- `public.cargo_hub_chamados`: dados originais e projeção para a interface, com índices por CT-e, chave, andamento e ordenação.
- `public.cargo_hub_chamados_sources`: identificação das fontes já importadas.

A conta fornecida tem criação/uso no schema `public`, sem privilégio de criar schemas. Nenhum objeto de terceiros foi alterado. A importação usa `COPY` e atualização transacional, conserva os arquivos de origem e não apaga o histórico quando uma fonte fica indisponível. A sincronização verifica alterações a cada 30 segundos. A interface solicita até 100 registros por página, com busca e filtros no servidor.

O leitor usado para evitar chamados repetidos consulta o catálogo central quando ele está configurado. Novos chamados confirmados são registrados nesse banco. Os registros de execução, sessões, agendamentos e preferências continuam no armazenamento operacional existente; essa entrega migra o catálogo de chamados.

O marcador legado `aberturaNovelis=SOLUCIONADO` significava que já havia chamado. Ele não substitui mais o andamento real. “Pendente” entra em pendentes/em análise; “Solucionado” e “Encerrado” entram no grupo concluído. A data de abertura usa `abertoEm` do relatório, quando disponível.

### Perfil privado

Configuração somente no `BACKEND/.env` privado, sem valores de acesso no código ou na interface:

```dotenv
CHAMADOS_PG_HOST=
CHAMADOS_PG_PORT=5432
CHAMADOS_PG_DATABASE=
CHAMADOS_PG_USER=
CHAMADOS_PG_PASS=
CHAMADOS_PG_SSLMODE=require
CHAMADOS_PG_SSLROOTCERT=
LOCAL_DOCUMENT_RETENTION_ENABLED=true
```

O perfil local usa `sslmode=disable` por determinação expressa do responsável em 14/11/2026. A conexão real foi validada assim; não há criptografia de transporte nesse modo. Não existe troca automática de TLS para conexão aberta. Para ativar verificação de identidade, fornecer hostname/CA e configurar `verify-full`, conforme a [documentação PostgreSQL](https://www.postgresql.org/docs/current/libpq-ssl.html).

Os valores reais foram gravados somente no `.env` ignorado pelo Git. O instalador privado contém o perfil operacional e deve permanecer restrito. Os padrões destinados a distribuição sem perfil privado não contêm essas credenciais.

### Resultados reais no servidor indicado

- 11.071 chamados importados.
- 264 pendentes/em análise e 10.807 solucionados ou encerrados no momento da conferência.
- Duas páginas de 100 registros sem repetição.
- Busca por CT-e, filtro de pendentes, busca com caracteres especiais e ajuste da última página conferidos.
- Primeira página medida em aproximadamente 2,8 segundos neste ambiente.
- Nenhum chamado novo foi aberto no portal para realizar esses testes.

As consultas SQL Server de CT-e continuam usando `CONSULTA_DB_*`; o PostgreSQL é o banco de comunicação, não substitui o Rodopar. O driver ODBC legado rejeitou parâmetros Python `date` com `HYC00`. As datas agora são parâmetros texto `yyyyMMdd`, convertidos com `CONVERT(date, ?, 112)`. A consulta real de um dia retornou 11 CT-es, todos dentro dos limites. Referência: [Microsoft — CAST e CONVERT](https://learn.microsoft.com/en-us/sql/t-sql/functions/cast-and-convert-transact-sql?view=sql-server-ver16).

## Instalador

- Painel de marca, logotipo, cabeçalho azul-marinho, detalhes verde-água e crédito Z3ro.dev.
- Recursos de imagem gerados por `scripts/build-installer-branding.py`; tema nativo em `installer/branding/Theme.iss`.
- Atualização encerra processos identificados pelo caminho da instalação e seus descendentes, incluindo Python, workers e navegador pertencentes ao Cargo Hub. Não seleciona processos apenas por nome ou pela porta 8000.
- O script exige o marcador `.automacao-novelis-install`, protege o próprio instalador e confere a data de criação antes de terminar um PID. Tarefa agendada só é interrompida quando sua ação pertence à instalação.
- Se os processos não puderem ser encerrados, a atualização é interrompida antes da substituição dos arquivos.
- Mantidos Inno Setup, Python local, wheelhouse offline, WebView2, Crystal RDC x86 1.0.2 e preservação de configurações. O driver PostgreSQL integra as dependências e a verificação de importação do bootstrap.

O MSI Crystal e a aprovação interna anterior permanecem os mesmos. A aprovação documentada é uma declaração do responsável; não representa verificação independente de contratos ou procedência pelo agente. Nada foi publicado externamente.

## Arquivos principais

| Área | Arquivos |
| --- | --- |
| Mensagens e permissão | `BACKEND/app/services/chamado_message.py`, `message_configuration.py`, `BACKEND/app/api/routers/message_configuration.py`, `FRONTEND-HUB/src/routes/mensagens.tsx` |
| Catálogo central | `BACKEND/app/infrastructure/chamados_postgres.py`, `BACKEND/app/services/chamados_catalog.py`, leitores, serviço e rotas Hub; `FRONTEND-HUB/src/routes/chamados.tsx` |
| Períodos e rotinas | `BACKEND/app/domain/consultation_period.py`, modelos, consulta SQL, fluxo pendentes, agendador e formulário; `FRONTEND-HUB/src/services/consultation.ts` e `components/app/consultation-period.tsx` |
| Notificações | `BACKEND/app/services/notifications.py`, `FRONTEND-HUB/src/components/app/notification-provider.tsx` e `notification-dialog.tsx` |
| Retenção | `BACKEND/app/services/local_document_retention.py`, ciclo de vida e configuração Hub |
| Ajuda e layout | `FRONTEND-HUB/src/routes/ajuda.tsx`, menu, página, raiz e CSS do menu |
| Instalação | `scripts/setup/stop-installed-stack.ps1`, `installer/AutomacaoNovelis.iss`, tema, gerador e scripts de build/bootstrap |

## Validação e homologação

Resultado final: **394 testes de backend aprovados, 4 ignorados; 36 testes de frontend aprovados**. Os quatro testes ignorados requerem instalações/fixtures específicas. TypeScript, verificações estáticas e compilação nativa passaram.

O bootstrap offline também passou em um layout isolado, usando os insumos efetivamente preparados para o instalador: Python local, API 0.1.36 e importação de `psycopg` 3.3.9. A primeira montagem desse ensaio omitia a interface compilada e foi rejeitada corretamente; a interface foi copiada antes da repetição bem-sucedida. O ensaio não executou o setup, não instalou Crystal e não usou credenciais operacionais.

Evidências locais em `runtime/ui-review/`:

- `communication-postgres-validation.json` e `communication-postgres-source-status.json`: consultas reais, sem credenciais ou linhas dos documentos.
- `consultation-custom-sql-validation.json`: teste SQL Server real, somente leitura.
- Relatórios JUnit do backend e JSON do frontend.
- `improvements-ui/results.json`: cinco telas em 1280 px, chamados em 900/390 px e exercício interativo. Sem transbordamento horizontal da página; o conteúdo começa depois do menu. As capturas de layout usam dados fictícios identificados como demonstração.
- `improvements-installer-build.log`: compilação. A prévia do tema também compilou no Inno 6.7.3 e 7.0.2; nenhuma instalação foi iniciada nessa inspeção visual.

Antes de produção, homologar instalação limpa e atualização de uma cópia instalada, com a conta real do operador, tray/backend ativos, confirmação de notificações, cada tipo de agendamento, geração fiscal real e limpeza semanal. Os testes de exclusão e seleção de processos usam pastas/inventário de teste; nenhum arquivo operacional foi apagado e nenhum processo real de terceiros foi encerrado para testá-los. Não houve homologação em VM ou PC limpo pelo agente.

O pacote privado de validação é `runtime/private-installer/NovelisCargoHubSetup-0.1.36-r1-PRIVADO.exe`. O manifesto ao lado contém hash, entradas e limitações verificadas. Publicação e produção continuam separadas da compilação técnica.

- Tamanho: 682.620.013 bytes (aproximadamente 651 MiB).
- SHA-256: `a067398631417dbd6d90e913bc9c8f3f47b019015c792272d25eb3c57c6f18b9`.
- Hashes do backend, scripts, frontend e executável Tauri conferem com o manifesto.
- Contém wheels PostgreSQL e perfil privado; nenhum valor de credencial consta no manifesto. Chave Crystal ausente do log e do manifesto, inclusive sem hífens.
- Sem assinatura Authenticode. `production_ready=false`; homologação em máquina limpa e atualização de uma instalação real continuam pendentes.
