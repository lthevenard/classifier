# Classificador de atos normativos do DOU

## Proposito

Este projeto tem como objetivo identificar quais orgaos da administracao publica federal editam atos normativos de efeitos gerais, isto e, quais orgaos atuam como "orgaos reguladores" no sentido empirico de produzir comandos gerais e abstratos direcionados a destinatarios externos.

A base de trabalho sera formada por publicacoes da Secao 1 do Diario Oficial da Uniao (DOU). A estrategia inicial e:

1. Coletar todos os atos publicados na Secao 1 do DOU em um periodo parametrizavel.
2. Aplicar filtros simples para excluir atos que claramente nao podem ser atos normativos de efeitos gerais.
3. Classificar os atos remanescentes com apoio de LLM em tres classes:
   - ato geral e abstrato, com efeitos normativos gerais;
   - ato de efeitos internos, voltado a disciplinar a organizacao ou o funcionamento interno do proprio orgao;
   - ato de efeitos concretos, direcionado a destinatarios externos especificos.
4. Agregar os resultados por orgao editor, tipo de ato, periodo e confianca da classificacao.

## Principios de desenho

- A coleta deve aceitar qualquer intervalo de datas, embora o primeiro classificador use o ultimo ano como recorte principal.
- Os dados brutos devem ser preservados para auditoria e reprocessamento.
- Cada etapa deve produzir artefatos intermediarios versionaveis ou reprodutiveis.
- A classificacao por LLM deve guardar prompt, modelo, resposta bruta, classe final e eventuais justificativas.
- O pipeline deve facilitar amostragem manual para avaliacao de qualidade.

## Pipeline previsto

1. `collect`: baixa os arquivos da Secao 1 do DOU no periodo definido.
2. `parse`: extrai metadados e texto integral de cada materia.
3. `filter`: remove tipos de publicacao que nao interessam ao classificador.
4. `classify`: envia os textos remanescentes ao LLM e normaliza as respostas.
5. `evaluate`: compara amostras classificadas com rotulos humanos.
6. `aggregate`: produz tabelas por orgao, classe, periodo e tipo de ato.

## Estado atual do repositorio

A etapa de coleta ja possui uma implementacao inicial em Python para XMLs de duas fontes oficiais: INLABS, para arquivos diarios recentes, e Portal Brasileiro de Dados Abertos, para arquivos historicos mensais por ano/mes/secao.

A etapa de estruturacao da base tambem ja possui uma primeira implementacao: os XMLs extraidos sao deduplicados por SHA-256, agrupados em materias logicas e gravados em uma base SQLite local. A documentacao da modelagem, do DER e dos resultados da primeira geracao esta em `docs/modelagem/base_publicacoes.md`.

Arquivos principais:

```text
src/
  dou_classifier/
    collect/
      download_inlabs.py  # CLI de coleta
      download_dados_abertos.py  # CLI de coleta historica mensal
      inlabs_client.py    # autenticacao e requisicoes ao INLABS
      dados_abertos_client.py  # descoberta de recursos mensais no dados.gov.br
      downloader.py       # download, validacao, extracao e manifesto
      dados_abertos_downloader.py  # download mensal, validacao, extracao e manifesto
      extract.py          # extracao segura dos XMLs do ZIP
      manifest.py         # manifesto JSONL das tentativas
      paths.py            # convencoes de caminhos
      date_ranges.py      # intervalos de datas
    parse/
      dou_xml.py          # parser dos XMLs e conversao de HTML para texto
      build_database.py   # CLI de construcao da base SQLite
      schema.sql          # schema SQLite versionado
    config.py             # leitura de credenciais por ambiente
tests/
  collect/
  parse/
```

## Instalacao local

Crie um ambiente virtual e instale o pacote em modo editavel:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

Configure as credenciais do INLABS em variaveis de ambiente. O arquivo `.env.example` mostra os nomes esperados, mas o `.env` real nao deve ser versionado:

```bash
export INLABS_EMAIL='seu_email_cadastrado_no_inlabs'
export INLABS_PASSWORD='sua_senha_do_inlabs'
```

Para consultar a API do Portal de Dados Abertos, configure tambem o token do perfil consumidor do `dados.gov.br`:

```bash
export DADOS_GOV_BR_API_TOKEN='seu_token_do_portal_de_dados_abertos'
```

### Cadastro no INLABS

As credenciais devem ser criadas na pagina oficial do INLABS:

- https://inlabs.in.gov.br/acessar.php

Na secao `Registrar`, informe e-mail, senha, nome completo, telefone, UF/cidade e, se aplicavel, nome da empresa. O e-mail e a senha cadastrados nessa pagina sao os valores que devem ser usados em `INLABS_EMAIL` e `INLABS_PASSWORD`.

Se ja houver cadastro, use a secao `Acessar`. Para recuperar acesso, use a area `Esqueci a Senha` na mesma pagina.

### Token do Portal de Dados Abertos

A API atual do Portal Brasileiro de Dados Abertos exige token de API. A pagina oficial do Catalogo de APIs Governamentais informa que a API permite consultar conjuntos de dados e que e preciso gerar um token para utiliza-la; no Swagger de producao, esse token e enviado no header `chave-api-dados-abertos`.

- https://www.gov.br/conecta/catalogo/apis/api-portal-de-dados-abertos
- https://dados.gov.br/dados/conteudo/como-acessar-a-api-do-portal-de-dados-abertos-com-o-perfil-de-consumidor

No nosso coletor, esse token e usado apenas para consultar o catalogo e descobrir a URL oficial do ZIP mensal. O arquivo em si e baixado do link catalogado da Imprensa Nacional (`www.in.gov.br`).

## Como coletar XMLs do INLABS

Para visualizar os arquivos que seriam coletados, sem autenticar nem baixar:

```bash
.venv/bin/dou-collect-inlabs \
  --start-date 2025-05-16 \
  --end-date 2025-05-17 \
  --sections DO1 DO1E \
  --dry-run
```

Para baixar a Secao 1 (`DO1`) em um intervalo:

```bash
.venv/bin/dou-collect-inlabs \
  --start-date 2025-05-16 \
  --end-date 2025-05-17 \
  --sections DO1
```

Por padrao, o comando:

- salva o ZIP bruto em `data/raw/inlabs/YYYY/MM/`;
- extrai os XMLs para `data/extracted/inlabs/YYYY/MM/YYYY-MM-DD-DO1/`;
- registra cada tentativa em `data/manifests/downloads.jsonl`;
- nao baixa novamente um ZIP local valido, salvo com `--force`.
- faz requisicoes sequenciais, sem paralelismo;
- espera 2 segundos entre requisicoes por padrao (`--sleep 2.0`);
- usa retentativas com backoff exponencial (`--retry-backoff 5.0`);
- respeita o cabecalho HTTP `Retry-After`, quando enviado pelo servidor.

Use `--sections DO1 DO1E` para incluir edicoes extras da Secao 1. Use `--no-extract` se quiser preservar apenas os ZIPs brutos nesta rodada.

## Como coletar XMLs historicos pelo Portal de Dados Abertos

A Carta de Servicos da Imprensa Nacional informa que as edicoes completas do DOU em XML tambem podem ser acessadas pelo Portal Brasileiro de Dados Abertos, agrupadas por ano, mes e secao, e publicadas ate o quinto dia util do mes subsequente:

- https://www.gov.br/imprensanacional/pt-br/arquivos/arquivos-acoes-e-programas/carta_de_servico_v2_edicao_-2020.pdf

Para o nosso recorte, esse caminho complementa o INLABS quando o endpoint diario nao entrega arquivos antigos. A nomenclatura historica dos recursos mensais segue o padrao `S01MMAAAA`, `S02MMAAAA` ou `S03MMAAAA`; portanto, a Secao 1 mensal e `S01`. Por conveniencia, a CLI aceita `DO1` e `DO1E`, mas ambos sao normalizados para `S01`, porque o pacote mensal do Portal e por secao, nao por edicao ordinaria/extra.

Para visualizar os recursos mensais que seriam baixados:

```bash
.venv/bin/dou-collect-dados-abertos \
  --start-date 2025-01-01 \
  --end-date 2025-12-31 \
  --sections S01 \
  --dry-run
```

Para baixar e extrair a Secao 1 historica:

```bash
.venv/bin/dou-collect-dados-abertos \
  --start-date 2025-01-01 \
  --end-date 2026-01-13 \
  --sections S01 \
  --sleep 2 \
  --retry-backoff 5
```

Por padrao, o comando:

- consulta o catalogo oficial em `https://dados.gov.br/dados/api/publico`;
- usa `DADOS_GOV_BR_API_TOKEN` no header `chave-api-dados-abertos`;
- salva o ZIP bruto em `data/raw/dados_abertos/YYYY/MM/S01MMAAAA.zip`;
- extrai os XMLs para `data/extracted/dados_abertos/YYYY/MM/S01MMAAAA/`;
- registra cada tentativa em `data/manifests/dados_abertos_downloads.jsonl`;
- nao baixa novamente um ZIP local valido, salvo com `--force`;
- faz downloads sequenciais, com pausa configuravel por `--sleep`;
- usa retentativas com backoff exponencial e respeita `Retry-After`, quando enviado.

Exemplo para complementar a coleta que falhou no INLABS antes de 2026-01-14:

```bash
.venv/bin/dou-collect-dados-abertos \
  --start-date 2025-01-01 \
  --end-date 2026-01-13 \
  --sections DO1 DO1E \
  --sleep 2 \
  --retry-backoff 5
```

Mesmo nesse exemplo, `DO1` e `DO1E` geram um unico download mensal por mes (`S01`), evitando duplicidade.

### Coleta 2025-01-01 a 2026-05-01

A coleta solicitada para o recorte de 2025-01-01 a 2026-05-01 deve ser executada com `DO1` e `DO1E`, para cobrir a Secao 1 ordinaria e suas edicoes extras:

```bash
.venv/bin/dou-collect-inlabs \
  --start-date 2025-01-01 \
  --end-date 2026-05-01 \
  --sections DO1 DO1E \
  --sleep 2 \
  --retry-backoff 5
```

Registro consolidado das coletas: `docs/coletas/coletas.md`.

Resultado da execucao principal em 2026-05-17:

- 972 combinacoes data/secao processadas.
- 126 downloads novos, 1 arquivo ja existente e 845 indisponiveis (`not_found`).
- 127 ZIPs brutos preservados em `data/raw/inlabs`.
- 28.012 XMLs extraidos em `data/extracted/inlabs`.
- Primeiro download bem-sucedido no recorte: 2026-01-14.
- Ultimo download bem-sucedido no recorte: 2026-04-30.

Observacao: nesta rodada, o endpoint direto do INLABS nao serviu os arquivos de 2025 solicitados; ele redirecionou para a pagina inicial do portal autenticado, e esses casos foram registrados como `not_found`.

### Coleta historica 2025 pelo Portal de Dados Abertos

A coleta complementar de todo o ano de 2025 para a Secao 1 foi executada pelo Portal de Dados Abertos:

```bash
.venv/bin/dou-collect-dados-abertos \
  --start-date 2025-01-01 \
  --end-date 2025-12-31 \
  --sections S01 \
  --sleep 2 \
  --retry-backoff 5 \
  --timeout 600
```

Registro consolidado das coletas: `docs/coletas/coletas.md`.

Resultado da execucao em 2026-05-17:

- 12 ZIPs mensais baixados, todos com resultado `downloaded`.
- 97.630 XMLs extraidos.
- Dados brutos preservados em `data/raw/dados_abertos/2025` (2,2 GB).
- XMLs extraidos em `data/extracted/dados_abertos/2025` (1,4 GB).
- Manifesto: `data/manifests/dados_abertos_downloads.jsonl`.
- Detalhes tecnicos consolidados: `docs/coletas/coletas.md`.

### Coleta responsavel

A documentacao publica do INLABS nao informa um limite numerico de requisicoes por minuto. Os exemplos oficiais disponibilizados pela Imprensa Nacional fazem downloads sequenciais e sugerem agendamento periodico com `crontab`, nao coleta paralela.

Por isso, a implementacao do projeto adota uma postura conservadora:

- nao ha concorrencia ou multiplos workers;
- a coleta historica e feita um arquivo por vez;
- arquivos ja baixados e validos nao sao solicitados novamente;
- `404` e tratado como ausencia esperada de edicao, sem novas tentativas agressivas;
- falhas temporarias sao retentadas com pausas crescentes;
- a pausa entre requisicoes pode ser aumentada com `--sleep`.

Para cargas historicas grandes, recomenda-se manter `--sleep` em alguns segundos ou mais e executar a coleta fora de horarios de pico. Para coleta diaria de manutencao, a abordagem mais alinhada aos exemplos oficiais e agendar uma execucao periodica apos a disponibilizacao das publicacoes.

## Como criar a base SQLite

Depois de extrair os XMLs, construa a base deduplicada com:

```bash
.venv/bin/dou-build-db \
  --input-dir data/extracted \
  --database-path data/database/dou.sqlite \
  --force \
  --progress-interval 5000
```

O comando:

- calcula SHA-256 de cada XML e descarta duplicatas exatas;
- agrupa fragmentos XML em materias logicas;
- preserva metadados estruturados, HTML original e texto plano processavel;
- grava a base em `data/database/dou.sqlite`;
- cria views iniciais para materias, orgaos, tipos de ato, fragmentos longos e estatisticas.

Documentacao da modelagem: `docs/modelagem/base_publicacoes.md`.

## Verificacao local

Rode os testes com:

```bash
.venv/bin/python -m pytest
```

## Etapa 1: coleta do DOU Secao 1

### Fonte primaria mapeada

A fonte inicial mais adequada e o INLABS, da Imprensa Nacional:

- Portal: https://inlabs.in.gov.br/
- Repositorio oficial com exemplos de automacao: https://github.com/Imprensa-Nacional/inlabs

Segundo o portal, o INLABS disponibiliza informacoes publicadas no DOU em XML, com objetivo de facilitar o processamento dos dados. O proprio repositorio oficial informa que o INLABS permite acesso a edicoes completas do DOU em PDF e XML desde 2020.

Os exemplos oficiais usam:

- login por `POST https://inlabs.in.gov.br/logar.php`;
- cookie `inlabs_session_cookie`;
- download em `https://inlabs.in.gov.br/index.php?p=YYYY-MM-DD&dl=YYYY-MM-DD-DO1.zip`;
- cabecalho `origem: 736372697074`;
- codigo `DO1` para a Secao 1;
- codigo `DO1E` para edicoes extras da Secao 1.

Para periodos historicos que nao estejam disponiveis pelo endpoint diario do INLABS, a fonte complementar e o Portal Brasileiro de Dados Abertos. A API do portal funciona como catalogo de metadados; os ZIPs mensais ficam nos links oficiais catalogados da Imprensa Nacional.

### Decisoes iniciais

- Baixar XML, nao PDF, como fonte principal de dados estruturados.
- Coletar `DO1` por padrao e permitir incluir `DO1E` por parametro.
- Tratar cada arquivo diario `.zip` como dado bruto imutavel.
- Extrair XML para uma camada processada, sem apagar os zips originais.
- Permitir reexecucao idempotente: se o zip do dia/secao ja existir e passar validacao, nao baixar novamente sem `--force`.

### Parametros necessarios para os scripts

- `--start-date`: data inicial no formato `YYYY-MM-DD`.
- `--end-date`: data final no formato `YYYY-MM-DD`.
- `--sections`: lista de secoes, inicialmente `DO1` e opcionalmente `DO1E`.
- `--output-dir`: diretorio raiz para dados baixados.
- `--force`: baixa novamente arquivos ja existentes.
- `--sleep`: intervalo entre requisicoes para reduzir risco de bloqueio.
- `--max-retries`: tentativas por arquivo.
- `--credentials-env`: nomes das variaveis de ambiente com login e senha.

Credenciais sugeridas:

- `INLABS_EMAIL`
- `INLABS_PASSWORD`

### Estrutura de dados sugerida

```text
data/
  raw/
    inlabs/
      YYYY/
        MM/
          YYYY-MM-DD-DO1.zip
          YYYY-MM-DD-DO1E.zip
  extracted/
    inlabs/
      YYYY/
        MM/
          YYYY-MM-DD-DO1/
          YYYY-MM-DD-DO1E/
  manifests/
    downloads.jsonl
```

### Manifesto de download

Cada tentativa de download deve registrar:

- data da publicacao;
- secao (`DO1`, `DO1E`);
- URL solicitada;
- caminho local;
- status HTTP;
- tamanho em bytes;
- hash SHA-256 do arquivo salvo;
- timestamp da tentativa;
- numero da tentativa;
- resultado (`downloaded`, `already_exists`, `not_found`, `failed`);
- mensagem de erro, quando houver.

### Cuidados tecnicos

- O INLABS exige autenticacao gratuita; o script nao deve armazenar credenciais no repositorio.
- Arquivos podem nao existir em fins de semana, feriados ou dias sem edicao da secao.
- `404` deve ser registrado como ausencia esperada, nao necessariamente erro fatal.
- A coleta historica deve lidar com muitas requisicoes: usar retentativas, pausa entre chamadas, backoff e logs retomaveis.
- A camada de parsing deve ser separada da camada de download para facilitar reprocessamento.
- Precisamos validar a estrutura real do XML assim que houver um primeiro arquivo baixado com credenciais.

### Modulos Python da etapa de coleta

```text
src/
  dou_classifier/
    collect/
      inlabs_client.py
      download_inlabs.py
      dados_abertos_client.py
      download_dados_abertos.py
      downloader.py
      dados_abertos_downloader.py
      extract.py
      manifest.py
      paths.py
      date_ranges.py
      checksums.py
    parse/
      dou_xml.py
      build_database.py
      schema.sql
    config.py
tests/
  collect/
    test_manifest.py
    test_date_ranges.py
    test_inlabs_client.py
    test_downloader.py
    test_extract.py
    test_paths.py
```

Responsabilidades:

- `inlabs_client.py`: autenticacao, sessao HTTP, download de um arquivo por data/secao.
- `download_inlabs.py`: CLI para percorrer intervalos de datas e chamar o cliente.
- `dados_abertos_client.py`: consulta o catalogo do Portal de Dados Abertos e localiza recursos mensais por ano/mes/secao.
- `download_dados_abertos.py`: CLI para percorrer meses e baixar recursos mensais historicos.
- `downloader.py`: orquestracao de download, validacao, extracao e manifesto.
- `dados_abertos_downloader.py`: orquestracao de download mensal, validacao, extracao e manifesto.
- `extract.py`: extracao segura de arquivos XML contidos nos ZIPs.
- `manifest.py`: leitura/escrita do manifesto e decisao de reexecucao.
- `paths.py`: convencoes de pastas para dados brutos e extraidos.
- `date_ranges.py`: validacao e iteracao sobre intervalos de datas.
- `checksums.py`: calculo de hash SHA-256 dos arquivos salvos.
- `dou_xml.py`: extracao de metadados, campos de texto e texto plano dos XMLs.
- `build_database.py`: deduplicacao dos XMLs, montagem de materias logicas e gravacao da base SQLite.
- `schema.sql`: schema relacional, indices e views da base SQLite.
- `config.py`: configuracoes comuns e leitura segura de variaveis de ambiente.

Detalhes da modelagem da base: `docs/modelagem/base_publicacoes.md`.

### Dependencias provaveis

- `requests` para HTTP.
- `argparse` para CLI, mantendo a primeira versao sem framework adicional.
- `zipfile` da biblioteca padrao para validacao e extracao dos ZIPs.
- `sqlite3`, `xml.etree` e `html.parser` da biblioteca padrao para construcao da base.
- `pytest` para testes.

Dependencias como `pandas`, `pyarrow`, `duckdb`, `lxml` ou clientes de LLM ficam para etapas posteriores, se forem necessarias para analise, exportacao ou classificacao.

### Perguntas abertas

- Incluir edicoes extras (`DO1E`) no recorte principal ou apenas em coleta opcional?
- O "ultimo ano" sera contado como ultimos 365 dias corridos ou como ano calendario anterior?
- Vamos manter todos os atos da Secao 1 ou aplicar ja na coleta algum filtro por tipo de materia?
- O destino analitico inicial sera CSV/Parquet local, SQLite ou DuckDB?

## Diario de progresso

### 2026-05-16

- Criado este documento inicial do projeto.
- Mapeada a fonte primaria de coleta: INLABS/Imprensa Nacional.
- Identificados os codigos `DO1` e `DO1E`, o fluxo de autenticacao e o padrao de URL usado pelos scripts oficiais.
- Definida uma primeira arquitetura para scripts Python de download por periodo, preservacao de dados brutos e manifesto de coleta.
- Implementada a primeira versao do pacote Python `dou_classifier`.
- Criada a CLI `dou-collect-inlabs` para coleta por intervalo de datas.
- Implementado login no INLABS via variaveis de ambiente, sem gravar credenciais no repositorio.
- Implementado download idempotente dos ZIPs XML, validacao de ZIP, extracao segura dos XMLs e manifesto append-only em JSONL.
- Adicionados testes unitarios para datas, caminhos, URL do INLABS, manifesto, extracao e fluxo basico de download sem rede.
- Reforcadas precaucoes de coleta responsavel: requisicoes sequenciais, pausa padrao maior, backoff exponencial em retentativas e respeito ao `Retry-After`.
- Registrada a tentativa de coleta do periodo 2025-01-01 a 2026-05-01; a execucao real ficou bloqueada pela ausencia das credenciais `INLABS_EMAIL` e `INLABS_PASSWORD` no ambiente.
- Ajustado o cliente para seguir redirects no download, em conformidade com os exemplos oficiais do INLABS.
- Ajustado o tratamento de datas indisponiveis: quando o INLABS redireciona para a pagina inicial em vez de entregar ZIP, o coletor registra `not_found` sem retentativas desnecessarias.
- Executada a coleta principal de 2025-01-01 a 2026-05-01 para `DO1` e `DO1E`: 126 downloads novos, 1 `already_exists`, 845 `not_found`, 127 ZIPs brutos e 28.012 XMLs extraidos.

### 2026-05-17

- Confirmado que o endpoint diario do INLABS nao cobriu o periodo anterior a 2026-01-14 na coleta executada.
- Mapeada a estrategia complementar pelo Portal Brasileiro de Dados Abertos: localizar os recursos mensais por ano/mes/secao no catalogo e baixar os ZIPs oficiais da Imprensa Nacional.
- Implementada a CLI `dou-collect-dados-abertos` para coleta historica mensal.
- Adicionados `dados_abertos_client.py` e `dados_abertos_downloader.py`, com normalizacao de secoes (`DO1`/`DO1E` -> `S01`), descoberta de recursos, download idempotente, validacao de ZIP, extracao segura e manifesto proprio.
- Atualizado `.env.example` com `DADOS_GOV_BR_API_TOKEN`.
- Adicionados testes unitarios para meses, caminhos do Portal, parsing dos recursos mensais e download historico sem rede.
- Ajustado o cliente do Portal de Dados Abertos para usar o endpoint oficial `https://dados.gov.br/dados/api/publico` e o header `chave-api-dados-abertos`, conforme o Swagger de producao.
- Executada a coleta historica da Secao 1 de 2025 pelo Portal de Dados Abertos: 12 ZIPs mensais baixados e 97.630 XMLs extraidos.
- Executada a coleta do pacote mensal `S01012026.zip` pelo Portal de Dados Abertos para cobrir a lacuna anterior ao primeiro arquivo diario disponivel no INLABS.
- Consolidado o registro tecnico das coletas em `docs/coletas/coletas.md`.
- Implementada a CLI `dou-build-db` para construir a base SQLite deduplicada.
- Adicionados `parse/dou_xml.py`, `parse/build_database.py` e `parse/schema.sql`.
- Adicionados testes unitarios para deduplicacao exata, montagem de materias com multiplos fragmentos e IDs repetidos em datas diferentes.
- Executada a primeira geracao de `data/database/dou.sqlite`: 132.027 XMLs lidos, 3.701 duplicatas descartadas, 128.326 fragmentos unicos e 120.537 materias logicas.
