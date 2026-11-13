# Entrega técnica — Crystal RDC x86 — 12/11/2026

> Atualização após o teste no PC NB-GFR-VIN-05: a versão 1.0.0 e o setup que a incorpora foram retirados dos testes. O MSI omitia SelfRegModules na sequência executável. A atualização para 1.0.1 foi executada pelo usuário e passou na verificação do runtime x86, sem editor XI R2 detectado. O DACTE real nesse PC continua pendente. Consulte [a análise da correção](crystal-rdc-correcao-selfreg.md). O restante deste documento preserva a entrega inicial.

Foi produzido um MSI **de teste** do RDC 11.5.0.313 x86, com os quatro merge
modules inventariados e sem o editor completo. Não foi instalado nesta estação,
pois ela já possui Crystal completo e runtime de outro aplicativo. Não houve
publicação, envio a terceiros, commit de chave ou redistribuição dos componentes.

Artefatos locais, ignorados pelo Git:

- [MSI de teste](../runtime/crystal-build/development/NovelisCrystalRDC-x86-1.0.0.msi).
- [Manifesto e auditoria estrutural](../runtime/crystal-build/development/NovelisCrystalRDC-x86-1.0.0.manifest.json).
- [Consolidação dos resultados](../runtime/crystal-tests/delivery.json).
- [Procedimento completo de build e homologação](crystal-rdc-msi.md).

MSI SHA-256: `1e3cb5352e22e656fa1a171d0d7738ff1977bfcede3bf6b3e2eb6eac7cbfcbdb`.
Tamanho: 54.759.424 bytes. ProductCode da versão 1.0.0:
`{91BD5684-A33F-516A-996C-38D91FBF0A02}`.

O MSI contém a propriedade de licença exigida pelo módulo: é um artefato
restrito, mesmo com PIDKEY oculto nos logs e ausente dos fontes. Não publicar.

## Verificações executadas

| Verificação | Resultado | Evidência local |
|---|---|---|
| SHA-256 dos quatro MSMs | Coincidem com inventário | Manifesto MSI e `modules.lock.json` |
| Build WiX e auditoria MSI | Passou: 1.246 arquivos, seis DLLs principais 11.5.0.313, sem Win64 ou crw32.exe | Manifesto MSI |
| ADO/PDF e COM no MSI | Propriedades ADO/PDF = 1; SelfReg original de craxddrt preservado | Manifesto MSI |
| PIDKEY | Campo autorizado configurado; propriedades Hidden; valor omitido | Manifesto e `security-audit.json` |
| Testes automatizados | 64 passaram; um aviso de dependência Starlette | `runtime/crystal-tests/pytest.log` |
| Sintaxe PowerShell | Oito arquivos verificados | `runtime/crystal-tests/powershell-syntax.log` |
| Compilação isolada do trecho Inno | Passou | `runtime/crystal-tests/inno-compile.log` |
| Compilação do Inno principal | Passou com Inno Setup 7; setup de teste gerado | `runtime/crystal-tests/inno-main-compile.log` |
| Helper com runtime já funcional | Retornou already_functional; não chamou msiexec | `runtime/crystal-tests/helper-already-present.json` |
| Desenvolvimento sem autorização explícita | Bloqueado na etapa authorization | `runtime/crystal-tests/helper-development-denied.json` |
| Distribuição sem licença/procedência aprovadas | Bloqueada | `runtime/crystal-tests/distribution-gate.log` |
| Varredura dos novos fontes/logs/relatórios | Nenhuma ocorrência do valor da chave nos arquivos não binários examinados | `runtime/crystal-tests/security-audit.json` |

A compilação do Inno utiliza os binários/cache existentes, sem reconstrução npm
ou PyInstaller. O setup de teste não foi executado. A compilação demonstra o
empacotamento e a validade do script; não demonstra instalação ou elevação UAC.

## Relatório real na estação de desenvolvimento

CT-e de teste: filial 1, série 10, documento 23167. Consulta SQL encontrou o
documento; o RDC leu 8 registros, adicionou 2 imagens e executou em processo x86
com `CrystalDesignRunTime.Application.11`. Identidade registrada no JSON:
`DELLMAR\joao.barbosa`. Essa é a conta deste teste local, não uma homologação da
futura conta de serviço do backend.

- **Windows / PrintOutEx:** PDF gerado; QR e Code 128 decodificados e iguais ao
  XML, protocolo encontrado. Os valores decodificados estão em
  `checks.symbols.decoded_symbols` do relatório.
- **Exportador PDF nativo:** Export executou e produziu PDF; QR conferiu com o
  XML, mas o Code 128 não foi decodificado. A validação rejeitou essa saída. Não
  concluir que carregar `crxf_pdf.dll` comprova um PDF correto. O padrão permanece
  Microsoft Print to PDF.
- A conexão SQL falhou em uma repetição intermediária e respondeu novamente na
  repetição seguinte. A falha de consulta ficou registrada, sem alterar a
  configuração do banco nem registrar credenciais.

Evidência mais recente:
[JSON do relatório e símbolos](../runtime/crystal-tests/development-dacte-recheck/dacte-diagnostic.json).
O PDF nativo rejeitado foi preservado somente como evidência local, em
`native-before-validation.pdf`; não foi encaminhado ao fluxo operacional.

A ordem atual das chamadas é OpenReport → AddPictureObject → ReadRecords →
PrintOutEx. A apresentação do QR é preparada antes da leitura; a implementação
não foi reordenada para aparentar outra sequência no relatório de testes.

## Arquivos da implementação

Criados para o pré-requisito:

- `installer/crystal/`: `Product.wxs`, `modules.lock.json`,
  `distribution-approval.example.json`, `runtime-probe.ps1`,
  `inspect-runtime.ps1`, `Prerequisite.iss`, `smoke.iss`.
- `scripts/crystal/`: `__init__.py`, `policy.py`, `msi_database.py`.
- `scripts/`: `bootstrap-crystal-build-tools.ps1`, `build-crystal-runtime.py`,
  `install-crystal-runtime.ps1`, `test-crystal-runtime.ps1`, `test-crystal-dacte.py`.
- `BACKEND/tests/test_crystal_prerequisite.py` e os dois documentos Crystal RDC.

Ajustados:

- `installer/AutomacaoNovelis.iss`: etapa automática do pré-requisito, configuração
  explícita do ProgID e destino separado para o setup de teste.
- `scripts/prepare-installer-inputs.py`, `build-installer.ps1`,
  `create-installer.ps1`: hash/manifesto, modos development/distribution e gate de
  procedência/licença. Uma tentativa rejeitada invalida o staging Crystal antigo.
- `BACKEND/app/services/crystal_reports/native-environment.ps1`: padrão DesignRunTime,
  criação real de COM/SQLOLEDB e driver ADO no diagnóstico.
- `BACKEND/app/services/crystal_reports/worker.ps1`: evidência de execução sem
  credenciais. `validation.py`: valores dos símbolos decodificados no resultado.
- `BACKEND/app/tools/dacte_components.py`: Crystal ausente é tratado pelo
  pré-requisito do setup, sem seleção manual de DLLs.
- `installer/dacte/dependencies.json`, `BACKEND/.env.example`, `.gitignore` e
  `docs/dacte-installer.md`.

As demais alterações que já existiam na área de trabalho foram preservadas.

## Pendências para produção

O usuário informou que **não há VM disponível**. Portanto, não foram executados:
instalação real do MSI, reinstalação, reparação, atualização 1.0.0 → 1.0.1,
reinicialização, teste sob a conta/sessão real do backend ou coexistência após
instalar este MSI. Testes nesta estação com Crystal completo não substituem
nenhuma dessas etapas.

Também faltam autenticação da procedência da mídia, comprovação de aquisição e
direitos Developer/RCAPI e redistribuição para o escopo pretendido. A aceitação
técnica do código KEY não resolve essas pendências. O build distribution está
bloqueado por falta das aprovações e evidências exigidas.

O RPT usa `IDAutomationSC128L DEMO`; sua licença/fonte de produção não acompanha
o MSI Crystal. Permanecem a equivalência fiscal/contingência do relatório e a
limitação observada no Code 128 do exportador nativo. As ações nativas antigas
também precisam ser verificadas quanto ao comportamento e aos logs na VM.

Estado final desta etapa: **implementado para testes; não homologado e não
liberado para distribuição/produção**.
