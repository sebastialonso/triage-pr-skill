#!/usr/bin/env python3
"""Reply to (and, where possible, resolve) one PR comment row.

Usage:
    apply_pr_decision.py review-thread OWNER REPO PR_NUMBER REPLY_TO_COMMENT_ID RESOLVE_ID BODY
    apply_pr_decision.py general-comment OWNER REPO PR_NUMBER BODY

"review-thread" posts a threaded reply on the diff-anchored comment and then
resolves the thread. "general-comment" posts a new top-level PR comment,
since GitHub has no reply or resolve concept for non-diff comments.
"""
import json
import subprocess
import sys


def run(args):
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    return result.stdout


def reply_review_thread(owner, repo, number, reply_to_comment_id, body):
    run([
        "gh", "api", f"repos/{owner}/{repo}/pulls/{number}/comments",
        "-f", f"body={body}",
        "-F", f"in_reply_to={reply_to_comment_id}",
    ])


def resolve_review_thread(thread_id):
    mutation = """
    mutation($id: ID!) {
      resolveReviewThread(input: {threadId: $id}) { thread { id isResolved } }
    }
    """
    run(["gh", "api", "graphql", "-f", f"query={mutation}", "-f", f"id={thread_id}"])


def reply_general_comment(owner, repo, number, body):
    run(["gh", "api", f"repos/{owner}/{repo}/issues/{number}/comments", "-f", f"body={body}"])


def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    kind = sys.argv[1]
    if kind == "review-thread":
        _, _, owner, repo, number, reply_to_comment_id, resolve_id, body = sys.argv
        reply_review_thread(owner, repo, number, reply_to_comment_id, body)
        resolve_review_thread(resolve_id)
    elif kind == "general-comment":
        _, _, owner, repo, number, body = sys.argv
        reply_general_comment(owner, repo, number, body)
    else:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    print(json.dumps({"status": "ok"}))


if __name__ == "__main__":
    main()
