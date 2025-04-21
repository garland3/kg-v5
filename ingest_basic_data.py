import os
import requests
import json
import argparse # Added argparse
from tqdm import tqdm

# Base URL for the API
BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

def read_text_file(file_path):
    """Read content from a text file."""
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()

def extract_knowledge_graph(text: str, project_id: int, user_email: str):
    """Call the extract endpoint to extract knowledge graph from text for a specific project."""
    url = f"{BASE_URL}/api/kg/extract"
    headers = {
        "Content-Type": "application/json",
        "X-User-Email": user_email # Use provided user email for auth
    }
    params = {"project_id": project_id} # Pass project_id as query parameter
    payload = {"text": text}
    
    print(f"  Extracting KG for project {project_id}...")
    response = requests.post(url, headers=headers, params=params, json=payload)
    
    if response.status_code != 200:
        print(f"Error extracting knowledge graph: {response.text}")
        return None
    
    # Return only the relevant parts (entities, relationships)
    data = response.json()
    return {
        "entities": data.get("entities", []),
        "relationships": data.get("relationships", [])
    }

def store_knowledge_graph(kg_data: dict, project_id: int, user_email: str):
    """Call the store endpoint to store the knowledge graph in Neo4j for a specific project."""
    url = f"{BASE_URL}/api/kg/store"
    headers = {
        "Content-Type": "application/json",
        "X-User-Email": user_email # Use provided user email for auth
    }
    params = {"project_id": project_id} # Pass project_id as query parameter
    
    print(f"  Storing KG for project {project_id}...")
    response = requests.post(url, headers=headers, params=params, json=kg_data)
    
    if response.status_code != 200:
        print(f"Error storing knowledge graph: {response.text}")
        return None
    
    return response.json()

def process_file(file_path: str, project_id: int, user_email: str):
    """Process a single text file by extracting and storing its knowledge graph for a specific project."""
    # Read the file content
    text = read_text_file(file_path)
    
    # Extract knowledge graph
    kg_data = extract_knowledge_graph(text, project_id, user_email)
    if kg_data is None: # Check for None explicitly
        print(f"  Extraction failed for {os.path.basename(file_path)}")
        return False
        
    # Check if extraction actually returned entities/relationships
    if not kg_data.get("entities") and not kg_data.get("relationships"):
        print(f"  No entities or relationships extracted from {os.path.basename(file_path)}")
        # Decide if this counts as success or failure - let's say success as the process ran
        return True 
        
    # Store knowledge graph
    result = store_knowledge_graph(kg_data, project_id, user_email)
    if result is None: # Check for None explicitly
        print(f"  Storing failed for {os.path.basename(file_path)}")
        return False
    
    return True

def main(project_id: int, user_email: str):
    """Main function to process all text files in the test_text folder for a specific project."""
    # Path to the test_text folder
    test_text_folder = "test_text"
    
    # Basic check for user_email
    if not user_email or '@' not in user_email:
        print("Error: A valid user email must be provided via --user-email or USER_EMAIL environment variable.")
        exit(1)
    
    # Get all .txt files in the folder
    txt_files = [
        os.path.join(test_text_folder, f) 
        for f in os.listdir(test_text_folder) 
        if f.endswith('.txt')
    ]
    
    # Process each file with a progress bar
    successful = 0
    failed = 0
    
    print(f"Found {len(txt_files)} text files to process for Project ID: {project_id}")
    
    for file_path in tqdm(txt_files, desc="Processing files"):
        file_name = os.path.basename(file_path)
        # print(f"\nProcessing {file_name}...") # tqdm provides progress
        
        if process_file(file_path, project_id, user_email):
            successful += 1
            # print(f"Successfully processed {file_name}")
        else:
            failed += 1
            # print(f"Failed to process {file_name}")
    
    print(f"\nProcessing complete for Project ID {project_id}: {successful} successful, {failed} failed")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest text data into the knowledge graph API for a specific project.")
    parser.add_argument(
        "--project-id", 
        type=int, 
        default=1, 
        help="The ID of the project to ingest data into."
    )
    parser.add_argument(
        "--user-email", 
        type=str, 
        default=os.getenv("USER_EMAIL", "test@example.com"), # Get email from env var or default
        help="The email address of the user performing the ingestion (for authorization and tracking)."
    )
    
    args = parser.parse_args()
    
    print(f"Starting ingestion for Project ID: {args.project_id} as User: {args.user_email}")
    main(args.project_id, args.user_email)
