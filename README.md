# Automacao Novelis

Aplicacao local para evoluir o projeto **Automation Auditoria CTE Ocorrencia** com backend Python, frontend React e Playwright.

## Objetivos

- Separar backend e frontend.
- Manter a automacao Playwright no backend local.
- Expor configuracao, execução e eventos ao vivo via API.
- Permitir configurar e visualizar passos direto no navegador.
- Evitar arquivos grandes: cada modulo deve ficar abaixo de 500 linhas.
- Preparar a base para modo instalador Windows.

## Estrutura

```text
BACKEND/     API FastAPI, servicos Playwright e orquestracao
FRONTEND/    React/Vite com dashboard e configurador de passos
scripts/     Bootstrap e execução local no Windows
docs/        Decisoes tecnicas e regras do projeto
runtime/     Arquivos gerados em execução (ignorado pelo Git)
```

## Primeiro uso

Python ainda precisa estar instalado na maquina. Depois:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run-dev.ps1
```

## App desktop

Abrir a tela local:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\desktop-app.ps1
```

Gerar executavel com a versao atual do projeto:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-desktop.ps1
```

Se ja tiver a versao local e quiser gerar o executavel, o atalho e instalar o agendador persistente na mesma passada:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-app.ps1 -InstallService
```

Instalar dependencias, atalho e agendador persistente:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-app.ps1 -InstallService
```


powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\publish-update.ps1 -Version 0.1.25 *> .\runtime\publish-0.1.25.log


Parar ou remover o agendador:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\stop-desktop-service.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\remove-desktop-service.ps1
```

Frontend:

```powershell
cd FRONTEND
npm install
npm run dev
```

Backend:

```powershell
cd BACKEND
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Legado

O projeto antigo fica em:

```text
C:\Users\joao.barbosa\Documents\AUTOMATION - AUDITORIA CTE - OCORRENCIA
```

O `.env` real do legado fica localmente em `BACKEND/.env` e esta ignorado pelo Git. O `.env.example` foi sanitizado para nao versionar senhas.

Fluxos expostos pelo backend:

- `integrado`
- `pre-passo`
- `tarifario`
- `gnre`
- `novelis`

## PDF de DACTE sem abrir o Rodopar

O backend oferece consulta direta ao banco e exportacao pelo RPT do Crystal,
alem da rota alternativa por XML. Rotas e verificacoes: [API DACTE](docs/crystal-dacte-api.md).
Preparacao de componentes, licencas e instalador: [instalacao DACTE](docs/dacte-installer.md).
