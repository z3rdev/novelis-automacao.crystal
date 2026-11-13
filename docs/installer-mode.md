# Modo Instalador

O modo instalador fica fora do dominio da automacao. Ele prepara dependencias,
gera o executavel desktop e registra o agendador persistente da sessao do
usuario.

## Componentes

- `DESKTOP/`: app Python com tela local e worker de agendamento.
- `scripts/install-app.ps1`: instala dependencias, builda o front e gera atalho.
- `scripts/build-desktop.ps1`: gera `dist/desktop/AutomacaoNovelis.exe`.
- `scripts/install-desktop-service.ps1`: registra a tarefa persistente.
- `scripts/stop-desktop-service.ps1`: encerra a tarefa persistente.
- `scripts/remove-desktop-service.ps1`: remove a tarefa persistente.
- `runtime/desktop-settings.json`: configuracoes protegidas por senha.
- `runtime/desktop-service.log`: log do agendador.

## Instalacao

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-app.ps1 -InstallService
```

Senha inicial das configuracoes: `admin`.

## Restricao operacional

Automacao visual com navegador aberto deve rodar na sessao do usuario. Por isso
o projeto usa uma tarefa persistente do Windows em vez de um servico Windows
puro. Servico Windows puro pode nao ter desktop interativo nem acesso aos mesmos
compartilhamentos de rede.
