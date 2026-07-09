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
      "resolve_id": "<GraphQL thread node id>" | null,
      "reply_to_comment_id": <REST comment databaseId to reply to> | null,
      "url": "<link to the first/anchor comment>",
      "comments": [
        {"author": "login", "is_bot": bool, "body": "...", "created_at": "...", "url": "..."}
      ]
    }
  ]
}

A "review_thread" row is a diff-anchored review comment thread (resolvable
via the GitHub API). A "general_comment" row is a top-level PR conversation
comment or review summary (not anchored to a line, not resolvable — only
reply-able).

Threads/groups made up entirely of bot/agent comments are dropped: there is
no human ask in them for the engineer to decide on. Already-resolved review
threads are dropped too, since they're presumably already settled.

Bot/agent detection: the GraphQL `author.__typename == "Bot"` field covers
GitHub Apps. It won't catch a coding agent that posts as a regular user
account, so BOT_LOGIN_PATTERNS below also matches on login name. Edit that
list for your org's specific bot/agent usernames if some aren't caught.
"""
import json
import re
import subprocess
import sys

BOT_LOGIN_PATTERNS = [
    r".*\[bot\]$",
    r"^copilot$",
    r"^copilot-pull-request-reviewer.*",
    r"^claude$",
    r"^claude-code.*",
    r"^devin-ai-integration.*",
    r"^cursor.*",
    r"^sweep-ai.*",
    r"^coderabbitai.*",
    r"^codeium.*",
]


def is_bot_author(author):
    if not author:
        return True  # deleted/ghost author, nothing a human can act on
    if author.get("__typename") == "Bot":
        return True
    login = author.get("login", "")
    return any(re.match(p, login, re.IGNORECASE) for p in BOT_LOGIN_PATTERNS)


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


def paginate(query, owner, repo, number, path):
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
            nodes { databaseId url body createdAt author { login __typename } }
          }
        }
      }
    }
  }
}
"""

QUERY_COMMENTS = """
query($owner:String!, $repo:String!, $number:Int!, $after:String) {
  repository(owner:$owner, name:$repo) {
    pullRequest(number:$number) {
      comments(first: 100, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes { databaseId url body createdAt author { login __typename } }
      }
    }
  }
}
"""

QUERY_REVIEWS = """
query($owner:String!, $repo:String!, $number:Int!, $after:String) {
  repository(owner:$owner, name:$repo) {
    pullRequest(number:$number) {
      reviews(first: 100, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes { databaseId url body submittedAt author { login __typename } }
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
        if all(is_bot_author(c["author"]) for c in comments):
            continue
        rows.append({
            "type": "review_thread",
            "resolve_id": t["id"],
            "reply_to_comment_id": comments[0]["databaseId"],
            "url": comments[0]["url"],
            "comments": [
                {
                    "author": (c["author"] or {}).get("login", "ghost"),
                    "is_bot": is_bot_author(c["author"]),
                    "body": c["body"],
                    "created_at": c["createdAt"],
                    "url": c["url"],
                }
                for c in comments
            ],
        })
    return rows


def build_general_comment_rows(issue_comments, reviews):
    items = []
    for c in issue_comments:
        items.append({
            "author": (c["author"] or {}).get("login", "ghost"),
            "is_bot": is_bot_author(c["author"]),
            "body": c["body"],
            "created_at": c["createdAt"],
            "url": c["url"],
        })
    for r in reviews:
        if not r["body"]:
            continue  # empty-body reviews (e.g. plain "Approve") add no content
        items.append({
            "author": (r["author"] or {}).get("login", "ghost"),
            "is_bot": is_bot_author(r["author"]),
            "body": r["body"],
            "created_at": r["submittedAt"],
            "url": r["url"],
        })
    items.sort(key=lambda x: x["created_at"])

    rows = []
    current = None
    for item in items:
        if not item["is_bot"]:
            if current:
                rows.append(current)
            current = {
                "type": "general_comment",
                "resolve_id": None,
                "reply_to_comment_id": None,
                "url": item["url"],
                "comments": [item],
            }
        elif current:
            current["comments"].append(item)
        # bot comments with no preceding human comment in this run are dropped
    if current:
        rows.append(current)
    return rows


def main():
    if len(sys.argv) != 4:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    owner, repo, number = sys.argv[1], sys.argv[2], sys.argv[3]

    meta = gh_graphql(QUERY_META, owner, repo, number)["data"]["repository"]["pullRequest"]
    threads = paginate(QUERY_THREADS, owner, repo, number,
                        ["repository", "pullRequest", "reviewThreads"])
    issue_comments = paginate(QUERY_COMMENTS, owner, repo, number,
                               ["repository", "pullRequest", "comments"])
    reviews = paginate(QUERY_REVIEWS, owner, repo, number,
                        ["repository", "pullRequest", "reviews"])

    rows = build_review_thread_rows(threads) + build_general_comment_rows(issue_comments, reviews)
    rows.sort(key=lambda r: r["comments"][0]["created_at"])
    for i, row in enumerate(rows, 1):
        row["row_id"] = i

    print(json.dumps({"pr": {"url": meta["url"], "title": meta["title"]}, "rows": rows}, indent=2))


if __name__ == "__main__":
    main()
