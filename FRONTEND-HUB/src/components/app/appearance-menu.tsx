import { Moon, Sun, Monitor } from "lucide-react";
import { useEffect, useRef, useState, type PointerEvent } from "react";
import { useAppearance } from "@/services/appearance-context";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export function AppearanceMenu() {
  const { preference, resolved, setPreference } = useAppearance();
  const [open, setOpen] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const held = useRef(false);
  const origin = useRef<{ x: number; y: number } | null>(null);
  const cancel = () => {
    if (timer.current !== null) clearTimeout(timer.current);
    timer.current = null;
  };
  useEffect(() => cancel, []);
  const toggle = () => {
    setOpen(false);
    setPreference(resolved === "dark" ? "light" : "dark");
  };
  const start = (event: PointerEvent<HTMLButtonElement>) => {
    if (event.button !== 0) return;
    // Radix normally opens on pointerdown; a short press toggles the theme instead.
    event.preventDefault();
    event.currentTarget.focus();
    cancel();
    held.current = false;
    origin.current = { x: event.clientX, y: event.clientY };
    timer.current = setTimeout(() => {
      timer.current = null;
      held.current = true;
      setOpen(true);
    }, 600);
  };
  const Icon = resolved === "dark" ? Moon : Sun;
  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Aparência"
          title={`Ativar modo ${resolved === "dark" ? "claro" : "escuro"}. Segure para opções.`}
          onPointerDown={start}
          onPointerUp={cancel}
          onPointerCancel={() => {
            cancel();
            held.current = true;
          }}
          onPointerLeave={cancel}
          onPointerMove={(event) => {
            if (
              origin.current &&
              Math.hypot(event.clientX - origin.current.x, event.clientY - origin.current.y) > 8
            )
              cancel();
          }}
          onBlur={cancel}
          onClick={() => {
            cancel();
            if (held.current) {
              held.current = false;
              return;
            }
            toggle();
          }}
          onKeyDown={(event) => {
            if (event.key === "ArrowDown" || (event.shiftKey && event.key === "F10")) {
              event.preventDefault();
              setOpen(true);
            } else if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              if (!event.repeat) toggle();
            }
          }}
        >
          <Icon className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-60">
        <DropdownMenuLabel>Aparência</DropdownMenuLabel>
        <DropdownMenuRadioGroup value={preference} onValueChange={() => setPreference("system")}>
          <DropdownMenuRadioItem value="system">
            <Monitor className="mr-2 h-4 w-4" />
            Seguir o computador
          </DropdownMenuRadioItem>
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
