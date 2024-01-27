
from googleapiclient.discovery import build
import os
# define the build_search_request function

def build_search_request(query, apiKey, cseID):
    service = build('customsearch', 'v1', developerKey=apiKey)
    return service.cse().list(q=query, cx=cseID, num=10)

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
     return parse_to_nodes(response)

def parse_to_nodes(response):
    items = response.get('items')
    content = []
    parent = {
        'type':'google_search',
        'content':content
    }

    for item in items:
        if item.get('title'):
            content.append({
                'type':'heading',
                'attrs':{
                    'level':3
                },
                'content':[
                    {
                    'type':'text',    
                    'text':item['title'],
                    'marks':[
                        { 
                            'type':'link',
                            'attrs' :{'href':item['link']}

                        }
                    ]}
                ]
            })
        if item.get('snippet'):
            content.append({
                'type':'text',
                'text':item['snippet'],
            })
        if item.get('displayLink'):
            content.append({
                'type':'text',
                'text':item['displayLink'],
                'marks':[
                    { 
                        'type':'link',
                        'attrs' :{'href':item['link']}

                    }
                ]
            })
    return parent

    