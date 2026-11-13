# DACTE direto pelo Crystal Reports

O backend oferece dois caminhos explicitos: `/pdf` usa o RPT do Crystal e
`/pdf-from-xml` usa o XML arquivado com outro renderizador. Nao ha troca automatica
de layout quando uma exportacao pelo RPT falha.

Fluxo local: FastAPI recebe filial, serie e documento, executa o RPT pelo Crystal
Reports instalado no Windows e retorna o PDF como anexo. O Rodopar nao e aberto.
O layout original e seus cinco subrelatorios sao usados sem alterar o arquivo RPT.
Por padrao, o Crystal imprime exclusivamente na impressora virtual local
Microsoft Print to PDF, com o arquivo de destino fornecido ao RDC. Aguarda o
termino da gravacao antes de retornar o anexo; nao utiliza a impressora padrao.
`CRYSTAL_PDF_ENGINE=native` seleciona explicitamente o exportador PDF antigo.
Nao ha troca automatica de mecanismo quando ele falha.

## Relatorio integrado

O arquivo salvo pelo usuario foi auditado e integrado em `assets/reports/dacte.rpt`,
sem dados nem credenciais de conexao armazenados. As chamadas ativas `rodEDI` e
`rodCalculaDVCteNfe` ja estavam substituidas no arquivo fornecido; esta integracao
preserva o arquivo original. Na exportacao padrao, a apresentacao do QR e
substituida apenas na copia em memoria, conforme descrito abaixo.

O diagnostico separa dependencias instaladas, conexao ao banco, exportacao e leitura
dos codigos. Uma falha ao carregar registros nao aprova a geracao do PDF. O campo
adicional de contingencia ainda usa Arial e a equivalencia fiscal esta pendente.
Detalhes, licencas e preparacao de outra maquina: [instalacao DACTE](dacte-installer.md).

## Dependencias

- Windows com Crystal Reports XI R2/RDC 11.5 de 32 bits e seu conector ADO instalados.
- A instalacao desta maquina registra `CrystalDesignRunTime.Application.11` no
  Crystal XI R2 (diretorio `Business Objects/Common/3.5/bin`). O registro
  `CrystalRuntime.Application.11` aponta para outra instalacao, incompleta para
  este RPT; por isso ele nao e o padrao do prototipo. Nao alteramos o registro.
- Acesso SQL direto as tabelas e views usadas no relatorio e subrelatorios.
- Conexao `CRYSTAL_DB_*` ou reutilizacao de `CONSULTA_DB_*` configurada
  localmente em `BACKEND/.env`; a configuracao real nao acompanha o instalador.

Configuracoes opcionais em `BACKEND/.env`:

```dotenv
# Se vazio, usa assets/reports/dacte.rpt do diretorio instalado.
CRYSTAL_DACTE_RPT_PATH=
# Vazio detecta automaticamente o componente COM x86 11.5.
CRYSTAL_REPORTS_PROGID=
CRYSTAL_EXPORT_TIMEOUT_SECONDS=120
CRYSTAL_PDF_ENGINE=windows
CRYSTAL_QR_PROVIDER=python
CRYSTAL_DB_USE_CONSULTA=true
```

Reinicie o backend depois de mudar a configuracao. O worker roda em processo
separado de 32 bits para nao misturar o Crystal antigo com o Python de 64 bits.
Uma exportacao por vez, sem janelas ou impressora fisica. Microsoft Print to PDF
deve estar habilitado no Windows quando o mecanismo `windows` for utilizado. A senha vai por stdin,
sem aparecer na linha de comando ou em arquivos temporarios.

## Inspecionar o RPT sem conectar ao banco

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/reports/dacte/inspect
```

Retorna os parametros, tabelas, selecao e subrelatorios, sem credenciais.

`GET /api/reports/dacte/diagnostics` verifica integridade, componentes e fontes.
Acrescente `?connect=true` para testar tambem a conexao SQL. O diagnostico completo
com exportacao e comparacao de codigos esta disponivel em `scripts/prepare-dacte.ps1`.

## Gerar e salvar um PDF

```powershell
$body = @{ filial = 2; serie = '10'; documento = 17419 } | ConvertTo-Json
Invoke-WebRequest `
  -Uri http://127.0.0.1:8000/api/reports/dacte/pdf `
  -Method Post -ContentType 'application/json' -Body $body `
  -OutFile .\dacte-2-10-17419.pdf
```

Tambem disponivel no Swagger em `http://127.0.0.1:8000/docs`.

O CT-e unico e aplicado a `P_CODFIL`, `P_SERCON`, `P_CODCON_INI` e
`P_CODCON_FIN` (inicio e fim iguais). A selecao original do RPT continua aplicada.
O relatorio e atualizado com os dados do banco; nao usa um retrato salvo no RPT.
Os PDFs ficam em `runtime/reports/dacte/`, com identificador unico por requisicao.
Arquivos parciais sao removidos quando a exportacao falha.

## Escopo

- A rota gera o documento; nao inicia os fluxos de automacao ou envia anexos.
- O fluxo principal utiliza Crystal. O codigo Rodopar foi preservado e desabilitado.
- O resultado depende dos dados, formulas, fontes e componentes exigidos pelo RPT.
- Esta e uma API para uso local; mantenha o backend em `127.0.0.1`.
- Testes: `cd BACKEND` e `.\.venv\Scripts\python.exe -m pytest tests/test_crystal_reports.py`.

## Alternativa funcional: PDF a partir do XML

A rota alternativa abaixo usa
[BrazilFiscalReport](https://engenere.github.io/BrazilFiscalReport/dacte/) 1.4.0.
O layout e o desse renderizador, com a identificacao do emitente lida do XML.
Essa rota dispensa Crystal, conexao SQL e abertura do Rodopar.

Instalacao opcional em `BACKEND`:

```powershell
.\.venv\Scripts\python.exe -m pip install ".[dacte]"
```

Le `CTE_<filial>-<serie>-<documento>.xml` na pasta ja configurada em
`XML_SEFAZ_DOWNLOAD_DIR`. Confere modelo 57, numero, serie e correspondencia da
chave com o protocolo de autorizacao arquivado. Nao verifica assinatura digital
nem consulta a situacao atual do documento na SEFAZ.

```powershell
$body = @{ filial = 1; serie = '10'; documento = 23167 } | ConvertTo-Json
Invoke-WebRequest `
  -Uri http://127.0.0.1:8000/api/reports/dacte/pdf-from-xml `
  -Method Post -ContentType 'application/json' -Body $body `
  -OutFile .\dacte-1-10-23167-xml.pdf
```

Os PDFs ficam em `runtime/reports/dacte-xml/`. A resposta inclui
`X-DACTE-Source: xml`. XML ausente retorna 404; arquivo inconsistente retorna 422.

Teste real: geracao local do CT-e `1 / 10 / 23167` em uma pagina A4.
Chave, protocolo e valor total foram conferidos contra o XML. O QR Code e o
Code 128 foram lidos do PDF renderizado e seus conteudos coincidiram com o XML.
O fluxo de automacao existente ainda nao foi alterado para consumir essa rota.

## Verificacao do caminho Crystal em 11/11/2026

A consulta SQL do RPT retornou os dados e o PDF foi gerado pelo Crystal +
Microsoft Print to PDF, preservando as fontes e o layout fornecidos. A chave
Code 128 e o protocolo conferem com o XML arquivado. O QR Code foi decodificado,
mas a biblioteca Barcodesoft DEMO acrescentou ` Demo` a URL: comparacao reprovada.
Esse foi o resultado do gerador comercial original, mantido como opcao explicita
`CRYSTAL_QR_PROVIDER=report`. A correcao do padrao esta descrita abaixo.

O exportador PDF nativo 11.5.0.313 desta maquina falhou com a fonte BcsQrcode,
inclusive em um relatorio minimo. Nao foi removido o QR Code para contornar o erro.

## Fluxo principal sem Rodopar

`Iniciar automacao` agora utiliza o gerador Crystal para os PDFs faltantes,
com os mesmos nomes e pastas de evidencias do fluxo existente. O codigo Rodopar,
seus mapas e controles foram mantidos, mas estao desabilitados por padrao:

```dotenv
RODOPAR_BROWSER_ENABLED=false
PENDENTES_PDF_SOURCE=crystal
PENDENTES_SKIP_PDF=false
```

Falha no Crystal nao seleciona o Rodopar como alternativa. Os acessos antigos
`pdf-rodopar`, `rodopar-pdf`, `pre-passo` e `integrado`, abertura de URL e proxy
DataPar ficam bloqueados. A interface mantem a opcao antiga desabilitada.

O PDF e gerado sem depender de XML. Antes de libera-lo na pasta de anexos,
o fluxo le QR/Code 128, confere numero/serie e impede o sufixo DEMO conhecido.
Arquivos de teste permanecem em `runtime/reports/dacte/`, com visualizacao pela
interface e por `GET /api/reports/dacte/files/{nome-gerado}.pdf`. A verificacao de
simbolos nao substitui a homologacao fiscal de contingencia.

Uma reativacao deliberada do fluxo antigo exige `RODOPAR_BROWSER_ENABLED=true`
e `PENDENTES_PDF_SOURCE=rodopar`, seguida de reinicio do backend. O overlay nao
reativa o acesso. `PENDENTES_SKIP_PDF=true` pausa a geracao de PDF; a chave antiga
`PENDENTES_SKIP_RODOPAR` fica restrita ao fornecedor legado.

## QR independente do componente DEMO

`CRYSTAL_QR_PROVIDER=python` e o padrao. Uma consulta SQL parametrizada busca
`RODCON.CTE_ID`, `RODCON.CTEQRC` e `RODFIL.CTEURL` para um unico CT-e ativo.
Quando a URL esta dividida em base e parametros, o gerador inclui o separador
`?` ou `&` ausente. Uma URL completa e conservada integralmente. Chave, modelo,
serie e numero sao conferidos antes da geracao; nenhum parametro fiscal e inventado.

A biblioteca aberta `qrcode` gera uma imagem BMP com margem de quatro modulos e
correcao L, correspondente ao nivel 2 da formula BCS. No relatorio aberto em
memoria, os campos `F_QRCODE` sao suprimidos e substituidos por essa imagem na
mesma posicao e dimensao. A altura das secoes e preservada. Os dois encoders BCS
de apresentacao sao esvaziados somente nessa copia; o RPT em disco, as demais
formulas, consultas e subrelatorios permanecem preservados. Nao ha remocao de
marca DEMO de um codigo comercial: o simbolo e calculado independentemente a
partir dos dados originais do banco, sem utilizar o resultado da biblioteca BCS.

Antes de retornar o PDF, o backend renderiza suas paginas e exige que todos os
QRs lidos coincidam integralmente com a URL de referencia e que a chave Code 128
coincida com o banco. A leitura inicia em 216 dpi e repete em 288/432 dpi somente
se algum tipo de simbolo estiver ilegivel. Leituras com erro de checksum sao
descartadas; uma divergencia real continua impedindo a liberacao. O CT-e
11-10-397 reproduziu aliasing nas barras em 216 dpi e foi lido corretamente em
288 dpi, sem alteracao do PDF ou das formulas. A fonte IDAutomation da
chave continua a do RPT, sem troca automatica de variante ou licenca.
XML nao e necessario para essa geracao. Contingencia permanece pendente de homologacao.

## Testar uma lista de CT-es

O utilitario abaixo executa o mesmo estagio Crystal do fluxo principal para uma
lista inteira. Gera um PDF de cada vez, valida QR/chave, grava os PDFs individuais
em uma pasta local exclusiva e cria um PDF reunindo os resultados para revisao.
O resultado e independente do historico de chamados, adequado para repetir um teste.

Na raiz do projeto:

```powershell
.\BACKEND\.venv\Scripts\python.exe .\scripts\test-dacte-batch.py --ctes 2-10-10402 1-10-23167 11-10-397
```

Para uma lista maior, salve um arquivo UTF-8 com um CT-e por linha no formato
`filial-serie-numero` e use `--file caminho\ctes.txt`. Entradas repetidas sao
processadas uma vez. Arquivos ficam em `runtime/output/dacte-batches/<lote>/`:
`individuais/`, `dactes-lote-teste.pdf` e `resultado.json`, com tempos e erros por CT-e.
O teste usa consultas SQL e o gerador PDF; nao executa XML, comprovantes ou chamados.

Para executar o fluxo completo pela interface, marque `Entrada manual` e cole a
lista em `Sequencia`. Desmarque `Modo teste / campos manuais`, pois esse modo
seleciona um unico CT-e. O fluxo completo aplica o historico de chamados e as
demais etapas configuradas; o utilitario acima e destinado ao teste isolado de PDF.
