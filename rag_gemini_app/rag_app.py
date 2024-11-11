"""This module contains the entire functionality of RAG app"""
import os
import io
import google.generativeai as genai
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain.chains.question_answering import load_qa_chain
from langchain.prompts import PromptTemplate
from pymongo import MongoClient
from dotenv import load_dotenv
from PyPDF2 import PdfReader

load_dotenv()
os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# MongoDB Setup
client = MongoClient(os.getenv("MONGODB_URI"))
db = client[os.getenv("MONGODB_DB")]
pdf_collection = db[os.getenv("MONGODB_COLLECTION")]  # Store PDFs in MongoDB


def store_pdf_in_mongodb(pdf_file):
    """Store PDF in MongoDB"""
    pdf_bytes = pdf_file.read()
    pdf_collection.insert_one({"file_name": pdf_file.name, "pdf_data": pdf_bytes})
    print(f"PDF {pdf_file.name} stored in MongoDB.")
    # Logic to handle file input, PDF text extraction, and conversational chain processing
    # pdf_name = "part_b.pdf"  # Modify to handle file input from your backend

    # Open the PDF file and pass the file object to the function
    # with open(pdf_name, 'rb') as pdf_file:
    # store_pdf_in_mongodb(pdf_file)  # Pass the opened file object


def get_pdf_from_mongodb(pdf_name):
    """Fetch the PDF from MongoDB by file name"""
    pdf_doc = pdf_collection.find_one({"file_name": pdf_name})
    if pdf_doc:
        pdf_bytes = pdf_doc["pdf_data"]
        return io.BytesIO(pdf_bytes)  # Return as BytesIO object to be processed
    print(f"No PDF found with name {pdf_name} in MongoDB.")
    return None


def get_pdf_text(pdf_docs):
    """Extract text from PDF documents"""
    text = ""
    for pdf in pdf_docs:
        pdf_reader = PdfReader(pdf)
        for page in pdf_reader.pages:
            text += page.extract_text()
    return text


def get_text_chunks(text):
    """Split text into smaller chunks for processing"""
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=10000, chunk_overlap=1000)
    chunks = text_splitter.split_text(text)
    return chunks


def get_vector_store(text_chunks):
    """ Initiate the embedding and vector storage process """
    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
    vector_store = FAISS.from_texts(text_chunks, embedding=embeddings)
    vector_store.save_local("faiss_index")


def get_conversational_chain():
    """function to involve gemini model and langchain """        
    prompt_template = """
    Answer the question as detailed as possible from the provided context, make sure to provide all the details, if the answer is not in
    provided context just say, "answer is not available in the context", don't provide the wrong answer\n\n
    Context:\n {context}?\n
    Question: \n{question}\n

    Answer:
    """
    model = ChatGoogleGenerativeAI(model="gemini-pro", temperature=0.3)

    prompt = PromptTemplate(
        template=prompt_template, input_variables=["context", "question"]
    )
    chain = load_qa_chain(model, chain_type="stuff", prompt=prompt)

    return chain


def user_input(user_question):
    """function that takes user input and performs further actions"""
    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")

    new_db = FAISS.load_local(
        "faiss_index", embeddings, allow_dangerous_deserialization=True
    )

    docs = new_db.similarity_search(user_question)

    chain = get_conversational_chain()

    response = chain(
        {"input_documents": docs, "question": user_question}, return_only_outputs=True
    )

    return response

def answer_pdf(question,file_name):
    """function to handle entire process"""
    print("Starting process...")

    # Logic to handle file input, PDF text extraction, and conversational chain processing
    # Open the PDF file and pass the file object to the function
    # with open(pdf_name, 'rb') as pdf_file:
    #     store_pdf_in_mongodb(pdf_file)  # Pass the opened file object

    # Fetch PDF from MongoDB
    print(f"Fetching PDF: {file_name} from MongoDB...")
    pdf_file = get_pdf_from_mongodb(file_name)
    if not pdf_file:
        print("PDF not found in MongoDB.")
        return

    # Extract text and generate vector store
    print(f"Extracting text from {file_name}...")
    raw_text = get_pdf_text([pdf_file])  # Pass PDF file as list
    print(
        f"Extracted raw text: {raw_text[:500]}..."
    )  # Print first 500 chars of raw text for debugging

    text_chunks = get_text_chunks(raw_text)
    print(f"Text split into {len(text_chunks)} chunks.")
    get_vector_store(text_chunks)

    # Generating the response
    return user_input(question)