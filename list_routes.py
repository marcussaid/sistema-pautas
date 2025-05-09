from app import app

def list_routes():
    import urllib
    output = []
    for rule in app.url_map.iter_rules():
        methods = ','.join(rule.methods)
        line = urllib.parse.unquote(f"{rule.endpoint:50s} {methods:20s} {str(rule)}")
        output.append(line)
    for line in sorted(output):
        print(line)

if __name__ == '__main__':
    list_routes()
