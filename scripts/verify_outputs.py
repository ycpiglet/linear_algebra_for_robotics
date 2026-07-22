#!/usr/bin/env python3
"""Verify rendered HTML, EPUB 3 packages, and PDF navigation contracts."""

from __future__ import annotations

import argparse
import json
import posixpath
import sys
import xml.etree.ElementTree as ET
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from pypdf import PdfReader

EXTERNAL_SCHEMES = {"http", "https", "mailto", "tel", "data", "javascript"}
FLAGSHIP_TITLES = ("자코비안", "최대우도추정", "칼만 필터")
FLAGSHIP_HTML = (
    "content/concepts/robotics/jacobian.html",
    "content/concepts/statistics/maximum-likelihood-estimation.html",
    "content/concepts/estimation/kalman-filter.html",
)
DOCUMENT_ID_PREFIX = "urn:robotics-math-atlas:document:v1:"
DOCUMENT_ID_FORBIDDEN = (
    "linear_algebra_for_robotics",
    "robotics-math-atlas/",
    "github.io",
    "/review/",
    "/preview/",
)
REFERENCE_TITLES = (
    "자코비안 장의 참고문헌",
    "최대우도추정 장의 참고문헌",
    "칼만 필터 장의 참고문헌",
)


class DocumentParser(HTMLParser):
    """Collect navigational links and fragment targets from HTML/XHTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.identifiers: set[str] = set()
        self.document_identifiers: list[str] = []
        self.has_main = False
        self._in_title = False
        self.title_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "main":
            self.has_main = True
        elif tag == "title":
            self._in_title = True
        identifier = values.get("id") or values.get("name")
        if identifier:
            self.identifiers.add(identifier)
        if tag == "meta" and (values.get("name") or "").casefold() == "dc.identifier":
            self.document_identifiers.append(values.get("content") or "")
        if tag in {"a", "area"} and values.get("href") is not None:
            self.links.append(values["href"] or "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)

    @property
    def is_redirect(self) -> bool:
        return "".join(self.title_parts).strip() == "Redirect" and not self.has_main


def parse_document(text: str) -> DocumentParser:
    parser = DocumentParser()
    parser.feed(text)
    parser.close()
    return parser


def is_external(href: str) -> bool:
    parsed = urlsplit(href)
    return parsed.scheme.casefold() in EXTERNAL_SCHEMES or href.startswith("//")


def _display(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def verify_html_tree(root: Path) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    html_files = sorted(root.rglob("*.html"))
    parsed_cache: dict[Path, DocumentParser] = {}

    def parsed(path: Path) -> DocumentParser:
        if path not in parsed_cache:
            parsed_cache[path] = parse_document(path.read_text(encoding="utf-8"))
        return parsed_cache[path]

    for source in html_files:
        source_label = _display(source, root)
        for href in parsed(source).links:
            if not href or href == "#" or is_external(href):
                continue
            split = urlsplit(href)
            path_text = unquote(split.path)
            fragment = unquote(split.fragment)
            if path_text.casefold().endswith((".qmd", ".md")):
                errors.append(f"{source_label}: source-document link survived render: {href}")
                continue

            if path_text.startswith("/"):
                target = root / path_text.lstrip("/")
            elif path_text:
                target = source.parent / path_text
            else:
                target = source
            target = target.resolve()
            if target.is_dir():
                target = target / "index.html"
            if not target.exists():
                errors.append(f"{source_label}: missing target for {href}")
                continue
            try:
                target.relative_to(root)
            except ValueError:
                errors.append(f"{source_label}: local link escapes output tree: {href}")
                continue
            if (
                fragment
                and target.suffix.casefold() in {".html", ".xhtml"}
                and fragment not in parsed(target).identifiers
            ):
                target_label = _display(target, root)
                errors.append(f"{source_label}: missing fragment #{fragment} in {target_label}")

    if not html_files:
        errors.append(f"{root}: no HTML files found")

    if (root / "atlas.html").is_file():
        document_id_sources: dict[str, str] = {}
        for source in html_files:
            source_label = _display(source, root)
            document = parsed(source)
            if document.is_redirect:
                continue
            document_ids = document.document_identifiers
            if len(document_ids) != 1:
                errors.append(
                    f"{source_label}: expected exactly one DC.identifier, "
                    f"found {len(document_ids)}"
                )
                continue
            document_id = document_ids[0]
            if not document_id.startswith(DOCUMENT_ID_PREFIX):
                errors.append(f"{source_label}: invalid DC.identifier: {document_id}")
                continue
            lowered = document_id.casefold()
            forbidden = next(
                (value for value in DOCUMENT_ID_FORBIDDEN if value.casefold() in lowered),
                None,
            )
            if forbidden is not None:
                errors.append(
                    f"{source_label}: URL-dependent DC.identifier contains {forbidden!r}"
                )
            previous = document_id_sources.get(document_id)
            if previous is not None:
                errors.append(
                    f"{source_label}: duplicate DC.identifier also used by {previous}"
                )
            else:
                document_id_sources[document_id] = source_label

        forbidden = (
            root / "AUTHORING_MANUAL.html",
            root / "platform/templates",
            root / "platform/generated/glossary.html",
        )
        for path in forbidden:
            if path.exists():
                errors.append(f"{_display(path, root)}: internal authoring source was published")
        for relative in FLAGSHIP_HTML:
            path = root / relative
            if not path.is_file():
                errors.append(f"{relative}: flagship chapter is missing")
                continue
            source = path.read_text(encoding="utf-8")
            if "page-glossary--static" not in source:
                errors.append(f"{relative}: build-time static page glossary is missing")
        for relative in (
            "assets/js/atlas.js",
            "assets/fonts/AtlasSansKR-Regular.woff2",
            "assets/fonts/AtlasSansKR-Bold.woff2",
            "assets/fonts/OFL.txt",
        ):
            if not (root / relative).is_file():
                errors.append(f"{relative}: required reader asset is missing")

    # Runtime atlas navigation comes from JSON and is invisible to a normal
    # HTML crawl. Validate every local manifest URL for outputs that contain
    # the atlas entry page. The focused proof companion intentionally omits it.
    manifest = root / "platform/generated/concept-manifest.json"
    if (root / "atlas.html").is_file() and manifest.is_file():
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        manifest_urls: set[str] = set()

        def collect_urls(value: object) -> None:
            if isinstance(value, dict):
                for key, item in value.items():
                    if key == "url" and isinstance(item, str):
                        manifest_urls.add(item)
                    else:
                        collect_urls(item)
            elif isinstance(value, list):
                for item in value:
                    collect_urls(item)

        collect_urls(payload)
        for href in sorted(manifest_urls):
            if not href or href == "#" or is_external(href):
                continue
            split = urlsplit(href)
            path_text = unquote(split.path)
            fragment = unquote(split.fragment)
            target = (
                root / path_text.lstrip("/")
                if path_text.startswith("/")
                else root / path_text
            )
            target = target.resolve()
            if target.is_dir():
                target = target / "index.html"
            if not target.exists():
                errors.append(
                    "platform/generated/concept-manifest.json: "
                    f"missing target for {href}"
                )
                continue
            try:
                target.relative_to(root)
            except ValueError:
                errors.append(
                    "platform/generated/concept-manifest.json: "
                    f"local URL escapes output tree: {href}"
                )
                continue
            if (
                fragment
                and target.suffix.casefold() in {".html", ".xhtml"}
                and fragment not in parsed(target).identifiers
            ):
                target_label = _display(target, root)
                errors.append(
                    "platform/generated/concept-manifest.json: "
                    f"missing fragment #{fragment} in {target_label}"
                )
    return errors


def verify_epub(path: Path) -> list[str]:
    errors: list[str] = []
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        members = set(archive.namelist())
        if not infos or infos[0].filename != "mimetype":
            errors.append(f"{path}: first EPUB member must be mimetype")
        elif infos[0].compress_type != zipfile.ZIP_STORED:
            errors.append(f"{path}: mimetype member must be stored without compression")
        if "mimetype" not in members:
            errors.append(f"{path}: missing mimetype member")
        elif archive.read("mimetype") != b"application/epub+zip":
            errors.append(f"{path}: invalid EPUB mimetype payload")

        container_member = "META-INF/container.xml"
        package_member = ""
        if container_member not in members:
            errors.append(f"{path}: missing {container_member}")
        else:
            try:
                container = ET.fromstring(archive.read(container_member))
                rootfile = next(
                    (
                        element
                        for element in container.iter()
                        if element.tag.rsplit("}", 1)[-1] == "rootfile"
                    ),
                    None,
                )
                package_member = rootfile.get("full-path", "") if rootfile is not None else ""
            except ET.ParseError as error:
                errors.append(f"{container_member}: invalid XML: {error}")
            if not package_member:
                errors.append(f"{container_member}: no package rootfile declared")
            elif package_member not in members:
                errors.append(f"{container_member}: missing package document {package_member}")

        documents = sorted(
            member for member in members if member.casefold().endswith((".xhtml", ".html"))
        )
        parsed_cache: dict[str, DocumentParser] = {}
        text_cache: dict[str, str] = {}
        xml_cache: dict[str, ET.Element] = {}

        def text(member: str) -> str:
            if member not in text_cache:
                text_cache[member] = archive.read(member).decode("utf-8")
            return text_cache[member]

        def parsed(member: str) -> DocumentParser:
            if member not in parsed_cache:
                parsed_cache[member] = parse_document(text(member))
            return parsed_cache[member]

        for member in documents:
            try:
                xml_cache[member] = ET.fromstring(archive.read(member))
            except (ET.ParseError, UnicodeDecodeError) as error:
                errors.append(f"{member}: invalid EPUB XHTML XML: {error}")

        for source in documents:
            for href in parsed(source).links:
                if not href or href == "#" or is_external(href):
                    continue
                split = urlsplit(href)
                path_text = unquote(split.path)
                fragment = unquote(split.fragment)
                if path_text.casefold().endswith((".qmd", ".md")):
                    errors.append(f"{source}: source-document link survived EPUB render: {href}")
                    continue
                target = (
                    posixpath.normpath(posixpath.join(posixpath.dirname(source), path_text))
                    if path_text
                    else source
                )
                if target not in members:
                    errors.append(f"{source}: missing EPUB member for {href}")
                    continue
                if (
                    fragment
                    and target.casefold().endswith((".xhtml", ".html"))
                    and fragment not in parsed(target).identifiers
                ):
                    errors.append(f"{source}: missing fragment #{fragment} in {target}")
        if not documents:
            errors.append(f"{path}: no HTML/XHTML documents found in EPUB")

        manifest: dict[str, tuple[str, str, str]] = {}
        spine: list[str] = []
        package_dir = posixpath.dirname(package_member)
        if package_member in members:
            try:
                package = ET.fromstring(archive.read(package_member))
            except ET.ParseError as error:
                errors.append(f"{package_member}: invalid XML: {error}")
                package = None
            if package is not None:
                version = package.get("version", "")
                if not version.startswith("3"):
                    errors.append(f"{package_member}: expected EPUB 3 package, found {version!r}")
                languages = [
                    (element.text or "").strip().casefold()
                    for element in package.iter()
                    if element.tag.rsplit("}", 1)[-1] == "language"
                ]
                has_korean_language = any(
                    language == "ko" or language.startswith("ko-")
                    for language in languages
                )
                if not has_korean_language:
                    errors.append(f"{package_member}: Korean dc:language is missing")

                for element in package.iter():
                    local_name = element.tag.rsplit("}", 1)[-1]
                    if local_name == "item":
                        item_id = element.get("id", "")
                        href = element.get("href", "")
                        media_type = element.get("media-type", "")
                        properties = element.get("properties", "")
                        if item_id:
                            manifest[item_id] = (href, media_type, properties)
                        target = posixpath.normpath(
                            posixpath.join(package_dir, unquote(urlsplit(href).path))
                        )
                        if href and target not in members:
                            errors.append(f"{package_member}: manifest target is missing: {href}")
                    elif local_name == "itemref":
                        spine.append(element.get("idref", ""))

                if not spine:
                    errors.append(f"{package_member}: EPUB spine is empty")
                for item_id in spine:
                    if item_id not in manifest:
                        errors.append(f"{package_member}: spine idref is missing: {item_id}")

                nav_items = [
                    item
                    for item in manifest.values()
                    if "nav" in item[2].split()
                ]
                if not nav_items:
                    errors.append(f"{package_member}: EPUB navigation item is missing")
                else:
                    nav_member = posixpath.normpath(
                        posixpath.join(package_dir, unquote(nav_items[0][0]))
                    )
                    if nav_member in members:
                        nav_text = text(nav_member)
                        if 'epub:type="toc"' not in nav_text and "epub:type='toc'" not in nav_text:
                            errors.append(f"{nav_member}: table-of-contents nav is missing")

                math_items = [item for item in manifest.values() if "mathml" in item[2].split()]
                if not math_items:
                    errors.append(f"{package_member}: no manifest item declares MathML")

                for href, media_type, properties in manifest.values():
                    if media_type != "application/xhtml+xml":
                        continue
                    member = posixpath.normpath(
                        posixpath.join(package_dir, unquote(urlsplit(href).path))
                    )
                    if member not in xml_cache:
                        continue
                    contains_mathml = any(
                        element.tag.rsplit("}", 1)[-1] == "math"
                        for element in xml_cache[member].iter()
                    )
                    declares_mathml = "mathml" in properties.split()
                    if contains_mathml and not declares_mathml:
                        errors.append(
                            f"{package_member}: {href} contains MathML but does not declare "
                            "the mathml property"
                        )
                    elif declares_mathml and not contains_mathml:
                        errors.append(
                            f"{package_member}: {href} declares the mathml property but "
                            "contains no MathML"
                        )

                font_items = [
                    item
                    for item in manifest.values()
                    if item[1] in {"font/woff2", "application/font-woff2"}
                    or item[0].casefold().endswith(".woff2")
                ]
                if len(font_items) < 2:
                    errors.append(
                        f"{package_member}: regular and bold Korean WOFF2 fonts are required"
                    )
                for href, _, _ in font_items:
                    member = posixpath.normpath(posixpath.join(package_dir, unquote(href)))
                    if member in members and archive.getinfo(member).file_size < 100_000:
                        errors.append(f"{member}: embedded Korean font is unexpectedly small")

        document_text = "\n".join(text(member) for member in documents)
        if "<math" not in document_text:
            errors.append(f"{path}: inline MathML is missing")
        for title in (*FLAGSHIP_TITLES, *REFERENCE_TITLES):
            if title not in document_text:
                errors.append(f"{path}: expected chapter or reference title is missing: {title}")
        for title in FLAGSHIP_TITLES:
            matching = [member for member in documents if title in text(member)]
            if not any("page-glossary--static" in text(member) for member in matching):
                errors.append(f"{path}: {title} chapter has no static page glossary")

        css_members = [member for member in members if member.casefold().endswith(".css")]
        css_text = "\n".join(text(member) for member in css_members)
        if "@font-face" not in css_text or "Atlas Sans KR" not in css_text:
            errors.append(f"{path}: EPUB CSS does not activate the embedded Korean font")
        if not any(member.casefold().endswith("ofl.txt") for member in members):
            errors.append(f"{path}: embedded font license OFL.txt is missing")
    return errors


def _outline_titles(items: object) -> list[str]:
    titles: list[str] = []
    if isinstance(items, list):
        for item in items:
            titles.extend(_outline_titles(item))
        return titles
    title = getattr(items, "title", None)
    if isinstance(title, str):
        titles.append(title)
    return titles


def _font_is_embedded(font: object) -> bool:
    try:
        value = font.get_object()
        descendants = value.get("/DescendantFonts", [])
        candidates = [value, *(entry.get_object() for entry in descendants)]
        for candidate in candidates:
            descriptor = candidate.get("/FontDescriptor")
            if descriptor is None:
                continue
            descriptor = descriptor.get_object()
            embedded = any(
                descriptor.get(key) is not None
                for key in ("/FontFile", "/FontFile2", "/FontFile3")
            )
            if embedded:
                return True
    except (AttributeError, KeyError, TypeError):
        return False
    return False


def verify_pdf(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        reader = PdfReader(path, strict=True)
    except Exception as error:  # pypdf exposes several parser-specific exceptions
        return [f"{path}: cannot parse PDF: {error}"]

    if len(reader.pages) < 2:
        errors.append(f"{path}: PDF must contain more than one page")
    if not reader.metadata or not reader.metadata.title:
        errors.append(f"{path}: PDF title metadata is missing")

    try:
        outline_titles = _outline_titles(reader.outline)
    except Exception as error:
        errors.append(f"{path}: cannot read PDF outline: {error}")
        outline_titles = []
    if not outline_titles:
        errors.append(f"{path}: PDF bookmarks/outline are missing")

    is_full_book = "proof" not in path.name.casefold()
    if is_full_book:
        for title in FLAGSHIP_TITLES:
            if not any(title in outline for outline in outline_titles):
                errors.append(f"{path}: PDF bookmark is missing for {title}")

    internal_links = 0
    embedded_font = False
    extracted_parts: list[str] = []
    for page in reader.pages:
        resources = page.get("/Resources")
        if resources is not None:
            resources = resources.get_object()
            fonts = resources.get("/Font", {})
            if hasattr(fonts, "get_object"):
                fonts = fonts.get_object()
            embedded_font = embedded_font or any(_font_is_embedded(font) for font in fonts.values())
        annotations = page.get("/Annots", [])
        for reference in annotations:
            annotation = reference.get_object()
            if annotation.get("/Subtype") != "/Link":
                continue
            action = annotation.get("/A")
            has_destination = annotation.get("/Dest") is not None
            has_goto_action = (
                action is not None and action.get_object().get("/S") == "/GoTo"
            )
            if has_destination or has_goto_action:
                internal_links += 1
        extracted_text = "\n".join(extracted_parts)
        if is_full_book and not all(title in extracted_text for title in FLAGSHIP_TITLES):
            extracted_parts.append(page.extract_text() or "")

    if not embedded_font:
        errors.append(f"{path}: no embedded PDF font was detected")
    if internal_links == 0:
        errors.append(f"{path}: no internal PDF links were detected")
    if is_full_book:
        extracted_text = "\n".join(extracted_parts)
        for title in FLAGSHIP_TITLES:
            if title not in extracted_text:
                errors.append(f"{path}: PDF text is missing {title}")
    return errors


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "outputs", nargs="+", type=Path, help="rendered HTML directory or .epub file"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    errors: list[str] = []
    for output in args.outputs:
        if output.is_dir():
            errors.extend(verify_html_tree(output))
        elif output.is_file() and output.suffix.casefold() == ".epub":
            errors.extend(verify_epub(output))
        elif output.is_file() and output.suffix.casefold() == ".pdf":
            errors.extend(verify_pdf(output))
        else:
            errors.append(f"unsupported or missing output: {output}")

    for error in errors:
        print(error, file=sys.stderr)
    if errors:
        print(f"Output verification failed: {len(errors)} error(s).", file=sys.stderr)
        return 1
    print(f"Output verification passed for {len(args.outputs)} target(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
