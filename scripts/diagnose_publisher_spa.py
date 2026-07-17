#!/usr/bin/env python3
"""Inspeciona shells de SPA e bundles para descobrir endpoints de catálogo."""
from __future__ import annotations

import argparse
import re
import warnings
from urllib.parse import urljoin, urlparse

import requests
import urllib3
from bs4 import BeautifulSoup

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}
INTERESTING = re.compile(
    r"api|graphql|catalog|livr|book|produto|product|isbn|search|busca|content",
    re.I,
)
URLISH = re.compile(
    r"https?://[^\"'`\\\s]{5,}|/[A-Za-z0-9_@.,?=&%:+\-]{2,}(?:/[A-Za-z0-9_@.,?=&%:+\-]*)+"
)


def fetch(session: requests.Session, url: str, insecure: bool, redirects: bool = True):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", urllib3.exceptions.InsecureRequestWarning)
            return session.get(
                url,
                headers=HEADERS,
                timeout=(8, 20),
                verify=not insecure,
                allow_redirects=redirects,
            )
    except requests.RequestException as exc:
        print(f"ERRO {url}: {exc!r}")
        return None


def inspect(base_url: str, insecure: bool) -> int:
    session = requests.Session()
    candidates = [
        base_url.rstrip("/") + "/",
        base_url.rstrip("/") + "/index.html",
    ]
    parsed = urlparse(base_url)
    if parsed.scheme == "https":
        candidates.append(base_url.replace("https://", "http://", 1).rstrip("/") + "/")
    else:
        candidates.append(base_url.replace("http://", "https://", 1).rstrip("/") + "/")

    pages: list[tuple[str, requests.Response]] = []
    for url in dict.fromkeys(candidates):
        no_redirect = fetch(session, url, insecure, redirects=False)
        if no_redirect is not None:
            print(
                f"PROBE {url} status={no_redirect.status_code} "
                f"location={no_redirect.headers.get('location', '')!r} "
                f"ct={no_redirect.headers.get('content-type', '')!r}"
            )
        response = fetch(session, url, insecure, redirects=True)
        if response is None:
            continue
        print(
            f"PAGE {url} -> {response.url} status={response.status_code} "
            f"ct={response.headers.get('content-type', '')!r} bytes={len(response.content)}"
        )
        snippet = " ".join(response.text[:500].split())
        print(f"  snippet={snippet!r}")
        if response.status_code < 400 and "html" in response.headers.get("content-type", "").lower():
            pages.append((response.url, response))

    script_urls: list[str] = []
    for page_url, response in pages:
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup.find_all("script", src=True):
            full = urljoin(page_url, tag["src"])
            if full not in script_urls:
                script_urls.append(full)
        for tag in soup.find_all("link", href=True):
            rel = " ".join(tag.get("rel") or [])
            if "preload" in rel.lower() and str(tag.get("as") or "").lower() == "script":
                full = urljoin(page_url, tag["href"])
                if full not in script_urls:
                    script_urls.append(full)

    print(f"SCRIPTS encontrados={len(script_urls)}")
    for script_url in script_urls[:12]:
        response = fetch(session, script_url, insecure)
        if response is None:
            continue
        print(f"SCRIPT {script_url} status={response.status_code} bytes={len(response.content)}")
        if response.status_code >= 400:
            continue
        found: list[str] = []
        for value in URLISH.findall(response.text):
            cleaned = value.rstrip(")]}>,;.")
            if INTERESTING.search(cleaned) and cleaned not in found:
                found.append(cleaned)
        for value in found[:60]:
            print(f"  candidato={value}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--insecure", action="store_true")
    args = parser.parse_args()
    return inspect(args.url, args.insecure)


if __name__ == "__main__":
    raise SystemExit(main())
