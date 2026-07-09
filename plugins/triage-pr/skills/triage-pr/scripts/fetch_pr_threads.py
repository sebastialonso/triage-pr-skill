#!/usr/bin/env python3
"""Fetch and normalize a GitHub PR's comments into decision-ready rows.

Usage:
    fetch_pr_threads.py OWNER REPO PR_NUMBER

Outputs JSON on stdout:
{
  "pr": {"url": ..., "title": ...},
  "rows": [
    {
      "row_id": 1,
      "type": "review_thread" | "general_comment",
      "url": "<link to the first/anchor comment>",
      "comments": [
        {"author": "login", "body": "...", "created_at": "...", "url": "..."}
      ]
    }
  ]
}

A "review_thread" row is a diff-anchored review comment thread. A
"general_comment" row is a top-level PR conversation comment or review
summary (not anchored to a line).

Every comment is included — human reviewers, bots, and coding agents alike.
Bot/agent comments often carry real analysis (CodeRabbit, Copilot, etc.) and
are treated the same as human feedback, not filtered out or specially
folded. The only thing dropped is already-resolved review threads, since
those are presumably already settled.

Review threads come from the GitHub GraphQL API because thread grouping and
resolved state have no REST equivalent. General comments and review bodies
have no such requirement, so they're fetched over plain REST, which is
simpler and paginates automatically via `gh api --paginate`.
"""
import json
import subprocess
import sys


def gh_graphql(query, owner, repo, number, after=None):
    args = ["gh", "api", "graphql", "-f", f"query={query}",
            "-f", f"owner={owner}", "-f", f"repo={repo}",
            "-F", f"number={number}"]
    if after:
        args += ["-f", f"after={after}"]
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    return json.loads(result.stdout)


def paginate_graphql(query, owner, repo, number, path):
    """path: list of keys from data down to the connection, e.g.
    ["repository", "pullRequest", "reviewThreads"]"""
    nodes = []
    after = None
    while True:
        data = gh_graphql(query, owner, repo, number, after)["data"]
        conn = data
        for key in path:
            conn = conn[key]
        nodes.extend(conn["nodes"])
        if conn["pageInfo"]["hasNextPage"]:
            after = conn["pageInfo"]["endCursor"]
        else:
            return nodes


def gh_rest_paginated(endpoint):
    result = subprocess.run(
        ["gh", "api", endpoint, "--paginate", "--slurp"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    pages = json.loads(result.stdout)
    return [item for page in pages for item in page]


QUERY_META = """
query($owner:String!, $repo:String!, $number:Int!) {
  repository(owner:$owner, name:$repo) {
    pullRequest(number:$number) { url title }
  }
}
"""

QUERY_THREADS = """
query($owner:String!, $repo:String!, $number:Int!, $after:String) {
  repository(owner:$owner, name:$repo) {
    pullRequest(number:$number) {
      reviewThreads(first: 50, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          isResolved
          comments(first: 50) {
            nodes { url body createdAt author { login } }
          }
        }
      }
    }
  }
}
"""


def build_review_thread_rows(threads):
    rows = []
    for t in threads:
        if t["isResolved"]:
            continue
        comments = t["comments"]["nodes"]
        rows.append({
            "type": "review_thread",
            "url": comments[0]["url"],
            "comments": [
                {
                    "author": (c["author"] or {}).get("login", "ghost"),
                    "body": c["body"],
                    "created_at": c["createdAt"],
                    "url": c["url"],
                }
                for c in comments
            ],
        })
    return rows


def build_general_comment_rows(issue_comments, reviews):
    rows = []
    for c in issue_comments:
        rows.append({
            "type": "general_comment",
            "url": c["html_url"],
            "comments": [{
                "author": (c["user"] or {}).get("login", "ghost"),
                "body": c["body"],
                "created_at": c["created_at"],
                "url": c["html_url"],
            }],
        })
    for r in reviews:
        if not r["body"]:
            continue  # empty-body reviews (e.g. plain "Approve") add no content
        rows.append({
            "type": "general_comment",
            "url": r["html_url"],
            "comments": [{
                "author": (r["user"] or {}).get("login", "ghost"),
                "body": r["body"],
                "created_at": r["submitted_at"],
                "url": r["html_url"],
            }],
        })
    return rows


def main():
    if len(sys.argv) != 4:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    owner, repo, number = sys.argv[1], sys.argv[2], sys.argv[3]

    meta = gh_graphql(QUERY_META, owner, repo, number)["data"]["repository"]["pullRequest"]
    threads = paginate_graphql(QUERY_THREADS, owner, repo, number,
                                ["repository", "pullRequest", "reviewThreads"])
    issue_comments = gh_rest_paginated(f"repos/{owner}/{repo}/issues/{number}/comments")
    reviews = gh_rest_paginated(f"repos/{owner}/{repo}/pulls/{number}/reviews")

    rows = build_review_thread_rows(threads) + build_general_comment_rows(issue_comments, reviews)
    rows.sort(key=lambda r: r["comments"][0]["created_at"])
    for i, row in enumerate(rows, 1):
        row["row_id"] = i

    print(json.dumps({"pr": {"url": meta["url"], "title": meta["title"]}, "rows": rows}, indent=2))


if __name__ == "__main__":
    main()
