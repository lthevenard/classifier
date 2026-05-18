import sqlite3
from pathlib import Path

from dou_classifier.parse.build_database import build_database


def write_xml(
    path: Path,
    *,
    article_id: str = "100",
    id_materia: str = "200",
    id_oficio: str = "300",
    name: str = "Materia teste",
    pub_date: str = "02/01/2026",
    pub_name: str = "DO1",
    edition_number: str = "1",
    art_type: str = "Portaria",
    art_category: str = "Ministerio Teste/Secretaria Teste",
    art_class: str = "00001:00002:00003:00004:00005:00006:00007:00008:00009:00010:00011:00001",
    number_page: str = "1",
    text_html: str = "<p>Texto teste</p>",
    identifica: str = "PORTARIA TESTE",
    ementa: str = "Ementa teste",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""<xml><article id="{article_id}" name="{name}" idOficio="{id_oficio}" pubName="{pub_name}" artType="{art_type}" pubDate="{pub_date}" artClass="{art_class}" artCategory="{art_category}" artSize="12" artNotes="" numberPage="{number_page}" pdfPage="http://example.test/pdf" editionNumber="{edition_number}" highlightType="" highlightPriority="" highlight="" highlightimage="" highlightimagename="" idMateria="{id_materia}">
  <body>
    <Identifica><![CDATA[{identifica}]]></Identifica>
    <Data><![CDATA[]]></Data>
    <Ementa><![CDATA[{ementa}]]></Ementa>
    <Titulo />
    <SubTitulo />
    <Texto><![CDATA[{text_html}]]></Texto>
  </body>
  <Midias />
</article></xml>""",
        encoding="utf-8",
    )


def connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def test_build_database_discards_exact_duplicate_xml_files(tmp_path):
    input_dir = tmp_path / "extracted"
    write_xml(input_dir / "fonte_a" / "515_20260102_200.xml")
    write_xml(input_dir / "fonte_b" / "515_20260102_200.xml")

    db_path = tmp_path / "dou.sqlite"
    stats = build_database(
        input_dirs=[input_dir],
        database_path=db_path,
        progress_interval=0,
    )

    assert stats.files_read == 2
    assert stats.duplicate_files == 1
    assert stats.unique_fragments == 1
    assert stats.materias == 1

    with connect(db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM fragmento_xml").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM materia").fetchone()[0] == 1
        assert (
            connection.execute(
                "SELECT tem_estrutura_legal FROM materia"
            ).fetchone()[0]
            == 0
        )


def test_build_database_assembles_multi_fragment_matter_in_order(tmp_path):
    input_dir = tmp_path / "extracted"
    write_xml(
        input_dir / "515_20260102_200-2.xml",
        article_id="102",
        art_class="00001:00002:00003:00004:00005:00006:00007:00008:00009:00010:00011:00003",
        number_page="2",
        text_html="<p>Segundo fragmento</p>",
        identifica="",
        ementa="",
    )
    write_xml(
        input_dir / "515_20260102_200-1.xml",
        article_id="101",
        art_class="00001:00002:00003:00004:00005:00006:00007:00008:00009:00010:00011:00002",
        number_page="1",
        text_html="<p>Primeiro fragmento</p>",
    )

    db_path = tmp_path / "dou.sqlite"
    stats = build_database(
        input_dirs=[input_dir],
        database_path=db_path,
        progress_interval=0,
    )

    assert stats.unique_fragments == 2
    assert stats.materias == 1
    assert stats.multi_fragment_materias == 1

    with connect(db_path) as connection:
        matter = connection.execute("SELECT * FROM materia").fetchone()
        assert matter["qtd_fragmentos"] == 2
        assert matter["pagina_inicial"] == 1
        assert matter["pagina_final"] == 2
        assert matter["texto_plain_completo"] == "Primeiro fragmento\n\nSegundo fragmento"
        assert matter["tem_estrutura_legal"] == 0

        rows = connection.execute(
            "SELECT nome_arquivo, ordem_fragmento FROM fragmento_xml ORDER BY ordem_fragmento"
        ).fetchall()
        assert [row["nome_arquivo"] for row in rows] == [
            "515_20260102_200-1.xml",
            "515_20260102_200-2.xml",
        ]


def test_build_database_does_not_collapse_same_ids_on_different_dates(tmp_path):
    input_dir = tmp_path / "extracted"
    write_xml(
        input_dir / "515_20260102_200.xml",
        article_id="100",
        id_materia="200",
        pub_date="02/01/2026",
        text_html="<p>Texto de uma data</p>",
    )
    write_xml(
        input_dir / "515_20260103_200.xml",
        article_id="100",
        id_materia="200",
        pub_date="03/01/2026",
        text_html="<p>Texto de outra data</p>",
    )

    db_path = tmp_path / "dou.sqlite"
    stats = build_database(
        input_dirs=[input_dir],
        database_path=db_path,
        progress_interval=0,
    )

    assert stats.unique_fragments == 2
    assert stats.materias == 2

    with connect(db_path) as connection:
        dates = [
            row["data_publicacao"]
            for row in connection.execute(
                """
                SELECT e.data_publicacao
                FROM materia m
                JOIN edicao_dou e ON e.id = m.edicao_id
                ORDER BY e.data_publicacao
                """
            )
        ]
        assert dates == ["2026-01-02", "2026-01-03"]


def test_build_database_marks_matter_with_legal_structure(tmp_path):
    input_dir = tmp_path / "extracted"
    write_xml(
        input_dir / "515_20260102_200.xml",
        text_html="<p>PORTARIA TESTE</p><p>Art. 1 Fica aprovado o regulamento.</p>",
    )

    db_path = tmp_path / "dou.sqlite"
    stats = build_database(
        input_dirs=[input_dir],
        database_path=db_path,
        progress_interval=0,
    )

    assert stats.materias == 1
    assert stats.materias_com_estrutura_legal == 1

    with connect(db_path) as connection:
        assert (
            connection.execute(
                "SELECT tem_estrutura_legal FROM materia"
            ).fetchone()[0]
            == 1
        )


def test_analysis_view_keeps_only_2025_matters_with_legal_structure(tmp_path):
    input_dir = tmp_path / "extracted"
    write_xml(
        input_dir / "515_20250102_201.xml",
        article_id="101",
        id_materia="201",
        pub_date="02/01/2025",
        text_html="<p>Art. 1 Fica aprovado o regulamento.</p>",
    )
    write_xml(
        input_dir / "515_20250102_202.xml",
        article_id="102",
        id_materia="202",
        pub_date="02/01/2025",
        text_html="<p>Despacho de mero expediente.</p>",
    )
    write_xml(
        input_dir / "515_20260102_203.xml",
        article_id="103",
        id_materia="203",
        pub_date="02/01/2026",
        text_html="<p>Art. 1 Fica aprovado o regulamento.</p>",
    )

    db_path = tmp_path / "dou.sqlite"
    stats = build_database(
        input_dirs=[input_dir],
        database_path=db_path,
        progress_interval=0,
    )

    assert stats.materias == 3
    assert stats.materias_com_estrutura_legal == 2

    with connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT id_materia, data_publicacao, tem_estrutura_legal
            FROM vw_materias_analise_2025
            ORDER BY id_materia
            """
        ).fetchall()
        assert [dict(row) for row in rows] == [
            {
                "id_materia": "201",
                "data_publicacao": "2025-01-02",
                "tem_estrutura_legal": 1,
            }
        ]
        assert (
            connection.execute(
                """
                SELECT valor
                FROM vw_estatisticas_base
                WHERE metrica = 'materias_analise_2025'
                """
            ).fetchone()[0]
            == "1"
        )
