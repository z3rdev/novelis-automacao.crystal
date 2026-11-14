import navyLogo from "@/assets/brand/cargo-hub-navy.png";
import whiteLogo from "@/assets/brand/cargo-hub-white.png";
import { cn } from "@/lib/utils";

export function BrandMark({
  tone = "navy",
  className,
}: {
  tone?: "navy" | "white";
  className?: string;
}) {
  return (
    <span className={cn("brand-mark", className)}>
      <img src={tone === "white" ? whiteLogo : navyLogo} alt="Cargo Hub" draggable={false} />
    </span>
  );
}

export function BrandName({ className }: { className?: string }) {
  return (
    <span className={cn("brand-name", className)}>
      Cargo<span>Hub</span>
    </span>
  );
}
