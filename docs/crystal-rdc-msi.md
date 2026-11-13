# Pré-requisito Crystal XI R2 RDC x86

O novo setup de teste está descrito em [instalador-cargo-hub.md](instalador-cargo-hub.md).
Sua revisão atual é a [r2](instalador-cargo-hub-r2.md), que antecipa a configuração
do backend em relação à execução do bootstrap. O MSI RDC 1.0.1 foi mantido.
O pacote com dados operacionais preenchidos está na
[r3 privada](instalador-cargo-hub-r3-privado.md), preservando o mesmo MSI.
Ele integra `FRONTEND-HUB` em Tauri, Python local e o MSI RDC 1.0.1. As entregas
bootstrap e os kits abaixo são históricos. A homologação do novo EXE no PC
físico e a liberação de licenciamento continuam pendentes.

Estado: implementação de teste. A compilação não comprova instalação, aceitação do
PIDKEY pelo runtime, direito de redistribuição ou homologação em máquina limpa.
Não publicar os artefatos de desenvolvimento.

No PC físico NB-GFR-VIN-05, o usuário executou a atualização 1.0.0 → 1.0.1 e
forneceu resultado `installed_verified`: COM x86 e DLLs 11.5.0.313 funcionais,
sem editor XI R2 detectado. O DACTE real ainda não foi testado nesse PC.
Veja [a evidência e os limites do reteste](crystal-rdc-correcao-selfreg.md).

Foi compilado um novo instalador integrado de teste com o MSI 1.0.1:
`runtime/crystal-build/development/installer/AutomacaoNovelis-CrystalRDC-1.0.1-bootstrap4-TESTE-NaoDistribuir.exe`.
Os logs posteriores do PC de teste mostram os arquivos da aplicação instalados,
mas o bootstrap não encontrou o Python e não criou a `.venv` do backend.
Os logs detalhados confirmaram desinstalação Python 1603 ignorada e chamada
posterior em modo Modify sem restaurar os arquivos. O próximo passo é
[executar a recuperação atual do backend](backend-bootstrap-recuperacao.md).
A reparação r2 restaurou o interpretador, mas deixou pip ausente. O kit r3
recupera pip com ensurepip e serializa os bootstraps.

## Projeto e entradas

`installer/crystal/Product.wxs` incorpora os quatro MSMs completos, em um único
recurso obrigatório. Não extrai DLLs nem altera os módulos comerciais.
`installer/crystal/modules.lock.json` fixa os quatro SHA-256 do inventário:

- `CrystalReports11_5_RDC_Runtime.msm`;
- `CrystalReports11_5_RDC_Reportengine.msm`;
- `CrystalReports11_5_RDC_License.msm`;
- `CrystalReports11_5_RDC_Designtime.msm`.

Todos correspondem ao conjunto x86 11.5.0.313. A auditoria do MSI exige
`craxddrt.dll`, `craxdrt.dll`, `crpe32.dll`, `crdb_ado.dll`, `u2lcom.dll` e
`crxf_pdf.dll` nessa versão, recusa componentes Win64 e `crw32.exe`, confere
`InstallCRDB_ADO=1`, `InstallU2FPDF=1` e a entrada SelfReg original do Designtime.
O instalador inclui também as dependências e ações originais dos MSMs; não deve
ser reduzido a essa lista de seis arquivos.

Os arquivos instalados localmente coincidem com os extraídos da mídia indicada.
Essa coincidência é integridade relativa ao inventário, não autenticação SAP.
A mídia tem identificação de distribuidor não oficial e a procedência continua
pendente. Nenhum componente proprietário foi adicionado ao repositório.

## Compilar o MSI de teste

Execute na raiz do projeto, em uma estação autorizada:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/bootstrap-crystal-build-tools.ps1
python scripts/build-crystal-runtime.py --verify-only
python scripts/build-crystal-runtime.py --mode development --key-file F:\KEY-CR2.txt
```

O bootstrap fixa o pacote oficial NuGet WiX 4.0.6 e seu SHA-256; requer .NET
Runtime 6 na estação de build, não na máquina que receberá o MSI. Os MSMs são
lidos de `C:\Program Files (x86)\Common Files\Merge Modules` por padrão; use
`--modules` para outra pasta autorizada com os mesmos hashes.

Saídas ignoradas pelo Git em `runtime/crystal-build/development/`:

- `NovelisCrystalRDC-x86-1.0.1.msi`;
- `NovelisCrystalRDC-x86-1.0.1.manifest.json`, sem chave;
- `build.log`, sanitizado antes de gravar.

O campo `KEY` é lido somente em memória. Não há parâmetro CLI que receba o valor
da chave. WiX recebe o valor no ambiente privado do subprocesso e configura o
ModuleConfiguration `PIDKEY`. Não se gera `.wixpdb`; o diretório intermediário é
temporário. As propriedades PIDKEY normal e modularizada são marcadas Hidden.
O diretório de saída fica restrito ao usuário do build, SYSTEM e Administradores.

**O MSI necessariamente contém a propriedade de licença configurada. Hidden não
é criptografia. Trate MSI, intermediários, cópias na VM e cache MSI como material
restrito; um administrador pode inspecioná-los.** Nunca anexe o MSI a chamados,
publique-o ou habilite logs detalhados do Windows Installer sem revisão.
As ações nativas antigas ainda precisam ser verificadas em VM quanto a logs.

O ProductCode é estável por versão. `--package-version 1.0.2` produz uma segunda
versão exclusivamente para o teste de atualização, com o mesmo UpgradeCode.
O nome utilizado pelo Inno continua fixado no pré-requisito 1.0.1.

## Integração com o Inno existente

`installer/crystal/Prerequisite.iss` é incluído pelo instalador principal.
Antes de substituir os arquivos da aplicação, ele executa o probe x86. São
necessários versão e arquitetura das DLLs, carregamento nativo, criação real de
`CrystalDesignRunTime.Application.11` e criação de SQLOLEDB x86. Presença de DLL
ou registro isolado não satisfaz a detecção.

Se necessário, extrai o MSI e o manifesto embutidos para a pasta temporária e
chama `scripts/install-crystal-runtime.ps1`. O helper confere SHA-256, manifesto,
modo de build e autorização de teste. Utiliza `msiexec /i ... /qn /norestart`.
Não passa PIDKEY na linha de comando. Em modo interativo, solicita elevação UAC
apenas nessa etapa. Implantação inteiramente silenciosa em máquina sem runtime
deve começar elevada. O instalador principal mantém seu escopo por usuário.

Tratamento: 0 exige novo probe funcional; 3010/1641 interrompem a continuação e
pedem reinicialização; 1618 informa outra instalação em andamento; 740 solicita
elevação; demais códigos ou falha do probe bloqueiam a instalação. O helper
registra resumos JSON e código de saída, sem log MSI detalhado. Uma política
global Logging/Debug do Windows Installer bloqueia a execução do MSI até revisão
pelo administrador da VM; o script não modifica essa política.

Reexecução com runtime já funcional é idempotente. `-Action Repair` força
`REINSTALL=ALL REINSTALLMODE=vomus`. Um produto próprio já registrado, porém sem
passar no probe, também recebe esses parâmetros. ARPNOREMOVE impede remoção
acidental pelo painel; não se remove o runtime ao desinstalar a aplicação,
pois os componentes podem ser compartilhados. Remoção deliberada só em snapshot
autorizado, conferindo o ProductCode do manifesto.

O instalador grava explicitamente na configuração da aplicação:

```dotenv
CRYSTAL_REPORTS_PROGID=CrystalDesignRunTime.Application.11
```

O backend também usa esse ProgID como padrão. Não recorre automaticamente ao
runtime 11.0 instalado por outro sistema. QR independente usa `AddPictureObject`
e, portanto, a biblioteca de criação de relatórios e os direitos RCAPI aplicáveis.

Preparação de um build principal **de teste**, sem publicação:

```powershell
python scripts/prepare-installer-inputs.py --mode development --crystal-manifest runtime/crystal-build/development/NovelisCrystalRDC-x86-1.0.1.manifest.json
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build-installer.ps1 -BuildMode development -CrystalManifest runtime/crystal-build/development/NovelisCrystalRDC-x86-1.0.1.manifest.json
```

O modo padrão do build principal é distribution e exige aprovação. Nenhum fluxo
pede que o usuário selecione DLLs Crystal. O diagnóstico de reparação orienta a
reexecutar o instalador quando falta o pré-requisito.
O setup de desenvolvimento sai em `runtime/crystal-build/development/installer`,
com sufixo `CrystalTESTE-NaoDistribuir`, separado da pasta de instaladores de release.

## Homologação na VM autorizada

Não executar estas etapas na estação com Crystal completo nem em terceiros.
Providenciar VM Windows x64 com snapshot, conta administrativa para instalação,
conta real do backend, SQL acessível com consulta de leitura e XML correspondente
ao CT-e escolhido. Registrar SO/build, identidade da VM, snapshot e responsável.
Aprovação de uso do ambiente é externa aos scripts.

O projeto/backend, suas dependências Python para DACTE e o relatório sanitizado
devem estar disponíveis na VM. Não transportar `.env` de produção indiscriminadamente.
Configurar as credenciais por canal autorizado, sem transcrição de console.

1. **Antes do MSI**, capturar baseline sem Crystal, preservando o arquivo:

   ```powershell
   BACKEND\.venv\Scripts\python.exe scripts/test-crystal-dacte.py --authorized-test --baseline-only --output runtime/crystal-vm/before
   ```

   O probe retorna código 2 sem runtime, mas a captura de baseline retorna 0.
   O baseline deve mostrar ausência de COM, DLLs e produtos Crystal. Conferir
   manualmente a imagem/snapshot: o probe sozinho não prova toda a história da VM.

2. Copiar somente o MSI de teste e seu manifesto para pasta de teste restrita da
   VM autorizada. Em PowerShell elevado, a partir da raiz do projeto:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install-crystal-runtime.ps1 -ManifestPath C:\TesteRestrito\NovelisCrystalRDC-x86-1.0.1.manifest.json -AllowDevelopment -ResultPath runtime/crystal-vm/install.json
   ```

3. Verificar `installed_verified` e repetir a execução, salvando `reinstall.json`.
   Esperado: `already_functional`, sem reinstalação desnecessária. Executar também
   com `-Action Repair`, salvando `repair.json`, e conferir o probe após reparação.
   Guardar `install.json` original para ligar o teste ao hash efetivamente instalado.

4. Reiniciar a VM, inclusive quando não houve 3010. Preparar Microsoft Print to
   PDF, spooler e fontes necessárias. `IDAutomationSC128L DEMO` consta do relatório
   atual: o MSI Crystal não instala essa fonte nem concede sua licença. A imagem
   limpa precisa receber uma fonte/pacote autorizado e compatível; ausência deve
   manter o diagnóstico pendente. O QR Python dispensa Barcodesoft/BCSQRCode.

5. Na sessão da **conta que efetivamente executará o backend**, executar com os
   valores reais de conta, CT-e e caminho de XML (o exemplo usa marcadores):

   ```powershell
   BACKEND\.venv\Scripts\python.exe scripts/test-crystal-dacte.py --authorized-test --environment clean-vm --expected-account "DOMINIO\conta-backend" --baseline runtime/crystal-vm/before/runtime-state.json --install-result runtime/crystal-vm/install.json --manifest C:\TesteRestrito\NovelisCrystalRDC-x86-1.0.1.manifest.json --require-reboot --native-pdf --filial 1 --serie 10 --documento NUMERO_AUTORIZADO --xml-reference C:\TesteRestrito\CTE_REFERENCIA.xml --output runtime/crystal-vm/after
   ```

   A conta informada é comparada à identidade do probe e do processo COM x86.
   Se o backend usa serviço, tarefa agendada ou sessão não interativa, executar
   por esse mesmo mecanismo; um teste interativo com o mesmo nome de usuário
   não certifica impressão em sessão de serviço. Não passar senha em argumentos.

6. O resultado inclui conexão SQL, registros lidos, chamadas COM, PDF, fontes,
   QR Code e Code 128 **com valores decodificados**, comparados ao XML. A ordem
   real atual é OpenReport → AddPictureObject → ReadRecords → PrintOutEx: o QR é
   preparado antes da leitura para substituir fórmulas de codificação. A opção
   `--native-pdf` exercita também `Export` com formato PDF e valida seus símbolos
   separadamente. Inspecionar visualmente páginas/layout, valores, protocolo e
   contingência. PDFs e XMLs têm dados fiscais: manter as evidências restritas.

7. Compilar 1.0.2 e instalar sobre 1.0.1 em snapshot de teste. Para atualização,
   usar `-Action Repair` no helper para forçar a chamada MSI mesmo se o runtime
   já estiver funcional. Confirmar substituição apenas do produto Novelis antigo,
   propriedades, registro COM, exportação, repetição e reparação da nova versão.
   Não desinstalar componentes Crystal de outros produtos.

8. Em outro snapshot com as versões Crystal realmente usadas na empresa, capturar
   registro COM/produtos antes e depois, testar as aplicações coexistentes e
   repetir os PDFs. Uma VM inicialmente sem Crystal não prova coexistência.

Arquivar baseline, manifestos, install/reinstall/repair/update JSONs, evidência
de reboot, diagnóstico JSON/HTML, imagens renderizadas, PDFs e revisão humana.
Mesmo um resultado `passed` mantém `production_ready=false` e aprovação manual
de homologação pendente. O script compara UUID da máquina, baseline sem Crystal,
hash instalado e produto registrado; não transforma uma execução na estação de
desenvolvimento em homologação.

## Aprovação para distribuição

Preencher, fora do Git, uma cópia de
`installer/crystal/distribution-approval.example.json`. Exigir responsável, data,
escopo interno/externo/OEM e duas evidências com hashes: procedência e licença.
Exemplos de evidências: mídia obtida de canal SAP autorizado; comprovante de
aquisição/entitlement Crystal Developer XI R2; contrato/EULA aplicável à entidade
e ao uso RCAPI; confirmação SAP para clientes externos/OEM quando aplicável.
Não incluir serial, chave ou captura de tela com códigos nas evidências de build.

O modo distribution recusa aprovações ausentes/incompletas ou evidências alteradas.
Após compilar esse modo, vincular `package_sha256` ao MSI revisado. O build Inno
exige a mesma aprovação e esse hash. Um MSI development nunca é aceito como
distribution. Nenhum script publica o resultado e a homologação continua sendo
um requisito independente.

A aceitação técnica do campo KEY não comprova titularidade, edição adquirida,
direito RCAPI ou redistribuição. A situação atual permanece bloqueada por essas
evidências e pela procedência. O texto da licença da mídia foi preservado na
investigação local anterior; não foi tratado como comprovação de aquisição.

No teste local de desenvolvimento de 12/11/2026, `PrintOutEx` gerou PDF com
QR e Code 128 correspondentes ao XML. O exportador nativo executou e gerou PDF,
com QR legível, mas o Code 128 não foi decodificado. Essa limitação mantém a
validação nativa pendente; presença/carregamento de `crxf_pdf.dll` não comprova
equivalência do resultado. O mecanismo padrão continua sendo `windows`.
Não havia VM disponível para testar o MSI sobre uma imagem limpa.

Referências oficiais consultadas:

- [SAP KBA 1218622, keycode no merge module RDC, XI/XI R2](https://userapps.support.sap.com/sap/support/knowledge/en/1218622).
- [SAP, informações de licenciamento Crystal e lista RCAPI](https://userapps.support.sap.com/sap%28bD1lbiZjPTAwMQ%3D%3D%29/support/sapnotes/public/services/attachment_DocServ.htm?iv_guid=FA163E84AD781FE094A046DF549858DC&iv_key=002075125900003093392017&iv_version=0006).
- [WiX, ConfigurationData](https://docs.firegiant.com/wix/schema/wxs/configurationdata/).
- [Microsoft, prevenção de informação confidencial em logs MSI](https://learn.microsoft.com/en-us/windows/win32/msi/preventing-confidential-information-from-being-written-into-the-log-file).

Essas referências explicam mecanismos e condições; a licença do caso concreto
precisa de aprovação pelo titular/fornecedor. Runtimes .NET modernos não são
substitutos demonstrados da API RDC 11.5 COM.
