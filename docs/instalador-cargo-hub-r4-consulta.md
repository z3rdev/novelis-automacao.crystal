# Revisão r4 privada e diagnóstico da consulta SQL

O [instalador r4 privado](../runtime/private-installer/NovelisCargoHubSetup-0.1.34-r4-PRIVADO-TESTE-NaoDistribuir.exe)
foi compilado e conferido em 12/11/2026, com 741.411.479 bytes e SHA-256
`8f45011d728f808c96a0970a18d6fc5b3cb3985515bce3b918b328c30d0c2937`.
O EXE permanece no diretório privado local. O compartilhamento recebeu o
script de diagnóstico, sem credenciais ou componentes comerciais.

## Evidências do NB-GFR-VIN-05

A execução das 16h01 de 12/11/2026 pulou a atualização SQL, tentou carregar
`FONTE DE DADOS\CONSULTA.xlsx` e encontrou o arquivo ausente. Nas execuções
das 17h00 e 17h01, a conexão apresentou o erro SQL Server 4060 ao abrir
`db_visual_dellmar`.

Às 17h13, o diagnóstico do arquivo ativo do PC de teste passou. Os dois
indicadores de habilitação SQL estavam ativos, o banco foi aberto e as
consultas de metadados das duas fontes foram aceitas. Esse teste executou
`SELECT TOP (0)` e verificou acesso. A consulta completa ainda precisava ser
executada.

Na repetição iniciada às 17h15, o fluxo tentou consultar um dia e recebeu
o erro 596 durante `SQLExecDirectW`. O servidor informou que a sessão estava
em estado de encerramento. O fluxo instalado seguiu para a planilha ausente
e terminou com uma fila vazia marcada como sucesso.

Na reprodução em desenvolvimento, houve uma recusa 4060 e um timeout de
metadados em tentativas distintas. Uma execução posterior da consulta real,
com o tratamento de repetição da r4, retornou oito CTEs para um dia. O teste
foi de leitura e não executou geração de documentos ou abertura de chamados.
O servidor informou versão 16.0.4265.3 e banco ONLINE na consulta de
metadados. A conta utilizada não possui VIEW SERVER STATE.

As evidências estão em `runtime/crystal-tests/physical-pc-20261112/consulta-sql/`
e nos arquivos `runtime/crystal-tests/consulta-sql-*.json`. Os relatórios de
diagnóstico registram indicadores e códigos de erro, sem credenciais.

## Ajustes implementados

- A consulta diária recebe o mesmo tratamento limitado de sessão encerrada
  já utilizado na busca manual. Ao receber 596, fecha a conexão e tenta uma
  vez com outra conexão. A segunda falha é propagada.
- A ausência de uma fonte local utilizável provoca falha explícita. Uma
  consulta válida que retorna zero linhas continua sendo aceita. A seleção
  explícita de um documento de teste continua funcionando.
- A desativação da etapa SQL gera `pendentes.sql_disabled` com os dois
  indicadores de configuração necessários para identificar a opção aplicada.
- O script `scripts/diagnose-consulta-sql.py` verifica a configuração ativa,
  o driver e o acesso SQL com consultas de leitura. As mensagens completas
  do driver são descartadas para evitar exposição de dados de autenticação.
- O manifesto do instalador registra hashes dos fontes de consulta e do
  diagnóstico, permitindo identificar o código utilizado no pacote.

O Inno inclui os arquivos atualizados pelas entradas existentes. A revisão
mantém o perfil operacional privado, o Tauri 0.1.34 e o MSI Crystal RDC 1.0.1.
O pacote fica em `runtime/private-installer`, sujeito às permissões restritas
desse diretório.

Os fontes alterados são `BACKEND/app/data/consulta_db.py`,
`BACKEND/app/automation/flows/pendentes/controles/plan.py`,
`BACKEND/app/automation/flows/pendentes/steps/pendentes.py` e
`scripts/setup/installer_receipt.py`. O diagnóstico foi criado em
`scripts/diagnose-consulta-sql.py`. As regressões foram acrescentadas em
`BACKEND/tests/test_consulta_db.py`, `test_pendentes_sources.py` e
`test_consulta_diagnostic.py`, no mesmo diretório de testes.

## Testes executados

A seleção de regressões terminou com 104 testes aprovados e quatro testes
dependentes da instalação isolada inicialmente ignorados. Esses quatro
testes foram executados em seguida com a instalação isolada e passaram.
Um caso adicional exercitou a entrada normal de execução e comprovou o estado
`failed` quando falta a fonte de consulta, totalizando 109 casos verificados.
Os 18 testes de consulta, fonte e diagnóstico foram repetidos após a revisão
final e passaram. A análise Ruff dos arquivos
de diagnóstico, manifesto e testes alterados passou.

Os logs estão em `runtime/crystal-tests/hub-r4-validation.log`,
`hub-r4-installed-fixture-validation.log`, `hub-r4-query-entry-tests.log`
e `hub-r4-lint.log`, no mesmo diretório. A instalação isolada está na máquina
de desenvolvimento e contém um SQLite local para testes de inicialização.
Os testes dessa instalação não executam fluxos de automação.

## Validação no PC de teste

Instale a r4 na pasta atual utilizando a mesma conta do backend. Execute
Consultar pendentes para um dia e confira os eventos `pendentes.sql_refresh`
e `pendentes.sql_loaded`. Um erro persistente deve terminar em `run.failed`
quando a fonte local também estiver indisponível.

O diagnóstico pode ser executado com o Python da aplicação.

```powershell
$pasta = "$env:LOCALAPPDATA\Programs\Automacao Novelis"
& "$pasta\BACKEND\.venv\Scripts\python.exe" -I `
  "$pasta\scripts\diagnose-consulta-sql.py" --root "$pasta" `
  --output "$pasta\runtime\consulta-sql.json"
```

A homologação da r4 nesse PC permanece pendente até o recebimento dos novos
eventos. A persistência de 596 exige investigar o erro anterior no log do
SQL Server com uma conta que tenha acesso a esse diagnóstico. A repetição
limitada trata uma falha transitória e preserva o erro quando a falha persiste.

Continuam pendentes a homologação DACTE/PDF com decodificação dos códigos,
os cenários de instalação e as aprovações de procedência e redistribuição
do Crystal e dos componentes comerciais. O pacote permanece de teste.
