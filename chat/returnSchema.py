def build_tree_str(data, level=0, result=''):
    if isinstance(data, list):
        for item in data:
            result = build_tree_str(item, level, result)
    elif isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, dict):
                description = v.get('description', '')[ 0: 50] + '...'
                actions = ', '.join(v.get('actions', []))
                id = v.get('id', '')
                keywords = v.get('keywords', [])
                if v.get('minimised', False) == False:
                    result += '-' * level + f'{k} | id: {id} | {description} | keywords: {str(keywords)} | actions : {actions}\n'
                    if 'elements' in v:
                        result = build_tree_str(v['elements'], level+2, result)
                    else:
                        result = build_tree_str(v, level+2, result)
                else:
                    result += '-' * level + f'{k} | id: {id} | {description} | keywords: {str(keywords)}| actions : {actions}\n'
            elif isinstance(v, list):
                for i in v:
                    result = build_tree_str(i, level, result)
            else:
                result += '-' * level + f'{k}: {v}\n'

    return str(result)

