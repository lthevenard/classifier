PRAGMA foreign_keys = ON;

CREATE TABLE base_info (
    nome TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);

CREATE TABLE edicao_dou (
    id INTEGER PRIMARY KEY,
    data_publicacao TEXT NOT NULL,
    pub_name TEXT NOT NULL,
    numero_edicao TEXT NOT NULL,
    secao_normalizada TEXT NOT NULL,
    UNIQUE (data_publicacao, pub_name, numero_edicao)
);

CREATE TABLE tipo_ato (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL UNIQUE
);

CREATE TABLE orgao (
    id INTEGER PRIMARY KEY,
    parent_id INTEGER REFERENCES orgao(id),
    nome TEXT NOT NULL,
    caminho_normalizado TEXT NOT NULL UNIQUE,
    caminho_raw TEXT NOT NULL,
    nivel INTEGER NOT NULL CHECK (nivel >= 1)
);

CREATE TABLE materia (
    id INTEGER PRIMARY KEY,
    edicao_id INTEGER NOT NULL REFERENCES edicao_dou(id),
    tipo_ato_id INTEGER NOT NULL REFERENCES tipo_ato(id),
    orgao_id INTEGER NOT NULL REFERENCES orgao(id),
    chave_natural TEXT NOT NULL UNIQUE,
    id_materia TEXT NOT NULL,
    id_oficio TEXT NOT NULL,
    nome_interno TEXT NOT NULL,
    art_category_raw TEXT NOT NULL,
    art_class_prefix TEXT NOT NULL,
    pagina_inicial INTEGER,
    pagina_final INTEGER,
    qtd_fragmentos INTEGER NOT NULL DEFAULT 0,
    identifica TEXT NOT NULL DEFAULT '',
    data_texto TEXT NOT NULL DEFAULT '',
    ementa TEXT NOT NULL DEFAULT '',
    titulo TEXT NOT NULL DEFAULT '',
    subtitulo TEXT NOT NULL DEFAULT '',
    texto_html_completo TEXT NOT NULL DEFAULT '',
    texto_plain_completo TEXT NOT NULL DEFAULT '',
    texto_sha256 TEXT NOT NULL DEFAULT '',
    tem_estrutura_legal INTEGER NOT NULL DEFAULT 0
        CHECK (tem_estrutura_legal IN (0, 1))
);

CREATE TABLE fragmento_xml (
    id INTEGER PRIMARY KEY,
    materia_id INTEGER NOT NULL REFERENCES materia(id),
    sha256_xml TEXT NOT NULL UNIQUE,
    nome_arquivo TEXT NOT NULL,
    article_id TEXT NOT NULL,
    id_materia TEXT NOT NULL,
    id_oficio TEXT NOT NULL,
    ordem_fragmento INTEGER,
    numero_pagina INTEGER,
    pdf_page TEXT NOT NULL DEFAULT '',
    art_class_raw TEXT NOT NULL DEFAULT '',
    art_size INTEGER,
    art_notes TEXT NOT NULL DEFAULT '',
    highlight_type TEXT NOT NULL DEFAULT '',
    highlight_priority TEXT NOT NULL DEFAULT '',
    highlight TEXT NOT NULL DEFAULT '',
    highlight_image TEXT NOT NULL DEFAULT '',
    highlight_image_name TEXT NOT NULL DEFAULT '',
    identifica TEXT NOT NULL DEFAULT '',
    data_texto TEXT NOT NULL DEFAULT '',
    ementa TEXT NOT NULL DEFAULT '',
    titulo TEXT NOT NULL DEFAULT '',
    subtitulo TEXT NOT NULL DEFAULT '',
    texto_html TEXT NOT NULL DEFAULT '',
    texto_plain TEXT NOT NULL DEFAULT ''
);

CREATE TABLE fragmento_midia (
    id INTEGER PRIMARY KEY,
    fragmento_xml_id INTEGER NOT NULL REFERENCES fragmento_xml(id),
    ordem INTEGER NOT NULL,
    conteudo TEXT NOT NULL DEFAULT '',
    atributos_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX idx_edicao_dou_data ON edicao_dou(data_publicacao);
CREATE INDEX idx_materia_edicao ON materia(edicao_id);
CREATE INDEX idx_materia_tipo_ato ON materia(tipo_ato_id);
CREATE INDEX idx_materia_orgao ON materia(orgao_id);
CREATE INDEX idx_materia_tem_estrutura_legal ON materia(tem_estrutura_legal);
CREATE INDEX idx_fragmento_xml_materia ON fragmento_xml(materia_id);
CREATE INDEX idx_fragmento_xml_id_materia ON fragmento_xml(id_materia);
CREATE INDEX idx_orgao_parent ON orgao(parent_id);

CREATE VIEW vw_materias AS
SELECT
    m.id,
    e.data_publicacao,
    e.pub_name,
    e.numero_edicao,
    e.secao_normalizada,
    t.nome AS tipo_ato,
    o.caminho_normalizado AS orgao,
    m.id_materia,
    m.id_oficio,
    m.nome_interno,
    m.pagina_inicial,
    m.pagina_final,
    m.qtd_fragmentos,
    m.identifica,
    m.data_texto,
    m.ementa,
    m.titulo,
    m.subtitulo,
    m.tem_estrutura_legal,
    m.texto_plain_completo
FROM materia m
JOIN edicao_dou e ON e.id = m.edicao_id
JOIN tipo_ato t ON t.id = m.tipo_ato_id
JOIN orgao o ON o.id = m.orgao_id;

CREATE VIEW vw_materias_analise_2025 AS
SELECT
    m.id,
    e.data_publicacao,
    e.pub_name,
    e.numero_edicao,
    e.secao_normalizada,
    t.nome AS tipo_ato,
    o.caminho_normalizado AS orgao,
    m.chave_natural,
    m.id_materia,
    m.id_oficio,
    m.nome_interno,
    m.art_category_raw,
    m.art_class_prefix,
    m.pagina_inicial,
    m.pagina_final,
    m.qtd_fragmentos,
    m.identifica,
    m.data_texto,
    m.ementa,
    m.titulo,
    m.subtitulo,
    m.tem_estrutura_legal,
    m.texto_plain_completo,
    m.texto_html_completo,
    m.texto_sha256
FROM materia m
JOIN edicao_dou e ON e.id = m.edicao_id
JOIN tipo_ato t ON t.id = m.tipo_ato_id
JOIN orgao o ON o.id = m.orgao_id
WHERE e.data_publicacao >= '2025-01-01'
  AND e.data_publicacao < '2026-01-01'
  AND m.tem_estrutura_legal = 1;

CREATE VIEW vw_materias_por_orgao AS
SELECT
    o.caminho_normalizado AS orgao,
    COUNT(*) AS total_materias
FROM materia m
JOIN orgao o ON o.id = m.orgao_id
GROUP BY o.caminho_normalizado;

CREATE VIEW vw_materias_por_tipo_ato AS
SELECT
    t.nome AS tipo_ato,
    COUNT(*) AS total_materias
FROM materia m
JOIN tipo_ato t ON t.id = m.tipo_ato_id
GROUP BY t.nome;

CREATE VIEW vw_fragmentos_longos AS
SELECT
    f.id,
    f.materia_id,
    f.nome_arquivo,
    LENGTH(f.texto_html) AS tamanho_texto_html,
    LENGTH(f.texto_plain) AS tamanho_texto_plain
FROM fragmento_xml f
ORDER BY tamanho_texto_html DESC;

CREATE VIEW vw_estatisticas_base AS
SELECT 'edicoes' AS metrica, CAST(COUNT(*) AS TEXT) AS valor FROM edicao_dou
UNION ALL
SELECT 'materias', CAST(COUNT(*) AS TEXT) FROM materia
UNION ALL
SELECT 'materias_com_estrutura_legal', CAST(COUNT(*) AS TEXT)
FROM materia
WHERE tem_estrutura_legal = 1
UNION ALL
SELECT 'materias_sem_estrutura_legal', CAST(COUNT(*) AS TEXT)
FROM materia
WHERE tem_estrutura_legal = 0
UNION ALL
SELECT 'materias_analise_2025', CAST(COUNT(*) AS TEXT)
FROM vw_materias_analise_2025
UNION ALL
SELECT 'fragmentos_xml', CAST(COUNT(*) AS TEXT) FROM fragmento_xml
UNION ALL
SELECT 'orgaos', CAST(COUNT(*) AS TEXT) FROM orgao
UNION ALL
SELECT 'tipos_ato', CAST(COUNT(*) AS TEXT) FROM tipo_ato
UNION ALL
SELECT 'midias', CAST(COUNT(*) AS TEXT) FROM fragmento_midia;
