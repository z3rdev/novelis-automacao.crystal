# DACTE com rpt-rs

## Checkpoint Crystal

O projeto anterior ao protótipo está publicado na `main` do repositório
`z3rdev/novelis-automacao.crystal`, com a tag `v0.1.34-crystal-r5` e o commit
`a1b1e22dba791417519b16560a6ca50a103b5f41`.

A publicação foi filtrada para proteger `.env`, credenciais, chaves, dados de execução,
pacotes proprietários, instaladores privados e uma captura OCR com código de sessão.
O frontend Tauri e o RPT sanitizado integram o checkpoint.

O protótipo tem a branch `codex/rpt-rs-poc`.

## Implementação

O backend Python chama `novelis-rpt-worker.exe` por JSON na entrada padrão. O worker
Rust lê o RPT original, produz o modelo e o plano de dados, recebe linhas tipadas e
renderiza o PDF. O adaptador Python executa consultas parametrizadas no SQL Server.
As credenciais permanecem no processo Python.

O relatório principal fornece 287 colunas. Os cinco sub-relatórios fornecem os
seguintes conjuntos.

| Escopo | Colunas |
| --- | --- |
| sub_ctrc | 16 |
| Sub_RODNFC.rpt | 7 |
| Sub_RODNFC2.rpt | 7 |
| Sub_RODCPL.rpt | 7 |
| SUB_PRODUTO_PERIGOSO.rpt | 8 |

Os joins vêm do modelo extraído do RPT. Cada consulta é limitada ao documento por
filial, série e número. A seleção original e os vínculos dos sub-relatórios seguem
para o pipeline do motor.

O modelo em memória recebe QR Code e Code 128 em bitmap, produzidos pelos geradores
existentes a partir da chave e do payload consultados no banco. O adaptador traduz
as condições Basic suportadas para expressões Crystal e preserva os limites dos
objetos. Instruções desconhecidas geram erro explícito. O RPT original tem seu
SHA-256 conferido antes e depois da exportação.

A API experimental é `RptRsService.export_candidate(document)`. O comando de avaliação
gera candidatos e evidências locais. A promoção ao fluxo operacional depende dos
resultados de fidelidade e homologação descritos abaixo.

## Compilação e execução

O projeto fixa Rust 1.99.1 MSVC x64 e o commit upstream
`3f5beb51dd34d36c4a4326280d25f473b44889d1`. `Cargo.lock` fixa as dependências.
O build requer MSVC C++ x64 e Windows SDK, detectados pelo `vswhere`.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-rpt-worker.ps1

& .\BACKEND\.venv\Scripts\python.exe .\scripts\evaluate-rpt-rs.py `
  --document 1-1-123 `
  --output-dir .\runtime\rpt-rs-evaluation
```

Substitua o documento por um CT-e autorizado. O ambiente Python deve conter as
dependências do backend e o extra `dacte`. A configuração SQL usa o `.env` operacional.

Para comparar, forneça `--reference-dir` com arquivos no padrão
`candidate-dacte-FILIAL-SERIE-NUMERO-windows.pdf`. Para usar outro executável,
forneça `--worker CAMINHO`. O build `-Release` grava em `rpt-worker/target/release`.

`evaluation.json` consolida os resultados. Cada candidato tem evidência JSON e,
quando há referência, um arquivo `.comparison.json` com códigos decodificados e
diferenças textuais. Esses arquivos contêm dados fiscais e pertencem à área local
ignorada pelo Git. O console apresenta somente identificadores, estados e contagens.

O código de saída 2 indica falha de execução, símbolos inválidos ou incompatibilidade
detectada com a referência. O código 0 identifica a geração dos candidatos. A revisão
visual e a conferência fiscal continuam registradas como pendentes no resultado.

## Resultados de desenvolvimento

Em 13/11/2026, foram gerados três documentos reais e comparados às referências Crystal
r5. Dois casos têm uma nota fiscal e o terceiro tem duas notas. Os seis escopos SQL
foram consultados nos três casos, incluindo os conjuntos legitimamente vazios.

| Caso | QR igual ao banco | Code 128 igual ao banco | Páginas rpt-rs | Páginas Crystal | Tokens da referência ausentes |
| --- | --- | --- | --- | --- | --- |
| A, uma nota | Sim | Sim | 2 | 1 | 50 |
| B, uma nota | Sim | Sim | 2 | 1 | 56 |
| C, duas notas | Sim | Sim | 2 | 1 | 52 |

A comparação lexical registra diferenças de conteúdo e formatação. As consultas
ocorrem em momentos distintos e podem refletir atualizações no banco. Cada diferença
precisa ser conciliada com os dados originais.

As seis páginas foram renderizadas com Poppler e revisadas visualmente. Foram
observados cabeçalhos repetidos, logo ausente, campos de endereço, carga e componentes
do frete vazios, diferenças de máscara e horário, e sobreposição das duas notas no
terceiro caso. O resultado está marcado como `production_ready=false`.

A inspeção original de fórmulas pelo CLI upstream encontrou 22 erros e seis avisos,
incluindo encoders e condições Basic. A adaptação normaliza 22 ocorrências de condições
e substitui dois objetos QR e um Code 128. Os diagnósticos de renderização retornaram
vazios apesar das divergências visuais, portanto a aprovação exige comparação externa.

O código upstream confirma que `emit_band_no_paginate`, utilizado pelos cabeçalhos,
avalia somente a supressão estática. O método de fluxo `emit_band` também avalia
`Section_Visibility`. Essa diferença explica a repetição de cabeçalhos condicionais.
As variáveis compartilhadas e os campos vazios ainda precisam de investigação.

O build debug x64 compilou com sucesso. O `dumpbin /DEPENDENTS` listou bibliotecas do
Windows e `VCRUNTIME140.dll`. A inspeção estática e o código do worker sustentam a
independência do processo Rust em relação à API COM Crystal.

Os testes selecionados passaram, totalizando 99 testes de backend, incluindo dez do
adaptador novo. Há um aviso preexistente de depreciação do TestClient. O Ruff passou
nos arquivos Python novos e o Rust foi formatado com `cargo fmt`.

As evidências locais estão em `runtime/rpt-rs-evaluation`, incluindo `evaluation.json`,
`evaluation.log`, `pytest.log`, `worker-build.log`, `native-dependencies.txt` e as
imagens das páginas. O teste foi executado na máquina de desenvolvimento.

## Próximas validações

1. Corrigir a supressão dos cabeçalhos no motor e medir a paginação novamente.
2. Investigar as variáveis compartilhadas entre os cinco sub-relatórios e o principal,
   reconciliando produto, pesos, valor da carga e componentes do frete com o SQL.
3. Corrigir logo, máscaras numéricas, horário e fluxo de múltiplas notas.
4. Validar as fórmulas e os códigos específicos de contingência, incluindo `f_cobbar1`
   e `f_cobbar2`, com documentos autorizados desse tipo.
5. Repetir a comparação com referências Crystal geradas sobre os mesmos dados e conferir
   posições, valores e paginação. Os códigos decodificados devem coincidir integralmente
   com o banco e com a referência.
6. Em um PC autorizado limpo, instalar o backend de teste, o driver ODBC SQL Server e
   os pré-requisitos nativos x64. Executar o comando com o worker compilado, o RPT e a
   configuração operacional, sob a conta real do backend. Registrar inventário do PC,
   ausência do editor Crystal, conexão SQL, códigos decodificados e inspeção de todas
   as páginas. Esse ensaio continua pendente.

## Origem e licença

O código do motor vem do repositório oficial `MrSrsen/rpt-rs`, fixado por commit.
A licença upstream declarada é MPL 2.0. A preparação de um pacote binário requer
revisão dos avisos e licenças das dependências e das fontes utilizadas.

[Código upstream fixado](https://github.com/MrSrsen/rpt-rs/tree/3f5beb51dd34d36c4a4326280d25f473b44889d1)

[Licença upstream](https://github.com/MrSrsen/rpt-rs/blob/3f5beb51dd34d36c4a4326280d25f473b44889d1/LICENSE)
