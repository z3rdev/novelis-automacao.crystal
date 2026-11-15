import type { ChatApi } from "./chat";

type Request = <T>(path: string, init?: RequestInit) => Promise<T>;
export function createChatApi(req: Request, download: (path: string) => Promise<Blob>): ChatApi {
  const post = <T>(path: string, body = {}) =>
    req<T>(path, { method: "POST", body: JSON.stringify(body) });
  const room = (id: string) => `/chat/rooms/${encodeURIComponent(id)}`;
  const files = (channel: string, id: string, kind: string) =>
    `${room(channel)}/requests/${encodeURIComponent(id)}/files/${kind}`;
  return {
    getChatInbox: () => req("/chat"),
    getChatDirectory: () => req("/chat/directory"),
    createChatRoom: (target_type, target) => post("/chat/rooms", { target_type, target }),
    getChatRoom: (id, before) => req(`${room(id)}${before ? `?before=${before}` : ""}`),
    sendChatMessage: (id, body, client_id) => post(`${room(id)}/messages`, { body, client_id }),
    readChatRoom: (id, through) => post(`${room(id)}/read`, { through }),
    requestGnre: (id, body) => post(`${room(id)}/requests`, body),
    claimGnre: (channel, id) => post(`${room(channel)}/requests/${encodeURIComponent(id)}/claim`),
    uploadGnre: (channel, id, kind, file, clientId) =>
      req(
        `${files(channel, id, kind)}?${new URLSearchParams({ filename: file.name, client_id: clientId })}`,
        {
          method: "PUT",
          body: file,
          headers: { "Content-Type": file.type || "application/octet-stream" },
          signal: AbortSignal.timeout(90_000),
        },
      ),
    downloadGnre: (channel, id, kind) => download(files(channel, id, kind)),
  };
}
