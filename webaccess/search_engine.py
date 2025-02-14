from functools import cached_property, lru_cache
from typing import Literal, List, Dict
from scraper import fetch
from lxml.etree import _Element
from lxml.html import HTMLParser, document_fromstring
from urllib.parse import unquote
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

@lru_cache(None, typed=True)
def _normalize_url(url: str) -> str:
    """Unquote URL and replace spaces with '+' along with some URL cleanup."""
    # for duckduckgo
    if "uddg=http" in url:
        url = url.split("uddg=", 1)[1]
        if "&rut=" in url:
            url = url.split("&rut=", 1)[0]
    # for yahoo
    if "/RU=http" in url:
        url = url.split("/RU=", 1)[1]
        if "/RK=2/RS" in url:
            url = url.split("/RK=2/RS=", 1)[0]
    return unquote(url.replace(" ", "+")) if url else ""

class SearchEngine:
    def __init__(self, provider: Literal['google', 'bing', 'yahoo', 'duckduckgo', 'auto'] = 'google') -> None:
        self.fetch = fetch
        self.provider = provider

    @cached_property
    def parser(self) -> HTMLParser:
        """Get an HTML parser configured for scraping."""
        return HTMLParser(remove_blank_text=True, remove_comments=True, remove_pis=True, collect_ids=False)

    def _search_google(self, query: str, num_results: int) -> List[str]:
        page_results = []
        cache = set()
        search_results = self.fetch.get(f'https://www.google.com/search?udm=14&q={query}&num={num_results}')
        tree = document_fromstring(search_results.content, parser=self.parser)
        elements = tree.xpath("//div")
        if not isinstance(elements, list):
            return []
        for e in elements:
            if isinstance(e, _Element):
                hrefxpath = e.xpath("./span/a/@href")
                href = str(hrefxpath[0]) if hrefxpath and isinstance(hrefxpath, list) else None
                href = _normalize_url(href) if href else None
                if href and href not in cache and href.startswith("http"):
                    cache.add(href)
                    page_results.append(href)
                    # print(f"{e.tag} {e.attrib} {href}")
        return page_results

    def _search_bing(self, query: str, num_results: int) -> List[str]:
        page_results = []
        cache = set()
        search_results = self.fetch.get(f'https://www.bing.com/search?q={query}&count={num_results}')
        # print(search_results.content)
        with open('bing.html', 'wb') as f:
            f.write(search_results.content)
        tree = document_fromstring(search_results.content, parser=self.parser)
        elements = tree.xpath("//h2")
        if not isinstance(elements, list):
            return []
        for e in elements:
            if isinstance(e, _Element):
                hrefxpath = e.xpath("./a/@href")
                # if hrefxpath and isinstance(hrefxpath, list):
                #     print(hrefxpath)
                #     print(f"{e.tag} {e.attrib}")
                href = str(hrefxpath[0]) if hrefxpath and isinstance(hrefxpath, list) else None
                href = _normalize_url(href) if href else None
                if ( href and href.startswith("http") and href not in cache ):
                    cache.add(href)
                    page_results.append(href)
                    # print(f"{e.tag} {e.attrib} {href}")
        return page_results

    def _search_yahoo(self, query: str, num_results: int) -> List[str]:
        page_results = []
        cache = set()
        search_results = self.fetch.get(f'https://search.yahoo.com/search?q={query}&n={num_results}')
        tree = document_fromstring(search_results.content, parser=self.parser)
        elements = tree.xpath("//div")
        if not isinstance(elements, list):
            return []
        for e in elements:
            if isinstance(e, _Element):
                hrefxpath = e.xpath("./a/@href")
                href = str(hrefxpath[0]) if hrefxpath and isinstance(hrefxpath, list) else None
                href = _normalize_url(href) if href else None
                if href and e.attrib.get('class') == 'd-ib v-v' and href not in cache:
                    cache.add(href)
                    page_results.append(href)
                    # print(f"{e.tag} {e.attrib} {href}")
        return page_results

    def _search_duckduckgo(self, query: str, num_results: int) -> List[str]:
        page_results = []
        cache = set()
        html = self.fetch.get(f'https://www.duckduckgo.com/html/?q={query}&num={num_results}')
        tree = document_fromstring(html.content, parser=self.parser)
        elements = tree.xpath("//div[h2]")
        if not isinstance(elements, list):
            return []
        for e in elements:
            if isinstance(e, _Element):
                hrefxpath = e.xpath("./a/@href")
                href = str(hrefxpath[0]) if hrefxpath and isinstance(hrefxpath, list) else None
                href = _normalize_url(href) if href else None
                if href and href not in cache:
                    cache.add(href)
                    page_results.append(href)
                    # print(f"{e.tag} {e.attrib} {href}")
        return page_results

    def search(self, query: str, num_results: int = 5) -> List[str]:
        """Dispatch search based on the selected provider."""
        if self.provider == 'google':
            return self._search_google(query, num_results)[:num_results]
        elif self.provider == 'bing':
            return self._search_bing(query, num_results)[:num_results]
        elif self.provider == 'yahoo':
            return self._search_yahoo(query, num_results)[:num_results]
        elif self.provider == 'duckduckgo':
            return self._search_duckduckgo(query, num_results)[:num_results]
        elif self.provider == 'auto':
            # Auto mode: randomly choose 2 search engines and combine their deduplicated results.
            engines = ['google', 'bing', 'yahoo', 'duckduckgo']
            chosen = random.sample(engines, 2)
            results = []
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = []
                for eng in chosen:
                    engine_obj = SearchEngine(provider=eng)
                    futures.append(executor.submit(engine_obj.search, query, num_results))
                for future in as_completed(futures):
                    try:
                        results.extend(future.result())
                    except Exception:
                        continue
            # Deduplicate while preserving order
            deduped = list(dict.fromkeys(results))
            return deduped[:num_results]
        else:
            return []

    def _search_with_error_handling(self, query: str, num_results_from_each: int) -> Dict:
        try:
            result_urls = self.search(query, num_results_from_each)
            return {'query': query, 'urls': result_urls}
        except Exception as e:
            # Returning an error message as part of the response, or you could handle it differently.
            print(f"Search error for query '{query}': {e}")
            return {'query': query, 'urls': [], 'error': str(e)}

    def bulk_search(self, queries: List[str], num_results_from_each: int = 3, combined: bool = True) -> List[Dict]:
        """
        Performs a bulk search across multiple queries in the same order as the input list.

        Args:
            queries: A list of search queries.
            num_results_from_each: The number of results to retrieve for each query.

        Returns:
            A list of dictionaries, each containing the query and its corresponding URLs.
        """
        max_workers = min(10, len(queries)) if queries else 1  # Adjust max_workers as needed.
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # executor.map preserves the order of input queries.
            results = list(executor.map(lambda q: self._search_with_error_handling(q, num_results_from_each), queries))
            if combined:
                urls = []
                for json_obj in results:
                    url = json_obj['urls']
                    if not url:
                        continue
                    urls.extend(url)
                return urls
        return results

if __name__ == '__main__':
    import time

    providers_to_test = ['google', 'bing', 'yahoo', 'duckduckgo', 'auto']
    providers_to_test = ['yahoo']
    query = 'Lion king movie'
    num_results = 5

    for provider in providers_to_test:
        start_time = time.time()
        print(f"Search results from {provider}:")
        search = SearchEngine(provider=provider)
        results = search.search(query, num_results=num_results)
        end_time = time.time()
        print(f"Execution time: {end_time - start_time} seconds")
        if results:
            for i in results:
                print(f"- {i}")
        else:
            print("No results found.")
        print("-" * 30)