# Novelis Cargo Hub 0.1.35

Build interno solicitado e aprovado pelo responsável na conversa de 13/11/2026.
O pacote privado incorpora a configuração operacional preenchida. Seu destino
é a implantação interna autorizada; o perfil de publicação MinIO e o marcador
de desenvolvedor permanecem fora do instalador.

## Conteúdo da versão

- Interface Cargo Hub em janela Tauri com identidade visual e ícone atualizados.
- Login por conta Windows e nome do operador, com registros de sessão no SQLite.
- Bandeja, recuperação da instância existente e opção de iniciar com o Windows.
- Notificações, atualização pelo MinIO, agendamentos e painel de usuários do desenvolvedor.
- Verificação dos arquivos dos CT-es e consulta SQL por período.
- DACTE Crystal COM x86 com QR e Code 128 gerados em imagens e PDFs organizados por CT-e.
- Python 3.12.10 x64 local, wheelhouse offline, Chromium, WebView2 e Visual C++ Runtime.
- Pré-requisito MSI Crystal RDC 1.0.2, com os quatro módulos 11.5.0.313 x86.

A API temporária usada pelo instalador verifica a disponibilidade do backend
sem iniciar agendamentos, interromper sessões ou restaurar execuções anteriores.
A inicialização normal mantém o comportamento operacional do aplicativo.

## Aprovação registrada

Ao ser solicitado o arquivo de aprovação de licença e procedência, o usuário
respondeu: “Foram testados e aprovados pode adicionar não tenho o caminho”.
A declaração foi registrada em arquivos privados fora do Git e vinculada ao
hash do MSI. A origem dessa aprovação é a conversa com o responsável.

Esses registros não representam um contrato, certificado SAP ou verificação
independente do entitlement e da mídia. O manifesto identifica a aprovação
como `user_declaration_in_conversation`, com escopo interno e verificação
independente falsa. Seriais e PIDKEY não constam desses registros.

## Evidências do build

Os logs e relatórios ficam em `runtime/ui-review/release-0.1.35-*`.
O manifesto junto ao executável vincula seu SHA-256 aos arquivos do backend,
scripts, frontend estático, ícone, executável nativo e pré-requisito Crystal.

A validação do layout instalado usa bancos isolados e os mesmos insumos de
Python/wheels/frontend do pacote, sem executar a automação empresarial.
Esse teste não executa o instalador final nem instala o MSI Crystal sobre
uma máquina limpa. A situação da homologação independente permanece explícita
nos manifestos. A aprovação informada pelo usuário é registrada separadamente
das verificações efetivamente executadas pelo agente.
