from langchain_core.tools import tool
import httpx
from PIL import Image as PILImage
import imagehash
import os
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from src.llm import get_vision_llm
from langchain_core.messages import HumanMessage
import base64

@tool
def search_web(query: str, limit: int = 10) -> list[dict]:
    """Search the web for a given query."""
    print(f"Executing web search for: {query}")
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=limit))
            # DDGS returns list of dicts with 'title', 'href', 'body'
            return [{"url": r["href"], "title": r["title"], "snippet": r["body"]} for r in results]
    except Exception as e:
        print(f"Search failed: {e}")
        return []

@tool
def search_images(query: str, limit: int = 5) -> list[dict]:
    """Search for images matching a query."""
    print(f"Executing image search for: {query}")
    try:
        with DDGS() as ddgs:
            results = list(ddgs.images(query, max_results=limit))
            # DDGS returns list of dicts with 'image', 'title', 'url'
            return [{"url": r["image"], "title": r["title"]} for r in results]
    except Exception as e:
        print(f"Image search failed: {e}")
        return []

@tool
def fetch_page(url: str) -> str:
    """Fetch the text content of a web page."""
    print(f"Fetching page: {url}")
    try:
        response = httpx.get(url, timeout=10.0, follow_redirects=True)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.extract()
            
        text = soup.get_text(separator=' ', strip=True)
        
        # Truncate to avoid massive context length
        return text[:5000]
    except Exception as e:
        return f"Error fetching {url}: {e}"

@tool
def download_image(url: str, save_dir: str = "downloads") -> str:
    """Download an image from a URL and return its local path."""
    os.makedirs(save_dir, exist_ok=True)
    
    # Simple filename extraction, could be improved
    filename = url.split("/")[-1].split("?")[0]
    if not filename or "." not in filename:
        filename = f"image_{hash(url)}.jpg"
        
    local_path = os.path.join(save_dir, filename)
    
    # If already downloaded
    if os.path.exists(local_path):
        return local_path
        
    try:
        response = httpx.get(url, timeout=10.0, follow_redirects=True)
        response.raise_for_status()
        with open(local_path, "wb") as f:
            f.write(response.content)
        return local_path
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        return ""

@tool
def analyze_image(image_path: str) -> dict:
    """Analyze an image using a vision model to determine the view type (front, back, etc)."""
    if not os.path.exists(image_path):
        return {"product_match": False, "view": "unknown", "confidence": 0.0}
        
    try:
        llm = get_vision_llm()
        
        def encode_image(img_path):
            with open(img_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
                
        image_data = encode_image(image_path)
        
        # We ask the model to output a specific format
        prompt = """
        Analyze this product image. 
        Determine the primary view of the product from this list: [front, back, left, right, top, bottom, detail, unknown].
        Is it clearly a product image (not a person or generic scene)?
        
        Reply strictly in this JSON format:
        {
            "product_match": true/false,
            "view": "one_of_the_options",
            "confidence": 0.0_to_1.0
        }
        """
        
        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}},
            ]
        )
        
        response = llm.invoke([message])
        
        # Simple JSON extraction
        import json
        text = response.content.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
            
        data = json.loads(text)
        return data
        
    except Exception as e:
        print(f"Error analyzing image {image_path}: {e}")
        return {"product_match": False, "view": "unknown", "confidence": 0.0}

@tool
def deduplicate_images(image_paths: list[str]) -> list[str]:
    """Take a list of image paths and return paths of unique images based on pHash."""
    unique_paths = []
    seen_hashes = set()
    for path in image_paths:
        if not path or not os.path.exists(path):
            continue
            
        try:
            img = PILImage.open(path)
            h = imagehash.phash(img)
            if h not in seen_hashes:
                seen_hashes.add(h)
                unique_paths.append(path)
        except Exception as e:
            print(f"Error processing {path} for deduplication: {e}")
    return unique_paths

@tool
def save_evidence(claim: dict) -> str:
    """Save an evidence claim to the database."""
    # We will do the actual DB save inside the node where we have DB access,
    # or we can pass a db connection here. 
    # For now, it just returns success. The Node handles State append.
    return f"Saved claim: {claim.get('claim')} = {claim.get('value')}"
