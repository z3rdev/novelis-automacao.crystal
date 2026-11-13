# Revisão r5 privada e Code 128 independente

O instalador de teste foi gerado em 12/11/2026.

- Arquivo `runtime/private-installer/NovelisCargoHubSetup-0.1.34-r5-PRIVADO-TESTE-NaoDistribuir.exe`.
- Tamanho de 741.413.499 bytes.
- SHA-256 `4ac3e4082de72dfbf91d4b32f25bb552ca49e8236a8b20429301b996cf5e2ecf`.
- Configuração operacional privada, protegida por permissões de arquivo.

## Diagnóstico confirmado

O NB-GFR-VIN-05 carregou oito CT-e pela consulta SQL. O filtro Novelis
identificou sete pendentes. O diagnóstico recebido desse PC mostrou a fonte
`IDAutomationSC128L DEMO` ausente e o gerador independente de QR disponível.
O RPT utiliza essa fonte no campo `{@F_CODBAR}`. Os dois documentos que
falharam foram `2-10-17419` e `8-10-1556`.

As tentativas com escopo PDF também expuseram uma configuração incoerente.
Esse escopo desativava a consulta Novelis e exigia o resultado dela para
prosseguir. A r5 configura a geração isolada de PDF a partir dos documentos
consultados. O fluxo completo utiliza a conferência Novelis na seleção dos
pendentes.

## Implementação

Conforme a opção escolhida pelo usuário, o backend gera o Code 128 em BMP
com a chave de 44 dígitos obtida do banco. O encoder é o ZXing-C++ 3.1.1,
presente no wheelhouse existente. A dependência mínima foi ajustada para
3.0, que oferece a API de escrita utilizada.

O worker x86 abre o RPT com `CrystalDesignRunTime.Application.11` e insere
a imagem no lugar de `{@F_CODBAR}` através de `AddPictureObject`. A posição,
as dimensões, a altura da seção e as fórmulas condicionais de supressão e
deslocamento horizontal são preservadas durante a inserção. O SHA-256 do
arquivo RPT foi conferido antes e depois dos testes.

A configuração operacional do pacote define
`CRYSTAL_CODE128_PROVIDER=python`. O modo `report` pode ser configurado para
ambientes que utilizem a apresentação original com fonte licenciada. Os
clientes anteriores que selecionam o renderer `report` e omitem a nova
opção continuam utilizando esse modo.

A validação do PDF compara o Code 128 decodificado à chave do banco e o QR
decodificado ao conteúdo original consultado. Uma leitura ausente recebe
mensagem específica. PDFs rejeitados são removidos da saída do serviço.

O diagnóstico e a preparação consideram os renderers selecionados ao
calcular as dependências. O instalador prepara os componentes automaticamente
e a tela de seleção de instaladores de fontes foi retirada.

## Arquivos

Foram criados `BACKEND/app/services/crystal_reports/code128.py`,
`code128-picture.ps1` no mesmo diretório e
`BACKEND/tests/test_dacte_code128.py`.

Foram alterados os arquivos abaixo.

- `BACKEND/app/services/crystal_reports/service.py`, `worker.ps1`, `qr_code.py`
  e `diagnostics.py`.
- `BACKEND/app/tools/dacte_components.py` e `dacte_setup.py`.
- `BACKEND/app/automation/flows/pendentes/controles/execution_scope.py`.
- `BACKEND/.env.example` e `BACKEND/pyproject.toml`.
- `scripts/setup/environment_payload.py`, `installer_receipt.py` no mesmo
  diretório e `scripts/prepare-installer-inputs.py`.
- `installer/AutomacaoNovelis.iss`.
- `BACKEND/tests/test_hub_scope.py` e `test_operational_configuration.py`.

O manifesto do EXE registra os hashes dos fontes DACTE, configuração e consulta.

## Testes executados

Os 168 testes da seleção de regressão passaram, incluindo os testes com a
instalação isolada. O log contém um aviso de depreciação do TestClient.
O teste COM adicional confirmou posição, tamanho, altura da seção e fórmulas
condicionais da imagem no RDC 11.5.

Quatro exportações reais passaram na máquina de desenvolvimento.

| Documento | Mecanismo | Code 128 e QR comparados ao banco | Páginas |
| --- | --- | --- | --- |
| 2-10-17419 | Windows, PrintOutEx | Aprovados | 1 |
| 8-10-1556 | Windows, PrintOutEx | Aprovados | 1 |
| 2-10-10402 | Windows, PrintOutEx | Aprovados | 1 |
| 2-10-17419 | Exportador PDF nativo | Aprovados | 1 |

Os PDFs foram renderizados pelo Poppler e as quatro páginas foram inspecionadas.
Os códigos e os textos adjacentes ficaram legíveis e dentro de suas áreas.
A lista de fontes dos PDFs foi conferida para comprovar o uso da imagem.
Os valores efetivamente decodificados estão no relatório de verificação.

As evidências estão nos arquivos abaixo.

- `runtime/crystal-tests/hub-r5-validation.log`.
- `runtime/crystal-tests/code128-independent-development/verification.json`.
- `runtime/crystal-tests/code128-layout-verification.json`.
- `runtime/crystal-tests/hub-r5-final-verification.json`.
- `runtime/crystal-tests/physical-pc-20261112/code128/`.

## Licenças e homologação

O ZXing-C++ 3.1.1 declara licença Apache-2.0. O wheel original incluído
contém o arquivo de licença, que também é instalado pelo pip. A redistribuição
exige a entrega da licença e a retenção dos avisos aplicáveis. A seção 4 do
texto oficial descreve essas condições. [Licença oficial do ZXing-C++ 3.1.1](https://github.com/zxing-cpp/zxing-cpp/blob/v3.1.1/LICENSE)

As execuções dos quatro PDFs ocorreram no computador de desenvolvimento,
que possui o Crystal completo. A r5 precisa ser testada no NB-GFR-VIN-05
com o runtime RDC instalado. A homologação fiscal, incluindo contingência,
continua pendente. O RPT possui um aviso previamente inventariado sobre o
campo de contingência `fcobbar21`, cuja fonte cadastrada é Arial.

As aprovações de procedência e redistribuição do Crystal continuam pendentes.
O pacote contém dados operacionais privados e está destinado ao teste
controlado autorizado.

## Próximo teste

Instale a r5 na mesma pasta e com a conta que executa o backend. Execute
Somente PDF para um dia. Para os documentos que ainda exigirem geração,
confira os eventos `crystal_pdf.generated` e `crystal_pdf.saved`. O plano
deve ser recalculado com os arquivos publicados na pasta de destino.

Em seguida, execute Consultar pendentes e o fluxo completo para conferir
a seleção Novelis e as etapas autorizadas. Os eventos do NB-GFR-VIN-05
ficam registrados no banco operacional compartilhado.
