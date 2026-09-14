# Design Doc — Roteiro de Vídeo: Second Brain MVP

**Data:** 2026-05-08  
**Formato de saída:** Markdown (roteiro de vídeo para walkthrough)  
**Idioma:** Português (Brasil)  
**Duração alvo:** ~13 minutos  
**Tom:** Didático e empolgante — como um professor que quer que qualquer pessoa entenda e se inspire  
**Público:** Misto — começa acessível, aprofunda tecnicamente no meio, termina com visão de futuro  

---

## Decisões de Design

### Abordagem: Jornada do Criador
A estrutura narrativa foi escolhida sobre as alternativas (linear técnica e demo-first) porque:
- Cria identificação emocional antes de qualquer detalhe técnico
- O Karpathy funciona como **ponto de virada dramático**, não como referência de rodapé
- Permite que qualquer pessoa (técnica ou não) acompanhe a lógica da solução

### O Papel do Karpathy
A ideia do LLM Wiki do Karpathy é apresentada como **inspiração genuína**, depois como **limite** — não como crítica. A transição "isso era perfeito... até o momento em que quebrou" é o coração emocional do roteiro.

### Tensão central do vídeo
> "Como você transforma 18.000 notas espalhadas em conhecimento que você realmente usa?"

Essa tensão abre o vídeo e só é resolvida no ato 6.

---

## Estrutura dos 8 Atos

### Ato 1 — Gancho (~1 min)
**Objetivo:** Fazer o espectador pensar "esse sou eu"

Pontos-chave:
- Abrir com a experiência universal: ler algo incrível, anotar, nunca mais encontrar
- Escala do problema: Kindle, Notion, Google Keep — notas em silos que não conversam
- O problema não é quantidade. É que as notas nunca **sintetizam**
- Frase de fechamento do ato: *"O que eu precisava não era de uma busca melhor. Era de um segundo cérebro que pensasse junto comigo."*

---

### Ato 2 — A Descoberta (~2 min)
**Objetivo:** Apresentar o Karpathy e criar esperança

Pontos-chave:
- Andrej Karpathy (ex-OpenAI, ex-Tesla, criador do Backpropagation popularizado) publicou uma ideia simples e poderosa: usar um LLM para **manter um wiki pessoal**
- A ideia: suas notas brutas entram → o LLM sintetiza em páginas de conceito → essas páginas acumulam, se cruzam, crescem com o tempo
- O insight central do Karpathy: *"O wiki é um artefato persistente e composto. Os cruzamentos já estão lá."*
- Mostrar a diferença entre RAG puro (busca e responde do zero toda vez) vs LLM Wiki (conhecimento compilado que cresce)
- Reação: *"Isso era exatamente o que eu precisava."*

---

### Ato 3 — O Limite da Ideia (~1,5 min)
**Objetivo:** A virada dramática — onde o Karpathy quebra para este caso de uso

Pontos-chave:
- Testou a abordagem. Funcionou lindamente com ~80–100 artigos
- Com mais notas, o contexto do LLM começa a estourar — o modelo vê notas demais de uma vez
- Resultado: **alucinações de wikilinks** — o LLM cria conexões falsas com confiança
- Por que isso é grave num Zettelkasten: um link errado não é só um erro de fato. É uma **trilha falsa estrutural** que contamina consultas futuras
- A escala do problema: 18.000 notas × um modelo com janela de contexto de 8.000 tokens = impossível carregar tudo
- *"O Karpathy funciona para uma coleção curada. Para um Zettelkasten que cresce há anos, ele quebra."*

---

### Ato 4 — O Insight Híbrido (~2 min)
**Objetivo:** Apresentar a solução — RAG + LLM Wiki com controle humano

Pontos-chave:
- A solução não é escolher entre RAG e LLM Wiki — é **combinar os dois**
- Três princípios que resolvem o problema de escala:
  1. **Domain sharding:** dividir as notas em 26 domínios temáticos; o LLM só vê o índice de um domínio por vez (~3.000 tokens) — cabe na janela
  2. **O LLM propõe, o humano aprova:** nenhuma página chega ao wiki sem passar pelo portão de revisão
  3. **Fast-track para o óbvio:** propostas de alta confiança que atualizam páginas existentes são aprovadas automaticamente com log para revisão posterior
- Resultado: escala para qualquer volume, sem alucinação estrutural, sem custo de API — 100% local via Ollama

---

### Ato 5 — O Pipeline na Prática (~3 min)
**Objetivo:** Walkthrough técnico acessível — mostrar como as peças se encaixam

Sub-seções:
1. **Fontes de dados** — Notion (.md), Google Keep (.json), Kindle (clippings.txt), artigos, PDFs, Obsidian
2. **Ingestão** — parsers detectam idioma (PT, EN, FR, ES), classificam no domínio certo via palavras-chave + embeddings semânticos
3. **O agente Ollama** — lê só o `index.md` do domínio + a nota nova → propõe: "essa nota pertence à página X, com os links Y e Z"
4. **A CLI de revisão** — diff colorido, tecla `a` aprova, `r` rejeita, `e` edita; meta: menos de 10 segundos por proposta
5. **O commit atômico** — SQLite como coordenador de transação; escreve o arquivo Markdown, atualiza o ChromaDB, faz `git commit` na wiki
6. **A camada de query** — busca semântica (bi-encoder multilingual) + re-ranking (cross-encoder para buscas entre domínios) + síntese com Ollama → resposta com citações `[[wikilink]]`

Ponto de ênfase: mostrar uma página de wiki real com front matter YAML (slug, domínio, links, confidence, sources)

---

### Ato 6 — O Estado Atual (~1,5 min)
**Objetivo:** Mostrar o que já existe — tornar tangível o resultado

Números reais:
- **26 domínios** de conhecimento (analytics, filosofia, psicologia, ficção, neurociência, marketing, etc.)
- **315 páginas de wiki** compiladas
- **303 notas committed**, 450 classificadas aguardando revisão
- Rodando 100% local no RTX 3060 com **Qwen 3.5 9B** via Ollama
- Zero custo de API, zero dado saindo da máquina
- Wiki versionada em git — cada aprovação é um commit, toda reversão é um `git revert`
- Servidor MCP já implementado — Claude Code e outros agentes podem consultar o wiki diretamente

---

### Ato 7 — Como Melhorar (~1,5 min)
**Objetivo:** Abrir o horizonte — o que vem a seguir

Melhorias planejadas:
- **Writing assistant:** rascunhar posts (Dados & Devaneios) ancorados nas páginas do wiki
- **Auto-tagging:** sugerir tags para novas notas do Notion/Keep no momento da captura, baseado no que já está no wiki
- **Fine-tuning:** treinar um modelo pequeno com as próprias páginas compiladas do wiki
- **Calibração:** as primeiras 500 notas em modo manual para afinar os domínios e o threshold de confiança
- **Plugin Obsidian:** surfar propostas como modais dentro do Obsidian

---

### Ato 8 — Conclusão (~1 min)
**Objetivo:** Deixar uma ideia na cabeça do espectador

Pontos-chave:
- Voltar à tensão inicial: as 18.000 notas que não conversavam
- O Second Brain não é uma busca de palavras-chave. É um sistema que **acumula compreensão**
- A diferença filosófica: RAG puro é uma biblioteca. O LLM Wiki híbrido é um pensador que lembra
- Frase de fechamento: *"Cada nota aprovada não é só um arquivo salvo. É um tijolo numa estrutura de conhecimento que vai durar anos."*

---

## Notas de Produção

- **Demonstração ao vivo** recomendada no Ato 5: mostrar o terminal com a CLI de revisão e uma página de wiki aberta no Obsidian
- **Referência visual** no Ato 3: diagrama simples mostrando a janela de contexto sendo estourada
- **Referência ao Karpathy:** linkar o gist original nos créditos/descrição do vídeo
- **Dados reais** a citar nos números do Ato 6 para credibilidade

---

## Tom e Linguagem

- Usar "você" para criar proximidade
- Evitar jargão sem explicação: cada termo técnico introduzido vem com uma analogia acessível
- Analogias sugeridas:
  - Janela de contexto → *"é como tentar ler um livro de 600 páginas mas só conseguindo ver 20 por vez"*
  - Wikilink alucinado → *"um GPS que inventa uma rua que não existe — você segue e se perde"*
  - Domain sharding → *"em vez de um bibliotecário que conhece 18.000 livros de memória, você tem 26 especialistas — cada um expert no próprio domínio"*
  - Fast-track → *"como pré-aprovação de cartão de crédito para compras abaixo de R$ 50"*
