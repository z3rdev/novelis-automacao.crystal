# Revisão r6 do instalador Crystal

## Pastas dos PDFs

O fluxo Crystal passa a publicar os arquivos no padrão existente de pastas por
documento. Filial, série e número identificam o arquivo dentro da pasta.

```text
PDFS-RODOPAR/cte-17431/CTE_2-10-17431.pdf
```

A busca prioriza essa localização e reconhece os PDFs antigos na raiz, os nomes
com sublinhados e as pastas `cte_<numero>`. A identificação confere os três
componentes do CT-e.

Em 13/11/2026, os nove PDFs identificados na raiz do compartilhamento
`\\192.168.254.250\rede\Publico\AUTOMAÇÃO-CTE\PDFS-RODOPAR` foram movidos para as
respectivas pastas `cte-<numero>`. Todos os SHA-256 foram conferidos antes e depois.
O registro está em `runtime/crystal-tests/pdf-folder-migration-r6.json`.

## Causa da falha na instalação limpa

Os logs do NB-GFR-VIN-05 mostram preparação bem-sucedida do Python, instalação das
dependências e detecção do Chromium. A falha ocorreu em `backend_health`.

Durante a inicialização da API, `OperationsStore.initialize` tentou acessar a pasta
do SQLite compartilhado e recebeu `WinError 1326`, associado à autenticação da conta
Windows no servidor. O servidor Uvicorn encerrou com código 3.

As evidências recebidas estão preservadas em
`runtime/crystal-tests/physical-pc-20261113-r5`.

## Tratamento implementado

A verificação de instalação confere o acesso à pasta operacional antes de iniciar
a API. Na instalação interativa, falhas de autenticação abrem a janela nativa do
Windows para uma conta autorizada no compartilhamento. O mesmo recurso está
disponível na abertura do aplicativo Tauri.

O acesso informado é validado contra a pasta configurada. A opção de salvar pertence
à janela do Windows, e a confirmação ocorre depois do acesso validado. A integração
usa `CredUIPromptForCredentialsW`, `CredUIParseUserNameW`, `WNetAddConnection2W` e
`CredUIConfirmCredentialsW`. Os buffers da senha são zerados ao terminar cada tentativa.
O processo transmite os dados às APIs nativas em memória. [Documentação da janela de credenciais](https://learn.microsoft.com/en-us/windows/win32/api/wincred/nf-wincred-creduipromptforcredentialsw),
[conexão de rede](https://learn.microsoft.com/en-us/windows/win32/api/winnetwk/nf-winnetwk-wnetaddconnection2w),
[confirmação e persistência](https://learn.microsoft.com/en-us/windows/win32/api/wincred/nf-wincred-creduiconfirmcredentialsw).

Os resultados registram categorias e códigos numéricos para autenticação necessária,
cancelamento, conflito de sessão e compartilhamento indisponível. A instalação
silenciosa apresenta o diagnóstico em JSON. A janela do instalador lê uma mensagem
específica quando a preparação falha. Cada tentativa limpa a mensagem anterior.

O empacotamento também recebeu uma correção na chamada do build Tauri. Os argumentos
nativos são passados em uma lista explícita, evitando que `-File` seja interpretado
como o parâmetro `FilePath` da função PowerShell intermediária.

## Arquivos principais

- `BACKEND/app/services/cte_pdf_files.py` e o controle `pendentes/controles/crystal_pdf.py`.
- `scripts/setup/network_access.py` e `scripts/setup/windows_network.py`.
- `scripts/setup/verify_backend.py`, `launch_backend.py` e `installer_receipt.py`.
- `scripts/bootstrap.ps1` e `scripts/build-installer.ps1`.
- `installer/AutomacaoNovelis.iss` e `installer/backend/Preparation.iss`.
- `FRONTEND-HUB/src-tauri/src/backend.rs`.
- Testes de PDF, autenticação de rede e argumentos do build.

## Validações executadas

- 117 testes selecionados de backend passaram. Há um aviso preexistente de depreciação
  do TestClient.
- Os cinco testes do frontend e a verificação TypeScript passaram.
- O teste offline em uma pasta nova preparou a venv e iniciou a API com SQLite local
  isolado. O ambiente ignorou o Python global e variáveis de Python herdadas.
- As quatro funções nativas de credenciais foram carregadas no Windows da máquina de
  desenvolvimento. Os testes com respostas simuladas cobriram autenticação recusada,
  confirmação de acesso válido, cancelamento, conflito de sessão e limpeza dos buffers.
- O Ruff passou nos arquivos Python novos e nos arquivos alterados verificados.

Os logs estão em `runtime/crystal-tests/hub-r6-final-tests.log`,
`hub-r6-private-build.log` e `hub-r6-offline-installation.log`. A evidência da instalação
isolada está em `runtime/crystal-tests/hub-offline-20261113T121012Z/verification.json`.

## Pacote e próximo teste

O pacote de teste é
`runtime/private-installer/NovelisCargoHubSetup-0.1.34-r6-PRIVADO-TESTE-NaoDistribuir.exe`.
O manifesto adjacente registra tamanho, SHA-256 e os hashes dos fontes do PDF e da
autenticação. O pacote contém o perfil operacional privado, preparado a partir da
configuração operacional empacotada na r5.

O tamanho é 741.416.252 bytes. O SHA-256 é
`baa5bdd3b91b43546b73aea0c026e9e5798d3e1297c0b7bd61068edfd6f901dd`.

No NB-GFR-VIN-05, execute o instalador pela conta Windows que utilizará o backend.
Quando a janela de rede aparecer, informe localmente uma conta autorizada na pasta
`rede` do servidor. Confira instalação, abertura do Tauri, consulta dos pendentes e
gravação de um PDF na pasta `cte-<numero>`.

Inclua uma reabertura após novo logon, com a opção de salvar credenciais selecionada,
para verificar o acesso persistente. Os arquivos `backend-readiness.json` e
`bootstrap-result.json` devem registrar sucesso.

A autenticação interativa real no NB-GFR-VIN-05 e a instalação em Windows limpo
continuam pendentes. A execução isolada ocorreu na máquina de desenvolvimento.
As aprovações de procedência e redistribuição do runtime Crystal e a homologação
fiscal continuam pendentes. O manifesto mantém `production_ready=false`.
