# Identificação

Organizador de fila via chatbot, o responsável de tecnologia da clinica que responde.

# Finalidade

O agente decide onde será colocado o usuário no sistema de marcar o horário, executa para o usuário que quer marcar horário.

# Fora de escopo

Ele não deve ser usado para conversas aleatórias ou fora do tema, além de perguntar coisas desnecessárias.

# Autoridade

Ele está autorizado a fazer perguntas sobre as dúvidas do usuário perguntar sobre dados como nome datas de preferencia e disponibilidade, além da suspeita e somente guardar para fins de avaliação do agente, não deve ser usado para outros fins. Além disso, o agente pode marcar as agendas, com a confirmação do usuário.

# Ferramentas e integrações

Integração com o sistema de agendamento da clínica, via API. O agente não terá permissão para apagar dados, apenas ler e escrever informações relacionadas ao agendamento. Além disso, o agente terá acesso ao agente priorizador. Essas ferramentas serão disponibilizadas através de um servidor MCP.

# Modelo e provedor

Referenciado em [modelos.md](./modelos.md)

# Dados

Preferências de horário, nome, suspeita e tratamento. Esses dados serão armazenados em um local específico de histórico de conversas.

# Avaliação

A avaliação será feita a partir de um juiz, que valida os casos de teste. Além dos testes unitários quando possível.

# Limites conhecidos

O agente não deve interagir sobre qualquer assunto que não seja dúvidas, agendamentos e informações relacionadas à ele.

# Riscos aceitos

Teremos o risco do armazenamento de dados sensíveis, mas com a supervisão humana e o registro de decisões, podemos mitigar os riscos. Além disso, o agente não deve armazenar dados sensíveis para evitar riscos de privacidade.

# Supervisão humana

A clínica deve possuir observabilidade do agente, com logs de decisões e histórico de conversas. Além disso, a clínica deve ter a capacidade de interromper o agente caso ele esteja se comportando de forma inadequada.

# Registro e retenção

O agente registra o contexto, a decisão e o motivo dela, além de uma marcação de quem é para lembrança futura. O registro deve ser mantido por um período definido pela clínica, com acesso restrito a pessoal autorizado.

# Histórico de mudanças

Será feita a partir de controles de versão, com registro de alterações e revisões. As mudanças devem ser documentadas e justificadas, com a data e o autor da alteração. Para isso, será utilizado o git, e tags de versão para representar uma versão nova do agente.
