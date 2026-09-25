# failure-classifier

[![ci](https://github.com/maikonfcosta/failure-classifier/actions/workflows/ci.yml/badge.svg)](https://github.com/maikonfcosta/failure-classifier/actions/workflows/ci.yml)

**[English](#english)** · **[Português](#português)**

## English

When a Playwright pipeline goes red, this tells you whether the product is broken, the environment was down, or the test is out of date. Only a product bug should block a merge. I wrote a version of this at work; this one is rebuilt from scratch and measured against public data.

[Spec](SPEC.md) · Used by [playwright-reference-suite](https://github.com/maikonfcosta/playwright-reference-suite)

### Why the error message is not enough

Before writing any rule I broke [playwright-reference-suite](https://github.com/maikonfcosta/playwright-reference-suite) on purpose and read what Playwright reported:

| What I broke | What Playwright said |
|---|---|
| Stopped the API container | `Expected: 200 Received: 502`, which reads like a failed product assertion |
| Stopped the web container | `net::ERR_CONNECTION_REFUSED` |
| Renamed a button the test clicks | `locator.click: Timeout 3000ms exceeded ... waiting for getByRole(...)` |
| Made the API return empty data | `toBeVisible() failed ... element(s) not found` |

An outage looked like a product bug, and a product bug looked like a renamed selector. With the API down and no extra signal, 7 of 8 failures only said `Test timeout of 30000ms exceeded`. So the classifier reads two more things: a health probe taken right after the tests, and the 5xx or failed requests each page saw.

### How it decides

Rules run in order and the first match wins. There is no LLM involved.

| # | Signal | Verdict |
|---|---|---|
| 1 | `ERR_CONNECTION_*`, `ECONNREFUSED`, `ENOTFOUND` in the error | environment, high |
| 2 | Health probe failed | environment, high |
| 3 | The page saw a 5xx or a failed request | environment, high |
| 4 | A 5xx quoted in the message (`Received: 502`) | environment, high |
| 5 | An action (`click`, `fill`) timed out waiting for an element | test, **always low** |
| 6 | An `expect` failed with "element(s) not found" | product, low |
| 7 | An `expect` failed on a value, app healthy | product, high (low without a probe) |
| 8 | Anything else | unknown |

Only `product` and `unknown` block by default. Flaky tests (failed, then passed on retry) are listed but never block. A run where no test executed, or where Playwright reports a run-level error such as "No tests found", always fails.

Exit codes: `0` green, `1` something should block, `2` the tool was misused or got a file it cannot read.

### How well it does

Measured on 22 real failures, built by `scripts/build_dataset.py` from three controlled breakages of playwright-reference-suite (app healthy with outdated tests and simulated bugs, API stopped, web stopped). Labels come from the scenario and the test's name prefix, never from looking at the result.

| With the health probe | Cases |
|---|---|
| right, high confidence | 16 |
| right, low confidence | 4 |
| wrong, low confidence | 2 |
| **wrong, high confidence** | **0** |

Without the probe, the API outage becomes `unknown` and blocks. It is never called a confident product bug.

### Use it

In a workflow, after the Playwright step (which needs the `json` reporter and `continue-on-error: true`):

```yaml
- uses: maikonfcosta/failure-classifier@v1
  with:
    report: test-results/results.json
    health-url: http://localhost:4200/api/tags
```

For the network signal, copy [`playwright/network-errors.ts`](playwright/network-errors.ts) into your suite and wrap your `test` with it. It attaches a `network-errors` JSON to any test whose page saw a 5xx or a failed request.

Locally:

```bash
uvx --from git+https://github.com/maikonfcosta/failure-classifier failure-classifier results.json --health health.json
```

### How it is organized

```
src/failure_classifier/   report reader, rules, CLI (standard library only)
playwright/               the network-errors fixture to copy into a Playwright suite
dataset/                  22 labeled failures and the specs that produce them
scripts/build_dataset.py  rebuilds the dataset against playwright-reference-suite
tests/                    rules, CLI, edge cases, and accuracy against the dataset
action.yml                composite GitHub Action
```

### Decisions and trade-offs

#### Low confidence is fine, wrong with high confidence is not

A tool that says "I'm not sure" still points a person to the right place. A tool that is confidently wrong makes a team merge a bug because "it was the environment". Every rule that can be fooled caps its own confidence at low, and the accuracy test fails if any high-confidence answer is wrong.

#### Two cases it cannot tell apart

A test that waits for an element that was renamed, and a product bug that stopped rendering that element, produce the same report. Those go out as low confidence, and they are the 2 misses above. A test that expects an old text and a bug that changed the text also look identical; the tool calls both a product bug and blocks, which is the safe side.

#### I found a false green in my own tool

When Playwright finds no tests, the JSON report has zero counts and a run-level error. The first version printed "Nothing to classify" and exited 0: a pipeline that tested nothing, reported as green. That is the same failure I fixed at work, where a broken login setup ran zero tests and the pipeline stayed green. Empty and errored runs now always fail.

#### The dataset has tests of its own

If the dataset is wrong, the accuracy number means nothing. `tests/test_dataset.py` checks that there are at least 20 cases across the three categories, that every failure has an error message, and that only the outage cases carry network errors. Two cases I first wrote were wrong: one "product bug" was really a badly written test, and another never broke anything visible because the UI updates the favorite counter on its own.

#### Accepted for now

- Only Playwright's JSON report is supported.
- Trace files are not read. The network fixture covers the part of the trace that matters here.
- Diagnosing the cause of a product bug is out of scope. That is the next project, `ai-ci-triage`.
- An early commit of the dataset holds a Conduit test JWT from Playwright's call log. It is signed with the local-only secret in the suite's `compose.yaml` and works only against the Docker app, so I left history alone; the builder now redacts `Authorization` headers.

---

## Português

Quando um pipeline Playwright fica vermelho, esta ferramenta diz se o produto quebrou, se o ambiente caiu ou se o teste está desatualizado. Só bug de produto deveria barrar merge. Escrevi uma versão disso no trabalho; esta foi refeita do zero e medida com dados públicos.

[Spec](SPEC.md) · Usado por [playwright-reference-suite](https://github.com/maikonfcosta/playwright-reference-suite)

### Por que a mensagem de erro não basta

Antes de escrever qualquer regra, quebrei o [playwright-reference-suite](https://github.com/maikonfcosta/playwright-reference-suite) de propósito e li o que o Playwright reportou:

| O que eu quebrei | O que o Playwright disse |
|---|---|
| Parei o container da API | `Expected: 200 Received: 502`, que parece uma asserção de produto falhando |
| Parei o container web | `net::ERR_CONNECTION_REFUSED` |
| Renomeei um botão que o teste clica | `locator.click: Timeout 3000ms exceeded ... waiting for getByRole(...)` |
| Fiz a API devolver dado vazio | `toBeVisible() failed ... element(s) not found` |

Uma queda de ambiente parecia bug de produto, e um bug de produto parecia seletor renomeado. Com a API fora do ar e sem outro sinal, 7 de 8 falhas só diziam `Test timeout of 30000ms exceeded`. Por isso o classificador lê mais duas coisas: um health check feito logo depois dos testes, e as respostas 5xx ou requisições com falha que cada página viu.

### Como decide

As regras rodam em ordem e a primeira que casar vence. Não tem LLM envolvido.

| # | Sinal | Veredito |
|---|---|---|
| 1 | `ERR_CONNECTION_*`, `ECONNREFUSED`, `ENOTFOUND` no erro | ambiente, alta |
| 2 | Health check falhou | ambiente, alta |
| 3 | A página viu um 5xx ou uma requisição com falha | ambiente, alta |
| 4 | Um 5xx citado na mensagem (`Received: 502`) | ambiente, alta |
| 5 | Uma ação (`click`, `fill`) esgotou o tempo esperando um elemento | teste, **sempre baixa** |
| 6 | Um `expect` falhou com "element(s) not found" | produto, baixa |
| 7 | Um `expect` falhou num valor, com a app saudável | produto, alta (baixa sem health check) |
| 8 | Qualquer outra coisa | unknown |

Por padrão só `product` e `unknown` barram. Testes flaky (falharam e passaram no retry) aparecem na lista, mas nunca barram. Um run em que nenhum teste executou, ou em que o Playwright reporta um erro do run inteiro como "No tests found", sempre falha.

Exit codes: `0` verde, `1` algo deveria barrar, `2` a ferramenta foi mal usada ou recebeu um arquivo que não consegue ler.

### Quanto acerta

Medido em 22 falhas reais, montadas pelo `scripts/build_dataset.py` a partir de três quebras controladas do playwright-reference-suite (app saudável com testes desatualizados e bugs simulados, API parada, web parado). Os rótulos vêm do cenário e do prefixo do nome do teste, nunca de olhar o resultado.

| Com health check | Casos |
|---|---|
| certo, confiança alta | 16 |
| certo, confiança baixa | 4 |
| errado, confiança baixa | 2 |
| **errado, confiança alta** | **0** |

Sem o health check, a queda da API vira `unknown` e barra. Nunca é chamada de bug de produto com confiança.

### Como usar

Num workflow, depois do passo do Playwright (que precisa do reporter `json` e de `continue-on-error: true`):

```yaml
- uses: maikonfcosta/failure-classifier@v1
  with:
    report: test-results/results.json
    health-url: http://localhost:4200/api/tags
```

Para o sinal de rede, copie o [`playwright/network-errors.ts`](playwright/network-errors.ts) para a sua suíte e envolva o seu `test` com ele. Ele anexa um JSON `network-errors` a todo teste cuja página viu um 5xx ou uma requisição com falha.

Localmente:

```bash
uvx --from git+https://github.com/maikonfcosta/failure-classifier failure-classifier results.json --health health.json
```

### Como está organizado

```
src/failure_classifier/   leitor do relatório, regras, CLI (só biblioteca padrão)
playwright/               a fixture network-errors para copiar numa suíte Playwright
dataset/                  22 falhas rotuladas e os specs que as produzem
scripts/build_dataset.py  reconstrói a massa contra o playwright-reference-suite
tests/                    regras, CLI, casos de borda e acerto contra a massa
action.yml                GitHub Action composta
```

### Decisões e trade-offs

#### Confiança baixa tudo bem, errar com confiança alta não

Uma ferramenta que diz "não tenho certeza" ainda aponta a pessoa para o lugar certo. Uma que erra com convicção faz o time aprovar um bug porque "era ambiente". Toda regra que pode ser enganada limita a própria confiança em baixa, e o teste de acerto falha se qualquer resposta de confiança alta estiver errada.

#### Dois casos que ela não consegue separar

Um teste esperando um elemento que foi renomeado e um bug de produto que parou de renderizar esse elemento geram o mesmo relatório. Esses saem com confiança baixa, e são os 2 erros acima. Um teste que espera um texto antigo e um bug que mudou o texto também são idênticos; a ferramenta chama os dois de bug de produto e barra, que é o lado seguro.

#### Achei um falso verde na minha própria ferramenta

Quando o Playwright não acha nenhum teste, o relatório JSON vem com as contagens zeradas e um erro do run. A primeira versão imprimia "Nothing to classify" e saía com 0: um pipeline que não testou nada, reportado como verde. É a mesma falha que corrigi no trabalho, onde um setup de login quebrado rodava zero testes e o pipeline continuava verde. Hoje run vazio ou com erro sempre falha.

#### A massa tem testes próprios

Se a massa estiver errada, o número de acerto não vale nada. O `tests/test_dataset.py` confere que há pelo menos 20 casos nas três categorias, que toda falha tem mensagem de erro e que só os casos de queda de ambiente trazem erros de rede. Dois casos que escrevi primeiro estavam errados: um "bug de produto" era na verdade um teste mal escrito, e outro não quebrava nada visível porque a interface atualiza o contador de favoritos sozinha.

#### Aceito por enquanto

- Só o relatório JSON do Playwright é suportado.
- Os arquivos de trace não são lidos. A fixture de rede cobre a parte do trace que importa aqui.
- Diagnosticar a causa de um bug de produto está fora do escopo. Esse é o próximo projeto, `ai-ci-triage`.
- Um commit antigo da massa guarda um JWT de teste do Conduit, vindo do call log do Playwright. Ele é assinado com o segredo só local do `compose.yaml` da suíte e só funciona contra o app em Docker, então não reescrevi o histórico; o gerador agora mascara os headers `Authorization`.
