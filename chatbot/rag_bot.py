import fitz  # PyMuPDF
from google import genai
import numpy as np
import faiss
import pickle
import os


client = genai.Client(api_key='AIzaSyA6CLXP')

# --- PDF loading and chunking ---
def load_pdf_single_column(path):
    doc = fitz.open(path)
    full_text = ""
    for page in doc:
        blocks = page.get_text("blocks")
        blocks.sort(key=lambda b: b[1])
        page_text = ""
        for b in blocks:
            text = b[4].strip()
            if text:
                page_text += text + "\n"
        full_text += page_text + "\n"
    return full_text

def chunk_text(text, chunk_size=300, overlap=50):
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start += chunk_size - overlap
    return chunks

# --- Embeddings ---
def get_embeddings(chunks):
    embeddings = []
    for chunk in chunks:
        response = client.models.embed_content(
            model="gemini-embedding-001",
            contents=chunk
        )
        embeddings.append(response.embeddings[0].values)
    return embeddings

# --- FAISS index ---
def create_faiss_index(embeddings):
    dimension = len(embeddings[0])
    index = faiss.IndexFlatL2(dimension)
    index.add(np.array(embeddings, dtype='float32'))
    return index

def save_index(index, chunks, index_file="vector_index.faiss", chunks_file="chunks.pkl"):
    faiss.write_index(index, index_file)
    with open(chunks_file, "wb") as f:
        pickle.dump(chunks, f)

# --- Retrieve relevant chunks using FAISS ---
def retrieve_relevant_chunks(query, index, chunks, top_k=5):
    # Embed the query
    query_resp = client.models.embed_content(
        model="gemini-embedding-001",
        contents=query
    )
    query_vector = np.array([query_resp.embeddings[0].values], dtype='float32')

    # Search in FAISS
    distances, indices = index.search(query_vector, top_k)

    # Get the corresponding chunks
    relevant_chunks = [chunks[i] for i in indices[0]]
    return "\n".join(relevant_chunks)


# --- Example usage ---
pdf_folder = "./docs"
chunks = []

for filename in os.listdir(pdf_folder):
    if filename.endswith(".pdf"):
        pdf_path = os.path.join(pdf_folder, filename)
        text = load_pdf_single_column(pdf_path)
        chunks = chunk_text(text)
        chunks.extend(chunks)

embeddings = get_embeddings(chunks)
index = create_faiss_index(embeddings)
save_index(index, chunks)

# function to ask a question
def ask_question_and_print(question, index, chunks, top_k=3):
    # Retrieve the relevant chunks
    relevant_text = retrieve_relevant_chunks(question, index, chunks, top_k=top_k)
    
    # Get the answer using GPT
    prompt = f"""
    You are an expert career assistant. Using the resume/CV information below, answer the following question accurately:

    Question:
    {question}

    Resume/CV Information:
    {relevant_text}

    Instructions:
    - Answer concisely and to the point but clearly.
    - Only use information from the resume/CV.
    """
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    
    print(f"\n--- Question ---\n{question}\n")
    print(f"--- Answer ---\n{response.text}\n")


# --- Example usage ---
ask_question_and_print("Which projects demonstrate user experience in Large models?", index, chunks)
ask_question_and_print("Do user have experience in chemistry?", index, chunks)

