# Registro consolidado das coletas

## Escopo

Este arquivo consolida os registros tecnicos das coletas executadas para formar a camada bruta de XMLs da Secao 1 do Diario Oficial da Uniao (DOU).

Recorte inicialmente solicitado:

- Inicio: 2025-01-01.
- Fim: 2026-05-01.
- Conteudo-alvo: publicacoes da Secao 1 do DOU.
- Fontes oficiais usadas:
  - INLABS, para arquivos diarios recentes.
  - Portal Brasileiro de Dados Abertos, para arquivos mensais historicos.

Credenciais e tokens foram usados apenas via variaveis de ambiente no processo de coleta. Nenhum segredo foi registrado nos arquivos do projeto.

## Conclusao de cobertura

Temos material suficiente para seguir para a proxima etapa do projeto, com uma ressalva operacional importante.

O periodo de 2025-01-01 a 2026-04-30 esta coberto por arquivos oficiais:

- 2025-01 a 2025-12: pacotes mensais `S01` do Portal de Dados Abertos.
- 2026-01: pacote mensal `S01` do Portal de Dados Abertos, adicionado para cobrir a lacuna anterior a 2026-01-14.
- 2026-01-14 a 2026-04-30: arquivos diarios `DO1` e `DO1E` do INLABS.

O dia 2026-05-01 foi solicitado na coleta INLABS e retornou `not_found` para `DO1` e `DO1E`. Como 1 de maio e feriado nacional, esse resultado e compativel com ausencia de edicao ordinaria nesse dia. Ate a data da execucao, nao havia pacote mensal de maio de 2026 no Portal de Dados Abertos, pois pacotes mensais sao publicados apenas depois do fechamento do mes.

Na etapa de construcao da base, sera necessario deduplicar a sobreposicao entre o pacote mensal `S01012026.zip` e os arquivos diarios do INLABS de 2026-01-14 em diante.

## Totais locais

| Fonte | ZIPs brutos | XMLs extraidos | Dados brutos | Dados extraidos |
| --- | ---: | ---: | ---: | ---: |
| Portal de Dados Abertos | 13 | 104.015 | 2,8 GB | 1,4 GB |
| INLABS | 127 | 28.012 | 382 MB | 388 MB |
| Total fisico local | 140 | 132.027 | 3,2 GB | 1,8 GB |

Observacao: o total fisico local inclui sobreposicoes entre fontes, especialmente em janeiro de 2026. O total logico da base sera definido apenas depois do parsing e da deduplicacao.

## Coleta INLABS

### Objetivo

Coletar arquivos diarios XML da Secao 1 no INLABS para o periodo de 2025-01-01 a 2026-05-01.

Secoes solicitadas:

- `DO1`: Secao 1 ordinaria.
- `DO1E`: edicoes extras da Secao 1.

### Comando

```bash
.venv/bin/dou-collect-inlabs \
  --start-date 2025-01-01 \
  --end-date 2026-05-01 \
  --sections DO1 DO1E \
  --sleep 2 \
  --retry-backoff 5
```

### Parametros tecnicos

- Datas no intervalo: 486.
- Secoes por data: 2.
- Combinacoes data/secao planejadas: 972.
- Pausa entre requisicoes: 2 segundos.
- Backoff base para retentativas: 5 segundos.
- Paralelismo: nenhum.
- Manifesto: `data/manifests/downloads.jsonl`.
- ZIPs brutos: `data/raw/inlabs/YYYY/MM/`.
- XMLs extraidos: `data/extracted/inlabs/YYYY/MM/YYYY-MM-DD-SECAO/`.

### Resultado

A execucao principal ocorreu em 2026-05-17.

- Inicio aproximado: 2026-05-17T03:08:49Z.
- Fim aproximado: 2026-05-17T04:13:14Z.
- Duracao aproximada: 1h04min.
- `downloaded`: 126.
- `already_exists`: 1.
- `not_found`: 845.
- Primeiro download bem-sucedido no recorte: 2026-01-14.
- Ultimo download bem-sucedido no recorte: 2026-04-30.

Resumo por secao:

| Secao | Downloads novos | Ja existente | Indisponiveis |
| --- | ---: | ---: | ---: |
| `DO1` | 71 | 1 | 414 |
| `DO1E` | 55 | 0 | 431 |

Resumo local por mes e secao:

| Mes | Secao | ZIPs | Tamanho bruto | XMLs |
| --- | --- | ---: | ---: | ---: |
| 2026-01 | `DO1` | 12 | 50,9 MB | 3.686 |
| 2026-01 | `DO1E` | 7 | 1,2 MB | 15 |
| 2026-02 | `DO1` | 18 | 56,4 MB | 6.574 |
| 2026-02 | `DO1E` | 13 | 3,3 MB | 144 |
| 2026-03 | `DO1` | 23 | 77,9 MB | 9.132 |
| 2026-03 | `DO1E` | 18 | 0,3 MB | 96 |
| 2026-04 | `DO1` | 19 | 170,4 MB | 8.116 |
| 2026-04 | `DO1E` | 17 | 2,1 MB | 249 |

### Observacoes

- A primeira tentativa de execucao ficou bloqueada por credenciais ausentes. Depois da configuracao de `INLABS_EMAIL` e `INLABS_PASSWORD`, a coleta foi executada.
- O coletor foi ajustado para seguir redirects e tratar redirecionamento para a pagina inicial do INLABS como indisponibilidade (`not_found`).
- O endpoint diario do INLABS nao serviu arquivos de 2025 nem os primeiros dias de 2026 nessa rodada.
- `not_found` inclui arquivos historicos indisponiveis no endpoint diario, fins de semana, feriados e dias sem edicao para a secao solicitada.
- O arquivo `2026-03-28-DO1.zip` foi baixado como ZIP valido, mas extraiu 0 XMLs. Esse caso deve ser inspecionado na etapa de qualidade dos dados brutos.
- O manifesto `data/manifests/downloads.jsonl` e append-only e contem tambem tentativas anteriores de teste; por isso tinha 997 linhas apos a coleta, enquanto a execucao principal tinha 972 combinacoes data/secao.

## Coleta Portal de Dados Abertos

### Objetivo

Complementar o INLABS com pacotes mensais oficiais da Secao 1, principalmente para cobrir o historico de 2025 e a lacuna de janeiro de 2026 anterior ao primeiro arquivo diario disponivel no INLABS.

### Fonte e autenticacao

- Catalogo: `https://dados.gov.br/dados/api/publico`.
- Header de autenticacao: `chave-api-dados-abertos`.
- Variavel de ambiente usada pelo projeto: `DADOS_GOV_BR_API_TOKEN`.
- Arquivos baixados: recursos mensais `S01MMAAAA.zip` hospedados em links oficiais `www.in.gov.br`.

O cliente do projeto foi ajustado para usar o endpoint e o header indicados pelo Swagger de producao do Portal de Dados Abertos. A tentativa inicial com `Authorization: Bearer ...` retornou `401`.

### Comando para 2025

```bash
PYTHONUNBUFFERED=1 DADOS_GOV_BR_API_TOKEN='...' \
  .venv/bin/dou-collect-dados-abertos \
  --start-date 2025-01-01 \
  --end-date 2025-12-31 \
  --sections S01 \
  --sleep 2 \
  --retry-backoff 5 \
  --timeout 600
```

### Comando para janeiro de 2026

```bash
PYTHONUNBUFFERED=1 DADOS_GOV_BR_API_TOKEN='...' \
  .venv/bin/dou-collect-dados-abertos \
  --start-date 2026-01-01 \
  --end-date 2026-01-31 \
  --sections S01 \
  --sleep 2 \
  --retry-backoff 5 \
  --timeout 600
```

### Resultado

- Pacotes mensais baixados: 13.
- Resultado do coletor: 13 `downloaded`.
- XMLs extraidos: 104.015.
- Manifesto: `data/manifests/dados_abertos_downloads.jsonl`.
- Linhas no manifesto: 13.

Resumo por pacote mensal:

| Mes | Arquivo | Tamanho bruto | XMLs |
| --- | --- | ---: | ---: |
| 2025-01 | `S01012025.zip` | 256,6 MB | 8.886 |
| 2025-02 | `S01022025.zip` | 110,8 MB | 6.648 |
| 2025-03 | `S01032025.zip` | 67,7 MB | 6.782 |
| 2025-04 | `S01042025.zip` | 533,0 MB | 8.017 |
| 2025-05 | `S01052025.zip` | 187,5 MB | 7.940 |
| 2025-06 | `S01062025.zip` | 113,4 MB | 7.629 |
| 2025-07 | `S01072025.zip` | 204,2 MB | 9.295 |
| 2025-08 | `S01082025.zip` | 93,8 MB | 3.591 |
| 2025-09 | `S01092025.zip` | 166,7 MB | 9.249 |
| 2025-10 | `S01102025.zip` | 63,8 MB | 9.298 |
| 2025-11 | `S01112025.zip` | 93,4 MB | 8.411 |
| 2025-12 | `S01122025.zip` | 326,8 MB | 11.884 |
| 2026-01 | `S01012026.zip` | 552,6 MB | 6.385 |

### Observacoes

- O pacote mensal `S01012026.zip` foi baixado para preencher a lacuna deixada pelo INLABS entre 2026-01-01 e 2026-01-13.
- O pacote de janeiro de 2026 tambem contem publicacoes de datas que o INLABS ja havia baixado a partir de 2026-01-14. A base deve tratar essa sobreposicao por deduplicacao.
- Os pacotes de abril de 2025 e janeiro de 2026 foram os maiores arquivos observados nesta rodada.

## Arquivos preservados

Os logs textuais avulsos foram consolidados neste arquivo e removidos. Os manifestos JSONL foram preservados porque sao artefatos estruturados e append-only de auditoria:

- `data/manifests/downloads.jsonl`.
- `data/manifests/dados_abertos_downloads.jsonl`.

## Proxima etapa recomendada

Podemos seguir para a implementacao da arquitetura da base de dados e para a etapa de parsing. A analise de deduplicacao, metadados e DER proposto esta registrada em `docs/modelagem/base_publicacoes.md`.

Tarefas imediatas:

1. Implementar o parser dos XMLs com deduplicacao por SHA-256.
2. Montar materias logicas a partir dos fragmentos XML unicos.
3. Gerar a primeira base relacional local, preferencialmente em SQLite.
4. Criar views de auditoria para duplicatas, orgaos, tipos de ato e estatisticas da base.
