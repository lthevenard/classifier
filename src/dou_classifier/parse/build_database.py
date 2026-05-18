"""CLI para construir a base SQLite deduplicada de publicacoes do DOU."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from dou_classifier.parse.dou_xml import (
    DouFragment,
    fragment_sort_key,
    fragment_sort_key_from_values,
    normalize_pub_name,
    normalize_spaces,
    parse_fragment,
    sha256_bytes,
    sha256_text,
    split_category,
)
from dou_classifier.parse.legal_structure import has_legal_structure


SCHEMA_PATH = Path(__file__).with_name("schema.sql")


@dataclass(frozen=True)
class BuildStats:
    files_read: int
    duplicate_files: int
    unique_fragments: int
    materias: int
    multi_fragment_materias: int
    edicoes: int
    orgaos: int
    tipos_ato: int
    midias: int
    materias_com_estrutura_legal: int
    database_path: Path


@dataclass
class MatterState:
    id: int
    edicao_id: int
    tipo_ato_id: int
    orgao_id: int
    art_type: str
    art_category: str
    fragment_count: int = 1


def iter_xml_paths(input_dirs: list[Path]) -> list[Path]:
    paths: list[Path] = []
    for input_dir in input_dirs:
        paths.extend(
            path
            for path in input_dir.rglob("*")
            if path.is_file() and path.suffix.lower() == ".xml"
        )
    return sorted(paths)


def load_schema() -> str:
    return SCHEMA_PATH.read_text(encoding="utf-8")


def first_non_empty(values: list[str]) -> str:
    for value in values:
        if value:
            return value
    return ""


def minmax_int(values: list[int | None]) -> tuple[int | None, int | None]:
    present = [value for value in values if value is not None]
    if not present:
        return None, None
    return min(present), max(present)


class SQLiteBaseBuilder:
    def __init__(
        self,
        *,
        database_path: Path,
        input_dirs: list[Path],
        progress_interval: int = 5000,
    ) -> None:
        self.database_path = database_path
        self.input_dirs = input_dirs
        self.progress_interval = progress_interval
        self.connection: sqlite3.Connection | None = None
        self.seen_hashes: set[str] = set()
        self.edicoes: dict[tuple[str, str, str], int] = {}
        self.tipos_ato: dict[str, int] = {}
        self.orgaos: dict[str, int] = {}
        self.materias: dict[str, MatterState] = {}
        self.multi_fragment_materias: set[int] = set()
        self.stats: Counter[str] = Counter()

    def build(self) -> BuildStats:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.database_path) as connection:
            self.connection = connection
            self._configure_connection()
            self._create_schema()
            paths = iter_xml_paths(self.input_dirs)
            self.stats["files_discovered"] = len(paths)

            for index, path in enumerate(paths, start=1):
                self._process_file(path)
                if self.progress_interval > 0 and index % self.progress_interval == 0:
                    print(
                        f"Processados {index}/{len(paths)} XMLs; "
                        f"unicos={self.stats['unique_fragments']}; "
                        f"duplicados={self.stats['duplicate_files']}"
                    )
                    connection.commit()

            self._finalize_multi_fragment_matters()
            self._write_base_info()
            connection.commit()
            self._vacuum()
            stats = self._collect_stats()
            self.connection = None
            return stats

    def _configure_connection(self) -> None:
        conn = self._conn
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA temp_store = MEMORY")

    def _create_schema(self) -> None:
        self._conn.executescript(load_schema())

    def _process_file(self, path: Path) -> None:
        self.stats["files_read"] += 1
        content = path.read_bytes()
        xml_hash = sha256_bytes(content)
        if xml_hash in self.seen_hashes:
            self.stats["duplicate_files"] += 1
            return

        self.seen_hashes.add(xml_hash)
        fragment = parse_fragment(path, content, xml_hash)
        self._insert_fragment(fragment)
        self.stats["unique_fragments"] += 1

    def _insert_fragment(self, fragment: DouFragment) -> None:
        matter = self._get_or_create_matter(fragment)
        if matter.fragment_count > 1:
            self.multi_fragment_materias.add(matter.id)

        initial_order = 1 if matter.fragment_count == 1 else None
        cursor = self._conn.execute(
            """
            INSERT INTO fragmento_xml (
                materia_id, sha256_xml, nome_arquivo, article_id, id_materia,
                id_oficio, ordem_fragmento, numero_pagina, pdf_page,
                art_class_raw, art_size, art_notes, highlight_type,
                highlight_priority, highlight, highlight_image,
                highlight_image_name, identifica, data_texto, ementa,
                titulo, subtitulo, texto_html, texto_plain
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                matter.id,
                fragment.sha256_xml,
                fragment.file_name,
                fragment.article_id,
                fragment.id_materia,
                fragment.id_oficio,
                initial_order,
                fragment.number_page,
                fragment.pdf_page,
                fragment.art_class,
                fragment.art_size,
                fragment.art_notes,
                fragment.highlight_type,
                fragment.highlight_priority,
                fragment.highlight,
                fragment.highlight_image,
                fragment.highlight_image_name,
                fragment.identifica,
                fragment.data_texto,
                fragment.ementa,
                fragment.titulo,
                fragment.subtitulo,
                fragment.texto_html,
                fragment.texto_plain,
            ),
        )
        fragment_id = int(cursor.lastrowid)
        if fragment.midias:
            self._insert_media(fragment_id, fragment)

    def _insert_media(self, fragment_id: int, fragment: DouFragment) -> None:
        self._conn.executemany(
            """
            INSERT INTO fragmento_midia (
                fragmento_xml_id, ordem, conteudo, atributos_json
            )
            VALUES (?, ?, ?, ?)
            """,
            [
                (
                    fragment_id,
                    item.order,
                    item.content,
                    json.dumps(item.attributes, ensure_ascii=False, sort_keys=True),
                )
                for item in fragment.midias
            ],
        )
        self.stats["midias"] += len(fragment.midias)

    def _get_or_create_matter(self, fragment: DouFragment) -> MatterState:
        key = fragment.natural_key_hash
        existing = self.materias.get(key)
        if existing is not None:
            self._validate_matter_invariants(existing, fragment)
            existing.fragment_count += 1
            return existing

        edicao_id = self._get_or_create_edicao(fragment)
        tipo_ato_id = self._get_or_create_tipo_ato(fragment.art_type)
        orgao_id = self._get_or_create_orgao(fragment.art_category)
        page_start, page_end = minmax_int([fragment.number_page])
        text_sha256 = sha256_text(fragment.texto_plain)
        tem_estrutura_legal = int(has_legal_structure(fragment.texto_plain))

        cursor = self._conn.execute(
            """
            INSERT INTO materia (
                edicao_id, tipo_ato_id, orgao_id, chave_natural, id_materia,
                id_oficio, nome_interno, art_category_raw, art_class_prefix,
                pagina_inicial, pagina_final, qtd_fragmentos, identifica,
                data_texto, ementa, titulo, subtitulo, texto_html_completo,
                texto_plain_completo, texto_sha256, tem_estrutura_legal
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                edicao_id,
                tipo_ato_id,
                orgao_id,
                key,
                fragment.id_materia,
                fragment.id_oficio,
                fragment.name,
                fragment.art_category,
                fragment.art_class_prefix,
                page_start,
                page_end,
                1,
                fragment.identifica,
                fragment.data_texto,
                fragment.ementa,
                fragment.titulo,
                fragment.subtitulo,
                fragment.texto_html,
                fragment.texto_plain,
                text_sha256,
                tem_estrutura_legal,
            ),
        )
        state = MatterState(
            id=int(cursor.lastrowid),
            edicao_id=edicao_id,
            tipo_ato_id=tipo_ato_id,
            orgao_id=orgao_id,
            art_type=fragment.art_type,
            art_category=fragment.art_category,
        )
        self.materias[key] = state
        return state

    def _validate_matter_invariants(
        self, matter: MatterState, fragment: DouFragment
    ) -> None:
        tipo_ato_id = self._get_or_create_tipo_ato(fragment.art_type)
        orgao_id = self._get_or_create_orgao(fragment.art_category)
        edicao_id = self._get_or_create_edicao(fragment)
        if (
            tipo_ato_id != matter.tipo_ato_id
            or orgao_id != matter.orgao_id
            or edicao_id != matter.edicao_id
        ):
            raise ValueError(
                "Fragmentos da mesma materia com metadados divergentes: "
                f"idMateria={fragment.id_materia}, idOficio={fragment.id_oficio}, "
                f"name={fragment.name}"
            )

    def _get_or_create_edicao(self, fragment: DouFragment) -> int:
        key = (fragment.pub_date_iso, fragment.pub_name, fragment.edition_number)
        if key in self.edicoes:
            return self.edicoes[key]
        cursor = self._conn.execute(
            """
            INSERT INTO edicao_dou (
                data_publicacao, pub_name, numero_edicao, secao_normalizada
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                fragment.pub_date_iso,
                fragment.pub_name,
                fragment.edition_number,
                normalize_pub_name(fragment.pub_name),
            ),
        )
        item_id = int(cursor.lastrowid)
        self.edicoes[key] = item_id
        return item_id

    def _get_or_create_tipo_ato(self, value: str) -> int:
        key = normalize_spaces(value) or "(sem tipo)"
        if key in self.tipos_ato:
            return self.tipos_ato[key]
        cursor = self._conn.execute(
            "INSERT INTO tipo_ato (nome) VALUES (?)",
            (key,),
        )
        item_id = int(cursor.lastrowid)
        self.tipos_ato[key] = item_id
        return item_id

    def _get_or_create_orgao(self, category: str) -> int:
        parts = split_category(category)
        if not parts:
            parts = ["(sem orgao)"]

        parent_id: int | None = None
        raw_parts: list[str] = []
        normalized_parts: list[str] = []
        current_id: int | None = None

        for level, part in enumerate(parts, start=1):
            raw_parts.append(part)
            normalized_parts.append(normalize_spaces(part))
            normalized_path = " / ".join(normalized_parts)
            existing_id = self.orgaos.get(normalized_path)
            if existing_id is not None:
                current_id = existing_id
                parent_id = existing_id
                continue

            cursor = self._conn.execute(
                """
                INSERT INTO orgao (
                    parent_id, nome, caminho_normalizado, caminho_raw, nivel
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    parent_id,
                    normalize_spaces(part),
                    normalized_path,
                    "/".join(raw_parts),
                    level,
                ),
            )
            current_id = int(cursor.lastrowid)
            self.orgaos[normalized_path] = current_id
            parent_id = current_id

        if current_id is None:
            raise ValueError(f"Categoria sem orgao nao resolvida: {category}")
        return current_id

    def _finalize_multi_fragment_matters(self) -> None:
        if not self.multi_fragment_materias:
            return

        print(f"Montando {len(self.multi_fragment_materias)} materias com multiplos fragmentos")
        for index, matter_id in enumerate(sorted(self.multi_fragment_materias), start=1):
            rows = self._conn.execute(
                """
                SELECT
                    id, nome_arquivo, article_id, numero_pagina, art_class_raw,
                    texto_html, texto_plain, identifica, data_texto, ementa,
                    titulo, subtitulo
                FROM fragmento_xml
                WHERE materia_id = ?
                """,
                (matter_id,),
            ).fetchall()

            rows.sort(
                key=lambda row: fragment_sort_key_from_values(
                    art_class=row["art_class_raw"],
                    file_name=row["nome_arquivo"],
                    number_page=row["numero_pagina"],
                    article_id=row["article_id"],
                )
            )

            self._conn.executemany(
                "UPDATE fragmento_xml SET ordem_fragmento = ? WHERE id = ?",
                [(order, row["id"]) for order, row in enumerate(rows, start=1)],
            )

            html_parts = [row["texto_html"] for row in rows if row["texto_html"]]
            plain_parts = [row["texto_plain"] for row in rows if row["texto_plain"]]
            texto_html = "\n".join(html_parts)
            texto_plain = "\n\n".join(plain_parts)
            page_start, page_end = minmax_int([row["numero_pagina"] for row in rows])

            self._conn.execute(
                """
                UPDATE materia
                SET
                    pagina_inicial = ?,
                    pagina_final = ?,
                    qtd_fragmentos = ?,
                    identifica = ?,
                    data_texto = ?,
                    ementa = ?,
                    titulo = ?,
                    subtitulo = ?,
                    texto_html_completo = ?,
                    texto_plain_completo = ?,
                    texto_sha256 = ?,
                    tem_estrutura_legal = ?
                WHERE id = ?
                """,
                (
                    page_start,
                    page_end,
                    len(rows),
                    first_non_empty([row["identifica"] for row in rows]),
                    first_non_empty([row["data_texto"] for row in rows]),
                    first_non_empty([row["ementa"] for row in rows]),
                    first_non_empty([row["titulo"] for row in rows]),
                    first_non_empty([row["subtitulo"] for row in rows]),
                    texto_html,
                    texto_plain,
                    sha256_text(texto_plain),
                    int(has_legal_structure(texto_plain)),
                    matter_id,
                ),
            )

            if self.progress_interval > 0 and index % self.progress_interval == 0:
                print(
                    f"Materias multi-fragmento finalizadas: "
                    f"{index}/{len(self.multi_fragment_materias)}"
                )
                self._conn.commit()

    def _write_base_info(self) -> None:
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        info = {
            "schema_version": "3",
            "generated_at": now,
            "input_dirs": json.dumps(
                [str(path) for path in self.input_dirs],
                ensure_ascii=False,
            ),
            "files_discovered": str(self.stats["files_discovered"]),
            "files_read": str(self.stats["files_read"]),
            "duplicate_files": str(self.stats["duplicate_files"]),
            "unique_fragments": str(self.stats["unique_fragments"]),
            "multi_fragment_materias": str(len(self.multi_fragment_materias)),
            "legal_structure_filter_matches": str(
                self._count_legal_structure_matches()
            ),
            "analysis_view_2025_total_materias": str(
                self._count_analysis_view_2025()
            ),
        }
        self._conn.executemany(
            "INSERT OR REPLACE INTO base_info (nome, valor) VALUES (?, ?)",
            sorted(info.items()),
        )

    def _collect_stats(self) -> BuildStats:
        def count_table(table: str) -> int:
            return int(self._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])

        return BuildStats(
            files_read=self.stats["files_read"],
            duplicate_files=self.stats["duplicate_files"],
            unique_fragments=count_table("fragmento_xml"),
            materias=count_table("materia"),
            multi_fragment_materias=len(self.multi_fragment_materias),
            edicoes=count_table("edicao_dou"),
            orgaos=count_table("orgao"),
            tipos_ato=count_table("tipo_ato"),
            midias=count_table("fragmento_midia"),
            materias_com_estrutura_legal=self._count_legal_structure_matches(),
            database_path=self.database_path,
        )

    def _count_legal_structure_matches(self) -> int:
        return int(
            self._conn.execute(
                """
                SELECT COUNT(*)
                FROM materia
                WHERE tem_estrutura_legal = 1
                """
            ).fetchone()[0]
        )

    def _count_analysis_view_2025(self) -> int:
        return int(
            self._conn.execute(
                "SELECT COUNT(*) FROM vw_materias_analise_2025"
            ).fetchone()[0]
        )

    def _vacuum(self) -> None:
        self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        self._conn.execute("VACUUM")

    @property
    def _conn(self) -> sqlite3.Connection:
        if self.connection is None:
            raise RuntimeError("Conexao SQLite nao inicializada")
        self.connection.row_factory = sqlite3.Row
        return self.connection


def build_database(
    *,
    input_dirs: list[Path],
    database_path: Path,
    force: bool = False,
    progress_interval: int = 5000,
) -> BuildStats:
    if database_path.exists():
        if not force:
            raise FileExistsError(
                f"Base ja existe: {database_path}. Use --force para recriar."
            )
        database_path.unlink()
        wal_path = database_path.with_name(f"{database_path.name}-wal")
        shm_path = database_path.with_name(f"{database_path.name}-shm")
        for extra_path in (wal_path, shm_path):
            if extra_path.exists():
                extra_path.unlink()

    builder = SQLiteBaseBuilder(
        database_path=database_path,
        input_dirs=input_dirs,
        progress_interval=progress_interval,
    )
    return builder.build()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Construi a base SQLite deduplicada de publicacoes do DOU."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        action="append",
        default=None,
        help=(
            "Diretorio com XMLs extraidos. Pode ser informado mais de uma vez. "
            "Padrao: data/extracted."
        ),
    )
    parser.add_argument(
        "--database-path",
        type=Path,
        default=Path("data/database/dou.sqlite"),
        help="Caminho da base SQLite a ser criada.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Remove e recria a base se ela ja existir.",
    )
    parser.add_argument(
        "--progress-interval",
        type=int,
        default=5000,
        help="Intervalo de progresso em arquivos processados. Use 0 para silenciar.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    input_dirs = args.input_dir or [Path("data/extracted")]

    missing = [path for path in input_dirs if not path.exists()]
    if missing:
        print(
            "Diretorios de entrada inexistentes: "
            + ", ".join(str(path) for path in missing),
            file=sys.stderr,
        )
        return 2

    try:
        stats = build_database(
            input_dirs=input_dirs,
            database_path=args.database_path,
            force=args.force,
            progress_interval=args.progress_interval,
        )
    except Exception as exc:  # noqa: BLE001 - CLI transforma falha em mensagem clara.
        print(f"Falha ao construir a base: {exc}", file=sys.stderr)
        return 1

    print("Resumo da base:")
    print(f"  arquivos_lidos: {stats.files_read}")
    print(f"  duplicatas_descartadas: {stats.duplicate_files}")
    print(f"  fragmentos_unicos: {stats.unique_fragments}")
    print(f"  materias: {stats.materias}")
    print(f"  materias_multifragmento: {stats.multi_fragment_materias}")
    print(f"  edicoes: {stats.edicoes}")
    print(f"  orgaos: {stats.orgaos}")
    print(f"  tipos_ato: {stats.tipos_ato}")
    print(f"  midias: {stats.midias}")
    print(f"  materias_com_estrutura_legal: {stats.materias_com_estrutura_legal}")
    print(f"Base SQLite: {stats.database_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
