# Qual informação especializada o agente precisa, e por que ela não está no modelo:

Pensamos nos seguintes dados:
- Preço dos exames;
- Agendamento dos pacientes;
- Informação geral de cada profissional;
- Histórico de exames do paciente (faltas, quantidade de exames etc.);
- Comportamento do paciente (Pode ser obtido através dos resultados dos exames);

# Onde esses dados estão, e em que estado:

- **Onde ela vive/Como é obtido:** Sistema da clínica, entrevistas, tabelas e documentos;
- **Em que formato:** Planilha, registro de banco e PDF;
- **Dono:** A clínica e seus profissionais;
- **Acesso:** solicitação para a clinica ou dados fictícios;

# O que vai para o índice — e o que não vai:

- **O que entra:** 
  - Informação geral de cada profissional;
  - Histórico de exames do paciente;
  - Comportamento do paciente;
- **Quantidade de chunks:** Dezenas, já que são poucos documentos, e cada chunk é um parágrafo ou seção de cada documento.
- **O que fica de fora, e por quê:**
  - **Preço dos exames:** Não é relevante para a priorização do paciente;
  - **Agendamento dos pacientes:** É uma informação que muda constantemente, sendo melhor obtida por consulta estruturada.
- **Consulta estruturada:** agendamento dos pacientes

# A estratégia de chunking:

- **Unidade natural:** Seções e parágrafos de cada documento
- Se existe, corte por ela. Se não existe, por contagem de caracteres — e diga qual tamanho e por quê: ;
- **Tamanho:** 512 tokens, por ser um tamanho médio (Escolhido com base nesse artigo: <https://developer.nvidia.com/blog/finding-the-best-chunking-strategy-for-accurate-ai-responses/>)
- O chunk faz sentido sozinho? Este é o critério único. Um parágrafo que diga "o limite de que trata o item anterior" é inútil isolado, e a correção é herdar o cabeçalho;
- **Isolamento de chunks:** É provável que não haja dependência entre chunks, mas se houver, o chunk que depende de outro deve herdar o cabeçalho do chunk do qual depende.
- **Metadados:** 
  - Tipo de documento (PDF, planilha, registro de banco, entrevista);
  - Autor ou responsável pelo documento;
  - Seção ou parágrafo (para rastrear a origem do chunk);
  - Relevância para priorização do paciente (alta, média, baixa);



