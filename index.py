import os
import time
import random
import requests
from langchain_google_genai import ChatGoogleGenerativeAI
from parsera import Parsera
from googlesearch import search
from requests.exceptions import HTTPError
import traceback
import streamlit as st
from urllib.parse import urljoin, urlparse


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

st.title("Product Search and Scraper")

query = st.text_input("Enter your search query:")
num_results = st.slider("Number of google search results to try scraping", min_value=1, max_value=20, value=10)

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
        st.write(f"Google search took {end_time - start_time:.2f} seconds")

def is_relevant_result(result):
    if isinstance(result, list):
        # If result is a list, check if it contains at least one item
        # and that item is a dictionary with the required keys
        return (len(result) > 0 and
                isinstance(result[0], dict) and
                all(key in result[0] for key in ["Name", "Price", "Thumbnail Url"]))
    elif isinstance(result, dict):
        # If result is a dictionary, check for the required keys
        return all(key in result for key in ["Name", "Price", "Thumbnail Url"])
    else:
        # If result is neither a list nor a dictionary, it's not relevant
        return False
    
def scrape_url(url, elements, scraper):
    start_time = time.time()
    st.write(f"Scraping {url}: ")
    try:
        result = scraper.run(url=url, elements=elements)
        if is_relevant_result(result):
            # Fix image URLs
            if isinstance(result, list):
                for item in result:
                    item['Thumbnail Url'] = fix_image_url(item['Thumbnail Url'])
            elif isinstance(result, dict):
                result['Thumbnail Url'] = fix_image_url(result['Thumbnail Url'])
            return result
        print(f"Skipping irrelevant result from {url}")
        return None
    except Exception as e:
        print(f"Error scraping {url}: {str(e)}")
        print("Traceback:")
        traceback.print_exc()
        return None
    finally:
        end_time = time.time()
        st.write(f"=> Took {end_time - start_time:.2f} seconds")
    
def is_likely_seller_site(url):
    parsed_url = urlparse(url)
    domain = parsed_url.netloc.lower()
    
    # List of common e-commerce domains
    ecommerce_domains = ['farmersmarket', 'foodmap', 'thegioitraicay', 'traicaytonyteo', 'lottemart']
    
    # Check if the domain contains any of the e-commerce keywords
    return any(seller in domain for seller in ecommerce_domains)

def fix_image_url(image_url):
    if image_url.startswith('//'):
        return f"https:{image_url}"
    elif not urlparse(image_url).scheme:
        return f"https://{image_url}"
    return image_url

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

if st.button("Search and Scrape"):
    if query:
        with st.spinner("Searching and scraping..."):
            overall_start_time = time.time()
            search_results = get_google_search_results(query)[:num_results]

            elements = {
                "Name": "Name of the Product",
                "Price": "Price of the Product",
                "Thumbnail Url": "The thumbnail image url of the product, if it is the related product image, it may have different url format, make sure to extract the src value of the image tag and make sure it's the complete url, if it's not a complete url, make sure to add the domain name to it",
                "Website": "Product's details Website, make sure it's the complete url, if it's not a complete url, make sure to add the domain name to it",
            }

            scraper = Parsera(model=llm)

            all_results = []

            for url in search_results:
                result = scrape_url(url, elements, scraper)
                if result:
                    base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
                    all_results.append(result)
                    st.write(f"Result from {url}")
                    
                    if isinstance(result, list):
                        for item in result[:5]:
                            item['Website'] = fix_url(base_url, item.get('Website', ''))
                            col1, col2 = st.columns(2)
                            with col1:
                                st.image(item.get('Thumbnail Url', 'N/A'), width=200)
                            with col2:
                                st.write(f"**Name:** {item.get('Name', 'N/A')}")
                                st.write(f"**Price:** {item.get('Price', 'N/A')}")
                                st.write(f"**Website:** {item['Website']}")
                    elif isinstance(result, dict):
                        result['Website'] = fix_url(base_url, result.get('Website', ''))
                        col1, col2 = st.columns(2)
                        with col1:
                            st.image(result.get('Thumbnail Url', 'N/A'), width=200)
                        with col2:
                            st.write(f"**Name:** {result.get('Name', 'N/A')}")
                            st.write(f"**Price:** {result.get('Price', 'N/A')}")
                            st.write(f"**Website:** {result['Website']}")
                    
                    st.markdown("---")

                if len(all_results) == num_results:
                    break

            overall_end_time = time.time()
            st.write(f"Total processing time: {overall_end_time - overall_start_time:.2f} seconds")

            if not all_results:
                st.warning("No results found.")
    else:
        st.warning("Please enter a search query.")
        st.warning("Please enter a search query.")