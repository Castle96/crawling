# crawling

A simple tool to fetch a web page, extract readable text, summarize it, and save it as a Markdown file ready for local LLM ingestion.

## Usage

- Summarize a single URL:

```bash
python crawl_docs.py https://example.com/page
```

- Crawl a site and save each internal page:

```bash
python crawl_docs.py https://example.com --crawl
```

- Save files into a custom output directory:

```bash
python crawl_docs.py https://example.com/page --output-dir docs
```

The generated Markdown includes a `Summary` section and the extracted `Content` from the page.
