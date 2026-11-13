# Revisão r2: configuração antes da validação da API

[Instalador r2](../runtime/crystal-build/development/installer/NovelisCargoHubSetup-0.1.34-r2-TESTE-NaoDistribuir.exe)
gerado em 12/11/2026: 741.399.625 bytes. SHA-256:
`94138bf7afd5e422537f5d9fc481746388e3f5e33d4cd6c567c1de5592af47f5`.
O [manifesto](../runtime/crystal-build/development/installer/NovelisCargoHubSetup-0.1.34-r2-TESTE-NaoDistribuir.manifest.json)
foi conferido contra o EXE final. Tauri e MSI têm os mesmos hashes da entrega
anterior. O pacote permanece local e privado; não foi publicado no servidor.

A revisão r2 mantém aplicativo/Tauri 0.1.34 e Crystal RDC MSI 1.0.1. Corrige a
ordem de preparação do instalador e os diagnósticos de prontidão. O EXE sem o
sufixo `r2` foi retirado localmente por essa falha.

## Diagnóstico dos arquivos do PC de teste

O `bootstrap.log` comprova Python local, `.venv`, dependências e Chromium
preparados. O `backend-setup.log` registra `Application startup complete` e
Uvicorn escutando em uma porta local. Portanto, a mensagem anterior de que o
backend não iniciou não descrevia corretamente esse resultado.

O defeito confirmado no instalador estava em preparar o `.env` no evento
`ssPostInstall`. O Inno processa os comandos normais de `[Run]` antes desse
evento, conforme seu [código oficial](https://github.com/jrsoftware/issrc/blob/main/Projects/Src/Setup.MainForm.pas).
Logo, a restauração das configurações e o preenchimento de `NOVELIS_SQLITE_PATH`
ocorriam depois de executar a validação do backend.

O `.env` de fábrica tem `NOVELIS_SQLITE_PATH` vazio. Nesse estado, a API básica
inicia normalmente, mas a rota operacional do Hub responde HTTP 503. Essa
combinação foi reproduzida com a API real e explica o mecanismo da falha. O
verificador antigo não registrou o HTTP recebido naquele PC; esse detalhe
específico não pode ser recuperado dos JSONs antigos.

O erro ao abrir o aplicativo após a instalação incompleta também passou a ter
um código próprio: `backend_preparation_incomplete`.

## Correção

`installer/backend/Configuration.iss` contém `PrepareBackendInstallation`,
chamada em `BeforeInstall` da entrada que executa o bootstrap. Ela faz, nesta
ordem:

1. Limpa a marca anterior de preparo do backend.
2. Restaura as configurações preservadas do usuário.
3. Define `CrystalDesignRunTime.Application.11`.
4. Mantém o SQLite configurado ou preenche o caminho padrão quando vazio.
5. Grava as entradas usadas pelo diagnóstico DACTE.

Só então o Python é iniciado. O evento `ssPostInstall` deixou de ser usado para
essa preparação.

O verificador agora distingue servidor encerrado, resposta inválida, identidade
incompatível, erro HTTP e banco operacional não configurado. Registra códigos
e estados em `backend-readiness.json`, sem copiar `.env`, corpos arbitrários de
resposta ou credenciais.

As chamadas internas a `127.0.0.1` usam conexão direta. Isso evita herdar proxy
de ambiente/registro nessas chamadas, como permite a
[API oficial do Python](https://docs.python.org/3.12/library/urllib.request.html#urllib.request.ProxyHandler).
Proxy não foi identificado como causa do incidente; essa é uma proteção adicional
limitada às verificações locais.

## Verificação executada

- 51 casos passaram em `runtime/crystal-tests/hub-r2-validation.log`.
- Instaladores Inno sintéticos reproduziram o evento tardio e comprovaram a
  configuração disponível antes de `[Run]`, incluindo um caminho SQLite já
  definido pelo usuário e o ProgID Crystal correto.
- A API real no diretório isolado iniciou sem SQLite e respondeu HTTP 503 no
  Hub; com SQLite configurado, passou na prontidão. Registros em
  `runtime/crystal-tests/hub-r2-readiness/`.
- O teste de proxy e de diagnóstico sanitizado passou novamente após o último
  ajuste: `hub-r2-final-diagnostics-tests.log`.

Os ensaios usaram arquivos temporários e SQLite local isolado. O instalador
completo e o MSI Crystal não foram executados no computador de desenvolvimento.
O front Tauri recompilado e verificado na entrega anterior é reutilizado.

## Build e uso

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-installer.ps1 `
  -BuildMode development -InstallerRevision r2 `
  -CrystalManifest .\runtime\crystal-build\development\NovelisCrystalRDC-x86-1.0.1.manifest.json
```

O nome de saída é `NovelisCargoHubSetup-0.1.34-r2-TESTE-NaoDistribuir.exe`.
Execute essa revisão no PC de teste, usando a mesma pasta de instalação. As
configurações locais são preservadas e aplicadas antes de verificar a API.

A validação da r2 naquele PC, o DACTE real, SQL, PDF, decodificação do QR/Code 128
e as aprovações de licença/procedência permanecem pendentes. Não publicar para
produção com base nos testes de desenvolvimento.
