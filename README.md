# Classificador de atos normativos do DOU

Este repositorio contem o codigo e a documentacao de um projeto de pesquisa para identificar quais orgaos da Administracao Publica Federal editam atos normativos de efeitos gerais na Secao 1 do Diario Oficial da Uniao (DOU).

O objetivo empirico e construir uma base estruturada de publicacoes do DOU e, em etapa posterior, classificar os atos conforme seus efeitos:

- atos gerais e abstratos, com efeitos normativos gerais;
- atos de efeitos internos;
- atos de efeitos concretos direcionados a destinatarios especificos.

## Estado atual

O repositorio ja implementa duas etapas do pipeline:

1. **Coleta de XMLs oficiais do DOU**
   - INLABS, para arquivos diarios recentes.
   - Portal Brasileiro de Dados Abertos, para pacotes historicos mensais.

2. **Construcao da base relacional**
   - Deduplicacao dos XMLs por SHA-256.
   - Agrupamento de fragmentos XML em materias logicas.
   - Extracao de metadados estruturados.
   - Preservacao do HTML original e geracao de texto plano processavel.
   - Marcacao booleana de materias com estrutura textual legal.
   - Geracao de uma base SQLite local.

A etapa de classificacao por LLM ainda nao esta implementada.

## Estrutura do repositorio

```text
src/dou_classifier/
  collect/        # clientes, downloaders e CLIs de coleta
  parse/          # parser XML/HTML, schema e builder da base SQLite
  config.py       # leitura de credenciais por variaveis de ambiente

tests/
  collect/        # testes da etapa de coleta
  parse/          # testes da construcao da base

docs/
  coletas/        # registro tecnico das coletas executadas
  modelagem/      # DER e documentacao da base SQLite
  projeto/        # registro completo/historico do projeto
```

Os dados brutos, XMLs extraidos e bases geradas ficam em `data/`, que e ignorado pelo Git.

## Instalacao

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

Para usar os coletores, configure as credenciais necessarias:

```bash
export INLABS_EMAIL='seu_email_cadastrado_no_inlabs'
export INLABS_PASSWORD='sua_senha_do_inlabs'
export DADOS_GOV_BR_API_TOKEN='seu_token_do_portal_de_dados_abertos'
```

## Comandos principais

Coleta diaria pelo INLABS:

```bash
.venv/bin/dou-collect-inlabs \
  --start-date 2026-01-14 \
  --end-date 2026-01-31 \
  --sections DO1 DO1E
```

Coleta historica mensal pelo Portal de Dados Abertos:

```bash
.venv/bin/dou-collect-dados-abertos \
  --start-date 2025-01-01 \
  --end-date 2025-12-31 \
  --sections S01
```

Construcao da base SQLite:

```bash
.venv/bin/dou-build-db \
  --input-dir data/extracted \
  --database-path data/database/dou.sqlite \
  --force
```

Aplicacao do filtro de estrutura legal em uma base existente:

```bash
.venv/bin/dou-apply-legal-filter \
  --database-path data/database/dou.sqlite
```

Rodar testes:

```bash
.venv/bin/python -m pytest
```

## Documentacao

- [Registro das coletas](docs/coletas/coletas.md)
- [Modelagem da base SQLite](docs/modelagem/base_publicacoes.md)
- [Registro completo do projeto](docs/projeto/registro_completo.md)

## Artefatos locais

O repositorio versiona apenas codigo, testes e documentacao. Arquivos pesados ficam fora do Git:

- `data/raw/`: ZIPs brutos baixados das fontes oficiais;
- `data/extracted/`: XMLs extraidos;
- `data/manifests/`: manifestos locais de coleta;
- `data/database/dou.sqlite`: base SQLite gerada.

Na primeira geracao local registrada, a base SQLite reuniu 120.537 materias logicas a partir de 128.326 fragmentos XML unicos, apos descartar 3.701 duplicatas exatas. O filtro inicial de estrutura legal marcou 68.801 materias como candidatas para triagem/classificacao posterior e 51.736 como filtraveis de partida.
