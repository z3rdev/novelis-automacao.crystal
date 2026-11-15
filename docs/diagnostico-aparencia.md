# Diagnóstico DACTE e aparência

O botão **Aparência** na barra superior e na tela de entrada alterna **Claro / Escuro** com um clique. Segurar o botão por 600 ms abre a opção **Seguir o computador**; soltar o clique longo não alterna o tema. Também é possível abrir essa opção com seta para baixo ou Shift+F10 quando o botão está focado. A preferência fica salva no perfil local. O modo automático acompanha alterações do sistema enquanto o aplicativo está aberto. A troca alcança tabelas, formulários, menus, painéis, avisos e o editor de fluxo. O seletor não depende da senha das configurações operacionais.

Na janela nativa, `F12` e `Ctrl+Shift+I` são interceptados junto aos atalhos de impressão já bloqueados. O WebView2 também recebe `AreDevToolsEnabled=false`; a configuração Tauri desativa `devtools`. O bloqueio do WebView requer carregar o executável nativo atualizado; o bloqueio de teclas e o botão de tema acompanham a interface por HMR. Nenhum controle de modo desenvolvedor operacional ou credencial foi alterado.

A integração Tauri solicita o mesmo tema para a janela do Windows. Essa parte depende da permissão `core:window:allow-set-theme`. Uma prévia nativa antiga continua mostrando o tema interno mesmo que ainda não consiga alterar a moldura da janela. A prévia de desenvolvimento aberta recompilou e reiniciou automaticamente após a alteração nativa desta etapa; nenhum instalador foi gerado.

Validação da interação de 15/11: oito testes de tema/atalhos aprovados, TypeScript e ESLint aprovados. O navegador Edge com dados controlados confirmou clique curto, clique longo, soltura sem alternância extra, acompanhamento do tema do sistema e persistência após recarregar. Evidência: `runtime/dev-preview/appearance-press-validation.json`. O teste de teclas no navegador verificou o manipulador DOM; não foi uma inspeção manual da janela nativa. O executável debug em execução foi atualizado pelo observador Tauri às 10:10, horário de São Paulo.

## Diagnóstico da instalação

`runtime/installation/dacte-diagnostic.html` passa a agrupar os resultados em Crystal RDC x86, relatório e geração do DACTE, conexão e testes com documento, e preparação realizada. Exibe os estados verificado, ausente, falhou, não testado e pendente; a presença das dependências não promove os testes fiscais a concluídos.

O relatório tem filtros de atenção e verificações não concluídas, dados técnicos recolhidos, cópia, download JSON, impressão e tema claro/escuro. HTML, estilos e comportamento ficam em um único arquivo para uso offline. Os dados são escapados e campos de credenciais são ocultados na apresentação e na gravação do diagnóstico. A preparação sem Python tem uma página de falha compatível, sem tentar executar o Crystal.

O HTML instalado no computador de desenvolvimento foi atualizado usando o JSON já existente. A cópia anterior foi preservada como `dacte-diagnostic.before-redesign-20261115.html`. Essa atualização visual não refez testes de ambiente, conexão, exportação ou códigos; a data e os estados do resultado original foram mantidos.

## Verificações

- Testes de persistência do tema, mudança de tema do Windows e escolha entre janelas.
- Relatório com resultados parciais, campos sensíveis e texto não confiável.
- Preparação isolada sem Python, executada com Windows PowerShell.
- Conferência visual do app com dados controlados, incluindo entrada, agendamentos e fluxo.
- Conferência do HTML com os resultados existentes: filtros, JSON e tela de 540 pixels sem transbordamento horizontal.
- Na conferência visual, texto secundário do formulário no tema escuro apresentou contraste de 7,71:1 contra a superfície utilizada.

Os logs e capturas desta revisão estão em `runtime/dev-preview/appearance-*`, `app-dark-*` e `dacte-diagnostic-*`. O aplicativo instalado recebe os novos fontes e a permissão nativa no próximo build aprovado.
