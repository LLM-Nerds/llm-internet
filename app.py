import streamlit as st
from langchain_google_genai import ChatGoogleGenerativeAI
from parsera import Parsera
import io
import os
from gtts import gTTS # type: ignore
import requests
from bs4 import BeautifulSoup
import time
from urllib.parse import urlparse
import base64  # Add this import

os.system("playwright install")

def is_valid_url(url):
    parsed = urlparse(url)
    return bool(parsed.scheme) and bool(parsed.netloc)

@st.cache_resource
def initialize_llm():
    return ChatGoogleGenerativeAI(
      model="gemini-1.5-flash",
      google_api_key=os.getenv("GOOGLE_API_KEY"),
      temperature=0.0,
    )

st.title("Quick News")

llm = initialize_llm()

news_site = st.text_input("Enter the news site URL:", key="news_site")

def get_latest_news_urls(url, scraper):
    try:
        # Ensure the URL ends with a forward slash
        if not url.endswith('/'):
            url += '/'

        news_urls = scraper.run(url, { 
          "news_links": """
            A list of URLs to the latest news articles on this page. 
            Only include full article links, not category or tag pages. 
            Exclude any links that seem to navigate to pages like FAQ, regulations, terms and services, advertisement, category/list pages, tag pages, search pages, etc. 
            Ensure all items in the list are valid relative/absolute URLs format.
            Return the links as a list of strings.
          """
        })

        # check if news_urls is array of strings then return it, otherwise, check for news_links in the first item
        if isinstance(news_urls, list) and all(isinstance(item, str) for item in news_urls):
            return news_urls[:3]
        elif isinstance(news_urls, dict) and 'news_links' in news_urls:
            return news_urls[0]['news_links'][:3]
        else:
            print(f"Unexpected format for news links: {news_urls}")
            return []
    except Exception as e:
        print(f"Error getting news links from {url}: {str(e)}")
        return []

def summarize_article(news_site, url):
    try:
        # Check if the url is relative
        if not url.startswith("http"):
            url = f"{news_site}{url}"
        start_time = time.time()
        response = requests.get(url, timeout=30)
        end_time = time.time()
        print(f"Time taken to fetch {url}: {end_time - start_time} seconds")
        soup = BeautifulSoup(response.content, 'html.parser')
        
        text_content = soup.get_text()

        summary_prompt = f"""
        Extract the title and description of the news article in Vietnamese from the following HTML content:
        {text_content}
        Exclude article that seem like not about a news but a FAQ, regulations, terms and services, advertisement, category/list pages, tag pages, search pages, etc. If this is a case, return an empty string.
        If you cannot find any information about news article, or cannot process, return an empty string.
        Remove any markdown and format it as a report suitable for speaking.
        Return the title only, followed by the summarized description in about 100 words. Don't return anything else like "this is the title" or "this is the description".
        The language of result must be Vietnamese.
"""
        summary = llm.invoke(summary_prompt).content
        print(summary)
        return summary
    except requests.exceptions.Timeout:
        print(f"Request to {url} timed out. Please try again.")
        st.error("Request timed out. Please try again.")
        st.stop()
    except Exception as e:
        print(f"Error summarizing article {url}: {str(e)}")
        return None, None

def text_to_speech(text, lang):
    tts = gTTS(text=text, lang=lang)
    fp = io.BytesIO()
    tts.write_to_fp(fp)
    fp.seek(0)
    return fp.getvalue()

if "button_disabled" not in st.session_state:
    st.session_state.button_disabled = False

def fetch_news_and_generate_audio():
    try:
        # Access the stored value of news_site
        news_site = st.session_state.news_site
        print("Fetch from news site ", news_site)
        if not is_valid_url(news_site):
            st.error("Invalid URL. Please enter a valid news site URL.")
            st.stop()
        st.session_state.button_disabled = True
        with st.spinner("Cooking..."):
            scraper = Parsera(model=llm)
            news_urls = get_latest_news_urls(news_site, scraper)
            
            if not news_urls:
                # Retry once if no news articles are found
                news_urls = get_latest_news_urls(news_site, scraper)
            
            if news_urls:
                summaries = []
                for url in news_urls:
                    summary = summarize_article(news_site, url)
                    if summary:
                        summaries.append(f"{summary}")
                    time.sleep(1)  # To avoid overwhelming the server
                
                if summaries:
                    # Combine all summaries, filtering out empty ones
                    full_text = "".join([f"{summary} Bài viết tiếp theo." for summary in summaries if summary])                
                
                    print("Begin generate audio")
                    # Generate audio
                    audio_bytes = text_to_speech(full_text, 'vi')
                    print("Done generate audio")
                    
                    # Encode audio to base64
                    b64 = base64.b64encode(audio_bytes).decode()
                    
                    # Display audio player using HTML
                    st.markdown(
                        f'<audio autoplay controls><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>',
                        unsafe_allow_html=True
                    )
                    
                    for summary in summaries:
                        st.write(summary)
                        st.markdown("---")
                else:
                    st.warning("Failed to generate summaries for the articles.")
            else:
                st.warning("No news articles found on the given site after retrying.")
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
    finally:
        st.session_state.button_disabled = False

st.button("Tell me", on_click=fetch_news_and_generate_audio, disabled=st.session_state.button_disabled)
