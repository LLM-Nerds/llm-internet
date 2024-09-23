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


@st.cache_resource
def initialize_llm():
    return ChatGoogleGenerativeAI(
      model="gemini-1.5-flash",
      google_api_key=os.getenv("GOOGLE_API_KEY"),
      temperature=0.0,
    )

st.title("Quick News")

llm = initialize_llm()

news_site = st.text_input("Enter the news site URL:", "https://vatvostudio.vn/")

def get_latest_news_urls(url, scraper):
    try:
        # Ensure the URL ends with a forward slash
        if not url.endswith('/'):
            url += '/'
        
        news_urls = scraper.run(url, { 
            "news_links": "A list of URLs to the latest news articles on this page. Only include full article links, not category or tag pages. Return the links as a list of strings."
        })

        return news_urls[0]['news_links'][:3]
    except Exception as e:
        print(f"Error getting news links from {url}: {str(e)}")
        return []

def summarize_article(news_site, url):
    try:
        # Check if the url is relative
        if not url.startswith("http"):
            url = f"{news_site}{url}"
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        text_content = soup.get_text()

        summary_prompt = f"""
        Extract the title and description of the news article in Vietnamese from the following HTML content:
        {text_content}
        Remove any markdown and format it as a report suitable for speaking.
        Return the title only, followed by the summarized description in about 100 words. Don't return anything else like "this is the title" or "this is the description".
        The language of result must be Vietnamese.
"""
        summary = llm.invoke(summary_prompt).content
        print(summary)
        return summary
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
    st.session_state.button_disabled = True
    with st.spinner("Cooking..."):
        scraper = Parsera(model=llm)
        news_urls = get_latest_news_urls(news_site, scraper)
        
        if news_urls:
            summaries = []
            for url in news_urls:
                summary = summarize_article(news_site, url)
                if summary:
                    summaries.append(f"{summary}")
                time.sleep(1)  # To avoid overwhelming the server
            
            if summaries:
                # Combine all summaries
                full_text = " ".join([f"{summary} Bài viết tiếp theo." for summary in summaries])                
            
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
            st.warning("No news articles found on the given site.")
    st.session_state.button_disabled = False

st.button("Tell me", on_click=fetch_news_and_generate_audio, disabled=st.session_state.button_disabled)
