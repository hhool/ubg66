#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Optional


SEO_START = "<!-- SEO:START -->"
SEO_END = "<!-- SEO:END -->"


def title_case_from_slug(slug: str) -> str:
    return " ".join(part.upper() if part == "io" else part.capitalize() for part in slug.split("-"))


def choose_variant(values, key: str) -> str:
    if not values:
        return ""
    idx = int(hashlib.md5(key.encode("utf-8")).hexdigest(), 16) % len(values)
    return values[idx]


def strip_existing_seo_block(html: str) -> str:
    pattern = re.compile(r"\n?\s*" + re.escape(SEO_START) + r".*?" + re.escape(SEO_END) + r"\s*\n?", re.S)
    return pattern.sub("\n", html)


def page_type_and_name(rel_path: str):
    if rel_path == "index.html":
        return "home", "Home"
    if rel_path.startswith("game/") and rel_path.endswith(".html"):
        return "game", title_case_from_slug(Path(rel_path).stem)
    if rel_path.startswith("category/") and rel_path.endswith(".html"):
        return "category", title_case_from_slug(Path(rel_path).stem)
    return "default", Path(rel_path).stem.replace("-", " ").title()


def build_seo_block(cfg: dict, rel_path: str, page_type: str, page_name: str) -> str:
    site_name = cfg["site_name"]
    base_url = cfg["base_url"].rstrip("/")
    default_image = cfg["default_image"]

    if rel_path == "index.html":
        url = f"{base_url}/"
    else:
        url = f"{base_url}/{rel_path}"

    templates = cfg["templates"]

    if page_type == "home":
        title = cfg["home"]["title"]
        description = cfg["home"]["description"]
        json_ld = {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": site_name,
            "url": f"{base_url}/",
            "potentialAction": {
                "@type": "SearchAction",
                "target": f"{base_url}/search.html?q={{search_term_string}}",
                "query-input": "required name=search_term_string",
            },
        }
    elif page_type == "game":
        title = templates["game_title"].format(game_name=page_name, site_name=site_name)
        description = choose_variant(templates["game_description_variants"], rel_path).format(
            game_name=page_name,
            site_name=site_name,
        )
        json_ld = {
            "@context": "https://schema.org",
            "@type": "VideoGame",
            "name": page_name,
            "url": url,
            "description": description,
            "image": f"{base_url}/assets/upload/66games/jpg/{Path(rel_path).stem}.jpg",
            "publisher": {"@type": "Organization", "name": site_name},
        }
    elif page_type == "category":
        title = templates["category_title"].format(category_name=page_name, site_name=site_name)
        description = choose_variant(templates["category_description_variants"], rel_path).format(
            category_name=page_name,
            site_name=site_name,
        )
        json_ld = {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": f"{page_name} Games",
            "url": url,
            "description": description,
            "isPartOf": {"@type": "WebSite", "name": site_name, "url": f"{base_url}/"},
        }
    else:
        title = f"{page_name} | {site_name}"
        description = templates["default_description"].format(site_name=site_name)
        json_ld = {
            "@context": "https://schema.org",
            "@type": "WebPage",
            "name": page_name,
            "url": url,
            "description": description,
        }

    image = default_image if page_type != "game" else f"/assets/upload/66games/jpg/{Path(rel_path).stem}.jpg"
    image_url = image if image.startswith("http") else f"{base_url}{image}"

    json_ld_str = json.dumps(json_ld, ensure_ascii=True, separators=(",", ":"))

    lines = [
        SEO_START,
        f"<title>{title}</title>",
        f"<meta name=\"description\" content=\"{description}\">",
        f"<link rel=\"canonical\" href=\"{url}\">",
        f"<meta property=\"og:type\" content=\"website\">",
        f"<meta property=\"og:site_name\" content=\"{site_name}\">",
        f"<meta property=\"og:title\" content=\"{title}\">",
        f"<meta property=\"og:description\" content=\"{description}\">",
        f"<meta property=\"og:url\" content=\"{url}\">",
        f"<meta property=\"og:image\" content=\"{image_url}\">",
        f"<meta name=\"twitter:card\" content=\"summary_large_image\">",
        f"<meta name=\"twitter:title\" content=\"{title}\">",
        f"<meta name=\"twitter:description\" content=\"{description}\">",
        f"<meta name=\"twitter:image\" content=\"{image_url}\">",
        f"<script type=\"application/ld+json\">{json_ld_str}</script>",
        SEO_END,
    ]
    return "\n    ".join(lines)


def upsert_head_meta(html: str, seo_block: str) -> str:
    html = strip_existing_seo_block(html)
    html = re.sub(r"<title>.*?</title>\s*", "", html, count=1, flags=re.S)
    html = re.sub(r"<meta\s+name=[\"']description[\"'][^>]*>\s*", "", html, count=1, flags=re.I)
    head_match = re.search(r"<head>(.*?)</head>", html, flags=re.S | re.I)
    if not head_match:
        return html

    head_content = head_match.group(1)
    insert_pos = head_content.find("<link rel=\"stylesheet\"")
    if insert_pos == -1:
        insert_pos = len(head_content)

    new_head_content = head_content[:insert_pos] + "\n    " + seo_block + "\n    " + head_content[insert_pos:]
    return html[: head_match.start(1)] + new_head_content + html[head_match.end(1) :]


def select_batch(html_files, start: int, limit: int):
    if start < 0:
        raise ValueError("start must be >= 0")
    if limit < 0:
        raise ValueError("limit must be >= 0")
    if limit == 0:
        return []
    if start >= len(html_files):
        return []
    end = start + limit
    return html_files[start:end]


def run(root_dir: Path, start: int = 0, limit: Optional[int] = None, only_game_pages: bool = False):
    cfg_path = root_dir / "scripts" / "seo_variables.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))

    html_files = sorted(root_dir.rglob("*.html"))
    if only_game_pages:
        html_files = [path for path in html_files if path.relative_to(root_dir).as_posix().startswith("game/")]

    total_files = len(html_files)
    batch_limit = total_files - start if limit is None else limit
    files_to_process = select_batch(html_files, start, batch_limit)

    updated = 0
    for file_path in files_to_process:
        rel_path = file_path.relative_to(root_dir).as_posix()
        page_type, page_name = page_type_and_name(rel_path)
        html = file_path.read_text(encoding="utf-8")
        seo_block = build_seo_block(cfg, rel_path, page_type, page_name)
        new_html = upsert_head_meta(html, seo_block)

        if new_html != html:
            file_path.write_text(new_html, encoding="utf-8")
            updated += 1

    end = start + len(files_to_process)
    print(
        f"Processed {len(files_to_process)} HTML files (range {start}:{end} of {total_files}); "
        f"updated {updated} files"
    )


def parse_args():
    parser = argparse.ArgumentParser(description="Apply SEO variables to HTML files in batches")
    parser.add_argument(
        "--start",
        type=int,
        default=0,
        help="0-based start index in sorted HTML file list (default: 0)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="number of files to process from --start (default: process to end)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="batch size used with --batch-index (alternative to --start/--limit)",
    )
    parser.add_argument(
        "--batch-index",
        type=int,
        default=None,
        help="0-based batch index; requires --batch-size",
    )
    parser.add_argument(
        "--only-game-pages",
        action="store_true",
        help="process game/*.html only",
    )
    args = parser.parse_args()

    if args.batch_index is not None and args.batch_size is None:
        parser.error("--batch-index requires --batch-size")
    if args.batch_size is not None and args.batch_index is None:
        parser.error("--batch-size requires --batch-index")
    if args.batch_size is not None and args.batch_size <= 0:
        parser.error("--batch-size must be > 0")
    if args.batch_index is not None and args.batch_index < 0:
        parser.error("--batch-index must be >= 0")

    if args.batch_size is not None and args.batch_index is not None:
        args.start = args.batch_index * args.batch_size
        args.limit = args.batch_size

    return args


if __name__ == "__main__":
    cli_args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    run(
        project_root,
        start=cli_args.start,
        limit=cli_args.limit,
        only_game_pages=cli_args.only_game_pages,
    )