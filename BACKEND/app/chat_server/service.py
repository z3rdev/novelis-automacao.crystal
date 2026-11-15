"""Central document delivery is completed by the agent with access to the company share."""

from app.infrastructure.chat_documents import ChatDocuments
from app.services.chat import ChatService


class CentralDocuments(ChatDocuments):
    def publish(self, cte):
        # A workstation's durable maintenance agent materializes the verified S3 bundle.
        pass

    def view(self, row):
        value = super().view(row)
        value["directory"] = ""
        return value


class CentralChatService(ChatService):
    def __init__(self, settings, config):
        super().__init__(settings, config)
        self.documents = CentralDocuments(self.store, self.documents.files)
