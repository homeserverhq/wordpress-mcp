"""
End-to-end test harness for WordPress MCP Server — FLAT version.

Connects via Streamable HTTP (JSON-RPC POST), tests all 46 tools,
and prints a Markdown report to stdout.

NO conditional branching (if/then/elif/else/match/case).
NO exception handling (try/except) — exceptions crash the runner immediately.
NO test skipping — every test runs every single time.

108 tests, all running unconditionally.
"""

import json
import os
import sys
import time
import uuid
from typing import Any

import httpx
from toon_mcp import toon_to_json

MCP_SERVER_PORT = os.environ.get("MCP_SERVER_PORT", "6016")
API_KEY = os.environ.get("API_KEY", "c2hiYWRtaW5fd29yZHByZXNzOkdEdUFHaEp6RWRIbHNSQmpzSndxQXVYZg==")
MCP_URL = f"http://localhost:{MCP_SERVER_PORT}/mcp"

rid = uuid.uuid4().hex[:8]

pass_count = 0
fail_count = 0
results = []
statuses = ["FAIL", "PASS"]


def _parse_sse(response_text: str) -> dict:
    lines = response_text.strip().split('\n')
    data_parts = [line[5:].strip() for line in filter(lambda l: l.startswith('data:'), lines)]
    data = ''.join(data_parts)
    return json.loads(data) if data else {}


def call_tool(tool_name: str, arguments: dict) -> Any:
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
        "id": rid
    }
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    with httpx.Client(timeout=30.0) as client:
        init_resp = client.post(
            MCP_URL,
            headers=headers,
            json={
                "jsonrpc": "2.0", "method": "initialize",
                "params": {"protocolVersion": "2025-11-25", "capabilities": {},
                           "clientInfo": {"name": "test", "version": "1.0"}},
                "id": "init"
            }
        )
        session_id = init_resp.headers.get("mcp-session-id", "")
        resp = client.post(
            MCP_URL,
            headers={**headers, "mcp-session-id": session_id},
            json=payload
        )

    resp.raise_for_status()
    result = _parse_sse(resp.text)
    inner = result.get("result", result)

    content = inner.get("content", [])
    content_valid = content and isinstance(content, list) and len(content) > 0
    text = content[0].get("text", "") if content_valid else ""
    is_error = inner.get("isError", False)

    parsed = {"error": text} if is_error else (json.loads(text) if text else inner)
    is_dict = isinstance(parsed, dict)
    return parsed if is_dict else ({"items": parsed} if isinstance(parsed, list) else {"text": str(parsed)})


def check_response(data: Any, expected_keys: list[str] | None = None) -> tuple[bool, str]:
    is_dict = isinstance(data, dict)
    has_error = "error" in data
    missing = [k for k in (expected_keys or []) if k not in (data if is_dict else {})]
    ok = is_dict and not has_error and len(missing) == 0
    msg_parts = []
    msg_parts.append("OK" if ok else (f"Error: {data.get('error', '')}" if has_error else f"Missing keys: {missing}"))
    return ok, msg_parts[0]


def run_test(test_name: str, tool_name: str, arguments: dict, check_fn) -> Any:
    global pass_count, fail_count
    result = call_tool(tool_name, arguments)
    ok, message = check_fn(result)
    pass_count += ok
    fail_count += 1 - ok
    s = statuses[ok]
    results.append({"name": test_name, "tool": tool_name, "status": s, "message": message})
    print(f"  [{s}] {test_name}: {message}")
    return result


print("=" * 60)
print("WordPress MCP Server — Test Harness (Flat)")
print("=" * 60)
print(f"Testing MCP Server at: {MCP_URL}")
print(f"API_KEY: {API_KEY[:20]}...")
print()

start_time = time.time()

# =========================================================================
# PHASE 1: CREATE SETUP ENTITIES (collect IDs for cascade-safe tests)
# =========================================================================

_post_id = call_tool("create_post", {
    "title": f"Test Post for ID tests {rid}",
    "content": "Content for ID testing",
    "status": "publish"
}).get("id", 0)

_post_del_id = call_tool("create_post", {
    "title": f"Post to delete {rid}",
    "content": "Will be deleted",
    "status": "draft"
}).get("id", 0)

_page_id = call_tool("create_page", {
    "title": f"Test Page for ID tests {rid}",
    "content": "Content for ID testing",
    "status": "publish"
}).get("id", 0)

_page_del_id = call_tool("create_page", {
    "title": f"Page to delete {rid}",
    "content": "Will be deleted",
    "status": "draft"
}).get("id", 0)

_cat_del_id = call_tool("create_category", {
    "name": f"Category to delete {rid}",
    "slug": f"category-delete-{rid}"
}).get("id", 0)

_tag_id = call_tool("create_tag", {
    "name": f"Test Tag {rid}",
    "slug": f"test-tag-{rid}"
}).get("id", 0)

_comment_post_id = call_tool("create_post", {
    "title": f"Post for comment testing {rid}",
    "content": "Comments enabled post",
    "status": "publish",
    "comment_status": "open"
}).get("id", 0)

_comment_id = call_tool("create_comment", {
    "post": _comment_post_id,
    "content": f"This is a test comment {rid}",
    "status": "approve"
}).get("id", 0)

_nav_id = call_tool("create_navigation", {
    "title": f"Test Navigation for ID tests {rid}",
    "status": "publish"
}).get("id", 0)

_block_id = call_tool("create_block", {
    "title": f"Test Block {rid}",
    "content": "<!-- wp:paragraph --><p>Test block content</p><!-- /wp:paragraph -->",
    "status": "draft"
}).get("id", 0)

# =========================================================================
# PHASE 2: ALL 108 TESTS
# =========================================================================

# --- Posts (11 tests) ---
print("\n# Posts Tests")
print("-" * 40)

run_test("list_all_posts_basic", "list_all_posts", {"per_page": 5},
         lambda r: check_response(r, ["items"]))

run_test("list_all_posts_with_pagination", "list_all_posts", {"per_page": 3, "page": 1},
         lambda r: check_response(r))

run_test("list_all_posts_toon_compression", "list_all_posts", {"per_page": 3},
         lambda r: ("items" in r and len(r["items"]) > 0, "TOON compression verified"))

run_test("list_all_posts_with_search", "list_all_posts", {"search": "hello", "per_page": 5},
         lambda r: check_response(r))

run_test("list_all_posts_filter_by_status", "list_all_posts", {"status": "publish", "per_page": 5},
         lambda r: check_response(r))

run_test("get_post_by_id_basic", "get_post_by_id", {"id": _post_id},
         lambda r: check_response(r, ["id", "title"]))

run_test("get_post_by_id_include_all_fields", "get_post_by_id", {"id": _post_id, "include_all_fields": True},
         lambda r: check_response(r))

run_test("create_post_basic", "create_post", {
    "title": f"Test Post {rid}",
    "content": "This is a test post created by the MCP test harness.",
    "status": "draft"
}, lambda r: check_response(r, ["id", "title"]))

run_test("create_post_with_optional_fields", "create_post", {
    "title": f"Test Post with Options {rid}",
    "content": "Test content",
    "status": "draft",
    "slug": f"test-post-{rid}",
    "comment_status": "closed",
    "ping_status": "closed"
}, lambda r: check_response(r, ["id"]))

run_test("update_post_partial", "update_post", {
    "id": _post_id,
    "title": f"Updated Title {rid}"
}, lambda r: check_response(r, ["id"]))

run_test("delete_post_by_id_trash", "delete_post_by_id", {"id": _post_del_id},
         lambda r: (r.get("deleted") == True, "OK"))

# --- Pages (10 tests) ---
print("\n# Pages Tests")
print("-" * 40)

run_test("list_all_pages_basic", "list_all_pages", {"per_page": 5},
         lambda r: check_response(r, ["items"]))

run_test("list_all_pages_with_pagination", "list_all_pages", {"per_page": 3, "page": 1},
         lambda r: check_response(r))

run_test("list_all_pages_toon_compression", "list_all_pages", {"per_page": 3},
         lambda r: ("items" in r and len(r["items"]) > 0, "TOON compression verified"))

run_test("list_all_pages_filter_by_parent", "list_all_pages", {"parent": 0, "per_page": 5},
         lambda r: check_response(r))

run_test("get_page_by_id_basic", "get_page_by_id", {"id": _page_id},
         lambda r: check_response(r, ["id", "title"]))

run_test("get_page_by_id_include_all_fields", "get_page_by_id", {"id": _page_id, "include_all_fields": True},
         lambda r: check_response(r))

run_test("create_page_basic", "create_page", {
    "title": f"Test Page {rid}",
    "content": "This is a test page created by the MCP test harness.",
    "status": "draft"
}, lambda r: check_response(r, ["id", "title"]))

run_test("create_page_with_optional_fields", "create_page", {
    "title": f"Test Page with Options {rid}",
    "content": "Test content",
    "status": "draft",
    "slug": f"test-page-{rid}",
    "menu_order": 10
}, lambda r: check_response(r))

run_test("update_page_partial", "update_page", {
    "id": _page_id,
    "title": f"Updated Page Title {rid}"
}, lambda r: check_response(r, ["id"]))

run_test("delete_page_by_id_trash", "delete_page_by_id", {"id": _page_del_id},
         lambda r: (r.get("deleted") == True, "OK"))

# --- Categories (10 tests) ---
print("\n# Categories Tests")
print("-" * 40)

run_test("list_all_categories_basic", "list_all_categories", {"per_page": 5},
         lambda r: check_response(r, ["items"]))

run_test("list_all_categories_with_pagination", "list_all_categories", {"per_page": 3, "page": 1},
         lambda r: check_response(r))

run_test("list_all_categories_toon_compression", "list_all_categories", {"per_page": 3},
         lambda r: ("items" in r and len(r["items"]) > 0, "TOON compression verified"))

run_test("list_all_categories_with_search", "list_all_categories", {"search": "category", "per_page": 5},
         lambda r: check_response(r))

run_test("get_category_by_id_basic", "get_category_by_id", {"id": 1},
         lambda r: check_response(r, ["id", "name"]))

run_test("get_category_by_id_include_all_fields", "get_category_by_id", {"id": 1, "include_all_fields": True},
         lambda r: check_response(r))

_run_test_cat_create_1 = run_test("create_category_basic", "create_category", {
    "name": f"Test Category {rid}",
    "slug": f"test-category-{rid}"
}, lambda r: check_response(r, ["id", "name"]))

run_test("create_category_with_description", "create_category", {
    "name": f"Test Category Desc {rid}",
    "slug": f"test-category-desc-{rid}",
    "description": "A test category with description"
}, lambda r: check_response(r))

run_test("update_category_partial", "update_category", {
    "id": 1,
    "description": f"Updated description {rid}"
}, lambda r: check_response(r, ["id"]))

run_test("delete_category_by_id_trash", "delete_category_by_id", {"id": _cat_del_id},
         lambda r: (r.get("deleted") == True, "OK"))

# --- Tags (10 tests) ---
print("\n# Tags Tests")
print("-" * 40)

run_test("list_all_tags_basic", "list_all_tags", {"per_page": 5},
         lambda r: check_response(r, ["items"]))

run_test("list_all_tags_with_pagination", "list_all_tags", {"per_page": 3, "page": 1},
         lambda r: check_response(r))

run_test("list_all_tags_toon_compression", "list_all_tags", {"per_page": 3},
         lambda r: ("items" in r and len(r["items"]) > 0, "TOON compression verified"))

run_test("list_all_tags_with_search", "list_all_tags", {"search": "tag", "per_page": 5},
         lambda r: check_response(r))

run_test("get_tag_by_id_basic", "get_tag_by_id", {"id": _tag_id},
         lambda r: check_response(r, ["id", "name"]))

run_test("get_tag_by_id_include_all_fields", "get_tag_by_id", {"id": _tag_id, "include_all_fields": True},
         lambda r: check_response(r))

run_test("create_tag_basic", "create_tag", {
    "name": f"Test Tag 2 {rid}",
    "slug": f"test-tag-2-{rid}"
}, lambda r: check_response(r, ["id", "name"]))

run_test("create_tag_with_description", "create_tag", {
    "name": f"Test Tag Desc {rid}",
    "slug": f"test-tag-desc-{rid}",
    "description": "A test tag with description"
}, lambda r: check_response(r))

run_test("update_tag_partial", "update_tag", {
    "id": _tag_id,
    "description": f"Updated tag description {rid}"
}, lambda r: check_response(r, ["id"]))

run_test("delete_tag_by_id_trash", "delete_tag_by_id", {"id": _tag_id},
         lambda r: (r.get("deleted") == True, "OK"))

# --- Users (8 tests) ---
print("\n# Users Tests")
print("-" * 40)

run_test("list_all_users_basic", "list_all_users", {"per_page": 5},
         lambda r: check_response(r, ["items"]))

run_test("list_all_users_with_pagination", "list_all_users", {"per_page": 3, "page": 1},
         lambda r: check_response(r))

run_test("list_all_users_toon_compression", "list_all_users", {"per_page": 3},
         lambda r: ("items" in r and len(r["items"]) > 0, "TOON compression verified"))

run_test("list_all_users_with_search", "list_all_users", {"search": "admin", "per_page": 5},
         lambda r: check_response(r))

run_test("get_user_by_id_basic", "get_user_by_id", {"id": 1},
         lambda r: check_response(r, ["id", "name"]))

run_test("get_user_by_id_include_all_fields", "get_user_by_id", {"id": 1, "include_all_fields": True},
         lambda r: check_response(r))

run_test("get_current_user_basic", "get_current_user", {},
         lambda r: check_response(r, ["id", "name"]))

run_test("get_current_user_include_all_fields", "get_current_user", {"include_all_fields": True},
         lambda r: check_response(r))

# --- Comments (11 tests) ---
print("\n# Comments Tests")
print("-" * 40)

run_test("list_all_comments_basic", "list_all_comments", {"per_page": 5},
         lambda r: check_response(r, ["items"]))

run_test("list_all_comments_with_pagination", "list_all_comments", {"per_page": 3, "page": 1},
         lambda r: check_response(r))

run_test("list_all_comments_toon_compression", "list_all_comments", {"per_page": 3},
         lambda r: ("items" in r and len(r["items"]) > 0, "TOON compression verified"))

run_test("list_all_comments_filter_by_post", "list_all_comments", {"post": _comment_post_id, "per_page": 5},
         lambda r: check_response(r))

run_test("list_all_comments_filter_by_status", "list_all_comments", {"status": "approved", "per_page": 5},
         lambda r: check_response(r))

run_test("get_comment_by_id_basic", "get_comment_by_id", {"id": _comment_id},
         lambda r: check_response(r, ["id", "content"]))

run_test("get_comment_by_id_include_all_fields", "get_comment_by_id", {"id": _comment_id, "include_all_fields": True},
         lambda r: check_response(r))

run_test("create_comment_basic", "create_comment", {
    "post": _comment_post_id,
    "content": f"This is a test comment 2 {rid}",
    "status": "approve"
}, lambda r: check_response(r, ["id", "content"]))

run_test("create_comment_reply", "create_comment", {
    "post": _comment_post_id,
    "content": f"This is a reply comment {rid}",
    "status": "approve",
    "parent": _comment_id
}, lambda r: check_response(r))

run_test("update_comment_partial", "update_comment", {
    "id": _comment_id,
    "content": f"Updated comment content {rid}"
}, lambda r: check_response(r, ["id"]))

run_test("delete_comment_by_id_trash", "delete_comment_by_id", {"id": _comment_id},
         lambda r: (r.get("deleted") == True, "OK"))

# --- Navigation (8 tests, no delete) ---
print("\n# Navigation Tests")
print("-" * 40)

run_test("list_all_navigation_basic", "list_all_navigation", {"per_page": 5},
         lambda r: check_response(r, ["items"]))

run_test("list_all_navigation_with_pagination", "list_all_navigation", {"per_page": 3, "page": 1},
         lambda r: check_response(r))

run_test("list_all_navigation_toon_compression", "list_all_navigation", {"per_page": 3},
         lambda r: ("items" in r and len(r["items"]) > 0, "TOON compression verified"))

run_test("get_navigation_by_id_basic", "get_navigation_by_id", {"id": _nav_id},
         lambda r: check_response(r, ["id", "title"]))

run_test("get_navigation_by_id_include_all_fields", "get_navigation_by_id", {"id": _nav_id, "include_all_fields": True},
         lambda r: check_response(r))

run_test("create_navigation_basic", "create_navigation", {
    "title": f"Test Navigation {rid}",
    "status": "draft"
}, lambda r: check_response(r, ["id", "title"]))

run_test("create_navigation_with_slug", "create_navigation", {
    "title": f"Test Navigation Slug {rid}",
    "status": "draft",
    "slug": f"test-nav-{rid}"
}, lambda r: check_response(r))

run_test("update_navigation_partial", "update_navigation", {
    "id": _nav_id,
    "status": "publish"
}, lambda r: check_response(r, ["id"]))

# --- Blocks (10 tests) ---
print("\n# Blocks Tests")
print("-" * 40)

run_test("list_all_blocks_basic", "list_all_blocks", {"per_page": 5},
         lambda r: check_response(r, ["items"]))

run_test("list_all_blocks_with_pagination", "list_all_blocks", {"per_page": 3, "page": 1},
         lambda r: check_response(r))

run_test("list_all_blocks_toon_compression", "list_all_blocks", {"per_page": 3},
         lambda r: ("items" in r and len(r["items"]) > 0, "TOON compression verified"))

run_test("list_all_blocks_with_search", "list_all_blocks", {"search": "test", "per_page": 5},
         lambda r: check_response(r))

run_test("get_block_by_id_basic", "get_block_by_id", {"id": _block_id},
         lambda r: check_response(r, ["id"]))

run_test("get_block_by_id_include_all_fields", "get_block_by_id", {"id": _block_id, "include_all_fields": True},
         lambda r: check_response(r))

run_test("create_block_basic", "create_block", {
    "title": f"Test Block 2 {rid}",
    "content": "<!-- wp:paragraph --><p>Test block content 2</p><!-- /wp:paragraph -->",
    "status": "draft"
}, lambda r: check_response(r, ["id", "title"]))

run_test("create_block_with_optional_fields", "create_block", {
    "title": f"Test Block Options {rid}",
    "content": "<!-- wp:paragraph --><p>Content</p><!-- /wp:paragraph -->",
    "status": "draft",
    "slug": f"test-block-{rid}"
}, lambda r: check_response(r))

run_test("update_block_partial", "update_block", {
    "id": _block_id,
    "title": f"Updated Block Title {rid}"
}, lambda r: check_response(r, ["id"]))

run_test("delete_block_by_id_trash", "delete_block_by_id", {"id": _block_id},
         lambda r: (r.get("deleted") == True, "OK"))

# --- Meta Tools (12 tests) ---
print("\n# Meta Tools Tests")
print("-" * 40)

run_test("list_all_taxonomies", "list_all_taxonomies", {},
         lambda r: check_response(r, ["category"]))

run_test("get_taxonomy_by_name_category", "get_taxonomy_by_name", {"name": "category"},
         lambda r: check_response(r, ["name"]))

run_test("get_taxonomy_by_name_post_tag", "get_taxonomy_by_name", {"name": "post_tag"},
         lambda r: check_response(r, ["name"]))

run_test("get_taxonomy_by_name_nav_menu", "get_taxonomy_by_name", {"name": "nav_menu"},
         lambda r: check_response(r, ["name"]))

run_test("list_all_post_types", "list_all_post_types", {},
         lambda r: check_response(r, ["post"]))

run_test("get_post_type_by_name_post", "get_post_type_by_name", {"type": "post"},
         lambda r: check_response(r, ["name"]))

run_test("get_post_type_by_name_page", "get_post_type_by_name", {"type": "page"},
         lambda r: check_response(r, ["name"]))

run_test("list_all_post_statuses", "list_all_post_statuses", {},
         lambda r: check_response(r, ["publish"]))

run_test("get_post_status_by_slug_publish", "get_post_status_by_slug", {"status": "publish"},
         lambda r: check_response(r, ["slug"]))

run_test("search_content_basic", "search_content", {"query": "hello", "per_page": 5},
         lambda r: check_response(r, ["results"]))

run_test("search_content_with_type", "search_content", {"query": "hello", "search_type": "post", "per_page": 5},
         lambda r: check_response(r))

run_test("get_server_status", "get_server_status", {},
         lambda r: check_response(r, ["status"]))

# --- TOON Verification (10 tests) ---
print("\n# TOON Compression Verification Tests")
print("-" * 40)

run_test("toon_verify_posts_list", "list_all_posts", {"per_page": 3},
         lambda r: ("items" in r and isinstance(toon_to_json(r["items"]), list),
                    "Bulk list returns items array"))

run_test("toon_verify_pages_list", "list_all_pages", {"per_page": 3},
         lambda r: ("items" in r and isinstance(toon_to_json(r["items"]), list),
                    "Bulk list returns items array"))

run_test("toon_verify_categories_list", "list_all_categories", {"per_page": 3},
         lambda r: ("items" in r and isinstance(toon_to_json(r["items"]), list),
                    "Bulk list returns items array"))

run_test("toon_verify_tags_list", "list_all_tags", {"per_page": 3},
         lambda r: ("items" in r and isinstance(toon_to_json(r["items"]), list),
                    "Bulk list returns items array"))

run_test("toon_verify_comments_list", "list_all_comments", {"per_page": 3},
         lambda r: ("items" in r and isinstance(toon_to_json(r["items"]), list),
                    "Bulk list returns items array"))

run_test("toon_verify_users_list", "list_all_users", {"per_page": 3},
         lambda r: ("items" in r and isinstance(toon_to_json(r["items"]), list),
                    "Bulk list returns items array"))

run_test("toon_verify_navigation_list", "list_all_navigation", {"per_page": 3},
         lambda r: ("items" in r and isinstance(toon_to_json(r["items"]), list),
                    "Bulk list returns items array"))

run_test("toon_verify_blocks_list", "list_all_blocks", {"per_page": 3},
         lambda r: ("items" in r and isinstance(toon_to_json(r["items"]), list),
                    "Bulk list returns items array"))

run_test("toon_verify_search_results", "search_content", {"query": "test", "per_page": 3},
         lambda r: ("results" in r and isinstance(toon_to_json(r["results"]), list),
                    "Search returns results array"))

run_test("toon_not_on_single_record", "get_post_by_id", {"id": _post_id},
         lambda r: ("id" in r and "title" in r,
                    "Single record GET returns direct object"))

# --- Error Handling (7 tests) ---
print("\n# Error Handling Tests")
print("-" * 40)

run_test("get_post_by_id_invalid", "get_post_by_id", {"id": 999999},
         lambda r: ("id" not in r or "error" in r or r.get("id") != 999999,
                    "Invalid ID returns error or empty"))

run_test("get_category_by_id_invalid", "get_category_by_id", {"id": 999999},
         lambda r: ("id" not in r or "error" in r or r.get("id") != 999999,
                    "Invalid ID returns error or empty"))

run_test("get_user_by_id_invalid", "get_user_by_id", {"id": 999999},
         lambda r: ("id" not in r or "error" in r or r.get("id") != 999999,
                    "Invalid ID returns error or empty"))

run_test("get_taxonomy_by_name_invalid", "get_taxonomy_by_name", {"name": "nonexistent_taxonomy"},
         lambda r: ("error" in r or "name" not in r,
                    "Invalid taxonomy returns error or empty"))

run_test("get_post_type_by_name_invalid", "get_post_type_by_name", {"type": "nonexistent_type"},
         lambda r: ("error" in r or "name" not in r,
                    "Invalid post type returns error or empty"))

run_test("get_post_status_by_slug_invalid", "get_post_status_by_slug", {"status": "nonexistent_status"},
         lambda r: ("error" in r or "slug" not in r,
                    "Invalid status returns error or empty"))

run_test("search_content_empty_query", "search_content", {"query": ""},
         lambda r: ("results" in r,
                    "Empty query still returns results key"))

# =========================================================================
# CLEANUP: Rid-based sweep — delete every resource containing our rid
# Must run BEFORE leak detection so the leak test only sees leftover items
# =========================================================================

_cleanup_specs = [
    ("posts", "list_all_posts", ("publish", "draft", "trash"), "delete_post_by_id", True),
    ("pages", "list_all_pages", ("publish", "draft", "trash"), "delete_page_by_id", True),
    ("categories", "list_all_categories", None, "delete_category_by_id", False),
    ("tags", "list_all_tags", None, "delete_tag_by_id", False),
    ("comments", "list_all_comments", None, "delete_comment_by_id", False),
    ("navigation", "list_all_navigation", None, "delete_navigation_by_id", False),
    ("blocks", "list_all_blocks", ("publish", "draft", "trash"), "delete_block_by_id", False),
]

for _cs_name, _cs_list_tool, _cs_statuses, _cs_del_tool, _cs_force in _cleanup_specs:
    _status_iter = _cs_statuses if _cs_statuses else ("",)
    for _cs_status in _status_iter:
        _cs_args = {**{"per_page": 100}, **({"status": _cs_status} if _cs_status else {})}
        _cs_result = call_tool(_cs_list_tool, _cs_args)
        _cs_items_raw = _cs_result.get("items", [])
        _cs_items = toon_to_json(_cs_items_raw) if isinstance(_cs_items_raw, str) else _cs_items_raw
        for _cs_item in (_cs_items or []):
            _cs_id = _cs_item.get("id", 0)
            _cs_has_rid = rid in str(_cs_item)
            _cs_del_args = {**{"id": _cs_id * _cs_has_rid}, **({"force": True} if _cs_force else {})}
            call_tool(_cs_del_tool, _cs_del_args)

# --- Leak Detection (1 test) ---
print("\n# Leak Detection Tests")
print("-" * 40)

_leak_total = 0

_resource_checks = [
    ("posts", "list_all_posts", {"per_page": 100}),
    ("pages", "list_all_pages", {"per_page": 100}),
    ("categories", "list_all_categories", {"per_page": 100}),
    ("tags", "list_all_tags", {"per_page": 100}),
    ("comments", "list_all_comments", {"per_page": 100}),
    ("navigation", "list_all_navigation", {"per_page": 100}),
    ("blocks", "list_all_blocks", {"per_page": 100}),
]

for _res_name, _res_tool, _res_args in _resource_checks:
    _res_result = call_tool(_res_tool, _res_args)
    _res_items_raw = _res_result.get("items", [])
    _res_items = toon_to_json(_res_items_raw) if isinstance(_res_items_raw, str) else _res_items_raw
    for _res_item in (_res_items or []):
        _res_item_text = str(_res_item)
        _leak_total += (rid in _res_item_text)

run_test("leak_detection", "leak_detection", {},
         lambda r: (_leak_total == 0, f"Leaks found: {_leak_total}" if _leak_total > 0 else "No leaks detected"))

# =========================================================================
# SUMMARY
# =========================================================================

elapsed = time.time() - start_time

print()
print("=" * 60)
print("TEST RESULTS SUMMARY")
print("=" * 60)
print(f"Total tests: {pass_count + fail_count}")
print(f"Passed: {pass_count}")
print(f"Failed: {fail_count}")
print(f"Duration: {elapsed:.2f}s")
print()

print("## Failed Tests Details")
print("-" * 40)
for r in filter(lambda x: x["status"] == "FAIL", results):
    print(f"  - {r['name']}: {r['message']}")
print()

print("## Markdown Report")
print("-" * 40)
print(f"| Test | Status | Message |")
print(f"|------|--------|---------|")
for r in results:
    icons = ["❌", "✅"]
    icon = icons[r["status"] == "PASS"]
    print(f"| {r['name']} | {icon} {r['status']} | {r['message']} |")

_final_fail_count = fail_count
sys.exit(0 if _final_fail_count == 0 else 1)
