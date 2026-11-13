# Instalador integrado do Novelis Cargo Hub

Para a entrega com dados operacionais preenchidos, use a
[revisão r3 privada](instalador-cargo-hub-r3-privado.md). O modelo geral continua
sanitizado; o perfil privado é aplicado explicitamente ao arquivo ativo `.env`.

**Atualização:** o EXE original abaixo foi retirado por preparar a configuração
depois da validação do backend. Use a [revisão r2](instalador-cargo-hub-r2.md),
que corrige a ordem e registra a causa das recusas de prontidão.

Artefato de teste gerado em 12/11/2026:
[NovelisCargoHubSetup-0.1.34-TESTE-NaoDistribuir.exe](../runtime/crystal-build/development/installer/NovelisCargoHubSetup-0.1.34-TESTE-NaoDistribuir.exe).
Tamanho: 741.398.714 bytes. SHA-256:
`c59df6596052fe94664a0256c16ff83df3ceee69f2f2043f100a13b7531a7156`.
O [manifesto](../runtime/crystal-build/development/installer/NovelisCargoHubSetup-0.1.34-TESTE-NaoDistribuir.manifest.json)
vincula o EXE aos hashes do Tauri, front compilado, Python, WebView2, wheels e MSI.
O arquivo permanece local, com acesso limitado ao usuário, Administradores e
SYSTEM. Não foi publicado no compartilhamento de implantação.

Esta entrega substitui o fluxo de kits de recuperação por um único EXE de teste.
O instalador conserva o identificador e a pasta da instalação anterior, atualiza
o aplicativo para o front `FRONTEND-HUB` em janela Tauri e preserva `BACKEND/.env`.
Os arquivos de implantação publicados no servidor não são alterados pelo build.

## Conteúdo e inicialização

- Tauri x64 com o build estático atual do Cargo Hub, sem depender de Node no cliente.
- CPython 3.12.10 x64 completo, extraído do pacote oficial NuGet `python`, dentro
  de `runtime/python312`, com licença e manifesto SHA-256 de seus arquivos.
- Wheelhouse offline, Chromium do Playwright, Visual C++ x64 e instalador
  Evergreen x64 do Microsoft WebView2. O cliente não precisa das ferramentas C++
  usadas para compilar o aplicativo.
- MSI Crystal RDC 1.0.1 x86, com os mesmos quatro módulos 11.5.0.313 e as
  verificações de COM existentes. O editor Crystal não é instalado.

No modo instalado, o bootstrap usa exclusivamente o Python do aplicativo.
Ele não consulta o Python global, não executa o bundle MSI Python e não tenta
reparar ou remover instalações Python registradas no Windows. A `.venv` é
recriada na atualização e as dependências são instaladas sem índice de internet.

Depois dos imports e da conferência do Chromium, o setup inicia temporariamente
a API real em uma porta local livre e exige `/api/health` e
`/api/hub/health/ping` funcionais, com a versão e o diretório corretos. O processo
de teste é encerrado ao final. Essa validação não consulta o banco SQL nem gera DACTE.

O caminho SQLite já configurado é preservado. Se estiver vazio, o instalador usa
`\\192.168.254.250\rede\Publico\novelis-automacao\novelischamado.sqlite`.
A conta Windows precisa acessar e alterar o banco compartilhado; falha de rede
ou permissão impede a validação, sem criar um banco alternativo local.

Abrir o Cargo Hub inicia o backend em `127.0.0.1:8000`, se necessário. Um bloqueio
local evita partidas simultâneas. Um processo diferente usando essa porta não
é aceito como backend do aplicativo. A inicialização automática do serviço
Python usa a entrada da própria conta em HKCU Run, sem tarefa administrativa.

O novo front não usa o atualizador do launcher antigo. Atualizações deste EXE
de teste são realizadas pelo próprio setup integrado.

## Build controlado

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-installer.ps1 `
  -BuildMode development `
  -CrystalManifest .\runtime\crystal-build\development\NovelisCrystalRDC-x86-1.0.1.manifest.json
```

A versão vem de `DESKTOP/automacao_novelis_desktop/config.py` e também é aplicada
ao build Tauri. O Rust do projeto fica fixado em `src-tauri/rust-toolchain.toml`.
O script carrega o ambiente MSVC x64 e executa TypeScript e testes do front.
A compilação Rust usa uma tarefa por vez para limitar o consumo de memória;
`build-hub-desktop.ps1 -Jobs` permite ajustar esse limite em outro computador.
O modo de distribuição continua exigindo aprovação explícita de procedência e
licenciamento Crystal. Nenhuma chave é fornecida ao Inno pela linha de comando.

Fontes oficiais dos novos pré-requisitos:
[CPython para Windows](https://docs.python.org/3.12/using/windows.html#the-nuget-org-packages),
[pacote Python 3.12.10](https://www.nuget.org/packages/python/3.12.10),
[distribuição do WebView2](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution) e
[pré-requisitos Tauri](https://v2.tauri.app/start/prerequisites/).
Os executáveis Python, WebView2 e Visual C++ têm a assinatura do fornecedor
verificada no build; os arquivos do Python são vinculados ao hash fixado no
inventário de `installer/backend/python-runtime.lock.json`.

## Execução no PC de teste

Copie somente o novo EXE autorizado para a pasta local de teste e execute-o.
Selecione a pasta já usada pelo aplicativo para atualizar aquela instalação.
Aceite a elevação do Windows quando o MSI Crystal a solicitar. Não execute
outro setup ou kit de recuperação simultaneamente.

O setup oferece abrir o **Novelis Cargo Hub**, em janela própria. A instalação
é bloqueada como incompleta se o preparo falhar: código 20 para backend e 21
para WebView2. O retorno 0 depende das verificações realizadas pelo setup.
Um pedido de reinicialização do Crystal exige reiniciar e repetir o setup.

Os resultados ficam na pasta instalada, em `runtime`:

- `bootstrap.log` e `bootstrap-result.json`: preparo do ambiente.
- `backend-setup.log` e `backend-readiness.json`: inicialização temporária da API.
- `webview2-result.json`: detecção ou instalação do WebView2.
- `backend-local.log` e `backend-launch-error.json`: inicialização pelo aplicativo.
- `installation/crystal-install-result.json`: instalação do Crystal quando necessária.

## Limites da validação

Resultados automatizados desta etapa: TypeScript sem erros; 5 testes do front;
52 testes distintos de bootstrap, política Crystal, runtime local, bloqueios
Inno e inicialização da API. Os logs estão em `runtime/crystal-tests`.
O ensaio `hub-offline-20261112T160047Z/verification.json` concluiu o preparo
offline e recebeu resposta real da API 0.1.34. O ensaio de inicialização
`launcher-verification.json` comprovou reutilização da API na segunda chamada
e encerramento dos processos criados pelo teste.
O teste de remoção do serviço encerrou um interpretador do diretório isolado e
preservou outro Python externo ao aplicativo, sem alterar registro ou tarefas
do computador de desenvolvimento.
A janela nativa Tauri foi aberta no desenvolvimento e exibiu o front novo,
conectado à API já existente, sem iniciar fluxos. O executável Tauri e o setup
informam versão 0.1.34; o rodapé atual do front mantém seu identificador próprio
`v0.1.0 · Cargo Hub`. O instalador completo não foi executado no desenvolvimento.

O teste `scripts/test-hub-installation.py` usa uma pasta nova, o Python local,
wheelhouse sem índice de internet e SQLite isolado. Invalida deliberadamente
PYTHONHOME/PYTHONPATH e remove o Python global do PATH. O Chromium é referenciado
por uma junção para a cópia oficial do build; isso não representa instalação
em máquina limpa. Nenhum MSI Crystal é executado por esse teste.

Testes sintéticos do Inno comprovam os bloqueios de conclusão e abertura em
falhas do backend e WebView2. Build e testes no desenvolvimento não substituem
a instalação no PC físico autorizado. Continuam pendentes naquele PC: instalação
do novo EXE, reinicialização, backend sob a conta real, SQL, exportação PDF,
leitura do QR e do Code 128 e coexistência dos componentes Crystal.

O pacote permanece **de teste, sem aprovação de redistribuição e sem declaração
de produção pronta**. A aprovação de licença/procedência do Crystal e o
licenciamento das fontes comerciais continuam separados da aceitação técnica.

## Arquivos da implementação

| Área | Arquivos principais |
| --- | --- |
| Build | `scripts/build-installer.ps1`, `scripts/create-installer.ps1`, `scripts/build-hub-desktop.ps1`, `scripts/prepare-python-runtime.py`, `scripts/prepare-webview-runtime.py`, `scripts/setup/installer_receipt.py` |
| Python e API | `scripts/bootstrap.ps1`, `scripts/setup/app-local-python.ps1`, `scripts/setup/verify_backend.py`, `scripts/setup/launch_backend.py`, `installer/backend/python-runtime.lock.json` |
| Inno e WebView2 | `installer/AutomacaoNovelis.iss`, `installer/backend/Hub.iss`, `scripts/setup/prepare-webview.ps1` |
| Tauri | `FRONTEND-HUB/src-tauri/src/lib.rs`, `src/backend.rs`, `rust-toolchain.toml` |
| Inicialização automática | `scripts/install-desktop-service.ps1`, `scripts/remove-desktop-service.ps1`, `DESKTOP/automacao_novelis_desktop/process_manager.py`, `root_locator.py` |
| Verificação | `scripts/test-hub-installation.py`, `BACKEND/tests/test_app_local_installer.py`, `BACKEND/tests/test_hub_launcher.py`, `BACKEND/tests/test_hub_service_cleanup.py` |
| Orientação e entrega | Este guia, `docs/backend-bootstrap-recuperacao.md`, `docs/crystal-rdc-msi.md`, `runtime/crystal-tests/delivery.json` |

O projeto WiX e o MSI Crystal 1.0.1 não foram alterados nesta etapa. O novo
instalador incorpora aquele mesmo MSI e seu manifesto já verificado.
