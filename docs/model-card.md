- **Identificação** — nome do sistema, versão, data e os responsáveis
  nomeados: quem responde pelo agente quando algo dá errado.
- **Finalidade** — o que o agente decide ou executa, para quem, e os usos
  **fora de escopo**: o que ele não deve ser usado para fazer.
- **Autoridade** — o que o agente está autorizado a fazer e os limites dessa
  autorização: escopo, ações proibidas, credencial, limite de gasto, limiar de
  aprovação humana, quem pode suspendê-lo. É o campo detalhado no requisito 2.
- **Ferramentas e integrações** — cada ferramenta e servidor MCP que o agente
  usa, com a permissão que cada um concede (leitura, escrita, envio a
  terceiros).
- **Modelo e provedor** — o modelo, com a versão datada e não o *alias*
  ("-latest"); o provedor; a região onde os dados são processados; e os termos
  de retenção e de uso dos dados para treino.
- **Dados** — as fontes de dados, o dado pessoal tratado, a base legal, onde
  cada dado fica e por quanto tempo. É o campo detalhado no requisito 3.
- **Avaliação** — a suíte que mede o agente, a versão dela, os resultados
  agregados e por fatia, e a concordância do juiz com a avaliação humana.
- **Limites conhecidos** — os modos de falha já observados e os casos em que o
  agente não deve ser usado, mesmo dentro da finalidade.
- **Riscos aceitos** — cada risco que o grupo decidiu aceitar, com a razão e o
  que o limita; aceitar um risco é uma decisão registrada, e não um
  esquecimento.
- **Supervisão humana** — o que pausa para aprovação, quem aprova, em quanto
  tempo, e como se interrompe o agente.
- **Registro e retenção** — o que o sistema registra a cada decisão (entrada,
  contexto recuperado, versões, ferramentas, saída), por quanto tempo guarda e
  quem tem acesso ao registro.
- **Histórico de mudanças** — cada versão do sistema, o que mudou e quem
  aprovou a mudança.
