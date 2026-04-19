#!/usr/bin/env python3
import argparse
from difflib import get_close_matches
import hashlib
from html import unescape
import json
import re
from pathlib import Path
from typing import Optional


SEO_START = "<!-- SEO:START -->"
SEO_END = "<!-- SEO:END -->"

SPECIAL_TOKENS = {
    "io": "IO",
    "lol": "LOL",
    "fnf": "FNF",
    "fnaf": "FNAF",
    "fps": "FPS",
    "3d": "3D",
    "2d": "2D",
    "x3m": "X3M",
    "nba": "NBA",
    "nfl": "NFL",
    "gta": "GTA",
    "ovo": "OvO",
}


def title_case_from_slug(slug: str) -> str:
    words = []
    for part in slug.split("-"):
        lower_part = part.lower()
        if lower_part in SPECIAL_TOKENS:
            words.append(SPECIAL_TOKENS[lower_part])
        elif part.isdigit():
            words.append(part)
        else:
            words.append(part.capitalize())
    return " ".join(words)


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
    if rel_path == "404.html":
        return "error_404", "404"
    if rel_path.startswith("game/") and rel_path.endswith(".html"):
        return "game", title_case_from_slug(Path(rel_path).stem)
    if rel_path.startswith("category/") and rel_path.endswith(".html"):
        return "category", title_case_from_slug(Path(rel_path).stem)
    return "default", Path(rel_path).stem.replace("-", " ").title()


def should_skip_file(rel_path: str) -> bool:
    file_name = Path(rel_path).name
    return file_name.startswith("google") and file_name.endswith(".html")


def normalize_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def build_image_index(root_dir: Path):
    image_dir = root_dir / "assets" / "upload" / "66games" / "jpg"
    index = {}
    if not image_dir.exists():
        return index

    for path in image_dir.glob("*.jpg"):
        key = normalize_slug(path.stem)
        if key and key not in index:
            index[key] = path.name
    return index


def resolve_game_image(base_url: str, rel_path: str, image_index: dict, default_image: str) -> str:
    stem = Path(rel_path).stem
    stem_key = normalize_slug(stem)

    # Exact file-name match
    exact_name = f"{stem}.jpg"
    if stem_key in image_index and image_index[stem_key] == exact_name:
        return f"{base_url}/assets/upload/66games/jpg/{exact_name}"

    # Normalized match
    if stem_key in image_index:
        return f"{base_url}/assets/upload/66games/jpg/{image_index[stem_key]}"

    # Fuzzy match for minor slug typos (e.g. phsyics vs physics)
    close = get_close_matches(stem_key, list(image_index.keys()), n=1, cutoff=0.86)
    if close:
        return f"{base_url}/assets/upload/66games/jpg/{image_index[close[0]]}"

    # Safe fallback
    if default_image.startswith("http"):
        return default_image
    return f"{base_url}{default_image}"


def extract_category_item_list(base_url: str, html: str, category_name: str):
    pattern = re.compile(r'<a class="card" href="/game/([^"#?]+)\.html">.*?<h3>(.*?)</h3>', re.S | re.I)
    matches = pattern.findall(html)

    seen = set()
    items = []
    for slug, raw_name in matches:
        if slug in seen:
            continue
        seen.add(slug)

        name = re.sub(r"<[^>]+>", "", raw_name)
        name = unescape(name).strip()
        if not name:
            name = title_case_from_slug(slug)

        items.append((slug, name))
        if len(items) >= 24:
            break

    if not items:
        return None

    return {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": f"{category_name} Games List",
        "numberOfItems": len(items),
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": idx,
                "url": f"{base_url}/game/{slug}.html",
                "name": name,
            }
            for idx, (slug, name) in enumerate(items, start=1)
        ],
    }


def build_breadcrumb(base_url: str, page_type: str, page_name: str, url: str):
    items = [
        {
            "@type": "ListItem",
            "position": 1,
            "name": "Home",
            "item": f"{base_url}/",
        }
    ]

    if page_type == "category":
        items.append(
            {
                "@type": "ListItem",
                "position": 2,
                "name": f"{page_name} Games",
                "item": url,
            }
        )
    elif page_type == "game":
        items.append(
            {
                "@type": "ListItem",
                "position": 2,
                "name": "All Games",
                "item": f"{base_url}/category/all.html",
            }
        )
        items.append(
            {
                "@type": "ListItem",
                "position": 3,
                "name": page_name,
                "item": url,
            }
        )
    elif page_type == "home":
        return None
    elif page_type == "error_404":
        items.append(
            {
                "@type": "ListItem",
                "position": 2,
                "name": "404 Not Found",
                "item": url,
            }
        )
    else:
        items.append(
            {
                "@type": "ListItem",
                "position": 2,
                "name": page_name,
                "item": url,
            }
        )

    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": items,
    }


def build_seo_block(cfg: dict, rel_path: str, page_type: str, page_name: str, html: str, image_index: dict) -> str:
    site_name = cfg["site_name"]
    base_url = cfg["base_url"].rstrip("/")
    default_image = cfg["default_image"]

    if rel_path == "index.html":
        url = f"{base_url}/"
    else:
        url = f"{base_url}/{rel_path}"

    templates = cfg["templates"]
    extra_meta = []
    robots_meta = "index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1"
    og_type = "website"

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
    elif page_type == "error_404":
        title = f"404 Not Found | {site_name}"
        description = f"The page you requested could not be found on {site_name}. Browse the homepage to find more games."
        robots_meta = "noindex,follow"
        json_ld = {
            "@context": "https://schema.org",
            "@type": "WebPage",
            "name": "404 Not Found",
            "url": url,
            "description": description,
        }
    elif page_type == "game":
        og_type = "video.game"
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

    if page_type == "game":
        image_url = resolve_game_image(base_url, rel_path, image_index, default_image)
        json_ld["image"] = image_url
    else:
        image = default_image
        image_url = image if image.startswith("http") else f"{base_url}{image}"

    breadcrumb_ld = build_breadcrumb(base_url, page_type, page_name, url)
    if breadcrumb_ld is None:
        json_ld_payload = json_ld
    else:
        graph = [json_ld, breadcrumb_ld]
        if page_type == "category":
            item_list_ld = extract_category_item_list(base_url, html, page_name)
            if item_list_ld is not None:
                graph.append(item_list_ld)
        json_ld_payload = {
            "@context": "https://schema.org",
            "@graph": graph,
        }

    json_ld_str = json.dumps(json_ld_payload, ensure_ascii=True, separators=(",", ":"))

    lines = [
        SEO_START,
        f"<title>{title}</title>",
        f"<meta name=\"description\" content=\"{description}\">",
        f"<link rel=\"canonical\" href=\"{url}\">",
        f"<link rel=\"alternate\" hreflang=\"en\" href=\"{url}\">",
        f"<link rel=\"alternate\" hreflang=\"x-default\" href=\"{url}\">",
        f"<meta name=\"robots\" content=\"{robots_meta}\">",
        *extra_meta,
        f"<meta property=\"og:type\" content=\"{og_type}\">",
        f"<meta property=\"og:locale\" content=\"en_US\">",
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


def print_progress(current: int, total: int, updated: int):
    if total <= 0:
        percent = 100.0
    else:
        percent = (current / total) * 100
    print(f"Progress: {current}/{total} ({percent:.1f}%) | updated: {updated}")


def run(
    root_dir: Path,
    start: int = 0,
    limit: Optional[int] = None,
    only_game_pages: bool = False,
    progress_every: int = 25,
):
    cfg_path = root_dir / "scripts" / "seo_variables.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    image_index = build_image_index(root_dir)

    html_files = sorted(root_dir.rglob("*.html"))
    if only_game_pages:
        html_files = [path for path in html_files if path.relative_to(root_dir).as_posix().startswith("game/")]
    else:
        html_files = [path for path in html_files if not should_skip_file(path.relative_to(root_dir).as_posix())]

    total_files = len(html_files)
    batch_limit = total_files - start if limit is None else limit
    files_to_process = select_batch(html_files, start, batch_limit)
    batch_total = len(files_to_process)

    end = start + batch_total
    print(
        f"Starting batch: range {start}:{end} of {total_files} total files "
        f"(this run: {batch_total})"
    )

    updated = 0
    for idx, file_path in enumerate(files_to_process, start=1):
        rel_path = file_path.relative_to(root_dir).as_posix()
        page_type, page_name = page_type_and_name(rel_path)
        html = file_path.read_text(encoding="utf-8")
        seo_block = build_seo_block(cfg, rel_path, page_type, page_name, html, image_index)
        new_html = upsert_head_meta(html, seo_block)

        if new_html != html:
            file_path.write_text(new_html, encoding="utf-8")
            updated += 1

        if progress_every > 0 and (idx % progress_every == 0 or idx == batch_total):
            print_progress(idx, batch_total, updated)

    print(
        f"Processed {batch_total} HTML files (range {start}:{end} of {total_files}); "
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
    parser.add_argument(
        "--progress-every",
        type=int,
        default=25,
        help="print progress every N files (default: 25; use 0 to disable intermediate logs)",
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

    if args.progress_every < 0:
        parser.error("--progress-every must be >= 0")

    return args


if __name__ == "__main__":
    cli_args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    run(
        project_root,
        start=cli_args.start,
        limit=cli_args.limit,
        only_game_pages=cli_args.only_game_pages,
        progress_every=cli_args.progress_every,
    )