from search_engine import SearchEngine
from scraper import fetch
from typing import List, Literal, Optional, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import re
from functools import lru_cache

class SearchWithExtractor(SearchEngine):
    """
    Extends the SearchEngine class to provide content extraction from search results.
    """

    def __init__(self, provider: Literal['google', 'bing', 'yahoo', 'duckduckgo', 'auto'] = 'auto') -> None:
        """
        Initializes the SearchWithExtractor.

        Args:
            provider: The search engine provider to use.  Defaults to 'google'.
        """
        super().__init__(provider)
        self.fetch = fetch  # Dependency injection for the fetch utility

    def fetch_site_from_url(self, url: str, type: Literal['markdown', 'plain_text', 'clean'], max_text: Optional[int] = None) -> Optional[dict]:
        """
        Fetches and extracts content from a given URL.

        Args:
            url: The URL to fetch content from.
            type: The desired format of the extracted content ('markdown', 'plain_text' or 'cleaned text').
            max_text:  An optional maximum length for the extracted content.

        Returns:
            A dictionary containing the URL and its extracted content, or None if an error occurs.
        """
        try:
            content_obj = self.fetch.get(url)
            if content_obj is None:  # Handle potential None return
                print(f"Failed to retrieve content object from: {url}")
                return None

            content = content_obj.markdown if type == 'markdown' else content_obj.plain_text
            if type == "clean":
                content = re.sub(r'\n+', ' ', content)
                content = re.sub(r'\s+', ' ', content)
            if max_text and isinstance(max_text, int) and max_text > 0:
                content = content[:max_text]  # Truncate content if max_text is specified
            return {url: content}
        except Exception as e:
            print(f"Error fetching or processing {url}: {e}")  # More specific error logging
            return None

    def fetch_site_from_url_bulk(self, urls: List[str], type: Literal['markdown', 'plain_text', 'clean'] = 'markdown', max_text: Optional[int] = None) -> List[dict]:
        """
        Fetches and extracts content from multiple URLs, sorting by content length.

        Args:
            urls: A list of URLs to fetch.
            type: The desired content format ('markdown' or 'plain_text').
            max_text: An optional maximum length for the extracted content from each site.

        Returns:
            A list of dictionaries, each containing a URL and its extracted content,
            sorted in descending order of content length.
        """
        results = []
        with ThreadPoolExecutor(max_workers=len(urls)) as executor:
            futures = [executor.submit(self.fetch_site_from_url, url, type, max_text) for url in urls]
            for future in as_completed(futures):
                result = future.result()  # Get the result directly
                if result:
                    results.append(result)

        # Sort by content length (descending) using a stable sort.
        return sorted(results, key=lambda item: len(item[list(item.keys())[0]]) if item else 0, reverse=True)

    # @lru_cache(None, typed=True)
    def auto_search_and_extract(self, queries: List[str], num_results_from_each: int = 3, combined: bool = True) -> List[dict]:
        """
        Performs a bulk search across multiple queries in the same order as the input list.

        Args:
            queries: A list of search queries.
            num_results_from_each: The number of results to fetch for each query.
            combined: Whether to return a single list of URLs or a list of dictionaries for each query.

        Returns:
            A list of dictionaries, each containing the url and its corresponding extracted content.
        """
        search_results = self.bulk_search(queries, num_results_from_each, combined)
        extract_results = self.fetch_site_from_url_bulk(search_results, 'clean', max_text=4096)
        sorted_results = sorted(extract_results, key=lambda item: len(item[list(item.keys())[0]]) if item else 0, reverse=True)
        return sorted_results

if __name__ == '__main__':
    import time

    queries = ['BTC latest price', 'ChatGPT vs Deepseek', 'Did coca cola get banned', 'Tips to stay safe online']
    providers_to_test = ['google', 'bing', 'yahoo', 'duckduckgo', 'auto']
    num_results_from_each = 3
    for provider in providers_to_test:
        try:
            extractor = SearchWithExtractor(provider=provider)
            start_time = time.time()
            sorted_results = extractor.auto_search_and_extract(queries, combined=True)
            end_time = time.time()
            print(f"Execution time: {end_time - start_time} seconds for {provider}")
        except Exception as e:
            print(f"Error occurred for {provider}: {e}")

    # extractor = SearchWithExtractor(provider='bing')
    # search_results = extractor.bulk_search(queries, combined=True)
    # print(search_results)
    # results = extractor.fetch_site_from_url_bulk(search_results, 'plain_text', max_text=4096)
    # # sort the result by content length
    # sorted_results = sorted(results, key=lambda item: len(item[list(item.keys())[0]]) if item else 0, reverse=True)
    

    # all_fetched_data = []
    # for json_obj in search_results:
    #     site_urls = json_obj['urls']
    #     fetched_sites = extractor.fetch_site_from_url_bulk(site_urls, 'plain_text', max_text=4096)
    #     all_fetched_data.extend(fetched_sites)
    # sorted_results = sorted(all_fetched_data, key=lambda item: len(item[list(item.keys())[0]]) if item else 0, reverse=True)
