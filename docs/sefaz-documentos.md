# Documentos existentes, destinos e SEFAZ

O backend continua local em cada computador. Os documentos operacionais usam:

| Documento | Pasta |
|---|---|
| PDF DACTE | `\\192.168.254.250\rede\Publico\AUTOMAÇÃO-CTE\PDFS-RODOPAR` |
| XML CT-e | `\\192.168.254.250\rede\Publico\AUTOMAÇÃO-CTE\XML-SEFAZ` |

Novos arquivos usam `CTE_filial-serie-numero.pdf` ou `.xml` diretamente nessas
pastas. PDFs existentes em `cte-numero/CTE_filial-serie-numero.pdf` continuam
reconhecidos; nao sao movidos, excluidos ou gerados novamente. O diretorio
`runtime/reports/dacte` guarda o arquivo intermediario do renderizador Crystal.

O plano confere filial, serie e numero do PDF pelo nome completo e cabecalho PDF.
O XML tambem precisa conter a chave correspondente, a serie e o numero esperados.
Um numero parcialmente coincidente ou um HTML com extensao XML nao conta como
documento disponivel. Antes de gerar um PDF, a existencia e conferida novamente,
inclusive quando outro computador disponibilizou o arquivo depois do plano.

As etapas sem arquivos faltantes aparecem como **Ja disponiveis**, com uma
mensagem de reaproveitamento. Cancelar uma etapa posterior nao transforma esses
documentos em downloads cancelados.

## Somente XML e certificado

O fluxo **Somente busca de XML** usa a lista completa, consulta as chaves no SQL,
confere os arquivos existentes e baixa os faltantes, um CT-e por vez. Nao gera
PDFs, comprovantes nem chamados. Uma lista explicita de XML nao e descartada pelo
historico de chamados. Falhas de download impedem um resultado final de sucesso.

O navegador SEFAZ separado, usado em paralelo ao Crystal, aparece no monitor.
**Mostrar navegador** traz a janela para o operador resolver o hCaptcha; a
automacao observa a confirmacao e continua. O desafio permanece manual.

Em Configuracoes, informe `XML_SEFAZ_CERTIFICATE_CNPJ`. Se houver mais de um
certificado valido para o mesmo CNPJ, informe tambem
`XML_SEFAZ_CERTIFICATE_THUMBPRINT`. O backend consulta o repositorio
**CurrentUser/My** do Windows: o certificado deve estar valido e possuir chave
privada acessivel ao usuario que iniciou o backend. Sem configuracao, permanece a
selecao manual.

A regra usa o nome exato do titular e da autoridade emissora, limitada ao dominio
`cte.fazenda.gov.br`. Ela e gravada no perfil temporario exclusivo do Chromium da
automacao. Nao exporta PFX/chave privada nem altera as politicas do Windows. O
perfil e removido ao fechar o navegador. A versao do Chromium deve ser revalidada
quando atualizada, pois essa integracao usa a preferencia de selecao do navegador.

Referencias tecnicas: [formato da regra de selecao de certificado](https://learn.microsoft.com/en-us/deployedge/microsoft-edge-browser-policies/autoselectcertificateforurls)
e [leitura da preferencia pelo Chromium](https://github.com/chromium/chromium/blob/main/components/content_settings/core/browser/content_settings_policy_provider.cc).

## Verificacao em 11/11/2026

Os 14 PDFs do lote foram reconhecidos e reaproveitados em um teste com geracao
bloqueada. Os hashes permaneceram iguais; os 14 XMLs tiveram sua identidade
conferida. Relatorio local: `runtime/hub-qa/documents-reuse.json`.

O certificado da matriz foi encontrado valido no Windows. A pagina publica da
SEFAZ abriu. A autenticacao e o download completos ainda precisam ser conferidos
apos o hCaptcha: a consulta direta sem sessao recebeu HTTP 403, sem solicitacao de
certificado no registro de rede. O teste TLS local foi bloqueado pelo Kaspersky;
nenhuma excecao de seguranca foi criada. Esses testes nao comprovam ainda a
autenticacao automatica completa no portal.
