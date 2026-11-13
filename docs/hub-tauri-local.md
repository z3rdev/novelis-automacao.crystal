# Novelis Cargo Hub: backend local e SQLite compartilhado

Cada computador executa seu proprio backend Python/FastAPI em
`http://127.0.0.1:8000`. O aplicativo Tauri se conecta a essa API local.
O arquivo SQLite fica em:

```text
\\192.168.254.250\rede\Publico\novelis-automacao\novelischamado.sqlite
```

O servidor compartilha o arquivo. Ele nao precisa executar a API.
SQL, Crystal, impressao de PDF e Playwright continuam no computador do operador.

## Inicializacao em cada computador

1. Mantenha o projeto em uma pasta local, com Python 3.11 ou superior.
2. Prepare as dependencias com `scripts\bootstrap.ps1 -SkipFrontend`.
3. Configure `BACKEND\.env` com as credenciais e os caminhos dessa maquina.
4. Prepare Crystal x86, ODBC e impressora PDF conforme `dacte-installer.md`.
5. Abra `INICIAR-BACKEND.cmd` ou execute:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-local-backend.ps1
```

O comando inicia somente em `127.0.0.1:8000`, sem reload e com um worker.
Os logs de inicializacao ficam em `runtime\logs\backend-local`.
O inicializador avisa se a porta estiver ocupada por um backend antigo.
Nao encerra automaticamente outro processo.

## Cancelamento da execucao

Ao clicar em Parar, o estado passa para Parando. O backend interrompe os proximos
itens, solicita o cancelamento do cursor SQL e encerra o processo Crystal que
foi iniciado pela execucao. Uma leitura de rede ja entregue ao Windows pode
precisar retornar antes de encerrar; enquanto isso, outra execucao fica bloqueada.
Cancelada so e exibido depois de finalizar as tarefas e fechar os recursos.
Arquivos ja gerados antes da parada sao preservados.

As etapas da interface acompanham o estado final, sem manter Executando depois
do cancelamento. Os paineis adaptam as colunas a largura de sua propria secao.
A rolagem automatica do monitor fica limitada ao quadro de logs.

A configuracao persistente do banco em `BACKEND\.env` e:

```dotenv
NOVELIS_SQLITE_PATH=\\192.168.254.250\rede\Publico\novelis-automacao\novelischamado.sqlite
```

A falta de acesso a pasta de rede impede a inicializacao; nao e criado outro
banco vazio em uma pasta local. Cada usuario Windows precisa conseguir abrir
a pasta e criar/alterar os arquivos de banco, trava e journal nela.

## Concorrencia e separacao por computador

- O arquivo usa journal DELETE, synchronous FULL e busy timeout.
- Uma trava de arquivo e adquirida por operacao e liberada apos fechar a conexao.
  Outros backends aguardam ate 30 segundos por essa trava.
- Nao existe mais uma trava que exige manter apenas um backend aberto.
- Execucoes, eventos, preferencias e plano de pendencias identificam a maquina.
  Reiniciar um computador nao marca a execucao de outro como falha.
- Os snapshots de chamados e o historico importado permanecem compartilhados.
- A rotina legada de verificacao de duplicidade e os JSONs foram preservados;
  a importacao inicial nao representa uma migracao integral dessa rotina.

SQLite em compartilhamento depende da implementacao de sincronizacao e travas
SMB. Estas medidas reduzem a concorrencia no arquivo, mas nao garantem o mesmo
comportamento de um disco local diante de falhas de rede. WAL nao deve ser usado
entre computadores diferentes. Referencias oficiais:
[SQLite em rede](https://www.sqlite.org/useovernet.html) e
[restricoes do WAL](https://www.sqlite.org/wal.html).

## Frontend e Tauri

O front baixado esta em `FRONTEND-HUB`. A interface antiga em `FRONTEND` permanece
preservada. Para desenvolver:

```powershell
cd FRONTEND-HUB
npm ci
npm run dev:desktop
```

A previa fica em `http://127.0.0.1:1420`, usando
`http://127.0.0.1:8000/api/hub`. Enderecos centrais salvos pela versao anterior
sao ajustados para o endereco local ao abrir essa versao.

```powershell
npm run build:desktop
npx tsc --noEmit
npm test
```

O build estatico fica em `FRONTEND-HUB/dist-desktop`.
O modo Demonstracao continua separado dos dados reais.
O visualizador recebe o PDF real pela API do proprio computador.
A geracao de DACTE usa banco/Crystal; Rodopar continua desabilitado.
Destinos de documentos, reaproveitamento e certificado SEFAZ estao descritos em
[sefaz-documentos.md](sefaz-documentos.md).

Para compilar o executavel Tauri, instale Rust MSVC, Visual Studio Build Tools
com MSVC x64/x86 e Windows SDK, e WebView2. Depois execute
`scripts\build-hub-desktop.ps1`. O instalador do novo cliente e a inicializacao
automatica do Python pelo Tauri ainda fazem parte da integracao desktop.
