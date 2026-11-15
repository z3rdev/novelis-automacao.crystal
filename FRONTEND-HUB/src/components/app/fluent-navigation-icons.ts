import { createElement } from "react";
import { FluentIcon, type FluentIconName } from "./fluent-icon";

function symbol(name: FluentIconName) {
  return function SystemIcon({ className }: { className?: string }) {
    return createElement(FluentIcon, { name, className });
  };
}

export const fluentIcons = {
  home: symbol("home"),
  monitor: symbol("monitor"),
  play: symbol("play"),
  calendar: symbol("calendar"),
  list: symbol("list"),
  document: symbol("document"),
  report: symbol("report"),
  edit: symbol("edit"),
  bell: symbol("bell"),
  help: symbol("help"),
  settings: symbol("settings"),
  people: symbol("people"),
  lock: symbol("lock"),
  tools: symbol("tools"),
  scale: symbol("scale"),
  message: symbol("message"),
};
