"""Parser dos XMLs de materias do DOU."""

from __future__ import annotations

import hashlib
import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path


TEXT_SEPARATOR = "\x1f"


@dataclass(frozen=True)
class MediaItem:
    order: int
    content: str
    attributes: dict[str, str]


@dataclass(frozen=True)
class DouFragment:
    sha256_xml: str
    file_name: str
    article_id: str
    id_materia: str
    id_oficio: str
    name: str
    pub_name: str
    pub_date: date
    edition_number: str
    art_type: str
    art_category: str
    art_class: str
    art_size: int | None
    art_notes: str
    number_page: int | None
    pdf_page: str
    highlight_type: str
    highlight_priority: str
    highlight: str
    highlight_image: str
    highlight_image_name: str
    identifica: str
    data_texto: str
    ementa: str
    titulo: str
    subtitulo: str
    texto_html: str
    texto_plain: str
    midias: tuple[MediaItem, ...]

    @property
    def pub_date_iso(self) -> str:
        return self.pub_date.isoformat()

    @property
    def natural_key_values(self) -> tuple[str, str, str, str, str, str]:
        return (
            self.pub_date_iso,
            self.pub_name,
            self.edition_number,
            self.id_materia,
            self.id_oficio,
            self.name,
        )

    @property
    def natural_key_hash(self) -> str:
        return sha256_text(TEXT_SEPARATOR.join(self.natural_key_values))

    @property
    def art_class_prefix(self) -> str:
        parts = self.art_class.split(":")
        if len(parts) <= 1:
            return self.art_class
        return ":".join(parts[:-1])


class HtmlTextExtractor(HTMLParser):
    """Conversor simples de HTML editorial para texto plano."""

    block_tags = {
        "address",
        "article",
        "blockquote",
        "br",
        "caption",
        "div",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "li",
        "p",
        "section",
        "table",
        "tr",
    }
    cell_tags = {"td", "th"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in self.block_tags:
            self._newline()
        elif tag in self.cell_tags:
            self._space()

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.block_tags:
            self._newline()
        elif tag in self.cell_tags:
            self.parts.append(" | ")

    def handle_data(self, data: str) -> None:
        if data:
            self.parts.append(data)

    def get_text(self) -> str:
        text = "".join(self.parts)
        lines = []
        for line in text.splitlines():
            normalized = re.sub(r"[ \t\r\f\v]+", " ", line).strip()
            if normalized:
                lines.append(normalized)
        return "\n".join(lines)

    def _newline(self) -> None:
        if self.parts and not self.parts[-1].endswith("\n"):
            self.parts.append("\n")

    def _space(self) -> None:
        if self.parts and not self.parts[-1].endswith((" ", "\n")):
            self.parts.append(" ")


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def html_to_plain_text(value: str) -> str:
    parser = HtmlTextExtractor()
    parser.feed(value)
    parser.close()
    return html.unescape(parser.get_text())


def normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    return value.strip()


def normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def parse_dou_date(value: str) -> date:
    return datetime.strptime(value, "%d/%m/%Y").date()


def parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        match = re.search(r"\d+", value)
        if match is None:
            return None
        return int(match.group(0))


def normalize_pub_name(pub_name: str) -> str:
    value = pub_name.upper().strip()
    match = re.match(r"DO([123])", value)
    if match:
        return f"S{match.group(1)}"
    return value


def split_category(category: str) -> list[str]:
    return [normalize_spaces(part) for part in category.split("/") if part.strip()]


def article_class_last_number(art_class: str) -> int | None:
    if not art_class:
        return None
    last = art_class.split(":")[-1]
    return parse_int(last)


def filename_suffix_number(file_name: str) -> int | None:
    stem = Path(file_name).stem
    match = re.search(r"-(\d+)$", stem)
    if match is None:
        return None
    return int(match.group(1))


def fragment_sort_key(fragment: DouFragment) -> tuple[int, int, int, int]:
    art_class_number = article_class_last_number(fragment.art_class)
    suffix_number = filename_suffix_number(fragment.file_name)
    article_id_number = parse_int(fragment.article_id)
    return (
        art_class_number if art_class_number is not None else 10**9,
        suffix_number if suffix_number is not None else 10**9,
        fragment.number_page if fragment.number_page is not None else 10**9,
        article_id_number if article_id_number is not None else 10**9,
    )


def fragment_sort_key_from_values(
    *,
    art_class: str,
    file_name: str,
    number_page: int | None,
    article_id: str,
) -> tuple[int, int, int, int]:
    art_class_number = article_class_last_number(art_class)
    suffix_number = filename_suffix_number(file_name)
    article_id_number = parse_int(article_id)
    return (
        art_class_number if art_class_number is not None else 10**9,
        suffix_number if suffix_number is not None else 10**9,
        number_page if number_page is not None else 10**9,
        article_id_number if article_id_number is not None else 10**9,
    )


def parse_fragment(path: Path, content: bytes, sha256_xml: str | None = None) -> DouFragment:
    root = ET.fromstring(content)
    article = root.find("article")
    if article is None:
        raise ValueError(f"XML sem elemento article: {path}")

    attrs = article.attrib
    body_values = {
        "Identifica": "",
        "Data": "",
        "Ementa": "",
        "Titulo": "",
        "SubTitulo": "",
        "Texto": "",
    }
    body = article.find("body")
    if body is not None:
        for child in body:
            if child.tag in body_values:
                body_values[child.tag] = normalize_text("".join(child.itertext()))

    media_items: list[MediaItem] = []
    midias = article.find("Midias")
    if midias is not None:
        for index, media in enumerate(midias.findall("Midia"), start=1):
            content_text = normalize_text("".join(media.itertext()))
            attributes = {key: value for key, value in media.attrib.items()}
            if content_text or attributes:
                media_items.append(
                    MediaItem(order=index, content=content_text, attributes=attributes)
                )

    texto_html = body_values["Texto"]
    return DouFragment(
        sha256_xml=sha256_xml or sha256_bytes(content),
        file_name=path.name,
        article_id=attrs.get("id", ""),
        id_materia=attrs.get("idMateria", ""),
        id_oficio=attrs.get("idOficio", ""),
        name=attrs.get("name", ""),
        pub_name=attrs.get("pubName", ""),
        pub_date=parse_dou_date(attrs.get("pubDate", "")),
        edition_number=attrs.get("editionNumber", ""),
        art_type=normalize_spaces(attrs.get("artType", "")),
        art_category=attrs.get("artCategory", ""),
        art_class=attrs.get("artClass", ""),
        art_size=parse_int(attrs.get("artSize")),
        art_notes=attrs.get("artNotes", ""),
        number_page=parse_int(attrs.get("numberPage")),
        pdf_page=attrs.get("pdfPage", ""),
        highlight_type=attrs.get("highlightType", ""),
        highlight_priority=attrs.get("highlightPriority", ""),
        highlight=attrs.get("highlight", ""),
        highlight_image=attrs.get("highlightimage", ""),
        highlight_image_name=attrs.get("highlightimagename", ""),
        identifica=body_values["Identifica"],
        data_texto=body_values["Data"],
        ementa=body_values["Ementa"],
        titulo=body_values["Titulo"],
        subtitulo=body_values["SubTitulo"],
        texto_html=texto_html,
        texto_plain=html_to_plain_text(texto_html),
        midias=tuple(media_items),
    )

