import requests
from openai import OpenAI
import hashlib
from src.memory import get_collection, store, recall, pdf_ingest

# Connect (or reconnect) to the database
collection = get_collection()

# Feed a PDF once — re-running is safe due to upsert + deterministic IDs
pdf_ingest(collection, "data/ISENÇÃO IR.pdf", source_name="ISENÇÃO IR.pdf")

# Store a conversation turn
# store(
#     collection=collection,
#     text="User: My name is Ana and I love hiking.",
#     metadata={"source": "conversation", "role": "user"},
#     doc_id=hashlib.md5(b"user::ana introduction").hexdigest()
# )

# Query — ChromaDB finds the most semantically similar chunks
results = recall(collection, query="O que os documentos falam sobre isenção de IR sobre salário?", n_results=3)
for r in results:
    print(f"[score {r['score']:.2f}] ({r['metadata']['source']}) {r['text'][:80]}...")

# Use results to build a prompt for your local SLM
context = "\n".join(f"- {r['text']}" for r in results)
question = "What is the new 'isenção de IR' for a R$ 5000 salary?"
prompt = f"""
    PERSONA: You are a document retrieval tool and financial assistant. Your only job is to copy relevant information from the context below:
    RULES:
        1 - ONLY use information from the CONTEXT section.
        2 - If the answer is not part of the CONTEXT, reply exactly: "Information not found from source documents."
        3 - Do not explain, interpret or add anything.

    CONTEXT:
        {context}

    QUESTION:
        {question}

    ANSWER (from context only):
"""

client = OpenAI(base_url=f"http://127.0.0.1:1234/v1", api_key="")

completion = client.chat.completions.create(
    model="local_model",
    messages=[
        {"role": "system", "content": context},
        {"role": "user", "content": prompt}
    ],
    temperature=0.6
)

# print(completion.choices[0].message.content)
response_content = completion.choices[0].message.content

print(response_content)