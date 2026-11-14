# Usuários e dispositivos

O menu Desenvolvimento tem uma tela própria, Usuários e dispositivos, em
`/usuarios-dev`. O acesso exige uma sessão de operador válida, `CONFIG.dev`
com `DEVMODE=1` e `credentials.json` na pasta BACKEND da cópia em execução.
A API aplica a mesma restrição, inclusive quando o endereço é acessado diretamente.

O painel consulta o SQLite compartilhado dos registros de sessão, definido por
`LOGIN_AUDIT_DB_PATH`. O padrão é `logs/sessoes.sqlite` ao lado do banco operacional.
As novas informações ficam na tabela `devices`; as tabelas e os registros
anteriores de sessões e eventos são preservados.

## Informações exibidas

- Computador, conta Windows e MACs informados pelo próprio backend.
- Operadores com sessão ativa, hora de entrada, saída e último contato.
- Tipo da cópia, versão e pasta da aplicação.
- Automação parada, executando, parando, concluída, cancelada ou com falha.
- Busca por operador, conta, computador ou MAC e filtros de conexão e instalação.
- Detalhes do computador e suas sessões recentes.

O backend envia um sinal a cada 30 segundos, inclusive com a janela na bandeja.
O painel consulta os registros a cada 15 segundos. Um sinal com mais de
90 segundos deixa de contar como online. Sessões ainda marcadas como ativas
nessa situação aparecem como Sem sinal. A conexão indica atividade do
aplicativo; a presença física do operador não é medida.

O encerramento normal do backend marca o cliente como parado e encerra as
sessões locais ativas como interrompidas. Após uma queda abrupta, a expiração
do sinal permite identificar a ausência de atividade. O estado de automação
de um cliente offline é apresentado como o último estado recebido.

## Inventário de instalações

Uma instalação é identificada pela presença do marcador
`.automacao-novelis-install` e do arquivo de versão `installed-release.json`
na raiz da cópia executada. Um checkout aparece como Desenvolvimento.
O inventário conserva a primeira detecção e atualiza versão e pasta quando
a instalação muda no mesmo computador. A chave usa o nome do computador
e o tipo da cópia. Renomear o computador cria uma nova identificação.

O painel identifica instalações que já comunicaram sua presença. Um registro
offline preserva a última instalação detectada e não comprova desinstalação.
Clientes antigos com apenas logs de sessão aparecem como Não informado,
com a versão desconhecida. O próximo instalador deve incluir este backend
para esses clientes passarem a enviar o inventário.

## Disponibilidade e limites

O cliente grava os sinais em uma fila SQLite local e os replica pelo mecanismo
de auditoria existente. Durante uma falha da rede, sinais periódicos antigos
são substituídos pelo mais recente; entradas, saídas e transições de execução
são preservadas. Atualizações atrasadas não substituem um sinal mais recente.
O encerramento de uma instância anterior não marca uma instância nova como parada.

O painel consulta até 1.000 registros de dispositivos e as 500 sessões mais
recentes, informando quando esse limite foi atingido. Os indicadores se referem
aos registros exibidos. As contas conectadas são contadas por conta Windows,
enquanto a aba Sessões mostra cada sessão do aplicativo.

Uma falha no compartilhamento é exibida no painel. Se houver uma consulta
anterior, seus dados continuam visíveis com o aviso de indisponibilidade.
Os identificadores usados para autenticar sessões não são devolvidos por
essa consulta. O inventário e o histórico são disponibilizados pelo backend
local autorizado a ler o SQLite compartilhado.

## Validação

Os testes cobrem autenticação e modo desenvolvedor, instalação e checkout,
registro antes do login, atualização em segundo plano, expiração de atividade,
fila durante falha da rede, atualização de versão, dados de outros computadores
e encerramento do ciclo de vida real da aplicação FastAPI.

As verificações visuais usam dados de teste identificados nos logs e conferem
busca, filtros, sessões, detalhes, layout em 1024 pixels e retenção dos dados
quando a consulta falha. A coleta em computadores antigos requer a atualização
do backend; testes locais não representam homologação desses computadores.
