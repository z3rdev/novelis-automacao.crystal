# Sessão Novelis, identificação de consultas e parada na visão geral

Prévia de 14/11/2026. Sem compilação de instalador, release ou executável nativo.

## Abertura de chamados

O fluxo completo e a opção Somente chamados Novelis abrem os chamados por HTTP autenticado. Cada lote reaproveita uma sessão para preencher o formulário, enviar PDF/XML/ZIP e conferir o chamado gravado.

- O plano conserva os dados SQL, a conferência tarifária e as evidências já encontradas.
- Os CT-es conferidos pelo relatório inicial usam essa conferência durante a abertura.
- As consultas adicionais ao relatório são agrupadas por data de emissão e usam o mesmo cliente HTTP.
- A reserva de envio no SQLite compartilhado coordena tentativas simultâneas. Resultados pendentes de confirmação são reconferidos pelo portal.
- A confirmação verifica o número, o CT-e e os links dos anexos. O reconhecimento aceita os nomes renomeados pelo portal.
- Cancelar preserva as aberturas já confirmadas no relatório da execução. Cancelar antes do envio libera a reserva.
- Os eventos `novelis.save` e `novelis.chamado_exists` alimentam o relatório Excel e o catálogo de comunicação.

As evidências de cada item ficam em `runtime/novelis-http/<execução>/<CT-e>/result.json`. O aplicativo usa automaticamente esse mecanismo na etapa de chamados.

## Por que ainda há consultas com documentos disponíveis

PDF, XML e comprovante disponíveis eliminam a necessidade de gerar/baixar esses documentos novamente. Eles não comprovam que o chamado ainda precisa ser aberto.

O fluxo distingue:

| Origem exibida | Operação |
| --- | --- |
| SQL Server | Busca inicial dos CT-es do período ou complementação das chaves da entrada manual |
| Relatório Novelis | Conferência de chamados já existentes; pode reutilizar o Excel/cache válido ou baixar o relatório |
| Arquivos | Verificação de PDF, XML e comprovantes nas pastas, usando a fonte de dados já lida |

A consulta carrega as linhas SQL, aplica o filtro Novelis e só então verifica os arquivos dos CT-es restantes. A conferência de chamados existentes usa consultas indexadas no PostgreSQL. A importação integral do histórico fica fora dessa etapa.

A verificação dos arquivos é reaproveitada quando PDF, XML e comprovante já estão disponíveis. A geração de documentos e a localização de comprovantes pendentes levam a uma nova conferência dos arquivos alterados. O relatório final filtra os CT-es já abertos e conserva as evidências verificadas. O cache diário do relatório considera o dia local do operador, inclusive após a mudança de dia em UTC.

As mensagens agora identificam a origem antes da espera. A etapa atual e o cartão Consulta mostram a origem, e as categorias do monitor distinguem SQL Server, Relatório Novelis e Arquivos. A conferência final do relatório não é apresentada como um novo download quando apenas os dados disponíveis foram conferidos.

## Visão geral

O botão **Consultar agora** troca para **Parar automação** durante uma execução, inclusive quando iniciada em outra tela. O período fica desabilitado enquanto a automação está ativa.

Ao parar, a interface mostra **Parando…**, desabilita novos cliques e usa a mesma parada cooperativa do backend. Ao concluir o encerramento, volta a disponibilizar **Consultar agora**. O botão não inicia uma segunda consulta quando o operador está tentando parar.

## Verificações

- Testes de sessão cobrem reutilização, login inicial único, sessão expirada, autenticação recusada e recusa de acesso.
- Um navegador Playwright real contra servidor local de teste abriu cinco páginas protegidas com **um login**. A remoção dos cookies exigiu um segundo login. Não houve contato com o portal real ou salvamento de chamado nesse teste.
- A página React real foi exercitada com respostas de execução interceptadas: as três origens ficaram visíveis; o clique gerou uma solicitação de parada, nenhuma consulta adicional, mostrou Parando desabilitado e restaurou Consultar agora ao cancelar. Nenhuma execução real do usuário foi parada pelo teste.
- A suíte de cancelamento do backend foi mantida para verificar o encerramento das tarefas em andamento.

Evidências locais em `runtime/dev-preview/`: `session-consultation-tests.log`, `session-navigation.json`, `session-overview-tests.log`, `session-overview-typecheck.log`, `overview-stop-ui.json`, `backend-session-overview-tests.log` e `frontend-session-overview-tests.log`.

A regressão geral terminou com **500 testes backend aprovados e 4 ignorados**, além de **57 testes frontend aprovados**. A validação TypeScript e a análise dos novos módulos também passaram. Foi preservada a distinção entre concluir a leitura SQL e concluir toda a consulta: cancelar depois da leitura SQL continua apresentando a consulta interrompida como cancelada.

A abertura HTTP individual do CT-e 2-10-17445 foi confirmada no portal com o chamado 20261114583565 e os três anexos. Os testes automatizados em lote verificam a entrada normal do fluxo completo, um login para vários chamados, falhas parciais e cancelamento. A execução real de um novo lote completo está disponível na prévia.
