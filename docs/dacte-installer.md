# Instalacao integrada DACTE

O instalador existente continua sendo Inno Setup. `scripts/build-installer.ps1`
gera o setup; `scripts/create-installer.ps1` delega a esse mesmo build.
O pre-requisito RDC x86 agora tem um projeto MSI de teste e integracao automatica;
veja [build, licenciamento e homologacao](crystal-rdc-msi.md). A distribuicao
continua bloqueada e nao ha homologacao em maquina limpa.
O backend abre o RPT pelo componente COM/RDC do Crystal XI R2 em um processo
Windows PowerShell x86 isolado. Nao inicia o Rodopar e nao presume uma API HTTP
nativa do Crystal: as rotas REST pertencem ao nosso FastAPI.
O mecanismo PDF padrao e o Microsoft Print to PDF do proprio Windows, acionado
por `PrintOutEx` do Crystal com destino explicito. Somente essa impressora
virtual e aceita; nao altera nem utiliza a impressora padrao. O worker aguarda
cabecalho e marcador final do PDF antes de liberar o arquivo.
`CRYSTAL_PDF_ENGINE=native` seleciona o exportador antigo, sem fallback automatico.

## O que acompanha o pacote

- Backend, frontend e aplicativo existentes.
- Python 3.12 x64, Visual C++ x64 e Chromium ja usados pelo projeto.
- Wheelhouse offline com as dependencias do backend e do extra `[dacte]`:
  BrazilFiscalReport 1.4.0 para o caminho XML, qrcode/Pillow para o QR independente,
  pypdf, pypdfium2 e zxing-cpp para
  ler e comparar os simbolos do PDF. As licencas dos projetos acompanham as wheels.
- RPT integrado em `assets/reports/dacte.rpt`, manifesto com SHA-256 e auditoria.
- Scripts de preparacao, diagnostico x86 e instalacao assistida.
- Configuracao inicial sanitizada, sem usuarios, senhas, tokens, servidores de
  banco ou caminhos absolutos da maquina de desenvolvimento.

Microsoft Print to PDF e um recurso do Windows, verificado no diagnostico.
Se estiver desabilitado, ative-o nos Recursos do Windows; nenhum driver de
impressora externa e baixado ou instalado por este pacote.

O Crystal e incorporado exclusivamente pelos quatro merge modules inventariados
no MSI controlado. Nao se copiam DLLs isoladas nem fontes de Windows/Fonts.

## Componentes comerciais inspecionados

| Componente | Arquivo real | Mecanismo identificado | Estado de redistribuicao |
|---|---|---|---|
| Barcodesoft QRCode DEMO | qrcodedemo.exe | Inno Setup 6.1.0, assinatura Barcodesoft valida | Nao aprovado |
| IDAutomation Code 128 DEMO | IDAutomation_C128FontAdvantageDEMO.exe | Inno Setup 6.0.0, assinatura IDAutomation valida | Nao aprovado |
| Crystal XI R2 x86 | NovelisCrystalRDC-x86-1.0.1.msi (teste) | Quatro merge modules RDC 11.5.0.313 x86 | Procedencia/licenca e homologacao pendentes |

Os hashes estao em `installer/dacte/dependencies.json`. A presenca dos pacotes
DEMO nao comprova direitos de redistribuicao nem aptidao para uso operacional.
Por isso, o setup permite selecionar os dois EXEs obtidos pelo proprio usuario
e executa a instalacao assistida apenas se o hash corresponder ao pacote
inspecionado. Nao troca uma versao DEMO por uma versao licenciada automaticamente.

Os parametros Inno utilizados sao documentados pelo proprio fabricante do
instalador: `/SP-`, `/NORESTART`, `/NOCLOSEAPPLICATIONS` e `/LOG`. Modo silencioso
somente e permitido para um pacote com redistribuicao explicitamente aprovada.
Crystal exige a midia correta do fornecedor; um runtime moderno .NET nao e
considerado equivalente ao RDC 11.5 utilizado por esta implementacao.

Referencias: [IDAutomation](https://www.idautomation.com/license-matrix-for-barcode-fonts/),
[avaliacao Code 128](https://www.idautomation.com/barcode-fonts/code-128/download/),
[Barcodesoft](https://www.barcodesoft.com/),
[parametros Inno Setup](https://jrsoftware.org/ishelp/topic_setupcmdline.htm).

Para incorporar futuramente um pacote autorizado, use `installer/private-dacte/`,
registre o nome real, SHA-256, variante e evidencia em `dependencies.json` e
marque a aprovacao somente apos verificar os direitos correspondentes.
O build exige a evidencia local e verifica o hash; nao inclui o documento privado
de licenca no instalador. A pasta privada esta ignorada pelo Git.

## Auditoria do relatorio integrado

O arquivo fornecido foi lido duas vezes para confirmar um snapshot estavel,
mesmo estando aberto no editor. O original fica preservado, pelo hash, em
`runtime/rpt-source-originals/`; nao e incluido no setup.

A copia distribuivel foi salva pelo SDK com conexoes armazenadas removidas e
sem dados salvos. Formulas, tabelas, subrelatorios, geometria e fontes foram
comparados antes/depois. Nenhuma formula fiscal foi modificada nesta integracao.

Confirmado no arquivo salvo:

- As chamadas ativas `rodEDI` e `rodCalculaDVCteNfe` foram eliminadas pelo autor.
- `F_CODBAR`, `F_QRCODE` e `f_cobbar2` compilam; a auditoria cobre as demais formulas.
- No RPT original, `F_QRCODE` usa `BcsQrcode`. Na exportacao padrao, o campo e
  substituido em memoria por uma imagem QR independente; o arquivo nao e alterado.
- A chave principal usa `IDAutomationSC128L DEMO`.
- **Pendencia:** o objeto `fcobbar21`, que usa `f_cobbar2`, ainda utiliza Arial
  para uma sequencia codificada Code 128. Nao foi alterado automaticamente.
- A equivalencia do calculo adicional de contingencia continua pendente de
  documentos de referencia. Compilacao ou boa aparencia nao aprovam a regra fiscal.

O manifesto marca explicitamente `fiscal_validation.status=pending`.
O diagnostico nunca apresenta este relatorio como aprovado para producao.

## Configuracao externa

Por padrao o RPT vem do diretorio instalado, nunca de Downloads. Para usar outro
relatorio auditado, configure `CRYSTAL_DACTE_RPT_PATH`. `CRYSTAL_REPORTS_PROGID`
vazio seleciona um componente COM x86 11.5 registrado; nao seleciona o 11.0 por engano.

Use as configuracoes locais, fora do pacote:

```dotenv
CRYSTAL_DB_USE_CONSULTA=false
CRYSTAL_PDF_ENGINE=windows
CRYSTAL_QR_PROVIDER=python
CRYSTAL_DB_SERVER=
CRYSTAL_DB_HOST=
CRYSTAL_DB_INSTANCE=
CRYSTAL_DB_PORT=
CRYSTAL_DB_AUTH=sql
CRYSTAL_DB_DATABASE=
CRYSTAL_DB_USER=
CRYSTAL_DB_PASS=
```

Informe `SERVER` completo, ou `HOST`, `INSTANCE` e `PORT` separadamente.
`CRYSTAL_DB_AUTH=windows` usa autenticacao integrada sem encaminhar usuario/senha
SQL. `CRYSTAL_DB_USE_CONSULTA=true` permite reutilizar a conexao CONSULTA_DB
existente. Nenhum servidor informado nos testes foi fixado no pacote.

## Computador novo

1. Use Windows 10/11 x64. O setup instala o aplicativo por usuario.
2. Apos aprovacao de procedencia/licenca e homologacao, o setup podera preparar
   automaticamente o RDC x86. No estado atual, usar apenas o procedimento de
   teste autorizado documentado; nao instalar o editor completo como requisito.
3. O setup verifica COM, versoes e carregamento x86 e instala o MSI quando
   necessario, com elevacao administrativa. A etapa Componentes DACTE trata
   apenas os pacotes comerciais opcionais de codigos de barras/fontes.
4. O bootstrap usa a wheelhouse offline; o preparador identifica arquitetura,
   registro, fontes e dependencias. DLL nativa do Crystal nao e substituida.
5. O padrao `CRYSTAL_QR_PROVIDER=python` dispensa instalacao/registro do Barcodesoft
   e da fonte BcsQrcode. O preparador marca esse componente como nao necessario.
   Somente com a opcao explicita `report`, o registro do Barcodesoft x86 solicita elevacao pelo
   preparador integrado. DLL x64 e recusada antes de executar o regsvr32 x86.
   O preparador tambem registra a mesma fonte BcsQrcode em Windows/Fonts, pela
   API GDI e pelo registro persistente do Windows, para o exportador PDF legado.
   Confere familia e hash, preserva os bytes e recusa substituir uma variante
   diferente. Uma copia de arquivo sem registro nao e considerada instalacao.
6. Configure o banco localmente em `BACKEND/.env`, pelo configurador do aplicativo.
   Em atualizacoes, a configuracao anterior e restaurada localmente, inclusive
   chaves personalizadas. Capturas e sessoes da maquina de build nao sao distribuidas.
7. Execute o atalho Diagnostico DACTE. Consulte os arquivos JSON/HTML em
   `runtime/installation/`. Pendencias comerciais ou de configuracao ficam explicitas.
8. Para testar um documento e comparar os simbolos com o XML original:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\prepare-dacte.ps1 `
  -Filial 1 -Serie 10 -Documento 23167 -XmlReference C:\Referencias\CTE_1-10-23167.xml
```

O diagnostico verifica DLLs existentes/carregaveis, PE x86, COM, execucao das
funcoes BCS, fontes reconhecidas pelo GDI do processo x86, integridade do RPT,
compilacao de formulas, conexao SQL, exportacao, QR Code e Code 128.
Sem documento/XML de referencia, os testes de exportacao e simbolos ficam pendentes.
Os arquivos gerados permanecem locais; nao ha envio de dados para validadores externos.

## Build e testes

```powershell
.\BACKEND\.venv\Scripts\python.exe scripts\package-dacte-report.py --source C:\Relatorios\dacte-corrigido.rpt
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-installer.ps1 -BuildMode development -CrystalManifest .\runtime\crystal-build\development\NovelisCrystalRDC-x86-1.0.1.manifest.json
cd BACKEND
.\.venv\Scripts\python.exe -m pytest -q
```

O build verifica o manifesto do RPT e nao le um arquivo do computador do
desenvolvedor implicitamente. E necessario reimportar quando o relatorio mudar.
O suporte efetivo ao Crystal legado em cada Windows 10/11 precisa ser homologado;
a deteccao local nao e uma certificacao de compatibilidade do fabricante.

## Arquivos da integracao

| Parte | Arquivos |
|---|---|
| API local | `BACKEND/app/api/routers/reports.py`, `app/api/router.py`, `app/main.py` |
| Crystal x86 | `BACKEND/app/services/crystal_reports/`: service, connection, worker, native-environment, report-audit, diagnostics e validation |
| Preparacao | `BACKEND/app/tools/dacte_setup.py`, `dacte_components.py`, `dacte_fonts.py`, `scripts/prepare-dacte.ps1` |
| RPT auditado | `assets/reports/dacte.rpt`, `assets/reports/dacte.manifest.json`, `scripts/package-dacte-report.py` |
| Empacotamento | `installer/AutomacaoNovelis.iss`, `installer/dacte/dependencies.json`, `scripts/build-installer.ps1`, `scripts/create-installer.ps1`, `scripts/prepare-installer-inputs.py`, `scripts/bootstrap.ps1` |
| Configuracao e dependencias | `BACKEND/.env.example`, `BACKEND/pyproject.toml`, `.gitignore` |
| Verificacao | `BACKEND/tests/test_crystal_reports.py`, `test_dacte_installation.py`, `test_dacte_diagnostics.py`, `test_dacte_xml.py` |
| Documentacao | `docs/dacte-installer.md`, `docs/crystal-dacte-api.md`, `README.md` |

Os demais arquivos que ja estavam alterados no projeto foram preservados.

## Desativacao do acesso legado

O fluxo principal `pendentes` seleciona `PENDENTES_PDF_SOURCE=crystal`. O gerador
grava as evidencias com os mesmos nomes/pastas utilizados pelo planejamento,
sem abrir Rodopar e sem usar Rodopar como fallback. A falha no Crystal aparece
como erro do estagio PDF. Um PDF com QR alterado pelo DEMO fica apenas como
teste local, sem ser copiado para a pasta consumida pelos chamados.

`RODOPAR_BROWSER_ENABLED=false` e o padrao do pacote e da configuracao local.
Os fluxos antigos, mapas e controles continuam no codigo. A interface mantem a
opcao PDF Rodopar desabilitada; o backend bloqueia os fluxos antigos, a abertura
de URLs DataPar e o proxy de preview. Os novos componentes sao
`pendentes/controles/crystal_pdf.py`, `pdf_source.py` e `services/rodopar_policy.py`,
com testes em `test_crystal_pdf_flow.py` e `test_rodopar_disabled.py`.

Uma reativacao deliberada exige alterar `RODOPAR_BROWSER_ENABLED=true` e
`PENDENTES_PDF_SOURCE=rodopar`, e reiniciar o backend. Nenhum erro ou comando de
overlay faz essa troca automaticamente.

## Resultado local em 11/11/2026

- Build do frontend, executavel desktop e Inno Setup concluidos.
- Instalacao do backend com `[dacte]` a partir da wheelhouse, em venv novo e pasta
  separada, sem rede: aprovado. RPT resolvido pela pasta instalada, cinco
  subrelatorios e configuracao de banco inicialmente vazia: conferidos.
- Banco encontrado para `1 / 10 / 23167`. Consulta original gerada pelo Crystal
  executada diretamente em cerca de um segundo; leitura pelo Crystal confirmada.
- Exportador nativo 11.5.0.313 falha com BcsQrcode, inclusive em relatorio minimo.
  Registro da fonte foi normalizado, preservando o hash, sem resolver essa falha.
- O teste inicial com o encoder BCS DEMO acrescentou ` Demo` a URL. Esse caminho
  comercial foi preservado na opcao explicita `CRYSTAL_QR_PROVIDER=report`.
- O padrao utiliza `qrcode` para gerar o simbolo a partir de CTEQRC/CTEURL do banco,
  substituindo a apresentacao do QR em memoria. Exige correspondencia integral
  da URL e da chave lidas do PDF antes de libera-lo. Nao usa XML nem Rodopar.
  Detalhes: [QR independente](crystal-dacte-api.md#qr-independente-do-componente-demo).
- Pendencias adicionais: fonte Arial no codigo adicional de contingencia,
  equivalencia de contingencia e homologacao em maquinas Windows 10/11 limpas.

Os relatórios tecnicos ficam em `runtime/installation/`. O teste em pasta isolada
nao substitui uma instalacao completa em outra maquina ou VM limpa.
