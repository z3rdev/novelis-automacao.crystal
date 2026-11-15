import type { ComponentType } from "react";
import { fluentIcons } from "./fluent-navigation-icons";

export interface NavigationItem {
  title: string;
  url: string;
  icon: ComponentType<{ className?: string }>;
  keywords?: string;
  developerOnly?: boolean;
  headerTitle?: string;
}

export const overviewItem: NavigationItem = {
  title: "Visão geral",
  url: "/",
  icon: fluentIcons.home,
};
export const navigationGroups: { title: string; items: NavigationItem[] }[] = [
  {
    title: "Automação",
    items: [
      { title: "Monitor ao vivo", url: "/monitor", icon: fluentIcons.monitor },
      { title: "Execução e lotes", url: "/execucao", icon: fluentIcons.play },
      { title: "Agendamentos", url: "/agendamentos", icon: fluentIcons.calendar },
    ],
  },
  {
    title: "Documentos fiscais",
    items: [
      { title: "CT-es pendentes", url: "/pendentes", icon: fluentIcons.list },
      { title: "Documentos e DACTE", url: "/documentos", icon: fluentIcons.document },
    ],
  },
  {
    title: "Chamados Novelis",
    items: [
      {
        title: "Chamados",
        url: "/chamados",
        icon: fluentIcons.report,
        headerTitle: "Chamados Novelis",
      },
      {
        title: "Modelo do chamado",
        url: "/mensagens",
        icon: fluentIcons.edit,
        keywords: "mensagem texto assinatura",
      },
    ],
  },
  {
    title: "Análise e cadastros",
    items: [
      { title: "Relatórios diários", url: "/relatorios", icon: fluentIcons.report },
      { title: "Tarifas e tonelagem", url: "/tarifas", icon: fluentIcons.scale },
    ],
  },
];
export const footerItems: NavigationItem[] = [
  { title: "Mensagens", url: "/conversas", icon: fluentIcons.message, keywords: "chat financeiro GNRE guia comprovante setores" },
  { title: "Notificações", url: "/notificacoes", icon: fluentIcons.bell },
  { title: "Ajuda", url: "/ajuda", icon: fluentIcons.help, keywords: "primeiros passos" },
];
export const settingsItems: NavigationItem[] = [
  { title: "Geral e diagnóstico", url: "/configuracoes", icon: fluentIcons.settings },
  {
    title: "Usuários e dispositivos",
    url: "/usuarios-dev",
    icon: fluentIcons.people,
    developerOnly: true,
  },
  {
    title: "Segurança",
    url: "/senha-mestre-dev",
    icon: fluentIcons.lock,
    keywords: "senha mestre",
    headerTitle: "Segurança · Senha mestre",
    developerOnly: true,
  },
  {
    title: "Central de diagnóstico",
    url: "/diagnosticos-dev",
    icon: fluentIcons.tools,
    keywords: "suporte remoto HTTP certificado Crystal DLL execuções",
    developerOnly: true,
  },
  { title: "Avançado", url: "/avancado", icon: fluentIcons.tools, developerOnly: true },
  {
    title: "Publicar notificações",
    url: "/notificacoes-dev",
    icon: fluentIcons.bell,
    developerOnly: true,
  },
];
export const allNavigationItems = [
  overviewItem,
  ...navigationGroups.flatMap((group) => group.items),
  ...footerItems,
  ...settingsItems,
];

export function matchesNavigation(item: NavigationItem, search: string, group = "") {
  const normalize = (value: string) =>
    value
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLocaleLowerCase("pt-BR");
  return normalize(
    `${group} ${item.title} ${item.headerTitle ?? ""} ${item.keywords ?? ""}`,
  ).includes(normalize(search.trim()));
}
