# test_neo4j_api.py
import requests
import json

BASE_URL = "http://localhost:8000"

def test_create_person():
    print("\n=== Testing Person Creation ===")
    
    # Create a few test people
    people = [
        {"name": "Alice Smith", "age": 32, "email": "alice@example.com"},
        {"name": "Bob Johnson", "age": 28, "email": "bob@example.com"},
        {"name": "Charlie Davis", "age": 45, "email": "charlie@example.com"}
    ]
    
    created_people = []
    for person in people:
        response = requests.post(f"{BASE_URL}/people/", json=person)
        if response.status_code == 200:
            created = response.json()
            created_people.append(created)
            print(f"Created: {created['name']} with ID: {created['id']}")
        else:
            print(f"Error creating person: {response.text}")
    
    return created_people

def test_get_all_people():
    print("\n=== Testing Get All People ===")
    
    response = requests.get(f"{BASE_URL}/people/")
    if response.status_code == 200:
        people = response.json()
        print(f"Found {len(people)} people:")
        for person in people:
            print(f"  - {person['name']} (ID: {person['id']})")
        return people
    else:
        print(f"Error getting people: {response.text}")
        return []

def test_get_person(person_id):
    print(f"\n=== Testing Get Person by ID: {person_id} ===")
    
    response = requests.get(f"{BASE_URL}/people/{person_id}")
    if response.status_code == 200:
        person = response.json()
        print(f"Retrieved: {person['name']}, Age: {person['age']}, Email: {person['email']}")
        return person
    else:
        print(f"Error getting person: {response.text}")
        return None

def test_update_person(person_id):
    print(f"\n=== Testing Update Person ID: {person_id} ===")
    
    update_data = {"age": 33, "email": "updated@example.com"}
    response = requests.put(f"{BASE_URL}/people/{person_id}", json=update_data)
    
    if response.status_code == 200:
        updated = response.json()
        print(f"Updated: {updated['name']}, New Age: {updated['age']}, New Email: {updated['email']}")
        return updated
    else:
        print(f"Error updating person: {response.text}")
        return None

def test_create_relationship(person1_id, person2_id, relationship_type):
    print(f"\n=== Testing Create Relationship ===")
    
    relationship_data = {
        "person1_id": person1_id,
        "person2_id": person2_id,
        "relationship_type": relationship_type
    }
    
    response = requests.post(f"{BASE_URL}/relationships/", json=relationship_data)
    if response.status_code == 200:
        result = response.json()
        print(f"Relationship created: {result['message']}")
        return True
    else:
        print(f"Error creating relationship: {response.text}")
        return False

def test_get_relationships(person_id):
    print(f"\n=== Testing Get Relationships for Person ID: {person_id} ===")
    
    response = requests.get(f"{BASE_URL}/people/{person_id}/relationships")
    if response.status_code == 200:
        relationships = response.json()
        print(f"Found {len(relationships)} relationships:")
        for rel in relationships:
            print(f"  - {rel['relationship_type']} → {rel['related_person_name']}")
        return relationships
    else:
        print(f"Error getting relationships: {response.text}")
        return []

def test_delete_person(person_id):
    print(f"\n=== Testing Delete Person ID: {person_id} ===")
    
    response = requests.delete(f"{BASE_URL}/people/{person_id}")
    if response.status_code == 200:
        result = response.json()
        print(f"Result: {result['message']}")
        return True
    else:
        print(f"Error deleting person: {response.text}")
        return False

def run_all_tests():
    # Create test people
    people = test_create_person()
    if not people or len(people) < 2:
        print("Not enough people created to test relationships. Exiting.")
        return
    
    # Get all people
    test_get_all_people()
    
    # Get a specific person
    test_get_person(people[0]["id"])
    
    # Update a person
    test_update_person(people[0]["id"])
    
    # Create a relationship
    test_create_relationship(people[0]["id"], people[1]["id"], "KNOWS")
    
    # Get relationships
    test_get_relationships(people[0]["id"])
    
    # Delete the third person (if created)
    if len(people) > 2:
        test_delete_person(people[2]["id"])
    
    print("\n=== All tests completed ===")

if __name__ == "__main__":
    run_all_tests()
