# Backend ausente no PC de teste — 12/11/2026

**Fluxo atual:** [instalador integrado do Cargo Hub](instalador-cargo-hub.md), com
front novo Tauri e Python próprio. Os kits descritos abaixo são histórico do
diagnóstico; não são o procedimento de entrega da nova versão.

Os logs fornecidos do PC `NB-GFR-VIN-05` mostram que o bootstrap chamou o
instalador Python, mas não encontrou o executável no destino
`%LOCALAPPDATA%\AutomacaoNovelis\python312\python.exe`. A `.venv` não foi
criada e o backend não iniciou; as recusas na porta 8000 são consequência.
A coleta `20261112T140041077Z` confirmou retorno 1603 na desinstalação anterior,
seguido de retorno 0 em uma alteração que não reinstalou os arquivos.

Evidências preservadas em
`runtime/crystal-tests/physical-pc-20261112/backend-failure/`:
`stack-start.log` e `desktop-console.txt`. A verificação anterior do runtime
Crystal 1.0.1 continua registrada separadamente. Esses logs não demonstram
falha de COM nem invalidam aquele resultado.

## Diagnóstico confirmado pela coleta

- A conta `NB-GFR-VIN-05\user` tem Python 3.12 registrado na pasta própria da
  aplicação, nas duas visões de registro, mas sem `python.exe` e sem `.venv`.
- O bundle Python tentou remover `pip_JustForMe` e falhou com `0x80070643`
  (retorno 1603). O bootstrap registrou o erro e continuou.
- O código antigo chamava a limpeza manual da pasta Python após essa falha.
  O log não comprova quais arquivos ainda existiam no momento da limpeza.
- A chamada seguinte entrou em `ActionLikeInstallation=Modify`. O bundle
  considerou `core_JustForMe` e `exe_JustForMe` presentes, com `execute: None`,
  e terminou com 0. Esse retorno não restaurou os arquivos ausentes.

O erro interno que fez a remoção do pip falhar e a causa inicial da ausência
dos arquivos não foram estabelecidos por essa coleta. O defeito confirmado no
nosso fluxo é ignorar a desinstalação malsucedida, fazer limpeza de arquivos e
esperar restauração de uma chamada normal em modo Modify.

Evidências originais: subpasta `20261112T140041077Z/` do diretório acima.
Análise estruturada: `runtime/crystal-tests/python-repair-analysis.json`.

## Resultado da reparação r2 e correção r3

A coleta `20261112T142506734Z` comprova que o bundle executou Repair e retornou
0, restaurando o interpretador. O bootstrap detectou em seguida `No module
named pip`, interrompeu corretamente a preparação e manteve a `.venv` ausente.
O MSI `pip_JustForMe` pulou `SetUpdatePipCommandLine` e `UpdatePip` por condição
falsa; reparar o produto MSI não recriou o módulo pip nesse estado.

O novo fluxo r3 usa `python -I -m ensurepip --upgrade --default-pip` quando o
interpretador próprio responde, mas pip não. O `ensurepip` usa os componentes
incluídos no Python, sem acesso à internet, conforme a
[documentação oficial](https://docs.python.org/3.12/library/ensurepip.html).
Depois exige novamente Python compatível e pip funcionais. Isso também evita
reexecutar o bundle inteiro quando somente pip precisa de recuperação.

O relatório mostra ainda invocações do bundle sobrepostas, com um retorno
`-2147023274` (`0x80070656`, Win32 1622: erro ao abrir log). O conflito no mesmo
arquivo é compatível com a sobreposição observada, sem prova independente de
que foi a única causa do erro. A r3 obtém um bloqueio exclusivo em
`runtime/bootstrap.lock` antes de abrir transcrição ou alterar o resultado.
Outra preparação aguarda até 600 segundos; encerrar o processo libera o bloqueio.

Um log filho da tentativa de remoção das 11:20 também explica o 1603 dessa
tentativa: `LaunchConditions` não detectou uma instalação Python 3.12. Esse
arquivo não corresponde ao log filho original das 10:38.

Evidências preservadas na subpasta `20261112T142506734Z/`. A análise atual está
em `runtime/crystal-tests/python-pip-repair-analysis.json`. A recuperação r3
no PC de teste continua pendente; o runtime Crystal não foi alterado.

## Mudanças implementadas

- `scripts/bootstrap.ps1` registra a etapa, resultado e código final em
  `runtime/bootstrap-result.json`, com transcrição em `runtime/bootstrap.log`.
  Valida imports das dependências antes de informar sucesso.
- O conjunto offline de wheels exige CPython 3.12 x64; interpretadores de
  outras versões ou x86 são recusados nessa modalidade. Essa verificação é
  preventiva, não uma causa comprovada para o erro recebido.
- O bootstrap usa `/repair` do instalador oficial para uma instalação
  registrada nas pastas exatas pertencentes à aplicação. Preserva os arquivos
  existentes e não executa desinstalação automática. Registro fora dessas
  pastas com Python indisponível interrompe a operação.
- O instalador Python 3.12.10 x64 é conferido por SHA-256 antes de executar:
  `67b5635e80ea51072b87941312d00ec8927c4db9ba18938f7ad2d27b328b95fb`.
  O cache coincidiu com o digest publicado em python.org e apresentou
  Authenticode válido da Python Software Foundation. A assinatura Sigstore
  não foi verificada criptograficamente por esta comparação de digest.
- Retorno 0/3010 do bundle exige depois executar Python compatível e pip.
  Falha interrompe a preparação e preserva os arquivos para diagnóstico.
- Se somente pip falta no Python próprio, recupera-o com `ensurepip` antes
  de recorrer novamente ao bundle. Serializa execuções do bootstrap para
  proteger a instalação, seus logs e o resultado compartilhado.
- `scripts/setup/bootstrap-state.ps1` concentra a escrita dos resultados.
  O empacotador de servidor também passou a incluir esse helper requerido pelo
  bootstrap. O pacote de servidor publicado não foi regenerado nesta etapa.
- `scripts/run-dev.ps1` interrompe ao receber erro do bootstrap e aponta seus
  logs. Não repete a mesma tentativa antes de substituir o erro por ausência
  da `.venv`.
- `installer/backend/Preparation.iss` exige um marcador de conclusão novo e
  o executável da `.venv`. Em caso de falha, bloqueia DACTE, serviço e abertura
  automática, informa instalação incompleta e retorna código 20. O integrador
  não interpreta apenas o término do processo como sucesso.
- `scripts/repair-backend.ps1` coleta os logs específicos do Python e do
  bootstrap. Em modo de reparação, preserva cópias anteriores dos scripts,
  aplica somente os scripts próprios atualizados e executa o bootstrap em
  PowerShell de 64 bits. Inclui agora os logs internos dos MSIs do Python.

Os callbacks e o código de saída personalizado seguem a documentação do
[Inno Setup](https://jrsoftware.org/ishelp/topic_scriptevents.htm) e dos
[parâmetros BeforeInstall/AfterInstall](https://jrsoftware.org/ishelp/topic_scriptinstall.htm).
A instalação silenciosa do Python mantém os parâmetros documentados pelo
[CPython 3.12](https://docs.python.org/3.12/using/windows.html#installing-without-ui).
A [documentação de Repair](https://docs.python.org/3.12/using/windows.html#modifying-an-install)
prevê restaurar arquivos removidos/modificados. O parâmetro `/repair` é
processado pelo [engine Burn](https://github.com/wixtoolset/wix3/blob/develop/src/burn/engine/core.cpp),
e a ação é suportada pelo
[bootstrapper CPython 3.12.10](https://github.com/python/cpython/blob/v3.12.10/Tools/msi/bundle/bootstrap/PythonBootstrapperApplication.cpp).

## Kit corrigido r3

O ZIP `runtime/crystal-tests/Kit-recuperacao-backend-20261112-r3.zip` contém apenas
scripts próprios, sem MSI, MSMs, DLLs Crystal, chave, credenciais ou `.env`.
O kit anterior foi retirado porque continha o bootstrap com o fluxo defeituoso.
Uma cópia dos scripts r3 foi disponibilizada e conferida em
`\\192.168.254.250\arquivos ti\teste\Recuperacao-backend-r3`.

Para uma nova coleta sem reparação, no PC de teste:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File '\\192.168.254.250\arquivos ti\teste\Recuperacao-backend-r3\repair-backend.ps1' `
  -CollectOnly
```

A pasta instalada é obtida do registro da conta atual. Para outra pasta,
acrescentar `-InstallationRoot 'C:\caminho\da\instalacao'`. A identificação
exige o marcador próprio e `BACKEND\pyproject.toml`, antes de gravar arquivos.

O modo de coleta preserva os logs existentes e cria um ZIP em
`<instalacao>\runtime\backend-recovery\`. A saída `RECOVERY_REPORT=` contém o
caminho exato. Esse ZIP preserva as evidências da preparação do Python.
A coleta não executa o instalador nem altera os scripts.
Não coleta `.env`, KEY-CR2.txt ou logs de instalação Crystal.

## Reparação controlada

Após fechar a aplicação e preservar os logs, o mesmo kit permite:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File '\\192.168.254.250\arquivos ti\teste\Recuperacao-backend-r3\repair-backend.ps1'
```

O modo de reparação pode instalar Python e dependências do backend. Usa o cache
local quando disponível. Se esse cache faltar, o bootstrap pode recorrer aos
downloads já previstos no projeto. Não aplicar em computadores de terceiros.
`RECOVERY_STATUS=backend_prepared` confirma que o bootstrap concluiu a criação
do ambiente; não comprova conexão SQL, backend atendendo, DACTE ou homologação.
Se falhar, o ZIP inclui os logs anteriores e posteriores, mantendo a causa
original disponível mesmo que o instalador sobrescreva seu próprio log.

Após a preparação passar, abrir a aplicação e executar o diagnóstico sem SQL:

```powershell
$instalacao = (Get-ItemProperty 'HKCU:\Software\AutomacaoNovelis').InstallRoot
powershell -NoProfile -ExecutionPolicy Bypass `
  -File "$instalacao\scripts\prepare-dacte.ps1" -NoDatabase
```

Os testes locais e recibos estão consolidados em
`runtime/crystal-tests/delivery.json`. Os testes isolados na estação de
desenvolvimento não comprovam instalação Python no PC de teste. O reparo
nesse PC, o SQL, o DACTE real, os dados decodificados, o licenciamento e a
procedência continuam pendentes até haver evidência própria.

## Verificações executadas

- 42 testes relacionados passaram, incluindo detecção do Python compatível com os wheels,
  marcador de sucesso antigo substituído por falha, coleta sem `.env` e recusa
  de pasta de instalação não identificada.
- Regressões adicionais cobrem reparação oficial com retorno 1603, retorno 0
  sem arquivos, pip inválido, registro fora das pastas próprias, instalação
  inicial e integridade do instalador. Os arquivos anteriores são preservados
  nos cenários simulados. A coleta dos logs filhos também passou em teste próprio.
- A ausência real de pip foi reproduzida em um ambiente isolado criado com
  `venv --without-pip`. O helper restaurou pip com `ensurepip` e passou na
  execução repetida. O teste de exclusão mútua confirmou que outro processo
  aguarda a liberação do arquivo antes de continuar.
- Um instalador Inno sintético, contendo somente fixtures próprias, foi
  compilado e executado. A etapa dependente rodou no sucesso; foi bloqueada
  tanto em falha declarada como em encerramento sem marcador, com retorno 20.
  Esse teste não executa Crystal nem registra tarefa de backend.
- O bootstrap completo criou uma `.venv` nova em pasta isolada com espaços e
  instalou as dependências a partir do wheelhouse empacotado. Os imports
  passaram e o Chromium existente foi reconhecido. A estação já possuía
  Python 3.12 x64; o instalador Python não foi executado nesse ensaio.
- O setup principal foi recompilado com a reparação oficial do Python, o
  tratamento de falha e o mesmo MSI Crystal 1.0.1. Não foi instalado pela automação.
- O probe real do Python 3.12 x64 e pip existentes passou. A função de
  integridade aceitou o instalador oficial em cache. Nenhuma reparação Python
  nativa foi executada na estação de desenvolvimento.

Novo artefato local restrito:
`runtime/crystal-build/development/installer/AutomacaoNovelis-CrystalRDC-1.0.1-bootstrap4-TESTE-NaoDistribuir.exe`.
O recibo `runtime/crystal-tests/inno-main-bootstrap4-artifact.json` contém
tamanho e SHA-256. Logs: `pytest-bootstrap-recovery.log`,
`pytest-python-repair.log`, `pytest-python-pip-repair.log`,
`bootstrap-isolated-console.log` e `inno-main-pip-lock-compile.log` na pasta
`runtime/crystal-tests/`.

A compilação não comprova que a reparação Python passará no PC de teste.
Os EXEs anteriores com o bootstrap defeituoso foram retirados dos testes.
O MSI Crystal 1.0.1 permanece o mesmo; o defeito tratado aqui é do bootstrap Python.
O setup contém componentes Crystal restritos e permanece sem aprovação de
redistribuição; somente o kit de scripts próprios foi colocado no compartilhamento.
