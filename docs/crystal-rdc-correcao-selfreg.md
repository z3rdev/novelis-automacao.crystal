# Correção do MSI após o teste no PC físico

Atualização: o resultado posterior fornecido pelo usuário confirma
`installed_verified`, retorno MSI 0 e runtime funcional após atualizar 1.0.0 para
1.0.1 no mesmo PC. As observações iniciais abaixo descrevem a falha anterior.

O diagnóstico recebido de `NB-GFR-VIN-05`, em 12/11/2026, mostra processo x86,
SQLOLEDB criado, COM Crystal não criado e ausência dos dois ProgIDs pesquisados.
O editor XI R2 não foi detectado. `functional=false` impede considerar o runtime
pronto, apesar do código de saída 0 informado para a instalação.

O probe antigo só localizava DLLs a partir do registro COM. Com o registro
ausente, `exists=false` e `path=""` não provam ausência física das DLLs.
Também não listava o produto próprio Novelis no filtro de produtos Crystal.
Os resultados recebidos foram preservados, sem alterações, em
`runtime/crystal-tests/physical-pc-20261112/`.

## Defeito identificado no pacote 1.0.0

O MSI contém 46 entradas `SelfReg`, incluindo `craxddrt.dll`, mas sua
`InstallExecuteSequence` não contém `SelfRegModules`. A auditoria anterior
verificava a tabela, sem exigir a ação executável: essa verificação foi insuficiente.
Outras ações de criação/remoção/publicação também estavam ausentes.

A ação [SelfRegModules](https://learn.microsoft.com/en-us/windows/win32/msi/selfregmodules-action)
processa a tabela SelfReg e chama DllRegisterServer. Ter a tabela sem agendar a
ação não realiza esse registro. A falha de empacotamento é compatível com o COM
ausente. O novo probe confirmou os cinco arquivos presentes/carregáveis já na
versão 1.0.0, porém com COM ausente (`0x80040154`); após 1.0.1 o COM foi criado.

O MSI 1.0.0 foi retirado dos testes. O setup Inno anteriormente gerado contém
esse MSI e também deve ser considerado retirado. Os binários anteriores foram
preservados como evidência; não houve substituição silenciosa mantendo a versão.

## Correção 1.0.1

O projeto WiX agora agenda explicitamente:

| Ação | Sequência |
|---|---:|
| UnpublishComponents | 1700 |
| SelfUnregModules | 2200 |
| RemoveRegistryValues | 2600 |
| RemoveFiles | 3500 |
| RemoveFolders | 3600 |
| CreateFolders | 3700 |
| SelfRegModules | 5600 |
| PublishComponents | 6200 |

`InstallFiles=4000`, `WriteRegistryValues=5000` e `InstallFinalize=6600` são
conferidos na auditoria, juntamente com as relações de ordem. Ações inexistentes,
desabilitadas ou fora de ordem bloqueiam a geração do manifesto de sucesso.
O gate de staging e o helper também exigem `audit.execute_sequence_verified=true`.

Os MSMs comerciais, seus hashes, arquivos, GUIDs e configurações não foram
modificados. A mudança é no projeto MSI que os hospeda. Nenhuma DLL foi copiada
ou registrada isoladamente.

Novo artefato: `NovelisCrystalRDC-x86-1.0.1.msi`.
SHA-256: `2c8d0886cf48e3f9479884a0f906ddec52226481fbaba81b52195542cb499080`.
ProductCode: `{292A5FD3-7C11-5197-9685-CBC0CADF4CF5}`.
O UpgradeCode foi mantido para atualizar o produto próprio 1.0.0, se registrado.

O probe atualizado consulta MsiQueryProductState, MsiQueryFeatureState e
MsiGetComponentPath. Assim identifica o produto Novelis, o estado do recurso
CrystalRDC e os caminhos de componentes mesmo sem COM. Falhas COM registram
somente HRESULT, sem a mensagem nativa que poderia conter dados de licença.
Não utiliza Win32_Product nem executa reparação automática.

## Validações desta correção

- Build 1.0.1 e auditoria do MSI concluídos.
- Regressão com o MSI real antigo: rejeitado por ausência das ações obrigatórias.
- Regressão com o novo MSI: sequência aceita, incluindo registro após InstallFiles.
- 70 testes relacionados passaram.
- O trecho real de integração Inno foi recompilado com o MSI 1.0.1.
- O instalador Inno principal também foi recompilado com o MSI 1.0.1. A
  compilação passou; o novo setup ainda não foi executado no PC de teste.
- Probe atualizado executado na estação de desenvolvimento. Esse teste não
  instala o novo MSI nem substitui a verificação no PC físico.

Logs: `runtime/crystal-tests/msi-sequence-regression.json`,
`pytest-selfreg-fix.log`, `inno-selfreg-fix.log`, `inno-main-101-compile.log` e
`physical-pc-20261112/analysis-and-fix.json`.

O novo setup está em
`runtime/crystal-build/development/installer/AutomacaoNovelis-CrystalRDC-1.0.1-TESTE-NaoDistribuir.exe`.
O recibo `runtime/crystal-tests/inno-main-101-artifact.json` registra tamanho,
SHA-256 e o MSI incorporado. O build usou fontes do backend/RPT e os binários e
caches existentes; não recompilou npm ou PyInstaller. Apenas no modo de
desenvolvimento, usa compressão ZIP para reduzir o tempo de compilação.
O EXE anterior, que incorpora o MSI 1.0.0, continua retirado.

## Reteste confirmado no PC físico

O resultado fornecido pelo usuário, preservado em
`runtime/crystal-tests/physical-pc-20261112/install-1.0.1.json`, confirma:

- `installed_verified`, `msi_exit_code=0` e `exit_code=0`.
- Antes: produto 1.0.0 instalado, arquivos presentes/carregáveis, COM ausente
  com `0x80040154` e `functional=false`.
- Depois: produto 1.0.0 ausente e produto 1.0.1 instalado, com recurso CrystalRDC
  local. A atualização 1.0.0 → 1.0.1 passou na verificação do runtime.
- `CrystalDesignRunTime.Application.11` criado em processo de 32 bits.
- As cinco DLLs verificadas existem, carregam em x86 e têm versão 11.5.0.313.
- SQLOLEDB x86 criado e editor XI R2 não detectado.

A identidade deste teste foi `NB-GFR-VIN-05\user`. O usuário informou que o PC
possui apenas o runtime Crystal; ainda não há backend instalado. Portanto,
não houve teste real do DACTE, conexão SQL, AddPictureObject ou exportação PDF
nesse PC. `rcapi_export_tested=false` e `production_ready=false` foram mantidos.

Esse teste comprova a atualização do runtime já presente em 1.0.0. Não substitui
a instalação direta de 1.0.1 em uma imagem sem produto/arquivos anteriores, nem
os testes de reparação, reinstalação, reinicialização, conta/sessão real do backend
e coexistência.


## Procedimento usado no reteste do runtime

Transferir o MSI 1.0.1 e extrair `Kit-teste-RDC-1.0.1.zip` na mesma pasta
`C:\Users\user\Documents\TESTE`. O ZIP contém apenas scripts próprios e o
manifesto, sem o MSI, MSMs, DLLs comerciais ou valor da chave.

No PowerShell como administrador, **no PC de teste**:

```powershell
$pasta = 'C:\Users\user\Documents\TESTE'
powershell -NoProfile -ExecutionPolicy Bypass `
  -File "$pasta\install-crystal-runtime.ps1" `
  -ManifestPath "$pasta\NovelisCrystalRDC-x86-1.0.1.manifest.json" `
  -AllowDevelopment -ProbeDirectory $pasta `
  -ResultPath "$pasta\resultado-instalacao-1.0.1.json"
```

O helper aplica o MSI e valida novamente COM, versões, arquitetura e carregamento.
Não usar regsvr32 manual, não copiar DLLs e não ativar `/L*v` para esse teste.
O arquivo JSON informa a etapa e o código de saída. `installed_verified` confirma
somente as verificações do runtime; DACTE real/SQL/AddPictureObject/PDF/códigos,
conta real do backend, reparação, reinstalação, reboot e coexistência continuam
dependendo de homologação.

## Próximo teste: instalar backend e abrir o RPT

Atualização: depois desta orientação, o usuário forneceu logs da aplicação
instalada no PC de teste. A preparação do Python falhou e a `.venv` não foi
criada. O backend não abriu a porta 8000. Antes de repetir o teste abaixo,
seguir [a coleta e recuperação do bootstrap](backend-bootstrap-recuperacao.md).
O sucesso anterior do runtime Crystal não equivale à preparação do backend.

Como o usuário confirmou que há somente o runtime no PC, transferir o novo
setup integrado de teste para esse PC e executá-lo com a conta que usará a
aplicação. Ele inclui backend, RPT e o pré-requisito 1.0.1. O runtime já
funcional deve ser reconhecido pelo probe, sem reinstalação desnecessária.
A instalação completa e seu bootstrap ainda precisam ser verificados nesse PC.
O agente não publicou nem copiou o setup para compartilhamentos.

Após instalar, no PowerShell da conta do teste, considerando a pasta padrão:

```powershell
$instalacao = Join-Path $env:LOCALAPPDATA 'Programs\Automacao Novelis'
powershell -NoProfile -ExecutionPolicy Bypass `
  -File "$instalacao\scripts\prepare-dacte.ps1" -NoDatabase
```

Se outra pasta foi escolhida, ajustar `$instalacao`. O diagnóstico fica em
`$instalacao\runtime\installation\dacte-diagnostic.json`, com relatório HTML
na mesma pasta. Essa etapa verifica o ambiente local sem consultar SQL. Se
faltarem fontes ou a configuração do banco, o estado pode continuar pendente;
isso não invalida o reteste do runtime já concluído.

Configurar SQL localmente antes do teste real; não enviar senhas nem copiar o
`.env` da estação de desenvolvimento. O RPT usa `IDAutomationSC128L DEMO`, cuja
presença e licença continuam pendentes no PC de teste. O MSI Crystal não
fornece essa fonte. PDF, QR e Code 128 só serão aprovados após gerar o DACTE
real e comparar os dados decodificados com o XML de referência, sob a conta e
sessão efetivas do backend.

Licenciamento e procedência permanecem pendentes. O novo pacote é restrito ao
teste autorizado e continua com `production_ready=false`.
