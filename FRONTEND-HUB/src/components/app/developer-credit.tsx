import { toast } from "sonner";
import { desktop } from "@/services/desktop";

export const developerGithubUrl = "https://github.com/z3rdev";

export function DeveloperCredit() {
  return (
    <footer className="developer-credit">
      <span>Desenvolvido por</span>
      <a
        href={developerGithubUrl}
        target="_blank"
        rel="noopener noreferrer"
        onClick={(event) => {
          event.preventDefault();
          void desktop
            .openPath(developerGithubUrl)
            .catch(() => toast.error("Não foi possível abrir o GitHub."));
        }}
      >
        Z3ro.dev
      </a>
    </footer>
  );
}
