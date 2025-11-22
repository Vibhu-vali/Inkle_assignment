import requests
import json

API_URL = "http://localhost:8000/api/tourism/query"

def test_api():
    print("Testing Tourism API...")
    print("=" * 50)
    
    # Test 1: Weather only
    print("\n1. Testing Weather Query:")
    response = requests.post(API_URL, json={"place": "I am going to Bangalore, what is the temperature there"})
    print(json.dumps(response.json(), indent=2))
    
    # Test 2: Places only
    print("\n2. Testing Places Query:")
    response = requests.post(API_URL, json={"place": "I am going to Bangalore, lets plan my trip"})
    print(json.dumps(response.json(), indent=2))
    
    # Test 3: Both weather and places
    print("\n3. Testing Combined Query:")
    response = requests.post(API_URL, json={"place": "I am going to Bangalore, what is the temperature there? And what are the places I can visit?"})
    print(json.dumps(response.json(), indent=2))
    
    # Test 4: Non-existent place
    print("\n4. Testing Non-existent Place:")
    response = requests.post(API_URL, json={"place": "I am going to NonexistentCity123"})
    print(json.dumps(response.json(), indent=2))

if __name__ == "__main__":
    test_api()
