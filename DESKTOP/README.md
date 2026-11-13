# Desktop Automação Novelis

Camada local em Python para operar a automação fora do navegador.

## Executar em desenvolvimento

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\desktop-app.ps1
```

Senha inicial das configurações: `admin`.

## Serviço persistente

Este projeto usa uma tarefa persistente do Windows na sessão do usuário. Isso evita o problema de serviço Windows sem desktop interativo, já que Rodopar, Sefaz e Novelis precisam abrir navegador/janelas.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-desktop-service.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\stop-desktop-service.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\remove-desktop-service.ps1
```

Ao instalar, o script prepara o `.venv` se necessário, gera o executável se ele ainda não existir, cria o atalho do app e inicia a tarefa persistente. Quando a tarefa inicia, ela também sobe backend e frontend locais.

Logs: `runtime\desktop-service.log`.

## Instalador

O instalador oficial é gerado com Inno Setup:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-installer.ps1
```

O instalador:

- mostra a versão instalada e permite alterar o caminho de instalação;
- usa `%LOCALAPPDATA%\Programs\Automacao Novelis` como caminho padrão;
- leva o instalador do Python e cria um Python local em `runtime\python312`;
- instala o runtime Visual C++ necessário para o `python312.dll`;
- sobe o frontend instalado pelo `FRONTEND\dist`, sem precisar de Node no PC;
- encerra app, backend, frontend e tarefa persistente antes de atualizar;
- limpa a instalação anterior marcada como Automação Novelis;
- recria os atalhos para apontar para a versão nova.

## Atualizações

O app desktop verifica atualizações a cada 20 segundos na pasta padrão da rede. Use o script de publicação, porque ele monta o UNC com caracteres especiais de forma segura:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\publish-update.ps1
```

O manifesto publicado fica neste formato:

```json
{
  "version": "0.1.24",
  "title": "Nova versão Automação Novelis",
  "notes": "Resumo da atualização.",
  "installer": "AutomacaoNovelisSetup-0.1.24.exe"
}
```

Se não houver manifesto, o app usa o arquivo mais recente da pasta como sinal de atualização.
