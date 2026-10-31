import http.server
import json
import os
import sys
from urllib.parse import urlparse
from analyzer import GitHubOrgActivityAnalyzer
from auth import GitHubAuthManager

PORT = int(os.environ.get("PORT", 8080))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_FILE = os.path.join(BASE_DIR, "templates", "index.html")


class AnalyzerHTTPHandler(http.server.BaseHTTPRequestHandler):

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ["/", "/index.html"]:
            try:
                with open(TEMPLATE_FILE, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            except Exception as e:
                self.send_error(500, f"Error loading UI: {e}")
        elif parsed.path == "/api/auth/status":
            methods = GitHubAuthManager.detect_available_methods()
            self._send_json(methods, 200)
        else:
            self.send_error(404, "Page Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/analyze":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                payload = json.loads(body)
            except Exception:
                self._send_json({"error": "Invalid JSON body"}, 400)
                return

            org = payload.get("org")
            author = payload.get("author")
            token_input = payload.get("token")
            app_id = payload.get("app_id")
            private_key = payload.get("private_key")
            installation_id = payload.get("installation_id")
            include_unlinked = payload.get("include_branches_without_pr", True)

            if not org or not author:
                self._send_json({"error": "Both 'org' and 'author' are required"}, 400)
                return

            try:
                token, auth_method, meta = GitHubAuthManager.resolve_token(
                    token_input=token_input,
                    app_id=app_id,
                    private_key_pem=private_key,
                    installation_id=installation_id,
                )
            except Exception as e:
                self._send_json({"error": f"Authentication Error: {e}"}, 401)
                return

            try:
                analyzer = GitHubOrgActivityAnalyzer(token=token, org=org)
                result = {
                    "org": org,
                    "author": author,
                    "auth_method": auth_method,
                    "auth_details": meta,
                    "pull_requests": analyzer.analyze_pull_requests(author),
                    "issues": analyzer.analyze_issues(author),
                }

                if include_unlinked:
                    repos = analyzer.get_organization_repositories()
                    unlinked_all = []
                    for r in repos:
                        unlinked = analyzer.analyze_branches_without_prs(
                            repo=r["name"],
                            default_branch=r["default_branch"],
                            user_filter=author
                        )
                        unlinked_all.extend(unlinked)
                    result["branches_without_pr"] = unlinked_all
                else:
                    result["branches_without_pr"] = []

                self._send_json(result, 200)

            except Exception as e:
                self._send_json({"error": str(e)}, 500)
        else:
            self.send_error(404, "Endpoint Not Found")

    def _send_json(self, data, status_code=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # Clean logging
        sys.stderr.write(f"[{self.log_date_time_string()}] {args[0]} {args[1]} {args[2]}\n")


def run_server(port=PORT):
    server_address = ("", port)
    httpd = http.server.HTTPServer(server_address, AnalyzerHTTPHandler)
    print(f"\n=======================================================")
    print(f" Web UI running at http://localhost:{port}")
    print(f" Press Ctrl+C to terminate.")
    print(f"=======================================================\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        httpd.server_close()


if __name__ == "__main__":
    port_arg = PORT
    if len(sys.argv) > 1:
        try:
            port_arg = int(sys.argv[1])
        except ValueError:
            pass
    run_server(port_arg)
