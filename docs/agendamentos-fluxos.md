# Fluxos visuais dos agendamentos

Em **Agendamentos → Novo agendamento → Fluxo personalizado → Criar fluxo personalizado**, o operador monta uma sequência conectada de etapas. **Usar no agendamento** aplica o desenho ao formulário. **Salvar** grava o horário, os dias, o fluxo e suas configurações no banco compartilhado.

A listagem mostra horário, rotina, próxima execução, último resultado e ativação. O botão de reprodução inicia a rotina manualmente. No menu de três pontos ficam **Editar**, **Duplicar**, **Ver histórico de execuções** e **Excluir**. Duplicar abre um rascunho pausado para revisão e só cria outra rotina depois de salvar. O histórico lateral consulta as tentativas persistidas, com paginação e acesso restrito à conta Windows e ao computador da rotina. **Ver o que aconteceu** abre esse histórico quando há falha.

Criar e editar usam uma página própria, com o título e o formulário centralizados na mesma coluna. **Quando** reúne início, atalhos de dias, seleção manual e repetição. **O que executar** permite escolher fluxo completo, uma etapa ou fluxo personalizado. **Se falhar** configura quantidade e espera das novas tentativas.

Os nós disponíveis são atualização do tarifário, relatório Novelis, SQL, comparação, arquivos, PDF, XML, comprovante e abertura de chamado. A posição de um card organiza a visualização. As conexões definem a ordem de execução. Selecionar uma conexão permite removê-la e conectar outra sequência. Excluir um card une suas etapas anterior e seguinte.

**Atualizar tarifário** consulta o portal por HTTP e atualiza o catálogo compartilhado, como o botão **Atualizar do portal**. O nó aguarda a gravação no banco antes de avançar e mostra o total de tarifas no monitor. Pode ser usado sozinho ou conectado antes da consulta e da conferência dos CT-es. Não precisa de uma etapa SQL anterior e não altera os agendamentos já salvos.

A coleta mantém o controle compartilhado entre computadores. Se outro computador já estiver atualizando, o nó aguarda seu resultado. A proteção existente contra consultas repetidas permite reutilizar uma atualização concluída nos últimos 60 segundos. Falha ou interrupção impedem o avanço dessa execução e preservam o catálogo anterior. A espera tem limite de 16 minutos. Parar a rotina cancela a coleta iniciada por esse nó, sem cancelar uma coleta pertencente a outro computador.

Cada consulta possui início e fim relativos ao dia da execução. Zero representa hoje. De dois dias atrás até zero inclui anteontem, ontem e hoje. Dois nos dois campos consulta apenas anteontem. O intervalo permitido vai de hoje a 30 dias atrás.

O backend valida uma sequência conectada, sem ciclos. A comparação exige SQL e relatório carregados. A abertura de chamados exige comparação após as consultas utilizadas. A verificação dos anexos, a configuração de comprovantes, a conferência tarifária e a proteção contra abertura duplicada continuam nos executores existentes.

Os relatórios consultados pelo fluxo são obtidos por HTTP e ficam isolados por execução em `captures/workflows/<UUID>/`. Uma consulta curta do agendamento mantém seu próprio arquivo de relatório. A abertura usa o lote HTTP e suas confirmações entram no relatório diário compartilhado.

O agendador encaminha o desenho salvo ao executor e controla cada horário e tentativa por data, conta Windows e computador. O monitor identifica as etapas iniciadas, concluídas e com falha. A parada interrompe a sequência e preserva as confirmações já registradas.

## Frequência e novas tentativas

O formulário permite configurar de **1 a 48 execuções por dia** e um intervalo de **1 a 1440 minutos** entre os horários previstos. O horário cadastrado é o primeiro do dia. Por exemplo: 08:00, três execuções e intervalo de 120 minutos produzem 08:00, 10:00 e 12:00 nos dias da semana selecionados. O formulário mostra os horários antes de salvar e rejeita uma sequência de horários que ultrapasse a meia-noite.

Cada horário pode ter **0 a 10 novas tentativas após falha**, com espera de **1 a 1440 minutos** contada a partir do encerramento da tentativa anterior. Duas novas tentativas significam no máximo três tentativas no total para aquele horário. Sucesso encerra as tentativas desse horário; atingir o limite mantém o resultado como falha e encerra esse ciclo. Os próximos horários programados continuam válidos. A listagem mostra a próxima tentativa e, ao atingir o limite, informa **tentativas esgotadas**.

Somente falhas confirmadas geram novas tentativas. Uma parada solicitada pelo operador ou uma execução interrompida por reinicialização, sem resultado confirmado, não é reiniciada automaticamente. Uma tentativa já aguardando seu prazo permanece registrada e pode executar depois de reabrir o aplicativo, inclusive se seu prazo atravessar a meia-noite. Editar, desativar ou remover a rotina cancela as tentativas ainda aguardando.

Uma automação roda por vez neste computador. Se ele estiver ocupado, os horários vencidos do dia e as tentativas pendentes aguardam e são atendidos pela data prevista, sem sobreposição. O intervalo define horários previstos: atrasos e a duração de outras execuções podem mudar o início efetivo. Horários não iniciados de dias passados não são executados em lote ao reabrir o aplicativo. O botão manual continua iniciando uma execução avulsa, sem consumir os horários automáticos.

As tentativas ficam no SQLite compartilhado em `hub_schedule_attempts`, com chave por agendamento, data, horário e número da tentativa. A migração preserva a tabela anterior e importa seu histórico sem repetir a execução do dia. Agendamentos antigos mantêm **uma execução diária e nenhuma nova tentativa** até serem editados. A fila de novas tentativas usa o fluxo salvo e mantém as proteções existentes contra reenvio de chamados já confirmados.

O botão **Iniciar rotina** nas ações executa imediatamente o fluxo salvo, inclusive quando o agendamento está desativado. O monitor recebe a execução iniciada pelo operador. A próxima ocorrência automática segue o horário cadastrado. O botão aguarda o encerramento de uma automação que já esteja em andamento.

A prévia interativa inicializa o agendador e os demais serviços de segundo plano. O modo `NOVELIS_BACKEND_READINESS=1` fica reservado à verificação de instalação. A página de agendamentos informa quando o agendador está inativo.

Nos fluxos automáticos de abertura, a consulta SQL acrescenta os CT-es da fila persistida que continuam sem chamado, inclusive os de dias anteriores ao período escolhido. Os dados atuais do SQL têm prioridade. Os documentos da fila passam pela comparação com o relatório Novelis e pela verificação de anexos. Consultas isoladas e listas manuais seguem seus períodos e seleções.

A comparação prioriza a chave de acesso. Documentos com série e número iguais e chaves diferentes seguem como pendentes. Para confirmar uma abertura HTTP, a consulta ao relatório abrange da emissão do CT-e até o dia atual, incluindo chamados abertos posteriormente à emissão. O registro de envio coordena a confirmação de uma tentativa já realizada.

## Visão geral e finalização

Durante um fluxo personalizado, a Visão geral mostra os nós na ordem das conexões, com estado e progresso individuais. Consultas SQL, relatório Novelis e comparação possuem cards próprios. O nome do fluxo e a etapa atual acompanham essa sequência. O desenho e os eventos de cada nó são consultados fora do limite de 300 linhas da visualização dos logs.

O editor também oferece **Gerar relatório**, **Abrir relatório final** e **Modal de finalização**. Essas ações ficam ao final da sequência. A abertura do relatório exige um nó de geração anterior.

**Gerar relatório** atualiza o Excel diário existente. Quando solicitado explicitamente em um dia sem aberturas, gera o relatório com zero chamados. **Abrir relatório final** abre os detalhes na página Relatórios diários, onde o operador pode baixar o Excel. O modal apresenta o resultado da execução, o total de chamados e as etapas concluídas. Se as duas ações de interface estiverem selecionadas, o relatório abre ao fechar o modal.

O aplicativo aguarda o backend concluir a geração antes de apresentar a finalização. A apresentação é registrada localmente por execução para evitar repetições a cada consulta de atualização. Falha ou cancelamento preservam as aberturas confirmadas e permitem mostrar o resumo com sua situação final.

O canvas utiliza React Flow. A referência de integração está na documentação oficial. [React Flow](https://reactflow.dev/learn)
