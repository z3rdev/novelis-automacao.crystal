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
`scripts\build-hub-desktop.ps1`. Na instalação, o Tauri prepara e inicia o
backend local pelo inicializador incluído no pacote.

## Bandeja e início com o Windows

O Cargo Hub mantém um ícone na área de notificação do Windows. O botão X
oculta a janela e mantém o backend e os agendamentos ativos. Um clique no
ícone reabre a janela. O menu do ícone oferece Abrir Cargo Hub e Sair do
Cargo Hub. Abrir novamente o executável recupera a instância existente.

Em Configurações e diagnóstico, a opção Iniciar com o Windows registra a
inicialização na conta Windows atual, com o argumento `--background`.
Ela começa desativada em uma instalação nova. O instalador preserva uma
inicialização automática já habilitada e migra o serviço legado para o
aplicativo nativo. O início ocorre ao entrar nessa conta Windows.

Na instalação, o backend iniciado pelo aplicativo acompanha a identidade
do processo Tauri. Ao sair pelo menu da bandeja, esse backend encerra suas
tarefas de forma controlada. Um backend iniciado separadamente para
desenvolvimento mantém seu próprio ciclo de vida. O menu padrão de contexto
do WebView2 é desativado no aplicativo nativo.

As verificações automatizadas cobrem a interface, o transporte dos avisos e
o encerramento de um backend real quando seu processo pai termina. O teste
de uma sessão Windows nova e a homologação de instalação limpa permanecem
necessários antes da distribuição.

## Notificações e agendamentos do operador

A Central de notificações aparece no menu Desenvolvimento com `CONFIG.dev` e
`credentials.json` presentes e `DEVMODE=1`. O desenvolvedor publica título,
mensagem, prioridade e expiração opcional. Os avisos usam o mesmo MinIO das
atualizações, em `z3-releases/cargo-hub/notifications/`. Cada aviso tem um
objeto em `records/`; o encerramento grava um marcador em `archived/`.
O catálogo de até 200 avisos fica em `feed.json` e é consultado a cada
20 segundos, inclusive com a janela oculta na bandeja.

O backend do desenvolvedor usa as credenciais locais para publicar e
sincronizar. Os computadores dos operadores tentam ler o catálogo por
HTTPS e podem consumir o cache no SQLite compartilhado quando essa leitura
estiver indisponível. No servidor atual, o acesso anônimo retorna HTTP 403.
O cache permite que os clientes da rede recebam os avisos sem a chave de
publicação. Uma instalação sem acesso ao cache exige permissão de leitura
do catálogo no servidor. A aplicação não altera a política do bucket.

O sino abre o modal de leitura. A confirmação é registrada por conta Windows,
no SQLite compartilhado, e o encerramento de um aviso preserva seu histórico.
A migração dos avisos existentes mantém seus identificadores e confirmações.

Agendamentos ficam no menu Operação. Cada rotina configura nome, horário local,
dias da semana, tipo de execução e quantidade de dias anteriores incluídos.
O valor 0 consulta hoje. O valor 2 inclui anteontem, ontem e hoje. Os tipos
disponíveis são consulta e verificação, somente PDFs e fluxo completo.

As rotinas pertencem à conta Windows e ao computador onde foram salvas.
O backend precisa estar ativo nessa conta. A verificação ocorre a cada 15
segundos. Uma rotina já habilitada pode executar ao reabrir o backend depois
do horário no mesmo dia. Uma rotina criada ou reativada após seu horário
começa na próxima data selecionada. Cada rotina inicia uma vez por dia,
aguarda uma automação em andamento e registra o resultado no banco.
Uma ocorrência interrompida por reinício fica identificada no histórico.

O backend abre uma sessão de auditoria identificada pelo nome do operador
com o sufixo `(agendado)` para cada execução automática. A configuração
persiste no SQLite compartilhado com escopo por dispositivo e conta.

Atualizações, conexão e data dos dados ficam no rodapé da barra lateral.
O cabeçalho reúne as notificações e a identificação do operador à direita.

O menu Desenvolvimento também inclui Usuários e dispositivos, com inventário,
sessões e estado da automação no SQLite compartilhado dos logs. A atividade
continua sendo registrada com a janela na bandeja. Os critérios de conexão
e os limites do inventário estão em [developer-monitor.md](developer-monitor.md).

## Consulta por período e relatório compartilhado

A consulta por período do Cargo Hub exige uma consulta SQL atualizada.
Uma falha nessa etapa é apresentada diretamente e permite diagnosticar
a conexão do computador. O fluxo de entrada manual continua disponível
para listas e planilhas explicitamente selecionadas.

O relatório Novelis usado na verificação de CT-es já existentes fica em
`\\192.168.254.250\rede\Publico\AUTOMAÇÃO-CTE\FONTE-DADOS\RELATORIO-NOVELIS`,
nos arquivos `relatorio_cte.xlsx` e `relatorio_cte.json`. Esses caminhos
aparecem em Configurações e diagnóstico, junto aos destinos dos documentos.
O relatório reúne o histórico de chamados e participa da verificação dos
resultados da consulta SQL.
