# Servidor central de mensagens do Cargo Hub

O serviço expõe REST em `/api/hub/chat` e WebSocket em `/api/hub/chat/live`. Usa as tabelas existentes do PostgreSQL e o MinIO operacional. O acesso público é `https://chat-server-db-cargohub.appsy.app.br`.

## Arquivos privados

A implantação recebe três arquivos em `secrets/`, fora da imagem e do Git.

- `chat-server.private.json` contém as propriedades `CHAMADOS_PG_*` existentes e `MINIO_CREDENTIALS_FILE` apontando para `/run/secrets/minio-credentials`.
- `minio.credentials.json` usa `url`, `accessKey`, `secretKey` e `region` opcional.
- `chat-clients.private.json` contém uma lista `clients`. Cada entrada tem `id`, `token_sha256`, `computer_name`, `windows_users` e `enabled`.

Cada instalação usa um token próprio. O servidor confere o hash, o dispositivo e a conta Windows autorizada. O token fica no perfil privado do backend local. O nome do operador vem da sessão Windows local. O WebSocket autentica no primeiro frame e verifica a autorização periodicamente. As chaves do MinIO e do PostgreSQL permanecem no backend.

## Docker na VPS

O pacote usa `/opt/cargo-hub-chat`. A partir dessa pasta:

```sh
docker compose -f compose.yaml up -d --build
docker compose -f compose.yaml ps
curl --fail http://127.0.0.1:18437/health
```

A API publica na interface loopback da VPS e participa da rede externa `infra_default`, usada pelo Nginx Proxy Manager existente. O proxy deve encaminhar o domínio para `cargo-hub-chat:8080`, habilitar WebSocket e aceitar uploads de pelo menos 20 MB. Em outro host, ajuste o nome da rede externa à rede do proxy.

Quando a VPS tiver as portas 80 e 443 livres, há uma configuração opcional Caddy:

```sh
docker compose -f compose.yaml -f deploy/chat/compose.caddy.yaml up -d --build
```

O DNS do domínio deve apontar para a VPS e as portas do proxy devem estar acessíveis. O arquivo `.dockerignore` desta pasta deve ser copiado para a raiz do pacote antes do build. O contexto inclui apenas o código Python e os requisitos.

Para cadastrar outra instalação, execute `python3 deploy/chat/register-client.py --registry secrets/chat-clients.private.json --computer NOME-DO-PC --windows-user 'DOMINIO\usuario' --output perfil-cliente.private.json` na VPS. O comando grava o token somente no arquivo de saída. Execute `docker compose -f compose.yaml up -d --force-recreate chat` após alterar o cadastro. Transfira o perfil por um canal privado para o backend da instalação correspondente.

## Aplicativos Windows

Configure `CHAT_SERVER_CONFIG_FILE` no `.env` privado. O JSON apontado contém `url`, `client_id` e `token`. A URL deste ambiente é `https://chat-server-db-cargohub.appsy.app.br`.

O aplicativo conserva a sessão Windows local e encaminha as operações de chat ao servidor autenticado. A conexão WebSocket local retransmite eventos e mensagens ao servidor. O frontend atualiza as conversas, contadores, som e widget ao receber eventos. As consultas periódicas existentes fazem a recuperação quando a conexão cai.

`MINIO_CREDENTIALS_FILE`, `GNRE_S3_CREDENTIALS_FILE`, `EXECUTION_REPORT_S3_CREDENTIALS_FILE`, `minio.credentials.json` e `credentials.json` funcionam para operações sem `CONFIG.dev`. A publicação de atualizações continua usando a autorização de desenvolvedor existente.

## Documentos e integração com a rede

O servidor valida os uploads, salva no MinIO e unifica guia e comprovante. O estado fica como entrega pendente até um agente do Cargo Hub com acesso ao PostgreSQL, MinIO e compartilhamento publicar o PDF unificado na pasta de rede.

O agente local existente retoma entregas pendentes a cada 60 segundos. Após a confirmação persistida da abertura do chamado, arquiva os objetos e remove os arquivos de rede gerenciados. A retenção no MinIO continua em 30 dias após a confirmação. O serviço central também processa a expiração dos documentos arquivados.

Os dados atuais permanecem nas mesmas tabelas. Mensagens repetidas com o mesmo identificador recebem a confirmação da mensagem já gravada. O servidor publica eventos após operações confirmadas e reconstrói a caixa de entrada na reconexão.

## Validação

Confira `/health`, autenticação, rejeição de dispositivo inválido, acesso às conversas por setor, envio e confirmação de mensagem, reconexão, upload e entrega pelo agente Windows. O teste PostgreSQL usa tabelas de QA isoladas. O teste de WebSocket exercita o protocolo real e a idempotência.

O processo usa um worker para compartilhar as conexões em memória. O histórico durável fica no PostgreSQL. A ampliação para múltiplos workers exige distribuição dos eventos entre processos.

### Validação deste ambiente em 15/11/2026

O container foi compilado e iniciado na VPS `69.62.97.245`. O Nginx Proxy Manager existente encaminha o domínio com HTTPS e WebSocket. A verificação Docker retornou `healthy`.

- `/health` público respondeu HTTP 200. A caixa de entrada sem autenticação respondeu HTTP 401.
- A autenticação HTTP e WebSocket sobre TLS funcionou com os perfis cadastrados.
- As prévias principal e Financeiro passaram pelo encaminhamento local HTTP/WebSocket até a VPS. A prévia Financeiro também exercitou o proxy Vite na porta 1421.
- O acesso operacional ao bucket respondeu HTTP 200 e a política privada do prefixo GNRE foi conferida no servidor.
- A suíte do frontend passou com 198 testes. As regressões de chat/armazenamento passaram com 17 testes. A rodada final de servidor, adaptador e configuração MinIO passou com 6 testes.
- O teste isolado em PostgreSQL exerceu envio por WebSocket, recebimento pelo Financeiro, idempotência e recusa de identidade inválida. Os testes de armazenamento usam o provedor controlado da suíte.

Os registros ficam em `runtime/chat-vps/public-validation.json`, `local-preview-validation.json`, `deployment-validation.json` e nos logs `runtime/chat-complete-ui-tests.log`, `chat-final-backend-regressions.log` e `chat-final-server-tests.log`.

O cadastro atual contém este computador de desenvolvimento e a identidade da prévia Financeiro. Outras instalações precisam receber seus próprios perfis privados. A entrega real de um novo upload GNRE pela VPS até a pasta SMB aguarda o teste operacional com os operadores.
