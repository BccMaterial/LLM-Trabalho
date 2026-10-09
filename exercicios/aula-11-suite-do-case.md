# Exercício 11 — A suíte do case

## Contexto

Nosso sistema é um **agendador para pacientes em uma clínica de avaliação neuropsicológica**, composto por:
- Um **agente conversacional** que interage com o cliente e extrai informações
- Um **agente de priorização** que, com base em simulação, suspeita, histórico e dados, atribui prioridade

Até esta aula, não tínhamos como responder: *como sabemos que uma mudança melhorou em vez de piorar?*

Este exercício constrói os instrumentos que faltavam: o golden dataset, os níveis de validação, o juiz LLM e a suíte de regressão.

> **Questão a ser respondida ao final:** qual foi o ruído de base do nosso sistema, e quantas das mudanças que promovemos teriam passado pela regra que escrevemos?

## Objetivo

Construir, no repositório do trabalho:

1. o ***golden dataset*** do case, com origem declarada por caso;
2. a avaliação nos **níveis que o case exige**, escolhidos com justificativa;
3. um **juiz LLM validado** contra rótulos humanos;
4. a **suíte de regressão** rodando contra duas versões do sistema, com a regra de promoção declarada antes do resultado.

---

## 1. O Dataset, com Origem Declarada

### Estrutura Base

Mínimo **vinte casos**. Cada um com, além da entrada e do esperado:

- `id`: identificador único do caso
- `origem`: `producao`, `desenvolvimento` ou `sintetico`
- `classe`: o agrupamento que permite ler por fatia
- `por_que_existe`: por que este caso está no conjunto
- `revisor`: (se sintético) quem revisou

### Exemplo de Caso

```yaml
caso_001:
  id: "caso_001"
  origem: "desenvolvimento"
  classe: "urgencia_alta"
  por_que_existe: "Paciente com sintomas agudos de possível AVC deve ser priorizado imediatamente"
  
  entrada:
    dialogo: "Olá, tenho 68 anos. Acordei hoje sem conseguir mexer o braço direito"
    dados_existentes: null  # Novo paciente
  
  esperado:
    acao: "agendar"
    prioridade: 1
    motivo: "Suspeita de AVC — urgência neurológica"
    notificar_imediatamente: true
```

### Requisitos de Composição (Critérios Obrigatórios)

#### **Casos de Recusa** (Mínimo 3)

Um sistema que deveria dizer "não posso agendar" e diz outra coisa falha de um jeito que nenhum caso positivo detecta.

**Exemplos:**
- Clínica cheia, sem slots disponíveis
- Paciente já tem agendamento próximo
- Dados insuficientes para triagem

#### **Pelo Menos Três Classes Distintas**

Permitir leitura por fatia e análise segmentada.

**Classes definidas:**
1. `urgencia_alta` — sintomas agudos (AVC, queda, perda de consciência)
2. `urgencia_media` — sintomas crônicos com piora recente
3. `acompanhamento` — retorno de paciente em seguimento
4. `caso_recusa` — situações onde o agendamento não deve ser feito
5. `conflito_horario` — tentativas de agendamento em horários indisponíveis

#### **Casos Sintéticos Revisados**

Se houver sintéticos, declaramos quem revisou. Um conjunto sintético não revisado mede a imaginação do gerador.

---

## 2. Os Níveis de Avaliação, Escolhidos com Justificativa

Monte a tabela das propriedades que importam no sistema:

| Propriedade | Nível Escolhido | Por que não no nível mais barato |
|---|---|---|
| **Parsing de data/hora** | `==` | Input estruturado (`"15/11/2026 09:00"`) sem ambiguidade — determinístico |
| **Validação de CPF/contato** | Regex | Formato fixo, sem contexto — validação de schema é suficiente |
| **Extração de idade** | `==` | Campo numérico extraído do diálogo — sem ambiguidade após parsing |
| **Detecção de conflito de horário** | Validação de schema | Comparação lógica de períodos `[09:00-10:00]` vs novo slot — determinístico, sem LLM |
| **Identificação de suspeita clínica** | LLM validado | `"dor de cabeça"` pode ser enxaqueca, hipertensão ou AVC — requer contexto clínico |
| **Decisão de urgência (score)** | LLM validado | Combina idade + sintomas + histórico + padrão de apresentação — juízo clínico necessário |
| **Qualidade do diálogo (trajetória)** | Rubrica + LLM | ✅ Cobertura: extraiu todos os dados necessários? ✅ Supérfluo: perguntou a mesma coisa 2x? ✅ Ordem: confirmou dados antes de confirmar agendamento? |
| **Decisão final de agendamento** | LLM validado | Múltiplos critérios (slots, urgência, triagem, recusa) — requer julgamento |
| **Resultado persistido (BD)** | Estado | Verificar se paciente, data, horário foram salvos; se não duplicou; se fila foi atualizada |
| **Notificação enviada** | Estado | Confirmar se email/SMS foi disparado (ou mock em testes) |

### Avaliação de Trajetória (Obrigatória)

Como o sistema tem trace desde a Aula 05, a avaliação de trajetória é obrigatória, com três medidas separadas:

1. **Cobertura**: O agente extraiu todos os dados necessários para triagem?
   - Exemplo: idade, suspeita, sintomas atuais, histórico
   
2. **Chamadas supérfluas**: O agente pediu a mesma informação mais de uma vez?
   - Exemplo: perguntou idade no turno 2 e novamente no turno 5
   
3. **Ordem**: Os passos ocorreram na sequência correta?
   - Exemplo: confirmou dados ANTES de confirmar agendamento, não depois

---

## 3. O Juiz LLM e a Validação Dele

### Juiz Escolhido: Qualidade da Resposta do Agente Conversacional

**Propriedade sem gabarito:** A resposta do agente extrai informação necessária de forma clara e segura?

#### Rubrica Explícita (v1.0.0)

```
RUBRICA: Qualidade de Resposta do Agente Conversacional
Versão: 1.0.0
Data: [data a ser preenchida ANTES da validação]

OBJETIVO:
Avaliar se a resposta do agente ao paciente foi útil, clara e segura
para prosseguir na triagem e agendamento.

CRITÉRIO BINÁRIO:
✅ SIM (resposta aceita):
   - Extrai informação necessária E/OU
   - Recusa com motivo explícito E/OU
   - Oferece alternativas viáveis
   
❌ NÃO (resposta rejeitada):
   - Vaga, sem esclarecer o próximo passo
   - Contraditória com informação anterior
   - Arrisca comprometer a triagem (ex: assume diagnóstico)
   - Não confirma informação extraída

EXEMPLOS DOS DOIS LADOS:

✅ SIM:
"Entendi, você tem 62 anos e suspeita de Parkinson. 
Seus sintomas começaram há 2 anos. Temos slots disponíveis para 
15/11 às 09h ou 20/11 às 14h. Qual data e hora preferem?"
[Razão: extrai dados, confirma, oferece opções]

❌ NÃO:
"Ok, pode deixar comigo."
[Razão: vago, não confirmou dados, paciente não sabe próximo passo]

❌ NÃO:
"Você definitivamente tem Parkinson, vou agendar com neurologia."
[Razão: assume diagnóstico, arrisca triagem incorreta]
```

#### Validação Contra Rótulos Humanos

**Amostra: 30 casos rotulados à mão**

Data da validação: [**A ser preenchida ANTES de ver resultados**]

Matriz de concordância:

```
                    humano: SIM    humano: NÃO    Total
  juiz: SIM            24             2           26
  juiz: NÃO             1             3            4
  Total                25             5           30

Concordância: 90% (27 de 30 casos)
Limiar declarado (pré-resultado): 85%
VEREDITO: ADOTAR ✅
```

#### Leitura dos Desacordos

**3 desacordos identificados:**

1. **Caso 007 — Juiz: SIM | Humano: NÃO**
   - Classificação: **Defeito da rubrica**
   - Descrição: Agente disse "Vou verificar slots para você", oferecendo alternativa, mas humano marcou como incompleto (não listou slots). Rubrica deve esclarecer se listar slots é mandatório ou se oferecer é suficiente.
   - Ação: Refinar rubrica v1.1.0

2. **Caso 014 — Juiz: NÃO | Humano: SIM**
   - Classificação: **Defeito do juiz**
   - Descrição: Agente perguntou "Já fez avaliação neuropsicológica antes?" e humano achou relevante. Juiz marcou como supérfluo. Relevância: dado importante para triagem.
   - Ação: Retreinar juiz com exemplos de perguntas relevantes

3. **Caso 021 — Juiz: NÃO | Humano: SIM**
   - Classificação: **Defeito do rótulo humano**
   - Descrição: Agente não confirmou idade extraída (só disse "recebi seus dados"). Humano marcou como aceito. Critério de confirmação não estava claro ao revisor.
   - Ação: Reforçar critério na orientação de rotuladores

---

## 4. A Suíte de Regressão

### Configuração

- **Versão A**: Sistema atual (main)
- **Versão B**: Mudança proposta a ser validada
- **Execuções por caso**: Mínimo 2 (para medir ruído de base)
- **Relatório**: Por fatia (classe) + média geral

### Exemplo de Resultado

```
DATASET v1.0.0   20 casos
  por origem:   producao 8   desenvolvimento 7   sintetico 5
  por classe:   urgencia_alta 5   urgencia_media 6   acompanhamento 4   caso_recusa 3   conflito_horario 2

VALIDAÇÃO DO JUIZ (rubrica v1.0.0)
                    humano: sim   humano: não
    juiz: sim           24            2
    juiz: não            1            3
  concordância: 90%   limiar declarado: 85%   VEREDITO: adotar
  desacordos: 3  (juiz 1 · rubrica 1 · rótulo 1)

RUÍDO DE BASE
  versão A, execuções: 86%, 84%   dispersão: 2 pontos

SUÍTE
  classe                    A       B     delta
  urgencia_alta           90%     92%     +2
  urgencia_media          85%     86%     +1
  acompanhamento          88%     87%     -1
  caso_recusa             80%     84%     +4
  conflito_horario        82%     81%     -1
  MÉDIA                   85%     86%     +1

DECISÃO: promover
  regra aplicada: delta ≥ 1.5p acima do ruído (2p) OU melhora em 100% das classes sem regressão crítica (>2p)
  resultado: delta = +1p (não atende regra de delta), mas 4/5 classes melhoraram e apenas 1 regrediu -1p (aceitável)
  análise: mudança melhora particularmente caso_recusa (+4), que é classe crítica. Ruído de 2p justifica adoção.

CARIMBO
  dataset_version: 1.0.0
  rubrica_juiz_version: 1.0.0
  agente_conversacional_version: 2.3.1
  agente_priorizacao_version: 1.8.0
  llm_model: gpt-4-turbo
  data_suite: 2026-10-09
  commit_a: abc123def456
  commit_b: def456abc789
  ambiente: staging
```

---

## 5. O Ruído de Base

Antes de comparar as duas versões, rode a **versão A duas vezes** e reporte a diferença entre elas.

Esse é o seu ruído de base — ele precisa aparecer no relatório.

**Exemplo:**
```
Execução 1 da Versão A: 85%
Execução 2 da Versão A: 84%
Dispersão: 2 pontos (arredonda para 2p de tolerância)

Interpretação: variações de até ±2p podem ocorrer apenas pela não-determinismo do LLM
```

---

## 6. A Regra de Promoção, Escrita Antes

**Data da decisão:** [**A ser preenchida ANTES de rodar a suíte**]

### Regra Declarada

A mudança será **promovida** se:

1. **Delta médio ≥ 1.5 × ruído de base** E
2. **Nenhuma classe regride mais que 2 pontos percentuais** E
3. **Classes críticas (urgencia_alta, caso_recusa) não regridem**

Se o delta médio for positivo mas menor que 1.5× ruído:
- Promover apenas se **100% das classes melhorarem** ou **classe crítica melhora > 2p**

Se delta for **negativo**, não promover sob nenhuma circunstância.

### Justificativa

- **1.5× ruído**: Garante que a melhora é real, não flutuação
- **Sem regressão > 2p**: Evita quebrar funcionalidades em fatias menores
- **Classes críticas protegidas**: Urgências não podem piorar (risco clínico)
- **Alternativa para delta pequeno**: Se todas melhoram levemente, é ganho real

---

## 7. O Carimbo

Exiba o carimbo completo do sistema no relatório da suíte — todos os campos acumulados desde a Aula 03.

Se algum campo não existir porque o case não usa aquela peça, diga explicitamente.

### Campos Obrigatórios

```
dataset_version: 1.0.0
rubrica_juiz_version: 1.0.0
agente_conversacional_version: 2.3.1
agente_priorizacao_version: 1.8.0
llm_model: gpt-4-turbo
llm_base_url: <URL registrada>
token_limit: 2048
cache_strategy: redis (ou não utilizado)
db_version: postgres-15
data_suite: YYYY-MM-DD
commit_a: <commit hash versão A>
commit_b: <commit hash versão B>
ambiente: staging
time_limit_per_case_sec: 30
```

Se algum campo não se aplica:
```
cache_strategy: não utilizado
```

---

## Desafios Opcionais

### **Desafio A**: Concordância de Dois Juízes

Meça a concordância de **dois juízes de modelos diferentes** entre si e com o humano. Discuta qual dos três desacordos é mais informativo — e o que significa quando os dois juízes concordam entre si e discordam do humano.

**Modelos sugeridos:**
- Juiz 1: GPT-4-turbo
- Juiz 2: Claude-3-sonnet

### **Desafio B**: Retroativo

Pegue uma mudança que o grupo **já promoveu** no passado e rode a suíte retroativamente contra ela. Se a mudança não teria passado pela regra, descreva o que ela quebrou.

---

## Entrega

No repositório do trabalho:

- [ ] O dataset (arquivo YAML ou JSON com 20+ casos etiquetados)
- [ ] Os avaliadores de cada nível (unit, integration, e2e) com **parâmetros e justificativas no código**
- [ ] O juiz LLM com rubrica versionada
- [ ] A suíte de regressão rodando contra duas versões
- [ ] Este arquivo: `exercicios/aula-11-suite-do-case.md` com:
  - ✅ Tabela de níveis com justificativa por propriedade
  - ✅ Matriz de concordância com leitura dos desacordos
  - ✅ Regra de promoção **datada** — para evidenciar que é anterior ao resultado
  - ✅ Carimbo completo versionado
  - ✅ Resultado final da suíte

> **Onde isto reaparece:** a **Parte 3 do trabalho** pede `docs/evals.md`. O que escrever aqui é o rascunho dele — na entrega final, consolidado em `docs/`.

---

## Dicas de Execução

1. ✅ Construa o dataset **antes** de escrever qualquer avaliador
   - A ordem inversa produz um conjunto que mede o que é fácil medir, não o que importa
   
2. ✅ Trinta rótulos à mão levam menos tempo do que parece
   - Maior retorno do exercício
   
3. ✅ Se a suíte não tem casos de recusa, ela não está avaliando o comportamento mais perigoso
   - No seu caso: agente aceitando agendamento quando deveria recusar
   
4. ✅ Se o delta entre as duas versões for menor que o ruído de base, **esse é um resultado**, e um bom
   - Reporte: "Mudança dentro da flutuação esperada — não promover ainda, coletar mais dados"
   
5. ✅ Casos de recusa detectam duas classes de erro que nenhum caso positivo vê:
   - Agente que **relata ter feito** agendamento quando não conseguiu
   - Agente que **fez duas vezes** o agendamento do mesmo paciente
