import os
import time
import random
import requests
import json
from langchain_google_genai import ChatGoogleGenerativeAI
from parsera import Parsera
from googlesearch import search
from requests.exceptions import HTTPError
import traceback
import streamlit as st
from urllib.parse import quote_plus, urljoin, urlparse
from difflib import SequenceMatcher



os.system("playwright install")


user_agent_list = [
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.1.1 Safari/605.1.15',
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:77.0) Gecko/20100101 Firefox/77.0',
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36',
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:77.0) Gecko/20100101 Firefox/77.0',
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36',
]

@st.cache_resource
def initialize_llm():
    return ChatGoogleGenerativeAI(
        model="gemini-1.5-flash",
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0.0,
    )

llm = initialize_llm()

st.title("Advanced Web Search and Information Extractor")

query = st.text_input("Enter your search query:")
num_results = 5

def is_product_query(query):
    product_keywords = ['buy', 'price', 'product', 'item', 'purchase']
    return any(keyword in query.lower() for keyword in product_keywords)

def generate_extraction_elements(query):
    is_product_search = is_product_query(query)
    system_prompt = """
    You are an AI assistant that generates extraction elements for web scraping based on user queries.
    Given a user's search query, create a JSON object with key-value pairs representing the information to extract.
    The keys should be short labels, and the values should be descriptions of what to extract, the key should be lowercase.
    Number of keys should be equals or less than 5.
    Return only the JSON object, without any additional formatting or text.
    """

    if is_product_search:
        system_prompt += "The query is about a product, the required information is the product name, price, and image, url."

    user_prompt = f"Generate extraction elements for the following query: {query}"
    
    response = llm.invoke(system_prompt + "\n" + user_prompt)

    try:
        json_str = response.content.strip().removeprefix('json').removesuffix('').strip()
        elements = json.loads(json_str)


        return elements
    except json.JSONDecodeError as e:
        st.error(f"Failed to parse JSON: {str(e)}")
        st.error(f"Raw response: {response.content}")
        st.error("Using default elements.")
        return {
            "Title": "Main title or heading of the content",
            "Content": "Main content or summary related to the query",
            "Source": "URL or name of the source"
        }

# Get random user agent to avoid being blocked by Google
def get_google_search_results(query):
    start_time = time.time()
    user_agent = random.choice(user_agent_list)
    headers = {'User-Agent': user_agent}
    
    original_get = requests.get
    requests.get = lambda *args, **kwargs: original_get(*args, **{**kwargs, 'headers': headers})
    
    try:
        results = list(search(query, num_results)) 
        filtered_results = [url for url in results if is_likely_seller_site(url)]
        
        time.sleep(random.uniform(1, 3))
        return filtered_results
    except HTTPError as e:
        raise Exception("Unable to perform search.")
    finally:
        requests.get = original_get
        end_time = time.time()

def is_relevant_result(result):
    if isinstance(result, list):
        return len(result) > 0 and isinstance(result[0], dict) and len(result[0]) > 0
    elif isinstance(result, dict):
        return len(result) > 0
    else:
        return False
    
def scrape_url(url, elements, scraper):
    st.write(f"Scraping {url}: ")
    try:
        result = scraper.run(url=url, elements=elements)
        if is_relevant_result(result):
            return result
        print(f"Skipping irrelevant result from {url}")
        return None
    except Exception as e:
        print(f"Error scraping {url}: {str(e)}")
        print("Traceback:")
        traceback.print_exc()
        return None
    
def is_likely_seller_site(url):
    parsed_url = urlparse(url)
    domain = parsed_url.netloc.lower()
    
    # List of domains to exclude
    blacklist_domains = ['dienmayxanh.com', 'bachhoaxanh.com', 'fptshop.com.vn', 'wikipedia.org', 'vi.wikipedia.org']
    
    # Check if the domain is not in the blacklist
    return not any(seller in domain for seller in blacklist_domains)

def fix_url(base_url, path):
    if not path:
        return ''
    parsed_path = urlparse(path)
    if parsed_path.scheme:
        return path
    elif path.startswith('//'):
        return f'https:{path}'
    elif path.startswith('/'):
        return urljoin(base_url, path)
    else:
        return f'https://{path}'
    
def string_similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()

def filter_results_by_query(results, query, similarity_threshold=0.6):
    query = query.lower()
    
    def get_name_field(item):
        # Look for a 'name' field (case-insensitive)
        name_field = next((key for key in item.keys() if key.lower() == 'name'), None)
        # If no 'name' field, use the first available field
        return name_field or next(iter(item.keys()), None)
    
    def is_similar(item):
        name_field = get_name_field(item)
        if not name_field:
            return False
        
        name = str(item[name_field]).lower()
        
        # Check if query is a substring of the name
        if query in name:
            return True
        
        # Check for partial matches
        words_query = query.split()
        words_name = name.split()
        
        # Count how many query words are in the name
        matching_words = sum(1 for word in words_query if any(word in name_word for name_word in words_name))
        
        # If more than half of the query words are in the name, consider it a match
        if matching_words >= len(words_query) / 2:
            return True
        
        # Fall back to overall similarity check
        return string_similarity(query, name) >= similarity_threshold
    
    if isinstance(results, list):
        return [item for item in results if is_similar(item)]
    elif isinstance(results, dict):
        return [results] if is_similar(results) else []
    return []

if st.button("Search and Extract Information"):
    if query:
        with st.spinner("Searching and extracting information..."):
            overall_start_time = time.time()

            elements = generate_extraction_elements(query)
            with st.expander("Click to see the information I will extract"):
                st.json(elements)

            scraper = Parsera(model=llm)

            search_results = get_google_search_results(query)[:num_results]

            all_results = []

            is_product_search = is_product_query(query)

            for url in search_results:
                result = scrape_url(url, elements, scraper)
                if result:
                    base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
                    
                    if is_product_search:
                        filtered_result = filter_results_by_query(result, query)
                    else:
                        filtered_result = result if isinstance(result, list) else [result]
                    
                    if filtered_result:
                        all_results.extend(filtered_result)
                        st.write(f"Result from: {url}")
                        
                        for item in filtered_result[:10]:
                            col1, col2 = st.columns([1, 3])
                            
                            image_field = next((field for field in ['image', 'thumbnailUrl', 'imageUrl', 'Thumbnail Url'] if field in item), None)
                            
                            if image_field:
                                image_url = fix_url(base_url, item[image_field])
                                col1.image(image_url, use_column_width=True)
                            
                            with col2:
                                for key, value in item.items():
                                    if key != image_field:
                                        if key == 'Website':
                                            value = fix_url(base_url, value)
                                        st.write(f"**{key}:** {value}")
                            
                            st.markdown("---")

                if len(all_results) >= num_results:
                    break

            overall_end_time = time.time()
            st.write(f"Total processing time: {overall_end_time - overall_start_time:.2f} seconds")

            if not all_results:
                st.warning("No results found.")
    else:
        st.warning("Please enter a search query.")