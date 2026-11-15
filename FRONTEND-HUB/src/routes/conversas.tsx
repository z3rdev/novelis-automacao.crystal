import { createFileRoute } from "@tanstack/react-router";
import { ChatPage } from "@/components/app/chat/chat-page";

export const Route = createFileRoute("/conversas")({
  validateSearch: (search: Record<string, unknown>): { cte?: string; room?: string } => ({
    ...(typeof search["cte"] === "string" ? { cte: search["cte"].slice(0, 40) } : {}),
    ...(typeof search["room"] === "string" ? { room: search["room"].slice(0, 36) } : {}),
  }),
  head: () => ({ meta: [{ title: "Mensagens · Cargo Hub" }] }),
  component: Messages,
});
function Messages() {
  const search = Route.useSearch();
  return (
    <ChatPage
      key={`${search.cte ?? ""}:${search.room ?? ""}`}
      {...(search.cte ? { initialCte: search.cte } : {})}
      {...(search.room ? { initialRoom: search.room } : {})}
    />
  );
}
