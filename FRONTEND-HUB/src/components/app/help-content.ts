import type { FluentIconName } from "./fluent-icon";

export interface HelpTopic {
  id: string;
  title: string;
  icon: FluentIconName;
  intro: string;
  steps?: string[];
  paragraphs?: string[];
  note?: string;
  link?: string;
  action?: string;
}

export const helpTopics: HelpTopic[] = [
  {
    id: "consulta",
    title: "Como consultar os CT-es de um período",
    icon: "calendar",
    intro: "A consulta encontra CT-es e confere quais documentos já estão nas pastas da operação.",
    steps: [
      "Abra CT-es pendentes e escolha Dia atual ou um dos períodos da lista.",
      "Para escolher as datas, use Período personalizado e preencha De e Até. Você pode consultar até 30 dias atrás.",
      "Clique em Consultar CT-es. Ao terminar, use Sem PDF, Sem XML ou Prontos para revisar a fila.",
    ],
    note: "Um CT-e já encontrado permanece na fila até ter chamado, mesmo quando fica fora do período de uma nova consulta.",
    link: "/pendentes",
    action: "Consultar CT-es",
  },
  {
    id: "documentos",
    title: "Por que meu CT-e não está pronto?",
    icon: "document",
    intro:
      "Confira as colunas PDF, XML e Guia/Comprovante na fila. O indicador Chamado mostra se já é possível abrir a solicitação.",
    paragraphs: [
      "Disponível indica que o arquivo correspondente ao CT-e foi encontrado. Faltando indica que o documento ainda precisa ser obtido.",
      "Não exige, na coluna Guia/Comprovante, indica que esse documento não é necessário para aquele CT-e. A permissão de abertura sem comprovante também depende da configuração da operação.",
      "Se o documento acabou de ser salvo, aguarde a próxima conferência da lista. Confira se ele está na pasta compartilhada usada pela operação.",
    ],
    link: "/pendentes",
    action: "Conferir documentos na fila",
  },
  {
    id: "execucao",
    title: "Como iniciar ou parar uma automação",
    icon: "play",
    intro: "Em Execução e lotes, escolha a ação conforme o trabalho que precisa realizar.",
    steps: [
      "Selecione o fluxo. Você pode consultar, gerar PDF, buscar XML, procurar comprovantes, atualizar os chamados ou executar o fluxo completo.",
      "Revise o período ou informe a lista de CT-es.",
      "Clique em Iniciar. Acompanhe o andamento em Monitor ao vivo.",
      "Para interromper, clique em Parar automação e aguarde o encerramento.",
    ],
    note: "Se a SEFAZ pedir uma validação humana, abra o navegador pelo aviso no monitor e conclua o CAPTCHA.",
    link: "/execucao",
    action: "Abrir execução e lotes",
  },
  {
    id: "agendamento",
    title: "Como criar um agendamento",
    icon: "clock",
    intro: "Os horários seguem o relógio do computador onde a rotina foi cadastrada.",
    steps: [
      "Em Agendamentos, clique em Novo agendamento e dê um nome à rotina.",
      "Defina o horário e os dias da semana.",
      "Escolha quantas vezes executar no dia e o intervalo. Confira os horários previstos antes de salvar.",
      "Para repetir após falha, informe a quantidade de novas tentativas e o tempo de espera. Zero desativa essas tentativas.",
      "Escolha o tipo de execução e o período da consulta. Para montar uma sequência própria, escolha Criar fluxo personalizado.",
      "Salve e confira se a rotina aparece como ativa e com a próxima execução prevista. Para executar agora, use Iniciar rotina nas ações da linha.",
      "Mantenha o computador ligado, com rede e o Cargo Hub aberto ou na bandeja do Windows.",
    ],
    link: "/agendamentos",
    action: "Abrir agendamentos",
  },
  {
    id: "fluxos",
    title: "Como acompanhar meu fluxo personalizado",
    icon: "list",
    intro:
      "A Visão geral e o Monitor ao vivo mostram as etapas na mesma ordem definida nas conexões do seu fluxo.",
    paragraphs: [
      "Executando identifica a etapa atual. A contagem mostra quantos itens foram processados nessa etapa. As consultas também mostram o período escolhido.",
      "Ao encontrar uma falha, abra a atividade mais recente no monitor para conferir o motivo. Os chamados já confirmados permanecem registrados no relatório diário.",
    ],
    steps: [
      "No editor, conecte as etapas na ordem desejada. A posição dos cartões no desenho serve para organizar a tela.",
      "Ao final, adicione Gerar relatório. Se quiser consultar o resultado ao terminar, acrescente Abrir relatório final e Mostrar modal de finalização.",
    ],
    link: "/monitor",
    action: "Abrir monitor ao vivo",
  },
  {
    id: "chamados",
    title: "Como conferir um chamado aberto",
    icon: "report",
    intro:
      "A página Chamados reúne os registros da operação e o andamento informado pelo portal Novelis.",
    steps: [
      "Busque pelo número do chamado, CT-e, JDA ou responsável.",
      "Clique na linha para abrir os detalhes no painel lateral. Use o link do chamado para acessar o portal Novelis.",
    ],
    link: "/chamados",
    action: "Consultar chamados",
  },
  {
    id: "relatorios",
    title: "Onde estão os relatórios de aberturas?",
    icon: "report",
    intro:
      "Em Relatórios diários, cada data reúne os chamados confirmados nas execuções dos operadores.",
    paragraphs: [
      "Abra a data desejada para conferir os chamados e baixar o Excel. Novas aberturas confirmadas são incorporadas ao arquivo daquele dia.",
      "Quando uma execução é interrompida, os chamados que já foram confirmados também entram no relatório.",
    ],
    link: "/relatorios",
    action: "Abrir relatórios diários",
  },
  {
    id: "notificacoes",
    title: "Como ler os avisos da operação",
    icon: "bell",
    intro: "O sino no rodapé mostra quantos avisos ainda precisam ser lidos.",
    steps: [
      "Abra Notificações e selecione um comunicado.",
      "Depois de conferir o texto, clique em Marcar como lida. Você também pode marcar todos os avisos da lista.",
    ],
    note: "Fechar um aviso automático mantém o comunicado como não lido.",
    link: "/notificacoes",
    action: "Abrir notificações",
  },
  {
    id: "conexao",
    title: "O app perdeu a conexão. O que faço?",
    icon: "monitor",
    intro:
      "O Cargo Hub tenta reconectar automaticamente e informa a nova tentativa na tela de entrada.",
    steps: [
      "Confira a conexão de rede do computador e o acesso às pastas compartilhadas.",
      "Aguarde a reconexão. Se a mensagem continuar, informe o responsável pela instalação.",
    ],
    paragraphs: [
      "Fechar a janela pelo X mantém o Cargo Hub na bandeja. A opção Sair encerra o aplicativo e seus agendamentos.",
    ],
  },
  {
    id: "configuracoes",
    title: "Quem pode alterar as configurações?",
    icon: "lock",
    intro: "As configurações da operação exigem a senha mestre definida pelo responsável.",
    paragraphs: [
      "O desbloqueio vale por 15 minutos na sua sessão. Para encerrar esse acesso antes, use Bloquear.",
      "O responsável com acesso de desenvolvedor pode cadastrar ou alterar a senha em Configurações → Segurança. A senha é a mesma nos computadores da operação.",
    ],
    link: "/configuracoes",
    action: "Abrir configurações",
  },
];

export function helpTopic(id: unknown) {
  return helpTopics.find((topic) => topic.id === id) ?? helpTopics[0]!;
}

export const contextualHelp: Record<string, string> = {
  "/": "fluxos",
  "/monitor": "fluxos",
  "/execucao": "execucao",
  "/pendentes": "documentos",
  "/documentos": "documentos",
  "/agendamentos": "agendamento",
  "/chamados": "chamados",
  "/mensagens": "configuracoes",
  "/relatorios": "relatorios",
  "/notificacoes": "notificacoes",
  "/configuracoes": "configuracoes",
};
