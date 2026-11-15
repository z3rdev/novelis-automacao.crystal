import { createFileRoute } from "@tanstack/react-router";
import { HelpCenter } from "@/components/app/help-center";
import { helpTopic } from "@/components/app/help-content";

export const Route = createFileRoute("/ajuda")({
  validateSearch: (search: Record<string, unknown>) => ({ topic: helpTopic(search["topic"]).id }),
  component: HelpRoute,
  head: () => ({ meta: [{ title: "Ajuda · Cargo Hub" }] }),
});

function HelpRoute() {
  const { topic } = Route.useSearch();
  const navigate = Route.useNavigate();
  return (
    <HelpCenter
      topic={topic}
      onTopicChange={(id) => void navigate({ search: { topic: id }, replace: true })}
    />
  );
}
