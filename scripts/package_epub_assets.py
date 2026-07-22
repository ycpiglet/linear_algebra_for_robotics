#!/usr/bin/env python3
"""Embed Korean fonts and their license in an already-rendered EPUB 3 file."""

from __future__ import annotations

import argparse
import html
import os
import posixpath
import re
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NS = "http://www.idpf.org/2007/opf"
CONTAINER_NS = "urn:oasis:names:tc:opendocument:xmlns:container"
DC_NS = "http://purl.org/dc/elements/1.1/"
VIEWER_STATE_MEMBERS = {"META-INF/calibre_bookmarks.txt"}

# The paragraph-anchor filter can prepend its empty span to Quarto's raw
# figcaption paragraph. The span is EPUB-only repair debris, not caption text.
OPTIONAL_PARAGRAPH_ANCHOR = (
    r"(?:<span\b[^>]*\sclass\s*=\s*(?:"
    r'"[^"]*\bparagraph-anchor\b[^"]*"|'
    r"'[^']*\bparagraph-anchor\b[^']*'"
    r")[^>]*(?:/>\s*|>\s*</span>\s*))?"
)
MALFORMED_MERMAID_FIGURE = re.compile(
    r"<p><figure(?:\s+class(?:=(?:\"[^\"]*\"|'[^']*'))?)?></p>\s*"
    r"<div>\s*<p>(?P<image><img\b[^>]*?/>)</p>\s*</div>\s*"
    rf"<p>{OPTIONAL_PARAGRAPH_ANCHOR}<figcaption>\s*"
    r"(?P<caption>.*?)\s*</figcaption>\s*</figure></p>",
    re.DOTALL,
)
FILENAME_TITLE = re.compile(r"<title>\s*(?:ch\d+|nav)\.xhtml\s*</title>")
FIRST_HEADING = re.compile(r"<h1\b[^>]*>(?P<heading>.*?)</h1>", re.DOTALL)
HEADER_NUMBER = re.compile(
    r"<span\b[^>]*class=(?:\"[^\"]*header-section-number[^\"]*\"|"
    r"'[^']*header-section-number[^']*')[^>]*>.*?</span>",
    re.DOTALL,
)
SOURCE_ANCHOR = re.compile(
    r"<span\b[^>]*class=(?:\"[^\"]*source-anchor[^\"]*\"|"
    r"'[^']*source-anchor[^']*')[^>]*(?:/>|>.*?</span>)",
    re.DOTALL,
)
ANNOTATION = re.compile(r"<annotation\b[^>]*>.*?</annotation>", re.DOTALL)
MARKUP = re.compile(r"<[^>]+>")

ASSETS = (
    (
        ROOT / "assets/fonts/AtlasSansKR-Regular.woff2",
        "fonts/AtlasSansKR-Regular.woff2",
        "font/woff2",
        "atlas_sans_kr_regular",
    ),
    (
        ROOT / "assets/fonts/AtlasSansKR-Bold.woff2",
        "fonts/AtlasSansKR-Bold.woff2",
        "font/woff2",
        "atlas_sans_kr_bold",
    ),
    (
        ROOT / "assets/fonts/OFL.txt",
        "fonts/OFL.txt",
        "text/plain",
        "atlas_sans_kr_license",
    ),
)


def _plain_text(markup: str) -> str:
    """Return compact visible text for an EPUB title or image description."""

    without_hidden_math = ANNOTATION.sub("", markup)
    return " ".join(html.unescape(MARKUP.sub(" ", without_hidden_math)).split())


def _repair_mermaid_figures(document: str) -> str:
    """Repair Quarto's invalid EPUB wrapper for captioned Mermaid output."""

    def replacement(match: re.Match[str]) -> str:
        caption = match.group("caption").strip()
        image = match.group("image")
        if re.search(r'\balt=(?:""|\'\')', image):
            description = html.escape(_plain_text(caption), quote=True)
            image = re.sub(
                r'\balt=(?:""|\'\')',
                f'alt="{description}"',
                image,
                count=1,
            )
        return (
            '<figure class="figure">\n'
            "<div>\n"
            f"<p>{image}</p>\n"
            "</div>\n"
            f"<figcaption>{caption}</figcaption>\n"
            "</figure>"
        )

    return MALFORMED_MERMAID_FIGURE.sub(replacement, document)


def _replace_filename_title(document: str) -> str:
    """Replace Quarto's chNNN.xhtml window title with the visible H1 title."""

    if not FILENAME_TITLE.search(document):
        return document
    heading_match = FIRST_HEADING.search(document)
    if heading_match is None:
        return document
    heading = HEADER_NUMBER.sub("", heading_match.group("heading"))
    heading = SOURCE_ANCHOR.sub("", heading)
    title = _plain_text(heading)
    if not title:
        return document
    return FILENAME_TITLE.sub(f"<title>{html.escape(title)}</title>", document, count=1)


def _repair_xhtml(payload: bytes, member: str) -> bytes:
    document = payload.decode("utf-8")
    document = _repair_mermaid_figures(document)
    document = _replace_filename_title(document)
    repaired = document.encode("utf-8")
    try:
        ET.fromstring(repaired)
    except ET.ParseError as error:
        raise ValueError(f"cannot package malformed EPUB XHTML {member}: {error}") from error
    return repaired


def _contains_mathml(payload: bytes) -> bool:
    root = ET.fromstring(payload)
    return any(element.tag.rsplit("}", 1)[-1] == "math" for element in root.iter())


def _package_member(archive: zipfile.ZipFile) -> str:
    container = ET.fromstring(archive.read("META-INF/container.xml"))
    rootfile = container.find(f".//{{{CONTAINER_NS}}}rootfile")
    if rootfile is None or not rootfile.get("full-path"):
        raise ValueError("EPUB container has no package rootfile")
    return rootfile.get("full-path", "")


def package_assets(epub: Path) -> None:
    if not epub.is_file():
        raise FileNotFoundError(epub)
    for source, _, _, _ in ASSETS:
        if not source.is_file() or source.stat().st_size == 0:
            raise FileNotFoundError(f"required EPUB asset is missing: {source}")

    with zipfile.ZipFile(epub, "r") as source_archive:
        infos = source_archive.infolist()
        if not infos or infos[0].filename != "mimetype":
            raise ValueError("mimetype must be the first EPUB member")
        package_member = _package_member(source_archive)
        package_dir = posixpath.dirname(package_member)
        package = ET.fromstring(source_archive.read(package_member))
        manifest = package.find(f"{{{PACKAGE_NS}}}manifest")
        if manifest is None:
            raise ValueError("EPUB package has no manifest")

        existing_ids = {item.get("id", "") for item in manifest}
        existing_hrefs = {item.get("href", "") for item in manifest}
        additions: list[tuple[Path, str]] = []
        for source, relative_member, media_type, item_id in ASSETS:
            member = posixpath.normpath(posixpath.join(package_dir, relative_member))
            href = posixpath.relpath(member, package_dir or ".")
            if href not in existing_hrefs:
                unique_id = item_id
                suffix = 2
                while unique_id in existing_ids:
                    unique_id = f"{item_id}_{suffix}"
                    suffix += 1
                ET.SubElement(
                    manifest,
                    f"{{{PACKAGE_NS}}}item",
                    {"id": unique_id, "href": href, "media-type": media_type},
                )
                existing_ids.add(unique_id)
                existing_hrefs.add(href)
            additions.append((source, member))

        original = {
            info.filename: source_archive.read(info.filename)
            for info in infos
        }

        for member, payload in list(original.items()):
            if member.casefold().endswith((".xhtml", ".html")):
                original[member] = _repair_xhtml(payload, member)

        for item in manifest:
            if item.tag.rsplit("}", 1)[-1] != "item":
                continue
            href = item.get("href", "")
            media_type = item.get("media-type", "")
            if media_type != "application/xhtml+xml" or not href:
                continue
            member = posixpath.normpath(
                posixpath.join(package_dir, unquote(href))
            )
            if member not in original:
                continue
            properties = item.get("properties", "").split()
            has_mathml = _contains_mathml(original[member])
            if has_mathml and "mathml" not in properties:
                properties.append("mathml")
            elif not has_mathml and "mathml" in properties:
                properties.remove("mathml")
            if properties:
                item.set("properties", " ".join(properties))
            else:
                item.attrib.pop("properties", None)

        ET.register_namespace("", PACKAGE_NS)
        ET.register_namespace("dc", DC_NS)
        package_bytes = ET.tostring(package, encoding="utf-8", xml_declaration=True)

    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{epub.name}.", suffix=".tmp", dir=epub.parent
    )
    os.close(file_descriptor)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(temporary, "w") as target_archive:
            for info in infos:
                if info.filename in VIEWER_STATE_MEMBERS:
                    continue
                payload = (
                    package_bytes
                    if info.filename == package_member
                    else original[info.filename]
                )
                target_archive.writestr(info, payload)
            for source, member in additions:
                if member in original:
                    continue
                info = zipfile.ZipInfo(member)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                target_archive.writestr(info, source.read_bytes())
        os.replace(temporary, epub)
    finally:
        temporary.unlink(missing_ok=True)

    print(f"Packaged EPUB fonts and license: {epub}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("epub", type=Path)
    arguments = parser.parse_args()
    package_assets(arguments.epub.resolve())


if __name__ == "__main__":
    main()
