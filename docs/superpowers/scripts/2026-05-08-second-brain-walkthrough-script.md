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

> 🎯 **Objetivo:** O espectador entende a solução e sente que ela é elegante — não um hack, mas uma resposta arquitetural para o problema certo.

[CENA: diagrama mostrando RAG e LLM Wiki como duas metades que se encaixam]

A solução não era escolher entre RAG e LLM Wiki. Era [ÊNFASE] combinar os dois — e resolver o problema de escala com três princípios.

[PAUSA]

**Primeiro princípio: domain sharding.**

[CENA: mostrar os 26 domínios como gavetas separadas — analytics, filosofia, psicologia, ficção...]

Em vez de um único bibliotecário que precisa conhecer 18.000 livros de memória, você tem 26 especialistas — cada um expert no próprio domínio. O LLM nunca vê o corpus inteiro. Ele vê apenas o índice de um domínio por vez — cerca de 3.000 tokens. Cabe na janela de contexto com folga.

[PAUSA]

**Segundo princípio: o LLM propõe, o humano aprova.**

[CENA: CLI de revisão mostrando um diff colorido de uma proposta]

Nenhuma página chega ao wiki sem passar por um portão de revisão humana. O LLM lê a nota nova, consulta o índice do domínio e propõe: "essa nota pertence à página X, com os links Y e Z, com essa confiança." Eu vejo o diff, aprovo ou rejeito. Isso elimina o risco de corrupção estrutural — porque o humano é o guardião dos links.

[PAUSA]

**Terceiro princípio: fast-track para o óbvio.**

[CENA: barra de confiança passando de 0 a 0.85 — verde]

Não quero revisar manualmente cada uma das 18.000 notas. Para propostas de alta confiança — acima de 85% — que apenas atualizam páginas já existentes sem criar links novos, o sistema aprova automaticamente e registra num log. É como pré-aprovação de cartão de crédito para compras abaixo de R$ 50 — você revisa o extrato depois, não cada transação.

[PAUSA]

[CENA: diagrama completo do pipeline com os três princípios destacados]

O resultado: um sistema que escala para qualquer volume, sem alucinação estrutural, rodando 100% local — sem custo de API, sem dado saindo da máquina.
## Ato 5 — O Pipeline na Prática (~3 min)

> 🎯 **Objetivo:** O espectador acompanha o caminho de uma nota do início ao fim — sem precisar entender código para entender o valor de cada etapa.

[CENA: abrir a pasta `data/raw/` mostrando as subpastas notion/, keep/, kindle/]

Vamos acompanhar o caminho de uma nota, do início ao fim.

**Etapa 1: As fontes**

O sistema lê notas de qualquer lugar: exportações do Notion em Markdown, Google Keep em JSON, highlights do Kindle no arquivo de clippings, artigos em PDF, notas do Obsidian. Você coloca os arquivos na pasta `data/raw/` e o sistema começa a trabalhar.

[PAUSA]

**Etapa 2: Parsing e classificação**

[CENA: mostrar o terminal com o parser identificando idioma e domínio de uma nota]

Cada nota é lida por um parser específico para o formato. O sistema detecta o idioma automaticamente — português, inglês, francês, espanhol. Depois, classifica a nota num dos 26 domínios usando uma combinação de palavras-chave configuráveis e similaridade semântica. Uma nota sobre "MMM e ROAS" vai para analytics. Uma sobre "Taleb e antifragilidade" vai para filosofia.

[PAUSA]

**Etapa 3: A proposta do Ollama**

[CENA: mostrar o index.md do domínio `philosophy` — lista de conceitos já existentes]

Aqui é onde a mágica acontece. O modelo — Qwen 3.5 9B rodando localmente via Ollama — recebe dois inputs: o índice do domínio (uma lista de todos os conceitos já compilados, em ~3.000 tokens) e a nota nova. Ele retorna uma proposta em JSON: "essa nota pertence à página antifragilidade, com confiança 0.87, adicionando o link para via-negativa".

[CENA: mostrar o JSON da proposta no terminal]

Nada é escrito ainda. É só uma proposta.

[PAUSA]

**Etapa 4: A revisão humana**

[CENA: CLI de revisão com diff colorido — verde para adições, vermelho para remoções]

A proposta aparece na minha tela como um diff colorido. Verde são adições. Eu vejo exatamente o que vai mudar na página do wiki. Aperto `a` para aprovar, `r` para rejeitar com motivo, `e` para editar antes de aprovar. Para propostas claras, levo menos de 10 segundos.

[PAUSA]

**Etapa 5: O commit atômico**

[CENA: mostrar o git log do wiki com commits sequenciais]

Aprovada a proposta, o sistema executa uma transação coordenada: escreve o arquivo Markdown da página do wiki, atualiza o índice vetorial (ChromaDB) com o novo conteúdo, registra os links cruzados e faz um `git commit` na wiki. Cada aprovação é um commit. Para reverter uma decisão ruim: `git revert`.

[PAUSA]

**Etapa 6: A consulta**

[CENA: terminal com uma query sendo feita — "O que é antifragilidade?" — e a resposta com citações [[wikilink]]]

Na hora de consultar, a busca semântica encontra as páginas mais relevantes usando embeddings multilingues — uma busca em português encontra páginas em inglês e vice-versa. O modelo sintetiza a resposta usando apenas as páginas do wiki como contexto, citando as fontes com `[[wikilinks]]`. Não inventa nada que não esteja lá.

[CENA: abrir uma página do wiki no Obsidian — mostrar o front matter YAML com slug, domínio, links, confidence]

E aqui está uma página real do wiki — com metadados estruturados, as fontes originais, os links para conceitos relacionados, e o texto sintetizado pelo LLM e aprovado por mim.
## Ato 6 — O Estado Atual (~1,5 min)

> 🎯 **Objetivo:** Tornar o resultado concreto com números reais — o espectador vê que isso não é um projeto hipotético, é um sistema funcionando.

[CENA: abrir o Obsidian com o vault do wiki — mostrar os 26 domínios na barra lateral]

Então, onde estamos hoje?

[PAUSA]

**26 domínios de conhecimento** organizados: analytics, filosofia, psicologia, ciência de dados, neurociência, economia comportamental, ficção, marketing, liderança, história... cada um com seu próprio índice e suas próprias páginas compiladas.

[CENA: navegar por alguns domínios no Obsidian — mostrar as páginas interligadas]

**315 páginas de wiki** já compiladas. Cada uma sintetizando notas de múltiplas fontes, em múltiplos idiomas, com wikilinks aprovados por mim.

**303 notas committed** — integradas ao wiki. Mais 450 classificadas e aguardando na fila de revisão.

[PAUSA]

[CENA: mostrar o `nvidia-smi` com o Qwen 3.5 9B usando a VRAM do RTX 3060]

Tudo isso rodando 100% localmente no meu RTX 3060, com o modelo Qwen 3.5 9B via Ollama. Zero custo de API. Zero dado saindo da minha máquina. Zero dependência de serviços externos.

[PAUSA]

[CENA: mostrar o git log do wiki — lista de commits com as páginas aprovadas]

A wiki inteira está versionada em git. Cada aprovação é um commit com o nome da página e o score de confiança. Se eu aprovar algo errado, é um `git revert`.

[CENA: abrir o `mcp_server.py` brevemente — mostrar que existe]

E tem mais: já tem um servidor MCP implementado. Isso significa que o Claude Code — a IA que uso no terminal — pode consultar diretamente a minha base de conhecimento enquanto trabalha comigo. O Second Brain virou um recurso para outros agentes de IA.
## Ato 7 — Como Melhorar (~1,5 min)

> 🎯 **Objetivo:** O espectador vê o potencial futuro e entende que o sistema é uma plataforma — não um fim em si mesmo.

[CENA: abrir o arquivo `second-brain-sdd.md` na seção "Future Work"]

O que temos hoje é uma fundação. As direções mais promissoras para a próxima fase:

[PAUSA]

**Writing assistant.** As páginas do wiki são o contexto perfeito para escrever. A próxima feature é usar o wiki para rascunhar posts — ancorando cada parágrafo em conceitos já compilados, com citações automáticas. Nada escrito do zero; tudo construído sobre conhecimento acumulado.

[PAUSA]

**Auto-tagging no momento da captura.** Hoje você classifica a nota depois de capturar. O próximo passo é sugerir tags e domínio já no momento em que você escreve no Notion ou no Obsidian — com base no que já está no wiki.

[PAUSA]

**Calibração com as primeiras 500 notas.** O sistema foi projetado para rodar as primeiras 500 notas em modo manual — sem fast-track — para medir a taxa de rejeição por domínio e afinar os thresholds. Essa etapa ainda está pela frente.

[PAUSA]

**Fine-tuning no próprio wiki.** No longo prazo: treinar um modelo pequeno com as páginas compiladas. Em vez de um modelo genérico que propõe integrações para qualquer assunto, um modelo que conhece [ÊNFASE] especificamente o meu Zettelkasten.

[CENA: fade suave — preparar para a conclusão]
## Ato 8 — Conclusão (~1 min)

> 🎯 **Objetivo:** Deixar uma ideia filosófica clara — não "esse sistema é legal" mas "esse sistema resolve um problema humano real de forma elegante".

[CENA: voltar à imagem inicial — as notas em silos desconexos]

Começamos com um problema simples: 18.000 notas que nunca sintetizavam.

[CENA: mostrar o grafo do wiki no Obsidian — nós conectados, domínios se cruzando]

O que o Second Brain resolve não é busca. É [ÊNFASE] acumulação de compreensão. Cada nota aprovada não é só um arquivo salvo. É um tijolo numa estrutura de conhecimento que vai durar anos.

[PAUSA]

A diferença filosófica é essa: RAG puro é uma biblioteca. Você entra, busca, sai. O LLM Wiki híbrido é um pensador que lembra — e que cresce com você.

[PAUSA]

O Karpathy tinha razão na intuição. A escala exigiu uma solução diferente. E essa solução — com domain sharding, portão humano e fast-track — é o que permite que o sistema cresça junto com o conhecimento, sem corromper a estrutura que dá valor a tudo isso.

[CENA: tela final com o título do projeto e os créditos]

O código está no repositório. O design document está documentado. Se você quiser construir algo similar, o link do gist do Karpathy está na descrição — é por onde eu comecei.

[PAUSA]

Obrigado por assistir.

---

## Notas de Produção

### Demonstrações ao vivo recomendadas
- **Ato 5, Etapa 3:** mostrar o terminal com o Ollama gerando uma proposta em JSON ao vivo
- **Ato 5, Etapa 4:** mostrar a CLI de revisão com diff colorido e apertar `a` ao vivo
- **Ato 5, Etapa 6:** fazer uma query real e mostrar a resposta com wikilinks
- **Ato 6:** abrir o Obsidian com o vault do wiki — navegar pelo grafo de conexões

### Referências a incluir na descrição do vídeo
- Gist do Karpathy: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
- Repositório do projeto: [link do repo]
- Spec de design: `docs/superpowers/specs/2026-05-08-second-brain-video-script-design.md`

### Recursos visuais sugeridos
- **Ato 3:** diagrama animado simples da janela de contexto sendo preenchida até o limite
- **Ato 4:** diagrama dos 3 princípios (domain sharding, portão humano, fast-track) com ícones
- **Ato 6:** screenshot do `git log` do wiki com commits reais

### Duração estimada por ato (para edição)
| Ato | Estimativa |
|---|---|
| Ato 1 — Gancho | ~1 min |
| Ato 2 — A Descoberta | ~2 min |
| Ato 3 — O Limite da Ideia | ~1,5 min |
| Ato 4 — O Insight Híbrido | ~2 min |
| Ato 5 — O Pipeline na Prática | ~3 min |
| Ato 6 — O Estado Atual | ~1,5 min |
| Ato 7 — Como Melhorar | ~1,5 min |
| Ato 8 — Conclusão | ~1 min |
| **Total** | **~13,5 min** |
