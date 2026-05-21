import argparse
import os
import re
import time
import hashlib
from urllib.parse import urljoin, urlparse, urldefrag

import requests
from bs4 import BeautifulSoup
import trafilatura


class DocsCrawler:
    def __init__(
        self,
        root_url,
        output_dir="docs",
        delay=0.5,
        max_pages=5000,
    ):
        self.root_url = root_url.rstrip("/")
        self.domain = urlparse(root_url).netloc
        self.output_dir = output_dir
        self.delay = delay
        self.max_pages = max_pages

        self.visited = set()
        self.queue = [self.root_url]

        os.makedirs(output_dir, exist_ok=True)

    def normalize(self, url):
        url, _ = urldefrag(url)
        parsed = urlparse(url)

        if parsed.scheme not in ("http", "https"):
            return None

        if parsed.netloc != self.domain:
            return None

        if re.search(
            r"\.(pdf|zip|gz|jpg|jpeg|png|gif|svg|css|js|ico)$",
            parsed.path.lower(),
        ):
            return None

        return url.rstrip("/")

    def filename_for(self, url):
        h = hashlib.md5(url.encode()).hexdigest()[:10]

        parsed = urlparse(url)
        path = parsed.path.strip("/").replace("/", "_")

        if not path:
            path = "index"

        return os.path.join(
            self.output_dir,
            f"{path}_{h}.md"
        )

    def fetch(self, url):
        try:
            r = requests.get(
                url,
                timeout=20,
                headers={
                    "User-Agent": "DocsCrawler/1.0"
                },
            )
            r.raise_for_status()
            return r.text
        except Exception as e:
            print(f"FAILED {url}: {e}")
            return None

    def extract_title(self, html, url):
        soup = BeautifulSoup(html, "html.parser")

        if soup.title and soup.title.string:
            return soup.title.string.strip()

        h1 = soup.find("h1")
        if h1 and h1.get_text(strip=True):
            return h1.get_text(strip=True)

        return url

    def summarize_text(self, text, max_sentences=4):
        text = re.sub(r"\s+", " ", text).strip()
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]

        if len(sentences) <= max_sentences:
            return " ".join(sentences)

        words = [w.lower() for w in re.findall(r"\w+", text) if len(w) > 2]
        stopwords = {
            "the", "and", "for", "that", "this", "with", "from", "have",
            "are", "was", "were", "which", "also", "their", "been", "will",
            "than", "about", "more", "such", "into", "when", "these", "other",
            "some", "use", "used", "using", "your", "yourself", "can", "its",
        }
        freq = {}
        for word in words:
            if word in stopwords:
                continue
            freq[word] = freq.get(word, 0) + 1

        if not freq:
            return " ".join(sentences[:max_sentences])

        sentence_scores = {}
        for sentence in sentences:
            score = 0
            for word in re.findall(r"\w+", sentence.lower()):
                score += freq.get(word, 0)
            sentence_scores[sentence] = score

        top_sentences = sorted(
            sentences,
            key=lambda s: sentence_scores.get(s, 0),
            reverse=True,
        )[:max_sentences]

        return " ".join(top_sentences)

    def extract_markdown(self, html, url):
        title = self.extract_title(html, url)
        extracted = trafilatura.extract(
            html,
            include_links=True,
            include_formatting=True,
        )

        if not extracted:
            return None

        summary = self.summarize_text(extracted)
        return (
            f"# {title}\n\n"
            f"- Source: {url}\n\n"
            f"## Summary\n\n{summary}\n\n"
            f"## Content\n\n{extracted}"
        )

    def save(self, url, markdown):
        path = self.filename_for(url)

        with open(path, "w", encoding="utf-8") as f:
            f.write(markdown)

        print(f"SAVED {path}")

    def links(self, html, base_url):
        soup = BeautifulSoup(html, "html.parser")

        for a in soup.find_all("a", href=True):
            full = urljoin(base_url, a["href"])
            normalized = self.normalize(full)

            if normalized:
                yield normalized

    def process_page(self, url):
        html = self.fetch(url)
        if not html:
            return

        md = self.extract_markdown(html, url)
        if md:
            self.save(url, md)

    def crawl(self):
        while self.queue and len(self.visited) < self.max_pages:
            url = self.queue.pop(0)

            if url in self.visited:
                continue

            print(f"CRAWLING {url}")

            self.visited.add(url)

            html = self.fetch(url)

            if not html:
                continue

            md = self.extract_markdown(html, url)

            if md:
                self.save(url, md)

            for link in self.links(html, url):
                if link not in self.visited:
                    self.queue.append(link)

            time.sleep(self.delay)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fetch a web URL, extract readable text, summarize it, and save a Markdown file."
    )
    parser.add_argument("url", help="The URL to fetch and summarize")
    parser.add_argument("--output-dir", default="docs", help="Directory where Markdown files are saved")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between requests when crawling")
    parser.add_argument("--max-pages", type=int, default=5000, help="Maximum number of pages to crawl")
    parser.add_argument("--crawl", action="store_true", help="Follow internal links on the same domain and save each page")

    args = parser.parse_args()

    crawler = DocsCrawler(
        root_url=args.url,
        output_dir=args.output_dir,
        delay=args.delay,
        max_pages=args.max_pages,
    )

    if args.crawl:
        crawler.crawl()
    else:
        crawler.process_page(args.url)