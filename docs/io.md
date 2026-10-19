# Contrato de entrada e saída

Este documento reúne exemplos de I/O do sistema. Os exemplos foram produzidos como amostras de contrato e não dependem de execução real no ambiente. Os commits e datas são fictícios, e os logs correspondentes ficam em `logs/`.

## 1. Caminho feliz

### Entrada

"Quero agendar uma avaliação neuropsicológica. Tenho encaminhamento do meu médico. Quero um horário na próxima semana, de manhã."

### Saída

```json
{
  "resultado": {
    "status": "agendamento_sugerido",
    "mensagem": "Posso ajudar com o agendamento. Tenho as seguintes opções na próxima semana pela manhã: 18/11, 9h-10h; 19/11, 8h-9h; 20/11, 10h-11h. Preciso confirmar qual opção você prefere.",
    "acao": "aguarda_confirmacao"
  },
  "fonte": {
    "tipo": "disponibilidade_agenda",
    "registro": "agenda_proxima_semana_manha",
    "detalhes": "Consulta de disponibilidade atual da agenda para o paciente com encaminhamento válido."
  },
  "suficiencia": "suficiente"
}
```

### O que ler ali

A saída mostra que o sistema aceitou texto livre, identificou a intenção de agendamento, usou uma fonte verificável de disponibilidade e manteve a resposta em formato de objeto validado. A ausência de uma confirmação final indica que o fluxo ainda está em espera e não inventa um agendamento concluído.

### Metadados do exemplo

- commit: `0000000` (fictício)
- data: `2026-10-19T15:51:45-03:00`
- log: `logs/io-caminho-feliz.log`

## 2. Recusa

### Entrada

"Quero saber o prazo de diagnóstico garantido pela clínica."

### Saída

```json
{
  "resultado": {
    "status": "recusa",
    "mensagem": "Não encontrei uma garantia de prazo de diagnóstico documentada no corpus disponível. Não posso afirmar um prazo sem fonte oficial."
  },
  "fonte": {
    "tipo": "corpus",
    "registro": "docs/case.md",
    "detalhes": "Nenhum trecho documenta prazo garantido de diagnóstico."
  },
  "suficiencia": "insuficiente"
}
```

### O que ler ali

A resposta não tenta inventar um prazo. O sistema recusa com base em ausência de fonte e informa a lacuna claramente. Isso demonstra a exigência de `suficiencia = "insuficiente"` como parte do contrato.

### Metadados do exemplo

- commit: `0000001` (fictício)
- data: `2026-10-19T15:52:12-03:00`
- log: `logs/io-recusa.log`

## 3. Entrada incompleta

### Entrada

"Quero marcar um exame, mas não sei qual horário."

### Saída

```json
{
  "resultado": {
    "status": "solicita_dados",
    "mensagem": "Para continuar, preciso saber qual tipo de exame e se você já tem encaminhamento médico registrado. Também preciso saber a faixa de horários que você prefere."
  },
  "fonte": {
    "tipo": "pedido_de_clarificacao",
    "registro": "necessidade_de_dados",
    "detalhes": "A entrada menciona agendamento, mas ainda falta a informação essencial para oferecer horários válidos."
  },
  "suficiencia": "insuficiente"
}
```

### O que ler ali

O sistema não assume que tudo foi informado. Ele pede o que falta e não produz uma resposta que pareça completa sobre um caso ainda indefinido.

### Metadados do exemplo

- commit: `0000002` (fictício)
- data: `2026-10-19T15:53:04-03:00`
- log: `logs/io-incompleta.log`

## 4. Entrada ambígua

### Entrada

"Quero agendar para terça."

### Saída

```json
{
  "resultado": {
    "status": "solicita_desambiguacao",
    "mensagem": "Você se refere a qual terça? Preciso saber a data exata ou a semana. Também quero confirmar se a preferência é pela manhã ou tarde para sugerir horários corretos."
  },
  "fonte": {
    "tipo": "pedido_de_clarificacao",
    "registro": "ambiguidade_temporal",
    "detalhes": "A expressão 'terça' sem data ou turno é ambígua e não pode ser convertida em horário sem escolha."
  },
  "suficiencia": "insuficiente"
}
```

### O que ler ali

O sistema reconhece a ambiguidade e não responde como se a data já estivesse determinada. A saída deixa claro que a escolha precisa ser confirmada antes de agir.

### Metadados do exemplo

- commit: `0000003` (fictício)
- data: `2026-10-19T15:54:11-03:00`
- log: `logs/io-ambigua.log`

## 5. Entrada fora do escopo

### Entrada

"Me diga quem é o melhor técnico de computador para consertar meu notebook."

### Saída

```json
{
  "resultado": {
    "status": "fora_do_escopo",
    "mensagem": "Esse sistema atua apenas em agendamentos e orientações relacionadas a avaliações neuropsicológicas e processos da clínica. Não posso ajudar com suporte técnico de computadores."
  },
  "fonte": {
    "tipo": "escopo",
    "registro": "definicao_do_sistema",
    "detalhes": "O sistema limita seu escopo à clínica, não a suporte geral de tecnologia."
  },
  "suficiencia": "insuficiente"
}
```

### O que ler ali

A recusa é explícita e informa o que o sistema faz. Isso atende ao requisito de não responder como se a pergunta estivesse dentro do escopo, mesmo quando a conversa parece natural.

### Metadados do exemplo

- commit: `0000004` (fictício)
- data: `2026-10-19T15:55:20-03:00`
- log: `logs/io-fora-do-escopo.log`
