# Roteiro — Second Brain MVP: Como Transformei 18.000 Notas num Sistema que Pensa Junto Comigo

**Idioma:** Português (Brasil)  
**Duração estimada:** ~13 minutos  
**Tom:** Didático e empolgante  
**Data:** 2026-05-08  

---

## Ato 1 — Gancho (~1 min)

> 🎯 **Objetivo:** Criar identificação imediata — o espectador pensa "esse sou eu" antes de qualquer detalhe técnico.

[CENA: tela preta com texto aparecendo lentamente — "Você já leu algo incrível, anotou... e nunca mais encontrou?"]

Você já passou por isso: leu um artigo que mudou sua perspectiva, destacou um trecho no Kindle que parecia revelar algo importante, anotou uma ideia no celular às 23h — e simplesmente... sumiu.

[PAUSA]

Não porque você esqueceu. Mas porque suas notas vivem em silos que não conversam entre si.

[CENA: mostrar pastas do Notion, Google Keep e Kindle highlights lado a lado — desconexas]

Tenho notas no Notion. Tenho highlights no Kindle. Tenho registros no Google Keep. Ao longo de anos, acumulei mais de 18.000 notas espalhadas por essas três fontes — em português, inglês, francês.

O problema não era quantidade. Era que todas essas notas nunca [ÊNFASE] sintetizavam. Cada busca começava do zero. Cada conexão tinha que ser feita na minha cabeça, manualmente.

[PAUSA]

O que eu precisava não era de uma busca melhor. Era de um segundo cérebro que pensasse junto comigo.

[CENA: fade para o título do vídeo]

## Ato 2 — A Descoberta (~2 min)

> 🎯 **Objetivo:** Apresentar a ideia do Karpathy como uma revelação genuína — o espectador deve sentir a mesma empolgação que o criador sentiu.

[CENA: abrir o gist do Karpathy no browser — https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f]

Foi aí que encontrei uma ideia publicada por Andrej Karpathy — ex-diretor de IA da Tesla, ex-pesquisador sênior da OpenAI, um dos nomes mais respeitados no campo de inteligência artificial.

A ideia era simples e poderosa: usar um LLM para [ÊNFASE] manter um wiki pessoal.

[PAUSA]

Deixa eu explicar o que isso significa. Hoje, quando a maioria das pessoas fala de "IA com suas notas", está falando de RAG — Retrieval Augmented Generation. Você faz uma pergunta, o sistema busca os trechos mais relevantes das suas notas e usa um LLM para formular uma resposta. É uma busca semântica glorificada.

[CENA: diagrama simples — "Pergunta → Busca → Resposta" com seta de mão única]

O problema do RAG puro é que ele é [ÊNFASE] passivo. Cada pergunta começa do zero. O sistema não aprende, não acumula, não sintetiza. É uma biblioteca que não cresce.

[CENA: diagrama do LLM Wiki — notas brutas entram, páginas de conceito crescem com o tempo, se cruzam entre si]

O que o Karpathy propôs é diferente. Em vez de responder perguntas a partir das notas brutas, você usa o LLM para [ÊNFASE] compilar as notas num wiki de conceitos. Cada conceito vira uma página. As páginas se cruzam com wikilinks. E esse wiki é um artefato persistente — ele cresce e se aprofunda com o tempo.

A frase dele que ficou na minha cabeça foi essa: "O wiki é um artefato persistente e composto. Os cruzamentos já estão lá."

[PAUSA]

Não é busca. É [ÊNFASE] acumulação de compreensão.

Quando li isso, pensei: é exatamente o que eu precisava.
## Ato 3 — O Limite da Ideia (~1,5 min)

> 🎯 **Objetivo:** Virada dramática — a esperança criada no Ato 2 bate num muro específico e bem explicado. O espectador entende [ÊNFASE] por que o problema existe, não apenas que ele existe.

[CENA: terminal rodando o pipeline do Karpathy com poucas notas — funcionando bem]

Eu testei. Com 80, 90, 100 artigos — funcionou lindamente. As páginas de conceito eram coerentes, os wikilinks faziam sentido, o wiki estava crescendo do jeito certo.

[PAUSA]

Aí eu adicionei mais notas.

[CENA: mostrar o contexto do LLM sendo preenchido progressivamente — como uma barra que enche até o limite]

Aqui está o problema fundamental. LLMs têm uma janela de contexto — uma quantidade máxima de texto que conseguem processar de uma vez. É como tentar ler um livro de 600 páginas mas só conseguindo ver 20 por vez. Você perde o fio da meada.

O Karpathy parte do pressuposto de uma coleção [ÊNFASE] curada e relativamente pequena. Com 18.000 notas, é impossível passar o corpus inteiro pelo modelo de uma vez. E se você passa só uma parte, o LLM não tem contexto suficiente para saber o que já existe no wiki.

[PAUSA]

O resultado? Alucinações de wikilinks.

[CENA: exemplo de wikilink falso sendo criado — `[[antifragilidade]]` linkando para uma página que não existe, ou pior, existindo mas sendo incorreta]

O LLM começa a criar conexões entre conceitos que não têm relação real. E num Zettelkasten — um sistema onde o valor vem justamente dos elos entre ideias — um link errado não é só um erro de fato.

É como um GPS que inventa uma rua que não existe. Você segue com confiança... e se perde.

[PAUSA]

Um wikilink alucinado é [ÊNFASE] corrupção estrutural. Ele cria uma trilha falsa que contamina cada consulta futura que passa por ela.

O Karpathy funciona para uma coleção curada. Para um Zettelkasten que cresceu durante anos, ele quebra.

[CENA: pergunta visual na tela — "Como resolver isso?"]
## Ato 4 — O Insight Híbrido (~2 min)
## Ato 5 — O Pipeline na Prática (~3 min)
## Ato 6 — O Estado Atual (~1,5 min)
## Ato 7 — Como Melhorar (~1,5 min)
## Ato 8 — Conclusão (~1 min)

---

## Notas de Produção
