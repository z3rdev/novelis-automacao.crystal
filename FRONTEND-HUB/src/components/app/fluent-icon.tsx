import type { ComponentProps } from "react";
import { cn } from "@/lib/utils";

// System glyphs documented in Microsoft's Segoe Fluent Icons character map.
const glyphs = {
  search: "\uE721",
  help: "\uE897",
  check: "\uE73E",
  clock: "\uE917",
  error: "\uE783",
  cancel: "\uE711",
  minimize: "\uE921",
  restore: "\uE923",
  download: "\uE896",
  pause: "\uE769",
  play: "\uE768",
  calendar: "\uE787",
  document: "\uE8A5",
  report: "\uE9F9",
  attach: "\uE723",
  settings: "\uE713",
  people: "\uE716",
  monitor: "\uE770",
  list: "\uE9D5",
  home: "\uE80F",
  edit: "\uE70F",
  refresh: "\uE72C",
  forward: "\uE72A",
  open: "\uE8A7",
  lock: "\uE72E",
  warning: "\uE7BA",
  chevron: "\uE76C",
  bell: "\uEA8F",
  tools: "\uE90F",
  scale: "\uE9D2",
  menu: "\uE700",
  message: "\uE8BD",
} as const;

export type FluentIconName = keyof typeof glyphs;

export function FluentIcon({
  name,
  className,
  ...props
}: ComponentProps<"span"> & { name: FluentIconName }) {
  return (
    <span {...props} aria-hidden="true" className={cn("fluent-icon", className)}>
      {glyphs[name]}
    </span>
  );
}
