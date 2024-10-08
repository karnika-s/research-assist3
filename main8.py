from datetime import datetime
import streamlit as st
import os
import pdfplumber
from langchain_groq import ChatGroq
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains import create_retrieval_chain
from langchain_community.vectorstores import FAISS
import time
from gtts import gTTS
import base64
from dotenv import load_dotenv
import pickle

# Load environment variables
load_dotenv()
os.environ['GROQ_API_KEY'] = os.getenv("GROQ_API_KEY")
groq_api_key = os.getenv("GROQ_API_KEY")

# Use Hugging Face embeddings
os.environ['HF_TOKEN'] = os.getenv("HF_TOKEN")
from langchain_huggingface import HuggingFaceEmbeddings
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

# Create LLM model
llm = ChatGroq(groq_api_key=groq_api_key, model_name="Llama3-8b-8192", max_tokens=1024)

prompt = ChatPromptTemplate.from_template(
    """
    Answer the questions based on the provided context only.
    Please provide the most accurate response based on the question from the research_papers
    <context>
    {context}
    <context>
    Question: {input}
    """
)

# Create a simple Document-like class
class SimpleDocument:
    def __init__(self, text, metadata=None):
        self.page_content = text
        # self.metadata = metadata if metadata is not None else {}

# Function to create vector embeddings
def create_vector_embedding():
    if "vectors" not in st.session_state:
        st.session_state.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

        # Load PDF documents using pdfplumber
        documents = []
        pdf_directory = "research_papers"
        for filename in os.listdir(pdf_directory):
            if filename.endswith(".pdf"):
                pdf_path = os.path.join(pdf_directory, filename)
                with pdfplumber.open(pdf_path) as pdf:
                    for page in pdf.pages:
                        text = page.extract_text()
                        if text:
                            documents.append(SimpleDocument(text))

        st.session_state.docs = documents
        st.session_state.text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        st.session_state.final_documents = st.session_state.text_splitter.split_documents(st.session_state.docs[:50])
        st.session_state.vectors = FAISS.from_documents(st.session_state.final_documents, st.session_state.embeddings)

# Function to save the FAISS index
def save_faiss_index(faiss_index, filepath="faiss_index.pkl"):
    with open(filepath, "wb") as f:
        pickle.dump(faiss_index, f)
    # st.write("FAISS index saved to", filepath)
    st.write("Vector DB is ready...")


# Function to load the FAISS index
def load_faiss_index(filepath="faiss_index.pkl"):
    with open(filepath, "rb") as f:
        return pickle.load(f)
    

# Initialize chat history in session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

st.title("😎 My Research Assistant")

# Check if FAISS index already exists
if "vectors" not in st.session_state:
    if os.path.exists("faiss_index.pkl"):
        st.session_state.vectors = load_faiss_index()
        st.write("FAISS index loaded from file")
    else:
        create_vector_embedding()  # Function to create the FAISS index
        save_faiss_index(st.session_state.vectors)
    st.write("Vector Database is ready")


# # Callback function to clear the input box
# def clear_input():
#     st.session_state.input_box = ""


# Text input with key for resetting
user_prompt = st.text_input("Ask your questions related to Drupal, AWS, Moodle or Generative AI", key="input_box")

# Process the user prompt and generate a response
if user_prompt:
    timestamp1 = datetime.now().strftime("%d-%m-%Y")
    timestamp2 = datetime.now().strftime("%H:%M:%S")
    
    document_chain = create_stuff_documents_chain(llm, prompt)
    retriever = st.session_state.vectors.as_retriever()
    retrieval_chain = create_retrieval_chain(retriever, document_chain)

    start_time = time.process_time()
    response = retrieval_chain.invoke({'input': user_prompt})
    response_time = time.process_time() - start_time

    st.session_state.chat_history.append({
        "user": user_prompt,
        "bot": response['answer'],
        "timestamp2": timestamp2,
        "timestamp1": timestamp1
    })

    st.text_area("Response", value=response['answer'], height=200)
    st.write(f"Responded in: {response_time:.2f} seconds")

    # Callback function to clear the input box
    # def clear_input():
    #     st.session_state.input_box = ""

    st.markdown("<h6>Listen to the response here:</h6>", unsafe_allow_html=True)
    audio_placeholder = st.empty()

    tts = gTTS(text=response['answer'], lang='en')
    audio_file_path = "response.mp3"
    tts.save(audio_file_path)

    with open(audio_file_path, "rb") as audio_file:
        audio_b64 = base64.b64encode(audio_file.read()).decode()
        audio_html = f"""
        <audio controls>
            <source src="data:audio/mp3;base64,{audio_b64}" type="audio/mp3">
            Your browser does not support the audio element.
        </audio>
        """
        audio_placeholder.markdown(audio_html, unsafe_allow_html=True)


    with st.sidebar:
        st.markdown("<h2 style='text-decoration: underline; color:green;'>Chat History</h2>", unsafe_allow_html=True)
        for chat in reversed(st.session_state.chat_history):
            st.write(f"**Asked at**: {chat['timestamp2']}, {chat['timestamp1']}")
            st.write(f"**You**: {chat['user']}")
            st.write(f"**Assistant**: {chat['bot']}")
            st.write("---")

    with st.expander("Document Similarity Search"):
        for i, doc in enumerate(response['context']):
            st.write(doc)
            st.write('------------------------')
    
    # # Clear the input box after response is generated
    # st.session_state.input_box = ""
    # st.experimental_rerun()

    # Clear the input box after response is generated
    # st.button("Clear", on_click=clear_input)


# Custom CSS to pin text to the bottom
footer = """
<style>
    .footer {
        position: sticky;
        bottom: 0;
        left: 0;
        width: 100%;
        font-size: 8px;
        color: grey;
        text-align: center;
    }
</style>
<div class="footer">
<br>
<br>
<br>
<br>
    <p>Created using Groq, Hugging Face, FAISS & Langchain</p>
</div>
"""

st.write(footer, unsafe_allow_html=True)
