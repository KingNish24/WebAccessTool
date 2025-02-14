from typing import Optional, Dict, Union
from functools import lru_cache
from browserforge.headers import Browser, HeaderGenerator
import httpx
from httpx._models import Response as BaseResponse
from tldextract import extract
from markitdown import MarkItDown
import tempfile
import os
from io import StringIO
from markdown import Markdown
import re

class Response:
    def __init__(self, response: httpx.Response, convert_to_markdown, convert_to_plain_text):
        self._response = response
        self._convert_to_markdown = convert_to_markdown
        self._convert_to_plain_text = convert_to_plain_text
        self._markdown = None
        self._plain_text = None

    def __getattr__(self, item):
        """
        Delegate attribute access to the underlying httpx.Response
        """
        return getattr(self._response, item)

    @property
    def markdown(self) -> str:
        if self._markdown is None:
            self._markdown = self._convert_to_markdown(self._response.content)
        return self._markdown

    @property
    def plain_text(self) -> str:
        if self._plain_text is None:
            # This conversion optionally can work on self.markdown if desired
            self._plain_text = self._convert_to_plain_text(self._response.content)
        return self._plain_text

def generate_headers() -> Dict[str, str]:
    """Generate real browser-like headers using browserforge's generator."""
    browsers = [
        Browser(name='chrome', min_version=120),
        Browser(name='firefox', min_version=120),
        Browser(name='edge', min_version=120),
    ]
    return HeaderGenerator(browser=browsers, device='desktop').generate()

@lru_cache(None, typed=True)
def generate_convincing_referer(url: str) -> str:
    """Generate a Google search referrer URL for the given domain."""
    website_name = extract(url).domain
    return f'https://www.google.com/search?q={website_name}'

def headers_job( headers: Optional[Dict], url: str) -> Dict:
    """Adds useragent to headers if it doesn't exist, generates real headers and append it to current headers, and
        finally generates a referer header that looks like if this request came from Google's search of the current URL's domain.

    :param headers: Current headers in the request if the user passed any
    :return: A dictionary of the new headers.
    """
    headers = headers or {}

    # Validate headers
    headers['User-Agent'] = generate_headers().get('User-Agent')
    extra_headers = generate_headers()
    headers.update(extra_headers)
    headers.update({'referer': generate_convincing_referer(url)})

    return headers

def convert_to_markdown(content: bytes) -> str:
    """Converts HTML, PDF or Many other file content to Markdown using MarkItDown.

    Args:
        content: PDF, HTML, or other file content to convert to Markdown.

    Returns:
        The Markdown representation of the content.
    """
    md = MarkItDown()
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(content)
            tmp_file.flush()  # Ensure data is written to file
            temp_path = tmp_file.name
        markdown_result = md.convert_local(temp_path).text_content
        return markdown_result
    except Exception as e:
        raise e
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

def convert_to_plain_text(content: bytes) -> str:
    """Converts Markdown content to a clean text.

    Args:
        content: PDF, HTML, or other file content to convert to plain text.

    Returns:
        The clean text representation of the content.
    """
    md_content = convert_to_markdown(content)

    def unmark_element(element, stream=None):
        if stream is None:
            stream = StringIO()
        if element.text:
            stream.write(element.text)
        for sub in element:
            unmark_element(sub, stream)
        if element.tail:
            stream.write(element.tail)
        return stream.getvalue()

    Markdown.output_formats["plain"] = unmark_element

    __md = Markdown(output_format="plain")
    __md.stripTopLevelTags = False

    final_text = __md.convert(md_content)

    final_text = re.sub(r"\n+", "\n", final_text)

    return final_text

@lru_cache(typed=True)
class BasicScraper:
    """Basic scraper class for making HTTP requests."""
    def __init__(self, proxy: Optional[str] = None, follow_redirects: bool = True, timeout: Optional[Union[int, float]] = None, retries: Optional[int] = 3 ):
        self.proxy = proxy
        self.timeout = timeout
        self.follow_redirects = bool(follow_redirects)
        self.retries = retries

    def get(self, url: str, cookies: Optional[Dict] = None, timeout: Optional[Union[int, float]] = None, **kwargs: Dict) -> Response:
        """Make basic HTTP GET request for you but with some added flavors.

        :param kwargs: Any keyword arguments are passed directly to `httpx.get()` function so check httpx documentation for details.
        :return: A `Response` object that is the same as `Adaptor` object except it has these added attributes: `status`, `reason`, `cookies`, `headers`, and `request_headers`
        """
        headers = headers_job(kwargs.pop('headers', {}), url)
        with httpx.Client(proxy=self.proxy, transport=httpx.HTTPTransport(retries=self.retries), cookies=cookies) as client:
            request = client.get(url=url, headers=headers, follow_redirects=self.follow_redirects, timeout=self.timeout or timeout, **kwargs)

        # request.markdown = self.convert_to_markdown(request.content)
        # request.plain_text = self.convert_to_plain_text(request.markdown)
        response = Response(
            response=request, 
            convert_to_markdown=convert_to_markdown, 
            convert_to_plain_text=convert_to_plain_text)
        return response
      
fetch = BasicScraper()

if __name__ == '__main__':
    
    print("Testing Simple Web page and markdown output:")
    response = fetch.get('https://huggingface.co/spaces')
    print(response.markdown)

    print("\n\nTesting PDF link and plain text output:\n\n")
    response = fetch.get('https://arxiv.org/pdf/2409.13592')
    print(response.plain_text)