import sys
import math
import csv
import json
import re

def load_csv(infile):
    csv_data = []
    with open(infile, encoding = "mac_roman") as tsvfile:
    # with open(infile, encoding = "ISO-8859-1") as tsvfile:
      reader = csv.DictReader(tsvfile)
      for row in reader:
        csv_data.append(row)
        # print(row)
    return csv_data

def sanitize(s):
    s = s.replace(u"\u2020", " ")
    s = s.replace(u"\u00ac", "")
    s = s.replace(u"\u221a", "")
    s = s.replace(u"\u00c7", "")
    s = s.strip()
    return s
    # uniString = str(s, 'utf-8')
    # return uniString

def build_data(csv_data):
    d = []
    # for row in csv_data[:3]:
    for row in csv_data:
        # print(row)
        entry = {}
        entry["blackboard"] = sanitize(row["blackboard"])
        entry["login"] = sanitize(row["github"])
        entry["name"] = "{}".format(sanitize(row["name"]))
        # raw_gist = row["Answer 3"]
        # m = re.search('github.com/(.+?)\.git', raw_gist)
        # if m:
        #     found = m.group(1)
        # else:
        #     found = "unknown"
        entry["id"] = sanitize(row["SHA"])
        entry["avatar_url"] = "https://github.com/{}.png?size=40".format(entry["login"])

        d.append(entry)
    return d

if __name__ == '__main__':
    infile = sys.argv[1]
    outfile = sys.argv[2]

    reader = load_csv(infile)
    out_data = build_data(reader)
    d = {
        "meta": {},
        "records": out_data
    }
    with open(outfile, 'w') as f:
        json.dump(d, f, indent=4)
