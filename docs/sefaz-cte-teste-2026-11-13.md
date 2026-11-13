# Recuperação oficial de XML de CT-e

Investigação e testes reais executados em 13/11/2026 na máquina de desenvolvimento, com autorização do usuário e certificado já configurado no projeto.

## Resultado

| Verificação | Resultado |
| --- | --- |
| Chave de acesso válida | Sim, 44 dígitos, modelo 57 e DV calculado 6 |
| Consulta pública disponível | Sim, formulário SVSP com dados resumidos e protocolo de autorização de uso |
| Consulta de situação realizada | Sim, SOAP com certificado, HTTP 200 e `cStat=100`, autorizado |
| Download sem certificado possível | Nenhum XML completo obtido nos endpoints oficiais testados |
| Download com certificado possível | A distribuição funcionou e entregou dois `cteProc` de outras chaves. O XML solicitado permaneceu ausente |
| XML completo recuperado | A chave de teste permaneceu sem XML completo ao encerrar a distribuição disponível |
| Melhor alternativa gratuita | Distribuição oficial por NSU para atores habilitados. Para documento próprio do emitente, recuperar o XML original no sistema emissor ou utilizar um canal oficial individual autorizado |

Chave fornecida para o teste `26261113254104001065570100000028791000028796`.

Sua composição informa UF 26, Pernambuco, emissão 11/2026, emitente `13254104001065`, série 010, número 2879 e emissão normal. O ambiente de produção foi informado nas requisições. A chave, isoladamente, não codifica o ambiente.

## Serviços oficiais

Pernambuco utiliza SVSP. A relação nacional publica os serviços abaixo, além de autorização síncrona, recepção de eventos e status do serviço. Estes últimos atendem operações próprias e disponibilidade. A consulta de situação recebe a chave e devolve situação, protocolo e eventos relacionados. [Relação oficial de Web Services](https://www.cte.fazenda.gov.br/portal/webServices.aspx?tipoConteudo=wpdBtfbTMrw%3D)

| Finalidade | Endpoint de produção |
| --- | --- |
| Situação SOAP 4.00 | `https://nfe.fazenda.sp.gov.br/CTeWS/WS/CTeConsultaV4.asmx` |
| Distribuição nacional 1.00 | `https://www1.cte.fazenda.gov.br/CTeDistribuicaoDFe/CTeDistribuicaoDFe.asmx` |
| Consulta pública / QR | `https://nfe.fazenda.sp.gov.br/CTeConsulta/qrCode` |
| Formulário público nacional | `https://www.cte.fazenda.gov.br/portal/consulta.aspx?tipoConsulta=completa&tipoConteudo=mCK/KoCqru0=` |
| Consulta pública individual SVRS | `https://dfe-portal.svrs.rs.gov.br/Dfe/ConsultaPublicaDfe` |

O serviço `cteDistDFeInteresse` aceita `distNSU` para continuar um fluxo e `consNSU` para recuperar uma lacuna conhecida. A NT 2015.002 v1.05 documenta essas duas opções. O lote contém até 50 documentos GZIP/Base64. A disponibilidade é de até três meses após recepção no Ambiente Nacional. Ao terminar o fluxo, aguarda-se pelo menos uma hora. Repetições indevidas podem receber `656`. [NT 2015.002 v1.05, seções 2.1, 2.4–2.6 e 2.11](https://www.cte.fazenda.gov.br/portal/exibirArquivo.aspx?conteudo=LLSQYxGtwv0%3D)

O acesso depende do papel do interessado e de certificado válido. O CNPJ-base consultado precisa corresponder ao certificado. Remetente, destinatário, expedidor, recebedor, tomador e terceiro `autXML` possuem regras de distribuição. A tabela oficial exclui o XML do próprio CT-e para o emitente. Documentos entregues a terceiros podem ter chaves relacionadas mascaradas. [NT 2015.002 v1.05, tabela de distribuição e validações](https://www.cte.fazenda.gov.br/portal/exibirArquivo.aspx?conteudo=LLSQYxGtwv0%3D)

A comunicação dos Web Services exige autenticação TLS com certificado ICP-Brasil, A1 ou A3. A disponibilidade de uma chave privada para a conta executora e o funcionamento do provedor criptográfico são necessários. A consulta de situação possui leiaute próprio de retorno com protocolo. O XML autorizado completo usa a estrutura `cteProc`, contendo o documento e seu protocolo. [MOC CT-e 4.00, seções 3.2 e 4.5](https://www.cte.fazenda.gov.br/portal/exibirArquivo.aspx?conteudo=0eu1YksSGXM%3D)

Há um canal oficial individual de download pela SVRS que exige certificado da empresa. A orientação estadual também confirma a exclusão do XML próprio do emitente na distribuição nacional. A disponibilidade do download SVRS para esta chave de Pernambuco permaneceu sem validação prática, pois o formulário acessado apresentou CAPTCHA. [Receita Estadual RS, orientações de acesso ao XML](https://atendimento.receita.rs.gov.br/como-acessar-os-arquivos-xml-dos-ct-es)

## Requisições realmente executadas

Os registros sanitizados estão em `docs/evidence/sefaz-cte-2026-11-13.json`. Horários SOAP e da PoC são UTC. Corpos fiscais, cookies, formulários assinados e seletores do certificado permanecem na área local de testes com acesso restrito.

| Requisição | HTTP | Resultado observado |
| --- | --- | --- |
| GET formulário nacional, anônimo | 200 | CAPTCHA presente, investigação encerrada nesse formulário |
| GET formulário SVSP, anônimo | 200 | Formulário normal disponível |
| POST consulta resumida SVSP, anônimo | 200 | Chave e evento de autorização de uso visíveis no HTML, sem XML completo |
| GET WSDL de situação, anônimo / certificado | 403 / 200 | Acesso do serviço condicionado ao certificado |
| GET WSDL de distribuição, anônimo / certificado | 403 / 200 | Operação e namespaces conferidos no WSDL real |
| SOAP `cteConsultaCT`, anônimo | 403 | Sem retorno fiscal SOAP |
| SOAP `cteConsultaCT`, certificado | 200 | `cStat=100`, autorizado |
| SOAP `distNSU`, certificado | 200 em quatro lotes | `cStat=138`, 196 documentos recebidos |
| Login oficial de consulta completa SVSP, certificado | 302 em redirecionamentos, depois 403 | Autenticação recusada pelo endpoint de certificado, encerrada nessa resposta |
| GET consulta pública individual SVRS, anônimo / certificado | 200 / 200 | Formulário com CAPTCHA, investigação encerrada nesse formulário |

O certificado foi utilizado pelo repositório Windows, sem exportação da chave privada. A seleção existente no projeto localizou um certificado válido com chave privada e CNPJ-base correspondente ao emitente. Seu tipo A1/A3 não foi determinado. O acesso negado pelo portal SSO não permite concluir a causa administrativa ou criptográfica da recusa.

### Distribuição recebida

| NSU informado | Último NSU retornado | Documentos | `cteProc` completos | Coincidentes com a chave de teste |
| --- | --- | --- | --- | --- |
| 000000000000000 | 000000000003761 | 50 | 0 | 0 |
| 000000000003761 | 000000000003811 | 50 | 0 | 0 |
| 000000000003811 | 000000000003861 | 50 | 1 | 0 |
| 000000000003861 | 000000000003907 | 46 | 1 | 0 |

O maior NSU foi `000000000003907`. O processamento preservou 194 eventos e dois XMLs `cteProc` de outras chaves. O teste encerrou no final do fluxo e gravou o intervalo de espera. O comando TypeScript retornou `3`, indicando término sem o XML completo procurado.

O certificado tem o mesmo CNPJ-base do emitente. A ausência do XML no lote é compatível com a regra documental de distribuição do próprio CT-e. Essa é uma inferência. O retorno `138` confirma a localização dos documentos daquele lote e exige conferir cada chave.

## Prova de conceito

Código em `tools/sefaz-cte-poc`, com comandos Windows detalhados no README dessa pasta.

- `protocol.ts` valida a chave, constrói SOAP, interpreta os retornos e descompacta os documentos. Eventos e resumos recebem classificações próprias.
- `transport.ts` oferece HTTPS com A1/PFX e transporte Windows/Schannel para certificado já instalado.
- `cli.ts` implementa consulta, `distNSU`, `consNSU`, cursor persistente, trava de processo, espera e gravação dos XMLs.
- A confirmação do alvo exige chave coincidente em `infCte/@Id` e `protCTe/infProt/chCTe`, com autorização `100`.

O teste real executou os modos `validate`, `status` e `dist` do cliente compilado. Os testes locais de protocolo usam entradas sintéticas para verificar erros, namespaces e classificação. Seus resultados são apresentados como testes unitários.

## Limitações e pendências

- O XML completo da chave solicitada permaneceu indisponível no fluxo autorizado acessado.
- O modo A1/PFX aguarda um teste real com arquivo autorizado. O teste certificado executado usou o repositório Windows.
- `consNSU` está implementado e testado localmente. A distribuição recebida não apresentou lacuna que justificasse consulta pontual real.
- A PoC foi delimitada a produção, CNPJ e consulta normal SVSP. CPF, outros autorizadores, contingência e homologação permanecem fora da validação prática.
- A verificação do XML confirma estrutura e chave. A validação XSD completa e a verificação criptográfica da assinatura XML permanecem pendentes.
- A PoC precisa de coordenação do cursor com outros consumidores da empresa antes de execução contínua.

A automação gratuita pela distribuição oficial é viável para documentos disponíveis ao interessado. Neste caso, a consulta de situação funcionou e o XML completo da chave de teste permaneceu sem recuperação. Para o próprio emitente, a origem gratuita mais direta é o XML autorizado preservado pelo sistema que emitiu o CT-e.
