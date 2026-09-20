# Qual informação especializada o agente precisa, e por que ela não está no modelo:
Pensamos nos seguintes dados:
   - Preço dos exames
   - Agendamento dos pacientes
   - Informação geral de cada profissional
   - Histórico de exames do paciente (faltas, quantidade de exames etc.)
   - Comportamento do paciente
# Onde esses dados estão, e em que estado:
   - Onde ela vive: sistema da clínica, entrevistas, tabelas e documentos 
   - Em que formato: planilha, registro de banco e PDF
   - Dono: clinica e seus profissionais 
   - Acesso: solicitação para a clinica ou dados fictícios
# O que vai para o índice — e o que não vai:
   - O que entra: planilhas contendo o agendamento,  
   - Quantos chunks isso deve dar, na ordem de grandeza. Dezenas? Milhares? Milhões?
   - O que fica de fora, e por quê: preço dos exames, já que são valores fixos de consulta rápida   
   - O que se resolve por consulta estruturada em vez de por busca semântica: agendamento dos pacientes
# A estratégia de chunking:
  - Unidade natural: linha de planilha, seções e parágrafos de cada documento
  - Se existe, corte por ela. Se não existe, por contagem de caracteres — e diga qual tamanho e por quê;
  - O chunk faz sentido sozinho? Este é o critério único. Um parágrafo que diga "o limite de que trata o item anterior" é inútil isolado, e a correção é herdar o cabeçalho;
  - Que metadado cada chunk carrega, além do texto — e aqui reencontre a pergunta (3): é o metadado que permite o filtro.



