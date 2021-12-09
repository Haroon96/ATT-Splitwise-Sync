from splitwise import Splitwise
import json

with open('configuration.json') as f:
    config = json.load(f)
    auth = config['authentication']

sw = Splitwise(auth['consumer_key'], auth['consumer_secret'], api_key=auth['api_key'])

for group in sw.getGroups():
    for member in group.getMembers():
        print(member.getId(), member.getFirstName())