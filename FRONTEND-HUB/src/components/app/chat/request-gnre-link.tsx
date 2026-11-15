import { Link } from "@tanstack/react-router";
import { MessageSquare } from "lucide-react";
import { Button } from "@/components/ui/button";

export function RequestGnreLink({ cte }: { cte: string }) {
  return (
    <Button variant="outline" asChild>
      <Link to="/conversas" search={{ cte }}>
        <MessageSquare />
        Solicitar guia e comprovante
      </Link>
    </Button>
  );
}
