import os
import requests
import json
import argparse
import re

def run_user_list(file, forks):
    # Reading data back
    with open(file, 'r') as f:
        data = json.load(f)
    for f in forks:
        if f["owner"]["login"] not in data:
            print('{} not found in user list'.format(f["owner"]["login"]))
    for github_id in data:
        found = []
        for f in forks:
            if(re.match(github_id, f["owner"]["login"], re.IGNORECASE)):
                found.append(f["id"])
        num_found = len(found)
        if num_found == 0:
            print("NONE")
        elif num_found == 1:
            print(found[0])
        else:
            print(",".join(found))

if __name__ == "__main__":
    # argparse
    parser = argparse.ArgumentParser(description='Fetch members of an org')
    parser.add_argument('-o','--org', help='filter by org', default=None)
    parser.add_argument('-i','--id', help='id of gist', default="ccd26455c5e6c1f8385655c175d4c3f0")
    parser.add_argument('-s','--secret', help='json credentials (or "none")', default="env")
    parser.add_argument('-u','--userlist', help='print forks for userlist', default=None)
    parser.add_argument('-f','--file', help='user json file instead of live query', default=None)
    args = parser.parse_args()

    if args.file:
        with open(args.file, 'r') as f:
            response = json.load(f)
    else:
        params = {}
        if args.secret.lower() == "env":
            params = {
                "client_id": os.environ['GITHUB_ID'],
                "client_secret": os.environ['GITHUB_SECRET']
            }
        elif args.secret.lower() != "none":
            try:
                with open(args.secret) as json_file:
                    params = json.load(json_file)
            except IOError:
                print("no secret.json file, requests will be unauthenticated")
            except:
                print("secret.json file could not be read, requests will be unauthenticated")

        r = requests.get('https://api.github.com/gists/{}/forks?per_page=100'.format(args.id), params=params)
        print("Fetching: {}".format(r.url))
        response = r.text

    if(args.userlist is not None):
        run_user_list(args.userlist, response)
    else:
        print(response)

    