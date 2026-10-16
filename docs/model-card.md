- **Identificação** — nome do sistema, versão, data e os responsáveis
  nomeados: quem responde pelo agente quando algo dá errado.
  - organizador de fila via chatbot, o responsavel de tecnologia da clinica que responde 
- **Finalidade** — o que o agente decide ou executa, para quem, e os usos
  - o agente decide onde sera colocado o usuario no sistema de marcar o horario, executa para o usuario que quer marcar horario
  **fora de escopo**: o que ele não deve ser usado para fazer.
  - ele nao deve ser usado para conversas aleatorias fora do tema alem de perguntar coisas desnecessarias   
- **Autoridade** — o que o agente está autorizado a fazer e os limites dessa
  autorização: escopo, ações proibidas, credencial, limite de gasto, limiar de
  aprovação humana, quem pode suspendê-lo. É o campo detalhado no requisito 2.
  - ele esta autorizado a fazer perguntas sobre as duvidas do usuario perguntar sobre dados como nome data de preferencia e disponibilidade alem da suspeita e somente guardar isso nao perguntar nada sobre isso
- **Ferramentas e integrações** — cada ferramenta e servidor MCP que o agente
  usa, com a permissão que cada um concede (leitura, escrita, envio a
  terceiros).
  - integração com o banco de dado tera leitura e escrita mas nao tera permissão para apagar somente sobre observação 
- **Modelo e provedor** — o modelo, com a versão datada e não o *alias*
  ("-latest"); o provedor; a região onde os dados são processados; e os termos
  de retenção e de uso dos dados para treino.
  - mistral small 
- **Dados** — as fontes de dados, o dado pessoal tratado, a base legal, onde
  cada dado fica e por quanto tempo. É o campo detalhado no requisito 3.
  - dados utilizados serao preferencias de horario nome suspeita e qual tratamento, e sera armazenado em um local especifico de historico de conversas
- **Avaliação** — a suíte que mede o agente, a versão dela, os resultados
  agregados e por fatia, e a concordância do juiz com a avaliação humana.
  - avaliação sera feita a partir de um outro agente agindo como juiz a partir das decisões e os resultados dele
- **Limites conhecidos** — os modos de falha já observados e os casos em que o
  agente não deve ser usado, mesmo dentro da finalidade.
  - agente n deve interagir sobre qualquer assunto que nao seja a psicologia da avaliação 
- **Riscos aceitos** — cada risco que o grupo decidiu aceitar, com a razão e o
  que o limita; aceitar um risco é uma decisão registrada, e não um
  esquecimento.
  - risco de esquece dados sensiveis para n ter q armazenar tais
- **Supervisão humana** — o que pausa para aprovação, quem aprova, em quanto
  tempo, e como se interrompe o agente.
  - a clinica que a prova e tbm pode interromper o agente
- **Registro e retenção** — o que o sistema registra a cada decisão (entrada,
  contexto recuperado, versões, ferramentas, saída), por quanto tempo guarda e
  quem tem acesso ao registro.
  - ele registra o contexto a decisão e o motivo dela alem de uma marcação de quem é para lembrança futura
- **Histórico de mudanças** — cada versão do sistema, o que mudou e quem
  aprovou a mudança.
