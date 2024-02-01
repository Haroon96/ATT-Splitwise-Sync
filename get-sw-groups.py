from splitwise import Splitwise
import json

# load auth data
with open('configuration.json') as f:
    config = json.load(f)
    auth = config['authentication']

# create splitwise acc
sw = Splitwise(auth['consumer_key'], auth['consumer_secret'], api_key=auth['api_key'])

# get and print group data
for group in sw.getGroups():
    print(''.ljust(50, '='))
    print("Group name:", group.getName())
    print("Group ID:  ", group.getId())
    print(''.ljust(50, '='))
    for member in group.getMembers():
        print(str(member.getId()).ljust(20), member.getFirstName())
    print()