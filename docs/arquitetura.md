Ferramentas:
- **Simulação dos exames:** A partir do estado atual da clínica e na suspeita do paciente, é estimada a duração até a devolução do diagnóstico.
- **API da Clínica:** Torna possível a avalição do histórico do cliente a partir de seus dados cadastrados.

Laço:
- **Laço dúvida:** Responde o prompt de um usuário, e, caso o mesmo tenha mais dúvidas, permite que o usuário realize outro prompt.
- **Laço dados:** Inicialmente, solicita informações do usuário. Se o usuário possuí dados, consulta as informações solicitadas, e, caso mais informações sejam necessárias, informações novamente. Caso mais informações não sejam necessárias, encerra a conversa. Caso não sejam encontrados dados dos usuários, também termina a conversa.

Estado:

Orçamento:
- Não é possível terminar a execução caso dados do usuário não sejam encontrados.

Términmo: 
- Uma execução é finalizada quando os dados do usuário são encontradas e todas a
