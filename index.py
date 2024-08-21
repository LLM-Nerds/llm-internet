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
num_results = st.slider("Number of google search results to try scraping", min_value=1, max_value=10, value=5)

# Get random user agent to avoid being blocked by Google
def get_google_search_results(query):
    user_agent = random.choice(user_agent_list)
    headers = {'User-Agent': user_agent}
    
    original_get = requests.get
    requests.get = lambda *args, **kwargs: original_get(*args, **{**kwargs, 'headers': headers})
    
    try:
        results = list(search(query, num_results=5)) 
        time.sleep(random.uniform(1, 3))
        return results
    except HTTPError as e:
        raise Exception("Unable to perform search.")
    finally:
        requests.get = original_get

def is_relevant_result(result):
    if isinstance(result, list):
        # If result is a list, check if it contains at least one item
        # and that item is a dictionary with the required keys
        return (len(result) > 0 and
                isinstance(result[0], dict) and
                all(key in result[0] for key in ["Name", "Price", "Image"]))
    elif isinstance(result, dict):
        # If result is a dictionary, check for the required keys
        return all(key in result for key in ["Name", "Price", "Image"])
    else:
        # If result is neither a list nor a dictionary, it's not relevant
        return False
    
def scrape_url(url, elements, scraper):
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
    
def print_product_info(product):
    print(f"Name:    {product.get('Name', 'N/A')}")
    print(f"Price:   {product.get('Price', 'N/A')}")
    print(f"Image:   {product.get('Image', 'N/A')}")
    print(f"Website: {product.get('Website', 'N/A')}")
    print('-' * 40)

if st.button("Search and Scrape"):
    if query:
        with st.spinner("Searching and scraping..."):
            search_results = get_google_search_results(query)[:num_results]

            elements = {
                "Name": "Name of the Product",
                "Price": "Price of the Product",
                "Image": "The image url of the product, make sure it's the png/jpg/jpeg/gif/svg/webp url, if it's not a complete url, make sure to add the domain name to it",
                "Website": "Product's details Website, make sure it's the complete url, if it's not a complete url, make sure to add the domain name to it",
            }

            scraper = Parsera(model=llm)

            all_results = []

            for url in search_results:
                result = scrape_url(url, elements, scraper)
                if result:
                    all_results.append(result)
                    if len(all_results) == num_results:
                        break

            if all_results:
                for i, result in enumerate(all_results, 1):
                    st.subheader(f"Result {i}")
                    
                    if isinstance(result, list):
                        for item in result[:5]:
                            col1, col2 = st.columns(2)
                            with col1:
                                st.image(item.get('Image', 'N/A'), width=200)
                            with col2:
                                st.write(f"**Name:** {item.get('Name', 'N/A')}")
                                st.write(f"**Price:** {item.get('Price', 'N/A')}")
                                st.write(f"**Website:** {item.get('Website', 'N/A')}")
                    elif isinstance(result, dict):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.image(result.get('Image', 'N/A'), width=200)
                        with col2:
                            st.write(f"**Name:** {result.get('Name', 'N/A')}")
                            st.write(f"**Price:** {result.get('Price', 'N/A')}")
                            st.write(f"**Website:** {result.get('Website', 'N/A')}")
                    
                    st.markdown("---")
            else:
                st.warning("No results found.")
    else:
        st.warning("Please enter a search query.")