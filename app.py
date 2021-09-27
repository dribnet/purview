import os
import time
import json
import re
from flask import Flask, Response, url_for
from flask import render_template
import requests
from werkzeug.contrib.cache import SimpleCache
from flask_cache_response_decorator import cache

app = Flask(__name__)
app.config.from_object(os.environ['APP_SETTINGS'])

# auth_params = {
#     "client_id": os.environ['GITHUB_ID'],
#     "client_secret": os.environ['GITHUB_SECRET']
# }

auth_token = os.environ['GITHUB_TOKEN']
auth_headers = {'Authorization': f'token {auth_token}'}

state_open_params = {
    "state": "open",
}

# todo: deployed should be memcached
server_cache = SimpleCache()

default_timeout = 5 * 60
cache_timeout = default_timeout
if 'DEVELOPMENT' in app.config:
    default_timeout = 1
    cache_timeout = None
print("Default timeout is {}".format(default_timeout))

@app.route('/')
def hello():
    return render_template("home.html")

@app.route('/archive')
def archive():
    return render_template("archive.html")

@app.route('/settings')
def get_settings():
    return "APP_SETTINGS: {}".format(os.environ['APP_SETTINGS'])

def fetch_and_cache_json(raw_get_fn, args, cache_key):
    rv = server_cache.get(cache_key)
    if rv is None:
        rv = raw_get_fn(args)
        r_json = json.loads(rv)
        cache_time = time.ctime()
        r_package = {
            "payload": r_json,
            "cachetime": cache_time
        }
        rv = json.dumps(r_package)
        server_cache.set(cache_key, rv, timeout=default_timeout)
    return rv

def nested_extract(m, key):
    keys = key.split("/")
    cur_m = m
    for k in keys:
        cur_m = cur_m[k]
    return cur_m

def fetch_filtered_json(raw_get_fn, args, cache_key, filter_keys):
    if cache_key == None:
        rv = raw_get_fn(args)
        raw_list = json.loads(rv)
    else:
        rv = fetch_and_cache_json(raw_get_fn, args, cache_key)
        raw_list = json.loads(rv)["payload"]
    filtered_list = []
    for e in raw_list:
        filtered_list.append({ k: nested_extract(e,k) for k in filter_keys })
    return json.dumps(filtered_list)

# here is the core time api
def time_get_raw_json(args):
    return '[{{"time": "{}"}}]'.format(time.ctime())

time_keys = [ "time" ]
time_cache_key = "time"

# route that is live (dynamic)
@app.route("/time.raw.live.json")
def get_time_live():
    return time_get_raw_json(None)

@app.route("/time.raw.json")
@cache(cache_timeout)
def get_time_raw():
    return fetch_and_cache_json(time_get_raw_json, None, time_cache_key)

@app.route("/time.live.json")
def get_time_live_json():
    return fetch_filtered_json(time_get_raw_json, None, None, time_keys)

@app.route("/time.json")
@cache(cache_timeout)
def get_time_json():
    return fetch_filtered_json(time_get_raw_json, None, time_cache_key, time_keys)

@app.route("/time.live.html")
def get_time_live_html():
    j = fetch_filtered_json(time_get_raw_json, None, None, time_keys)
    return render_template("time.html",
                           time=j)

@app.route("/time.html")
@cache(cache_timeout)
def get_time_html():
    j = fetch_filtered_json(time_get_raw_json, None, time_cache_key, time_keys)
    return render_template("time.html",
                           time=j)

with open('names.json') as json_data:
    member_names = json.load(json_data)

### eg: http://localhost:5000/members/vusd-mddn342-2016.html ###
### now do something similar for "org members"
def populate_names_slow(json_text):
    members = json.loads(json_text)
    for i in range(len(members)):
        member = members[i]
        r = requests.get('https://api.github.com/users/{}'.format(member["login"]), headers=auth_headers, params=state_open_params)
        user_info = json.loads(r.text)
        if user_info["name"] is not None:
            members[i]["name"] = user_info["name"]
        else:
            members[i]["name"] = "({})".format(member["login"])
        print("User info for {} is {}".format(member["login"], user_info["name"]))
    return json.dumps(members)

def populate_names(json_text):
    members = json.loads(json_text)
    new_members = []
    for i in range(len(members)):
        if members[i]["login"] in member_names:
            members[i]["name"] = member_names[members[i]["login"]]
            new_members.append(members[i])
        # else:
        #     members[i]["name"] = members[i]["login"]

    return json.dumps(new_members)

# here is the core org members api
def members_get_raw_json(org):
    r = requests.get('https://api.github.com/orgs/{}/members?per_page=100'.format(org), headers=auth_headers, params=state_open_params)
    return populate_names(r.text)

members_keys = ["login", "name", "avatar_url", "html_url"]
def members_cache_key(org):
    return "members/{}".format(org)

# route that is live (dynamic)
@app.route("/members/<org>.raw.live.json")
def get_members_raw_live(org):
    return members_get_raw_json(org)

@app.route("/members/<org>.raw.json")
@cache(cache_timeout)
def get_members_raw(org):
    return fetch_and_cache_json(members_get_raw_json, org, members_cache_key(org))

@app.route("/members/<org>.live.json")
def get_members_live_json(org):
    return fetch_filtered_json(members_get_raw_json, org, None, members_keys)

@app.route("/members/<org>.json")
@cache(cache_timeout)
def get_members_json(org):
    return fetch_filtered_json(members_get_raw_json, org, members_cache_key(org), members_keys)

@app.route("/members/<org>.live.html")
def get_members_live_html(org):
    j = fetch_filtered_json(members_get_raw_json, org, None, members_keys)
    members = json.loads(j)
    rows = [list(members[i:i+6]) for i in range(0, len(members), 6)]
    return render_template("members.html",
                           org=org, rows=rows)

@app.route("/members/<org>.html")
@cache(cache_timeout)
def get_members_html(org):
    return get_members_live_html(org)

### should now be easy to add "list gist forks"

def forks_get_raw_json(gist_id):
    r = requests.get('https://api.github.com/gists/{}'.format(gist_id), headers=auth_headers, params=state_open_params)
    api_text = r.text
    r = requests.get('https://api.github.com/gists/{}/forks?per_page=100'.format(gist_id), headers=auth_headers, params=state_open_params)
    forks_text = r.text
    return '{"forks":' + forks_text + ', "api":' + api_text + '}'

forks_keys = ["id", "owner/login", "owner/avatar_url", "owner/html_url"]
def forks_cache_key(gist_id):
    return "forks/{}".format(gist_id)

@app.route("/forks/<gist_id>.raw.json")
@cache(cache_timeout)
def get_forks_raw(gist_id):
    return fetch_and_cache_json(forks_get_raw_json, gist_id, forks_cache_key(gist_id))

def forks_to_records(gist_id, login, desc, forks, api):
    meta = {
        "login": login,
        "id": gist_id,
        "description": desc,
        "blocks_link": js_settings["blocks_run_root"] + login + "/" + gist_id
    }
    all_forks = [api] + forks
    records = [{
            "login": f["owner"]["login"],
            "avatar_url": f["owner"]["avatar_url"],
            "id": f["id"],
            "description": f["description"],
            "created_at": f["created_at"],
            "updated_at": f["updated_at"]
        } for f in all_forks]
    return {"meta": meta, "records": records}

def get_converted_forks(gist_id):
    json_str = fetch_and_cache_json(forks_get_raw_json, gist_id, forks_cache_key(gist_id))
    d = json.loads(json_str)
    payload = d["payload"]
    login = payload["api"]["owner"]["login"]
    desc = payload["api"]["description"]
    return forks_to_records(gist_id, login, desc, payload["forks"], payload["api"])

@app.route("/forks/<gist_id>.json")
@cache(cache_timeout)
def get_forks_json(gist_id):
    return json.dumps(get_converted_forks(gist_id))

@app.route("/forks/<gist_id>.html")
@cache(cache_timeout)
def get_forks_html(gist_id):
    d = get_converted_forks(gist_id)
    j = json.dumps(d)
    return render_template("forks.html", json=j,
        meta=d["meta"], num_versions=len(d["records"]),
        js_settings=js_settings, gist_id=gist_id)

assignment_table = {}
def get_assignment(assign_id):
    if not assign_id in assignment_table:
        with open("{}.json".format(assign_id)) as json_data:
            assign_data = json.load(json_data)
        assignment_table[assign_id] = assign_data
    return assignment_table[assign_id]

@app.route("/assignment/<assign_id>.html")
# @cache(cache_timeout)
def get_assignment_html(assign_id):
    d = get_assignment(assign_id)
    j = json.dumps(d)
    return render_template("assignment.html", json=j,
        meta=d["meta"], num_versions=len(d["records"]),
        js_settings=js_settings, assignment_id=assign_id)

# here is the core purview versions api
# this could be set from env, etc. in future
# broken "purview_file_root": "http://purview-blocks.herokuapp.com/"
js_settings = {
    "blocks_run_root": "https://bl.ocks.org/",
    "purview_file_root": "https://bl.ocks.org/"
}

def gist_branch_to_sha(gist_id, gist_branch):
    r = requests.get('https://api.github.com/gists/{}/{}'.format(gist_id, gist_branch), stream=True, headers=auth_headers, params=state_open_params)
    content = r.raw.read(256, decode_content=True).decode("utf-8")
    if content.startswith('{"url":'):
        match = re.search('^{"url":"([^"]*)"', content)
        if match == None:
            return None
        url = match.group(1)
        parts = url.split("/")
        return parts[-1]
    else:
        print("branch {} not found: {}".format(gist_branch, content))
        return None

def versions_get_raw_json(gist_id):
    purview_text = "null"
    sha_of_purview_branch = gist_branch_to_sha(gist_id, "purview")
    if sha_of_purview_branch is None:
        sha_of_purview_branch = gist_branch_to_sha(gist_id, "master")
    if sha_of_purview_branch is not None:
        r = requests.get('http://purview-blocks.herokuapp.com/anonymous/raw/{}/{}/_purview.json'.format(gist_id, sha_of_purview_branch))
        try:
            parse_test = json.loads(r.text)
            purview_text = r.text
        except:
            r = requests.get('http://purview-blocks.herokuapp.com/anonymous/raw/{}/{}/purview.json'.format(gist_id, sha_of_purview_branch))
            try:
                parse_test = json.loads(r.text)
                purview_text = r.text
            except:
                purview_text = '"bad_json"'

    r = requests.get('https://api.github.com/gists/{}'.format(gist_id), headers=auth_headers, params=state_open_params)
    return '{"purview":' + purview_text + ', "api":' + r.text + '}'

def versions_cache_key(gist_id):
    return "versions/{}".format(gist_id)

@app.route("/versions/<gist_id>.raw.json")
@cache(cache_timeout)
def get_versions_raw(gist_id):
    return fetch_and_cache_json(versions_get_raw_json, gist_id, versions_cache_key(gist_id))

def history_to_commits(d):
    commits = [[v["version"], v["committed_at"]] for v in d["history"]]
    return {"commits": commits}

def fetch_purview_records(gist_id, login, purview):
    commits = purview["commits"]
    purview_records = [{
            "login": login,
            "id": gist_id,
            "sha": c["sha"],
            "description": c["name"],
            "created_at": "unknown",
            "updated_at": "unknown"
        } for c in commits]
    return purview_records

def history_to_records_trimmed(gist_id, login, desc, purview_map, api):
    purview_records = []
    if purview_map is not None:
        try:
            purview_records = fetch_purview_records(gist_id, login, purview_map)
        except:
            purview_records = []
    meta = {
        "login": login,
        "id": gist_id,
        "description": desc,
        "blocks_link": js_settings["blocks_run_root"] + login + "/" + gist_id
    }
    known_shas = set()
    for r in purview_records:
        known_shas.add(r["sha"])

    history_is_known = False
    history_records = []
    for h in api["history"]:
        # quit iteration as soon as we hit a known sha
        if h["version"] in known_shas:
            break
        history_records.append({
                "login": login,
                "id": gist_id,
                "sha": h["version"],
                "description": None,
                "created_at": h["committed_at"],
                "updated_at": h["committed_at"]
            })

    # combine known records
    records = history_records + purview_records

    return {"meta": meta, "records": records}

def history_to_records(gist_id, login, desc, purview_map, api):
    purview_records = []
    if purview_map is not None:
        try:
            purview_records = fetch_purview_records(gist_id, login, purview_map)
        except:
            purview_records = []
    meta = {
        "login": login,
        "id": gist_id,
        "description": desc,
        "blocks_link": js_settings["blocks_run_root"] + login + "/" + gist_id
    }
    known_shas = set()
    for r in purview_records:
        known_shas.add(r["sha"])

    history_is_known = False
    history_records = []
    for h in api["history"]:
        if not h["version"] in known_shas:
            history_records.append({
                    "login": login,
                    "id": gist_id,
                    "sha": h["version"],
                    "description": None,
                    "created_at": h["committed_at"],
                    "updated_at": h["committed_at"]
                })

    hidden_records = None
    if purview_records:
        records = purview_records
        hidden_records = history_records
    else:
        records = history_records

    return {"meta": meta, "records": records, "hidden_records": hidden_records}

def get_converted_versions(gist_id):
    d = json.loads(fetch_and_cache_json(versions_get_raw_json, gist_id, versions_cache_key(gist_id)))
    payload = d["payload"]
    login = payload["api"]["owner"]["login"]
    desc = payload["api"]["description"]
    purview_map = None
    if payload["purview"] is not None and "commits" in payload["purview"]:
        purview_map = payload["purview"]
    return history_to_records(gist_id, login, desc, purview_map, payload["api"])

@app.route("/versions/<gist_id>.json")
@cache(cache_timeout)
def get_versions_json(gist_id):
    return json.dumps(get_converted_versions(gist_id))

@app.route("/versions/<gist_id>.html")
@cache(cache_timeout)
def get_versions_html(gist_id):
    d = get_converted_versions(gist_id)
    j = json.dumps(d)
    return render_template("versions.html", json=j,
        meta=d["meta"], js_settings=js_settings, gist_id=gist_id)

if __name__ == '__main__':
    app.run()

