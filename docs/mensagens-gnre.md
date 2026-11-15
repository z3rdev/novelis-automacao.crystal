# Mensagens e documentos GNRE

## Solicitação

Em **Mensagens**, o botão **+** junto ao campo de texto abre a solicitação na conversa selecionada. A lista **CT-es pendentes de GNRE e comprovante** mostra os itens da fila de abertura com documentação exigida e faltante. A seleção preenche o CT-e. Continua possível informar o CT-e manualmente, inclusive para tratar um chamado já existente.

O botão **Solicitar GNRE** do cabeçalho permite escolher Financeiro ou um operador online desse setor. A presença considera contato do chat nos últimos 90 segundos. Os documentos são vinculados à identidade completa `filial-serie-documento`, compartilhada entre as solicitações desse CT-e. O login usa o nome da conta Windows, sem edição pelo operador.

## Armazenamento

1. O backend valida o PDF ou converte a imagem aceita em PDF.
2. Envia cada documento ao MinIO privado e confere tamanho e SHA-256.
3. Lê os dois documentos do MinIO, unifica guia e comprovante e salva o resultado no MinIO.
4. Baixa o resultado para `\\192.168.254.250\rede\Publico\EXPEDIÇÃO - COMPROVANTES\<CT-e>\GNR_CMP_<CT-e>.pdf`.
5. Publica um índice de integridade na mesma pasta. O planejamento identifica guia e comprovante nesse PDF e a montagem do ZIP usa o unificado.
6. Após um evento persistido `novelis.save` com `result.ok=true`, número do chamado e data posterior ao envio dos documentos, arquiva os objetos no MinIO e confere sua integridade. Só então remove a cópia de rede gerenciada.
7. Os documentos continuam disponíveis pelo chat por **30 dias a partir da confirmação do chamado**. Ao vencer o prazo, o aplicativo bloqueia o download e exclui os objetos arquivados. Uma regra de expiração no MinIO também cobre esse prefixo, inclusive quando os aplicativos estão fechados.

Prefixos usados no bucket existente:

- `cargo-hub/gnre/pending/<CT-e>/`: envios aguardando confirmação do chamado.
- `cargo-hub/gnre/archive/<CT-e>/<arquivo-id>/`: documentos após a confirmação.

A regra `cargo-hub-gnre-archive-30-days` se aplica apenas ao segundo prefixo. As demais regras do bucket são preservadas. Os documentos pendentes não expiram antes da confirmação. O bucket verificado não usa versionamento. A remoção por lifecycle é processada pelo servidor depois da elegibilidade; a interface respeita o prazo mesmo antes da remoção física.

Documentação oficial da API de lifecycle: [PutBucketLifecycleConfiguration](https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/put_bucket_lifecycle_configuration.html) e [expiração de objetos](https://docs.aws.amazon.com/AmazonS3/latest/userguide/lifecycle-expire-general-considerations.html).

## Falhas e recuperação

- Falha no MinIO impede a confirmação do upload e a criação da cópia na rede.
- Falha na rede mantém os objetos no MinIO e deixa a entrega pendente, com nova tentativa automática a cada 60 segundos ou ao atualizar a conversa.
- Falha no arquivamento mantém a cópia da rede. A limpeza retoma após a conferência dos objetos arquivados.
- A limpeza verifica CT-e, revisão, caminho e hash. Arquivos manuais ou alterados não são removidos.
- As confirmações são recuperadas do histórico compartilhado por CT-e, sem depender dos últimos mil eventos ou de o chat estar aberto.
- Documentos do modelo anterior são migrados para o MinIO antes de retirar os arquivos antigos indicados no índice.
- Substituir documentos depois do arquivamento inicia uma nova revisão. Uma confirmação antiga não encerra essa nova revisão.

## Configuração privada

O backend usa `GNRE_S3_CREDENTIALS_FILE`, quando informado. Caso contrário, reutiliza `EXECUTION_REPORT_S3_CREDENTIALS_FILE`. Na máquina de desenvolvimento, também pode usar a configuração local de desenvolvimento existente.

O arquivo segue o formato já usado no projeto, com `url`, `accessKey`, `secretKey` e `region` opcional. Deve permanecer fora do repositório e do frontend. Cada backend que envia ou lê documentos precisa de acesso autorizado a esse armazenamento. A configuração atual do instalador não foi reconstruída nesta alteração.

Permissões necessárias incluem leitura da política de privacidade e do lifecycle do bucket, listagem dos dois prefixos e leitura, escrita, cópia e exclusão dos respectivos objetos. Criar ou alterar a regra de retenção exige permissão administrativa de lifecycle. Evite conceder publicação de releases aos operadores apenas para permitir GNRE.

## Widget

O widget compacto mantém o estado da automação e mostra o contador de mensagens não lidas. Clicar no aviso abre **Mensagens**. A leitura da conversa retira o aviso. O aplicativo solicita o som de notificação do Windows uma vez por nova sequência de mensagem, respeitando volume e sons configurados no sistema.

## Validação desta alteração

- Testes de interface cobrem seleção de CT-e, solicitação na mesma conversa, contador do widget, navegação e deduplicação do som.
- Testes PostgreSQL usam tabelas isoladas e S3 em memória. Cobrem concorrência, autorização, migração, arquivamento, falha de cópia, expiração e confirmação antiga entre mais de mil outros eventos.
- Teste real no MinIO usa PDFs de controle e uma identidade de CT-e exclusiva de QA. Confere a unificação, o download, os hashes e a remoção dos próprios objetos ao finalizar.
- Validação visual em claro e escuro, com larguras de 1440 e 1024 pixels, usa respostas controladas, sem abrir chamados fiscais.
- Logs e resultados estão em `runtime/dev-preview/gnre-*`. O teste operacional entre computadores e a percepção do som pelo operador ainda devem ser conferidos na prévia.

Nenhum instalador oficial foi gerado por esta alteração.

## Segunda janela para teste do Financeiro

Com a prévia principal aberta, execute no PowerShell:

```powershell
& 'E:\PROJETOS\AUTOMAÇÃO NOVELIS\scripts\start-finance-preview.ps1'
```

O comando abre uma segunda janela Tauri, intitulada **Financeiro · teste de mensagens**. Ela usa a identidade artificial `PREVIA\financeiro.teste` e o dispositivo de teste `NB-FIN-VIN-TESTE`. A conta Windows real e as regras de classificação dos computadores permanecem como estão.

A segunda janela tem origem web local `127.0.0.1:1421`, conexão local `127.0.0.1:18037` e bancos operacionais e de sessão locais em `runtime/dev-preview/finance-backend`. As conversas e os documentos continuam no armazenamento compartilhado. A identidade artificial exige `CONFIG.dev` e as credenciais locais de desenvolvimento, não funciona em uma instalação distribuída, e as mutações dessa conexão estão limitadas a login e chat. Agendamentos e rotinas fiscais não são iniciados nela.

Entre nas duas janelas. Na principal, envie uma mensagem ou solicitação para Financeiro. Na segunda, abra a conversa recebida e responda. O contador e o som devem avisar a janela destinatária. Para verificar o aviso no widget principal, deixe a janela principal em segundo plano e responda pelo Financeiro. O operador artificial aparece no diretório de mensagens enquanto estiver online.
