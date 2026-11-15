# Conferência tarifária dos CT-es — prévia de 14/11/2026

Integração da consulta SQL e do catálogo Novelis à tela **CT-es pendentes** e à preparação da mensagem do chamado. Nenhum instalador foi gerado nesta etapa.

## Regra definida pelo usuário

**Apenas sinalizar divergências.** A conferência financeira não remove CT-es da fila de abertura e não acrescenta bloqueio de chamado. Os requisitos de PDF, XML e comprovante continuam sendo avaliados pelas regras existentes.

O tarifário é a referência de TON contratada e frete. Os valores originais do SQL e o texto original da observação são preservados. Não há UPDATE no SQL Server, alteração do CT-e ou envio real de chamado nos testes desta etapa.

## Campos e correção da origem

Foi confirmado no código e nos dados reais:

- A consulta já seleciona `OBSERVACAO`, `OBSCON`, `VLR_TAR`, `FREVAL`, `OUTROS`, `VLR_TOTAL`, `VLR_FRETE_PESO`, cidades e UFs.
- Os registros usados no plano SQL conservavam esses campos em maiúsculas, mas não os convertiam para os campos `ton`, `id` e `percurso` que a mensagem utiliza. Isso explica os campos vazios no chamado.
- `cte_fields.enrich` agora normaliza os campos para consulta, plano e mensagem. `OBSERVACAO` tem prioridade, com `OBSCON` como complemento dos dados ausentes. São reconhecidos formatos como `TON 30`, `TON: 30`, `TON=30`, **`30 TON`**, `30TON`, `27,5 TON`, `36 toneladas`, `PERCURSO: ...`, `ID: ...` e `ID TARIFARIO: ...`. A quantidade pode vir antes ou depois da unidade; o valor dos impostos em outro trecho da observação não é interpretado como TON.
- O vínculo com RODCON usa a identidade completa: `CODFIL = FILIAL`, `SERCON = SERIE` e `CODCON = DOCUMENTO`, evitando buscar observação de outra série.
- **ID da observação e ID tarifário são campos distintos.** O primeiro não é reinterpretado como o ID do contrato do portal.
- A TON da observação fica em `tonObservacaoOriginal`, inclusive quando ausente. Uma TON preenchida a partir da referência não passa a ser apresentada como se estivesse na observação.

O frete de comparação vem de **`VLR_TAR`**. FREVAL, outros e total vêm das respectivas colunas SQL; não são valores inventados a partir do texto livre. O frete-peso é mantido separadamente.

## Correspondência do contrato

1. Padronizar origem/destino com UF e município.
2. Considerar a vigência **na data de emissão do CT-e**, com fim inclusivo.
3. Considerar a empresa de faturamento pelo CNPJ raiz do emitente, quando a chave estiver disponível. Contratos de outra empresa e tarifas ausentes na última coleta são excluídos da seleção.
4. Quando a TON estiver informada na observação, manter somente contratos cuja capacidade seja exatamente essa TON e selecionar o **maior ID tarifário numérico** entre eles. Essa é a regra de atualidade definida pelo usuário; não se usa a ordem do catálogo nem comparação alfabética de IDs.
5. O frete é conferido **depois da seleção**. Um contrato antigo com valor igual ao SQL não substitui o maior ID com a TON correta. Um ID tarifário explícito anterior fica preservado na observação; se diferir do selecionado, gera alerta.
6. Se não houver contrato com a TON correta, exibir **Sem tarifa**. Se o maior ID estiver duplicado em registros diferentes, manter **Conferir tarifa**, pois a regra não distingue esses registros.
7. Na ausência de TON, manter a identificação anterior: ID tarifário explícito confirmado, referência única por rota/vigência ou correspondência única de frete. A ausência da TON continua sinalizada, sem inventar um valor observado.

São exibidos os estados **Conferido**, **Divergência**, **Dados incompletos**, **Conferir tarifa**, **Sem tarifa** e **Indisponível**. Falha de leitura do catálogo gera alerta sem interromper a verificação dos documentos.

As quantias são comparadas em centavos usando `Decimal`. Uma diferença de R$ 0,01 é sinalizada. A TON é comparada exatamente à capacidade contratada. O total de referência mostrado é:

`frete do tarifário + FREVAL do SQL + OUTROS do SQL`

A composição original também é conferida: `VLR_TAR + FREVAL + OUTROS` contra `VLR_TOTAL`.

## Tela e mensagem

- A lista mostra origem/destino, TON da observação e da tarifa, ID tarifário, os dois fretes e resultado da conferência.
- O painel lateral mantém a situação dos documentos e acrescenta a comparação financeira, diferenças, IDs da observação, candidatos e link para o contrato do portal.
- A exportação Excel inclui os campos da conferência.
- Na preparação do chamado do fluxo de pendentes, uma correspondência única preenche **ID TARIFARIO** e **TON** da referência contratada. `ID` e `PERCURSO` originais continuam nos campos próprios da mensagem. Alertas são registrados e a abertura permanece permitida.
- Um resultado automático anterior não é reutilizado se uma nova conferência se tornar ambígua ou indisponível. Os dados originais permanecem recuperáveis.

O teste de preparação da mensagem utiliza o envio ao portal substituído por uma função de teste. Isso confirma os campos gerados e a ausência de bloqueio; **não representa um chamado efetivamente aberto**.

## Exemplo real conferido

CT-e **8-10-1559**:

| Informação | SQL / observação | Referência |
| --- | --- | --- |
| Rota | João Pessoa → Cabedelo, PB | PB-João Pessoa → PB-Cabedelo |
| TON | **30 t**, do trecho `30 TON` | **30 t** |
| ID da observação | 217903 | Preservado separadamente |
| ID tarifário | Ausente | 666318 |
| Frete base | R$ 4.644,00 | R$ 4.644,00 |
| FREVAL | R$ 159,30 | Mantido do SQL |
| Outros | R$ 1.200,83 | Mantido do SQL |
| Total | R$ 6.004,13 | R$ 6.004,13 com os componentes SQL |

O contrato é confirmado por rota, vigência, TON e frete. O estado correto é **Conferido**. A indicação anterior de TON ausente resultava de um erro do extrator, que só reconhecia a quantidade depois da unidade. O trecho real `ID 217903 | 30 TON - ROTA NÃO POSSUI PEDAGIO` é agora interpretado corretamente, sem confundir `1.645,14` de impostos com a tonelagem.

Para **ES-Vila Velha → SP-Pindamonhangaba**, com **30 t**, os contratos elegíveis 666311 e 666552 são resolvidos pelo **666552**. Os IDs 666605 (34 t), 666734 e 666883 (27 t) não entram nessa disputa. Rota, empresa e vigência continuam obrigatórias antes da escolha do maior ID.

A validação real dessa regra pela API e interface confirmou o **CT-e 1-10-26087**, tarifa **666552**, 30 t / 30 t e estado **Conferido**. A fila atual tem **18 conferidos e 2 divergências**, sem casos ambíguos. Foram executados **33 testes direcionados**, todos aprovados, cobrindo seleção numérica, ordem do catálogo, TON diferente, empresa/rota/vigência, ID anterior, divergência financeira e preparação do chamado sem bloqueio.

Na validação anterior, após a correção do formato com a quantidade antes da unidade e antes da regra de maior ID, os **20 CT-es** tinham **17 conferidos, 2 com divergência e 1 ambíguo**. Essa leitura SQL confirmou diretamente o caso 8-10-1559; não houve escrita no SQL Server.

## Atualização do tarifário

A tentativa de atualização relatada pelo usuário deixava apenas uma mensagem genérica, sem código/etapa suficientes para atribuir retrospectivamente a causa exata. A nova tentativa concluiu. Foram implementadas medidas verificáveis:

- Repetição limitada a uma nova tentativa da **consulta de leitura** em timeout, falha de rede ou HTTP 502/503/504. Login não é repetido indiscriminadamente. Não há contorno de CAPTCHA ou autenticação.
- Importação atualiza os registros cujo conteúdo mudou, marca como ausentes apenas os que desapareceram e conserva as versões anteriores. Tarifas/cidades inalteradas deixam de ser regravadas integralmente.
- A última conferência apresentada para os registros presentes usa a conclusão da coleta compartilhada, mesmo quando o valor não mudou.
- Estado compartilhado passa a guardar etapa e código seguro de falha, sem senha, cookie, cabeçalhos ou corpo de autenticação.
- Atualização real pela API usada pelo botão retornou **HTTP 202**, terminou na etapa **concluída** e manteve **10.027 tarifas**, sem erro JavaScript na leitura da interface.

Também foi corrigida uma trava na listagem de documentos: o índice mantinha o lock global durante cada acesso SMB e serializava pastas independentes. Agora há um lock por pasta. No perfil executado, a etapa de arquivos passou de **33,859 s para 7,219 s**. O índice continua restrito à consulta, preservando a detecção de criação/exclusão de arquivos.

## Evidências e limites

Regressão após a correção de `30 TON`: **462 testes backend passaram e 4 foram ignorados**. A validação pela API e interface reais confirmou 30 t / 30 t, tarifa 666318 e estado Conferido para o CT-e 8-10-1559. A suíte frontend já executada passou com 50 testes.

Arquivos locais em `runtime/dev-preview/`:

- `tariff-refresh-diagnosis.log`, `tariff-refresh-optimized.log`: nova coleta e persistência reais, com tempos por etapa.
- `audit-queue-profile.log`: perfil da fila e distribuição dos estados.
- `tariff-ui-validation.json`, `cte-tariff-ui-test.log`: atualização, API local, catálogo PostgreSQL e comparação na interface com dados reais; sessão técnica identificada e encerrada.
- `cte-tarifas-real.png`, `cte-tarifa-real-lateral.png`: capturas da lista e da comparação.
- `ton-postfix-real.json`, `ton-postfix-tests.log`, `backend-ton-postfix-tests.log`: leitura SQL real com a identidade completa e regressão de formatos de tonelagem. As capturas anteriores à correção de `30 TON` são históricas; a validação atual desse caso fica em `ton-postfix-ui.json` e `ton-postfix-lateral.png`.
- `tariff-latest-id-tests.log`, `tariff-latest-id-ui.json`, `tariff-latest-id-lateral.png`: regra de maior ID numérico com a TON correta, 33 testes direcionados e validação real do CT-e 1-10-26087 na interface; nenhum chamado foi enviado.
- `backend-cte-audit-final-tests.log`, `frontend-cte-audit-tests.log`, `cte-tariff-typecheck.log`, `cte-audit-final-lint.log`: regressão e análise estática.

Os testes não comprovam ausência de falhas futuras da rede/portal, execução da virada de vigência em tempo real nem homologação de instalador limpo. O candidato de instalador anterior permanece intacto. A prévia usa a configuração existente de revisão e não habilita agendamentos automáticos em segundo plano.
