"""Aplica filtro de estrutura legal a uma base SQLite ja construida."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from dou_classifier.parse.legal_structure import has_legal_structure


@dataclass(frozen=True)
class LegalFilterStats:
    total_materias: int
    materias_com_estrutura_legal: int
    materias_sem_estrutura_legal: int
    database_path: Path


def ensure_legal_filter_column(connection: sqlite3.Connection) -> None:
    columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info(materia)").fetchall()
    }
    if "tem_estrutura_legal" not in columns:
        connection.execute(
            """
            ALTER TABLE materia
            ADD COLUMN tem_estrutura_legal INTEGER NOT NULL DEFAULT 0
            CHECK (tem_estrutura_legal IN (0, 1))
            """
        )

    indexes = {
        row[1]
        for row in connection.execute("PRAGMA index_list(materia)").fetchall()
    }
    if "idx_materia_tem_estrutura_legal" not in indexes:
        connection.execute(
            """
            CREATE INDEX idx_materia_tem_estrutura_legal
            ON materia(tem_estrutura_legal)
            """
        )

    connection.executescript(
        """
        DROP VIEW IF EXISTS vw_materias;
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

        DROP VIEW IF EXISTS vw_estatisticas_base;
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
        SELECT 'fragmentos_xml', CAST(COUNT(*) AS TEXT) FROM fragmento_xml
        UNION ALL
        SELECT 'orgaos', CAST(COUNT(*) AS TEXT) FROM orgao
        UNION ALL
        SELECT 'tipos_ato', CAST(COUNT(*) AS TEXT) FROM tipo_ato
        UNION ALL
        SELECT 'midias', CAST(COUNT(*) AS TEXT) FROM fragmento_midia;
        """
    )


def apply_legal_structure_filter(
    database_path: Path,
    *,
    batch_size: int = 1000,
    progress_interval: int = 10000,
) -> LegalFilterStats:
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        ensure_legal_filter_column(connection)

        total = int(connection.execute("SELECT COUNT(*) FROM materia").fetchone()[0])
        cursor = connection.execute(
            "SELECT id, texto_plain_completo FROM materia ORDER BY id"
        )
        processed = 0
        matched = 0

        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break

            updates = []
            for row in rows:
                has_structure = has_legal_structure(row["texto_plain_completo"])
                matched += int(has_structure)
                updates.append((int(has_structure), row["id"]))

            connection.executemany(
                """
                UPDATE materia
                SET tem_estrutura_legal = ?
                WHERE id = ?
                """,
                updates,
            )
            processed += len(rows)

            if progress_interval > 0 and processed % progress_interval == 0:
                print(f"Materias processadas: {processed}/{total}")
                connection.commit()

        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        connection.executemany(
            "INSERT OR REPLACE INTO base_info (nome, valor) VALUES (?, ?)",
            [
                ("schema_version", "2"),
                ("legal_structure_filter_applied_at", now),
                ("legal_structure_filter_total_materias", str(total)),
                ("legal_structure_filter_matches", str(matched)),
                ("legal_structure_filter_non_matches", str(total - matched)),
            ],
        )
        connection.commit()

        return LegalFilterStats(
            total_materias=total,
            materias_com_estrutura_legal=matched,
            materias_sem_estrutura_legal=total - matched,
            database_path=database_path,
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Aplica o filtro de estrutura legal a base SQLite do DOU."
    )
    parser.add_argument(
        "--database-path",
        type=Path,
        default=Path("data/database/dou.sqlite"),
        help="Caminho da base SQLite a ser atualizada.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Quantidade de materias atualizadas por lote.",
    )
    parser.add_argument(
        "--progress-interval",
        type=int,
        default=10000,
        help="Intervalo de progresso em materias processadas. Use 0 para silenciar.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.database_path.exists():
        print(f"Base SQLite nao encontrada: {args.database_path}", file=sys.stderr)
        return 2

    try:
        stats = apply_legal_structure_filter(
            args.database_path,
            batch_size=args.batch_size,
            progress_interval=args.progress_interval,
        )
    except Exception as exc:  # noqa: BLE001 - CLI transforma falha em mensagem clara.
        print(f"Falha ao aplicar filtro: {exc}", file=sys.stderr)
        return 1

    print("Resumo do filtro de estrutura legal:")
    print(f"  materias: {stats.total_materias}")
    print(
        "  com_estrutura_legal: "
        f"{stats.materias_com_estrutura_legal}"
    )
    print(
        "  sem_estrutura_legal: "
        f"{stats.materias_sem_estrutura_legal}"
    )
    print(f"Base SQLite: {stats.database_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
