
from googleapiclient.discovery import build
import os
# define the build_search_request function

def build_search_request(query, apiKey, cseID):
    service = build('customsearch', 'v1', developerKey=apiKey)
    return service.cse().list(q=query, cx=cseID, num=3)

# define the execute_search function
def execute_search(request):
    try:
        return request.execute()
    except Exception as e:
        print('An error occurred: ', e)

# define the process_search_results function
def process_search_results(response):
    try:
        # Extract search results
        searchResults = response['items']
        # Format and return
        print(response)        

        return searchResults
    except KeyError:
        print('No search results found')
    except Exception as e:
        print('An error occurred: ', e)


def google_api_search(query):
     # Initiate Google API request
     request = build_search_request(query,os.getenv('GOOGLE_API_KEY'), '57fa4627dc0c54546')
     # Execute the search
     response = execute_search(request)
     # Process search results
     return process_search_results(response)

