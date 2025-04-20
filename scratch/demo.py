#!/usr/bin/env python
# Graph RAG with Milvus Implementation

# Import common libraries
import os
import numpy as np
import time
import pprint
from tqdm import tqdm

# Set OpenAI API key (replace with your own)
os.environ["OPENAI_API_KEY"] = "your-api-key"

# Import Milvus and related libraries
from pymilvus import MilvusClient
from langchain_openai import OpenAIEmbeddings
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

# Initialize embedding model
embedding_model = OpenAIEmbeddings(model="text-embedding-ada-002")

# Initialize LLM
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

# Constants
ENTITY_COLLECTION = "entity_collection"
RELATION_COLLECTION = "relation_collection"
PASSAGE_COLLECTION = "passage_collection"

# Initialize Milvus client - using Milvus Lite for local development
milvus_client = MilvusClient(uri="./milvus_demo.db")

# Check and drop collections if they exist
for collection_name in [ENTITY_COLLECTION, RELATION_COLLECTION, PASSAGE_COLLECTION]:
    if milvus_client.has_collection(collection_name):
        milvus_client.drop_collection(collection_name)
        print(f"Dropped existing collection: {collection_name}")

# Create collections
# Entity collection for storing entity information
milvus_client.create_collection(
    collection_name=ENTITY_COLLECTION,
    dimension=1536,  # Dimension for OpenAI embeddings
    primary_field_name="id",
    vector_field_name="embedding"
)

# Relation collection for storing relation information
milvus_client.create_collection(
    collection_name=RELATION_COLLECTION,
    dimension=1536,  # Dimension for OpenAI embeddings
    primary_field_name="id",
    vector_field_name="embedding"
)

# Passage collection for storing document passages
milvus_client.create_collection(
    collection_name=PASSAGE_COLLECTION,
    dimension=1536,  # Dimension for OpenAI embeddings
    primary_field_name="id",
    vector_field_name="embedding"
)

# Function to convert text to embeddings
def get_embeddings(texts):
    if not texts:
        return []
    
    embeddings = embedding_model.embed_documents(texts)
    return embeddings

# Sample data (replace with your own data)
# Entities
sample_entities = [
    {"id": 1, "name": "Milvus", "description": "An open-source vector database"},
    {"id": 2, "name": "Vector Database", "description": "A database optimized for vector similarity search"},
    {"id": 3, "name": "RAG", "description": "Retrieval-Augmented Generation, a technique to enhance LLM responses"}
]

# Relations
sample_relations = [
    {"id": 1, "head": "Milvus", "relation": "is a", "tail": "Vector Database"},
    {"id": 2, "head": "Vector Database", "relation": "used for", "tail": "RAG"},
    {"id": 3, "head": "RAG", "relation": "enhances", "tail": "LLM responses"}
]

# Passages
sample_passages = [
    {"id": 1, "text": "Milvus is an open-source vector database built for generative AI applications."},
    {"id": 2, "text": "Vector databases are essential for efficient similarity search in high-dimensional spaces."},
    {"id": 3, "text": "Retrieval-Augmented Generation (RAG) combines retrieval systems with generative models to improve responses."}
]

# Prepare data for insertion
# Entities
entity_records = []
for entity in sample_entities:
    entity_text = f"{entity['name']}: {entity['description']}"
    embedding = get_embeddings([entity_text])[0]
    entity_records.append({
        "id": entity["id"],
        "name": entity["name"],
        "description": entity["description"],
        "embedding": embedding
    })

# Insert entities
if entity_records:
    milvus_client.insert(
        collection_name=ENTITY_COLLECTION,
        data=entity_records
    )
    print(f"Inserted {len(entity_records)} entities into {ENTITY_COLLECTION}")

# Relations
relation_records = []
for relation in sample_relations:
    relation_text = f"{relation['head']} {relation['relation']} {relation['tail']}"
    embedding = get_embeddings([relation_text])[0]
    relation_records.append({
        "id": relation["id"],
        "head": relation["head"],
        "relation": relation["relation"],
        "tail": relation["tail"],
        "embedding": embedding
    })

# Insert relations
if relation_records:
    milvus_client.insert(
        collection_name=RELATION_COLLECTION,
        data=relation_records
    )
    print(f"Inserted {len(relation_records)} relations into {RELATION_COLLECTION}")

# Passages
passage_records = []
for passage in sample_passages:
    embedding = get_embeddings([passage["text"]])[0]
    passage_records.append({
        "id": passage["id"],
        "text": passage["text"],
        "embedding": embedding
    })

# Insert passages
if passage_records:
    milvus_client.insert(
        collection_name=PASSAGE_COLLECTION,
        data=passage_records
    )
    print(f"Inserted {len(passage_records)} passages into {PASSAGE_COLLECTION}")

# Create indexes for each collection
# For entity collection
milvus_client.create_index(
    collection_name=ENTITY_COLLECTION,
    field_name="embedding",
    index_type="HNSW",
    metric_type="COSINE",
    params={"M": 8, "efConstruction": 64}
)

# For relation collection
milvus_client.create_index(
    collection_name=RELATION_COLLECTION,
    field_name="embedding",
    index_type="HNSW",
    metric_type="COSINE",
    params={"M": 8, "efConstruction": 64}
)

# For passage collection
milvus_client.create_index(
    collection_name=PASSAGE_COLLECTION,
    field_name="embedding",
    index_type="HNSW",
    metric_type="COSINE",
    params={"M": 8, "efConstruction": 64}
)

# Load all collections into memory
for collection_name in [ENTITY_COLLECTION, RELATION_COLLECTION, PASSAGE_COLLECTION]:
    milvus_client.load_collection(collection_name)
    print(f"Loaded collection: {collection_name}")

# Graph RAG implementation
def graph_rag_search(query, top_k=3):
    """
    Implements Graph RAG search:
    1. Find related entities in the entity collection
    2. Find related relations in the relation collection
    3. Use the entities and relations to expand query context
    4. Search for passages with the expanded context
    5. Return the most relevant passages
    """
    query_embedding = get_embeddings([query])[0]
    
    # Step 1: Search for relevant entities
    entity_results = milvus_client.search(
        collection_name=ENTITY_COLLECTION,
        data=[query_embedding],
        output_fields=["name", "description"],
        limit=top_k
    )
    
    # Step 2: Search for relevant relations
    relation_results = milvus_client.search(
        collection_name=RELATION_COLLECTION,
        data=[query_embedding],
        output_fields=["head", "relation", "tail"],
        limit=top_k
    )
    
    # Step 3: Expand query with entities and relations
    entity_context = []
    for hits in entity_results:
        for hit in hits:
            entity_context.append(f"{hit['entity']['name']}: {hit['entity']['description']}")
    
    relation_context = []
    for hits in relation_results:
        for hit in hits:
            relation_context.append(f"{hit['entity']['head']} {hit['entity']['relation']} {hit['entity']['tail']}")
    
    # Create expanded context
    expanded_context = f"""
    Entities:
    {'. '.join(entity_context)}
    
    Relations:
    {'. '.join(relation_context)}
    
    Query: {query}
    """
    
    expanded_embedding = get_embeddings([expanded_context])[0]
    
    # Step 4: Search for passages with expanded context
    final_results = milvus_client.search(
        collection_name=PASSAGE_COLLECTION,
        data=[expanded_embedding],
        output_fields=["text"],
        limit=top_k
    )
    
    return final_results

# Compare with naive RAG
def naive_rag_search(query, top_k=3):
    """
    Implements naive RAG search by directly searching the passage collection
    """
    query_embedding = get_embeddings([query])[0]
    
    results = milvus_client.search(
        collection_name=PASSAGE_COLLECTION,
        data=[query_embedding],
        output_fields=["text"],
        limit=top_k
    )
    
    return results

# RAG generation with LLM
def generate_response(query, retrieved_context):
    """
    Generate a response using the LLM with the retrieved context
    """
    context_text = ". ".join([hit['entity']['text'] for hits in retrieved_context for hit in hits])
    
    prompt = ChatPromptTemplate.from_template(
        """You are an AI assistant helping with questions about vector databases and RAG.
        
        Context information:
        {context}
        
        Answer the following question based on the context information:
        Question: {question}
        
        Give a comprehensive and helpful response.
        """
    )
    
    chain = (
        prompt 
        | llm 
        | StrOutputParser()
    )
    
    response = chain.invoke({"context": context_text, "question": query})
    return response

# Example usage
if __name__ == "__main__":
    # Test query
    query = "How can Milvus be used for RAG systems?"
    
    print("=== Testing Graph RAG vs Naive RAG ===")
    
    # Graph RAG
    print("\n=== Graph RAG Results ===")
    graph_results = graph_rag_search(query)
    for i, hits in enumerate(graph_results):
        print(f"Results for query {i+1}:")
        for j, hit in enumerate(hits):
            print(f"Top {j+1}: {hit['entity']['text']} (Score: {hit['score']})")
    
    # Naive RAG
    print("\n=== Naive RAG Results ===")
    naive_results = naive_rag_search(query)
    for i, hits in enumerate(naive_results):
        print(f"Results for query {i+1}:")
        for j, hit in enumerate(hits):
            print(f"Top {j+1}: {hit['entity']['text']} (Score: {hit['score']})")
    
    # Generate response with Graph RAG
    print("\n=== Generated Response using Graph RAG ===")
    response = generate_response(query, graph_results)
    print(response)
