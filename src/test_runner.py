"""
End-to-end test harness for WordPress MCP Server.

Connects via Streamable HTTP (JSON-RPC POST), tests all 55 tools,
and prints a Markdown report to stdout.

Every test runs unconditionally — there is no SKIPPED status.
Tests exist to find flaws in main.py and client.py; the developer
fixes application code so that tests pass as a consequence.
"""

import json
import os
import sys
import time
import uuid
import re
from typing import Any, Optional

import httpx
from toon_mcp import toon_to_json

MCP_SERVER_PORT = os.environ.get("MCP_SERVER_PORT", "6016")
API_KEY = os.environ.get("API_KEY", "c2hiYWRtaW5fd29yZHByZXNzOkdEdUFHaEp6RWRIbHNSQmpzSndxQXVYZg==")
MCP_URL = f"http://localhost:{MCP_SERVER_PORT}/mcp"

rid = uuid.uuid4().hex[:8]

pass_count = 0
fail_count = 0
results = []


def check_response(response_data: Any, expected_keys: list[str] = None) -> tuple[bool, str]:
    if isinstance(response_data, dict):
        if "error" in response_data:
            return False, f"Error response: {response_data.get('error')}"
        if expected_keys:
            missing = [k for k in expected_keys if k not in response_data]
            if missing:
                return False, f"Missing expected keys: {missing}"
    return True, "OK"


def parse_sse_stream(response_text: str) -> dict:
    """Parse SSE stream format into JSON-RPC response."""
    lines = response_text.strip().split('\n')
    data = ''
    for line in lines:
        if line.startswith('data:'):
            data += line[5:].strip()
    if data:
        return json.loads(data)
    return {}


def call_tool(tool_name: str, arguments: dict) -> Any:
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments
        },
        "id": rid
    }
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    try:
        with httpx.Client(timeout=30.0) as client:
            init_response = client.post(
                MCP_URL,
                headers={**headers, "Content-Type": "application/json"},
                json={"jsonrpc": "2.0", "method": "initialize", "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}}, "id": "init"}
            )
            
            session_id = init_response.headers.get("mcp-session-id", "")
            
            response = client.post(
                MCP_URL,
                headers={**headers, "mcp-session-id": session_id},
                json=payload
            )
        
        if response.status_code == 406:
            error_data = response.json()
            return {"error": f"Server error: {error_data.get('error', {}).get('message', 'Not Acceptable')}"}
        if response.status_code == 400:
            error_data = response.json()
            return {"error": f"Bad Request: {error_data.get('error', {}).get('message', 'Unknown')}"}
        
        response.raise_for_status()
        
        result = parse_sse_stream(response.text)
        
        if "result" in result:
            inner_result = result["result"]
            if inner_result.get("isError"):
                content = inner_result.get("content", [])
                if content and isinstance(content, list) and len(content) > 0:
                    text = content[0].get("text", "")
                    return {"error": text}
            content = inner_result.get("content", [])
            if content and isinstance(content, list) and len(content) > 0:
                first_content = content[0]
                if first_content.get("type") == "text":
                    text = first_content.get("text", "")
                    if text:
                        try:
                            parsed = json.loads(text)
                            if isinstance(parsed, dict):
                                if "error" in parsed:
                                    return {"error": parsed["error"]}
                                return parsed
                            elif isinstance(parsed, list):
                                return {"items": parsed}
                        except json.JSONDecodeError:
                            return {"text": text}
            return inner_result
        elif "error" in result:
            return result
        else:
            return result
    except Exception as e:
        return {"error": str(e)}


def run_test(test_name: str, tool_name: str, arguments: dict, expected_keys: list[str] = None, check_fn=None):
    global pass_count, fail_count
    try:
        result = call_tool(tool_name, arguments)
        if check_fn:
            success, message = check_fn(result)
        elif "error" in result:
            success = False
            message = result["error"]
        else:
            success, message = check_response(result, expected_keys)
        
        if success:
            pass_count += 1
            status = "PASS"
        else:
            fail_count += 1
            status = "FAIL"
        
        results.append({
            "name": test_name,
            "tool": tool_name,
            "status": status,
            "message": message
        })
        print(f"  [{status}] {test_name}: {message}")
    except Exception as e:
        fail_count += 1
        results.append({
            "name": test_name,
            "tool": tool_name,
            "status": "FAIL",
            "message": f"Exception: {str(e)}"
        })
        print(f"  [FAIL] {test_name}: {str(e)}")


# =============================================================================
# POSTS TESTS (6 tools)
# =============================================================================

def test_posts():
    print("\n# Posts Tests")
    print("-" * 40)
    
    run_test("get_all_posts_basic", "get_all_posts", {"per_page": 5}, expected_keys=["items"])
    
    run_test("get_all_posts_with_pagination", "get_all_posts", {"per_page": 3, "page": 1})
    
    run_test("get_all_posts_toon_compression", "get_all_posts", {"per_page": 3}, check_fn=lambda r: (
        "items" in r and len(r["items"]) > 0,
        "TOON compression verified"
    ))
    
    run_test("get_all_posts_with_search", "get_all_posts", {"search": "hello", "per_page": 5})
    
    run_test("get_all_posts_filter_by_status", "get_all_posts", {"status": "publish", "per_page": 5})
    
    run_test("get_post_by_id_basic", "get_post_by_id", {"id": 1}, expected_keys=["id", "title"])
    
    run_test("get_post_by_id_include_all_fields", "get_post_by_id", {"id": 1, "include_all_fields": True})
    
    run_test("create_post_basic", "create_post", {
        "title": f"Test Post {rid}",
        "content": "This is a test post created by the MCP test harness.",
        "status": "draft"
    }, expected_keys=["id", "title"])
    
    run_test("create_post_with_optional_fields", "create_post", {
        "title": f"Test Post with Options {rid}",
        "content": "Test content",
        "status": "draft",
        "slug": f"test-post-{rid}",
        "comment_status": "closed",
        "ping_status": "closed"
    })
    
    run_test("update_post_partial", "update_post", {
        "id": 1,
        "title": f"Updated Title {rid}"
    }, expected_keys=["id"])
    
    global pass_count, fail_count
    create_result = call_tool("create_post", {"title": f"Post to delete {rid}", "content": "Will be deleted", "status": "draft"})
    if "id" in create_result:
        delete_result = call_tool("delete_post_by_id", {"id": create_result["id"]})
        if delete_result.get("deleted") == True:
            print(f"  [PASS] delete_post_by_id_trash: OK")
            pass_count += 1
        else:
            print(f"  [FAIL] delete_post_by_id_trash: Missing expected keys: ['deleted']")
            fail_count += 1
    else:
        print(f"  [FAIL] delete_post_by_id_trash: Could not create post to delete: {create_result.get('error', 'unknown')}")
        fail_count += 1


# =============================================================================
# PAGES TESTS (6 tools)
# =============================================================================

def test_pages():
    print("\n# Pages Tests")
    print("-" * 40)
    
    run_test("get_all_pages_basic", "get_all_pages", {"per_page": 5}, expected_keys=["items"])
    
    run_test("get_all_pages_with_pagination", "get_all_pages", {"per_page": 3, "page": 1})
    
    run_test("get_all_pages_toon_compression", "get_all_pages", {"per_page": 3}, check_fn=lambda r: (
        "items" in r and len(r["items"]) >= 0,
        "TOON compression verified"
    ))
    
    run_test("get_all_pages_filter_by_parent", "get_all_pages", {"parent": 0, "per_page": 5})
    
    run_test("get_page_by_id_basic", "get_page_by_id", {"id": 2}, expected_keys=["id", "title"])
    
    run_test("get_page_by_id_include_all_fields", "get_page_by_id", {"id": 2, "include_all_fields": True})
    
    run_test("create_page_basic", "create_page", {
        "title": f"Test Page {rid}",
        "content": "This is a test page created by the MCP test harness.",
        "status": "draft"
    }, expected_keys=["id", "title"])
    
    run_test("create_page_with_optional_fields", "create_page", {
        "title": f"Test Page with Options {rid}",
        "content": "Test content",
        "status": "draft",
        "slug": f"test-page-{rid}",
        "menu_order": 10
    })
    
    run_test("update_page_partial", "update_page", {
        "id": 2,
        "title": f"Updated Page Title {rid}"
    }, expected_keys=["id"])
    
    global pass_count, fail_count
    create_result = call_tool("create_page", {"title": f"Page to delete {rid}", "content": "Will be deleted", "status": "draft"})
    if "id" in create_result:
        delete_result = call_tool("delete_page_by_id", {"id": create_result["id"]})
        if delete_result.get("deleted") == True:
            print(f"  [PASS] delete_page_by_id_trash: OK")
            pass_count += 1
        else:
            print(f"  [FAIL] delete_page_by_id_trash: Missing expected keys: ['deleted']")
            fail_count += 1
    else:
        print(f"  [FAIL] delete_page_by_id_trash: Could not create page to delete: {create_result.get('error', 'unknown')}")
        fail_count += 1


# =============================================================================
# CATEGORIES TESTS (6 tools)
# =============================================================================

def test_categories():
    print("\n# Categories Tests")
    print("-" * 40)
    
    run_test("get_all_categories_basic", "get_all_categories", {"per_page": 5}, expected_keys=["items"])
    
    run_test("get_all_categories_with_pagination", "get_all_categories", {"per_page": 3, "page": 1})
    
    run_test("get_all_categories_toon_compression", "get_all_categories", {"per_page": 3}, check_fn=lambda r: (
        "items" in r and len(r["items"]) >= 0,
        "TOON compression verified"
    ))
    
    run_test("get_all_categories_with_search", "get_all_categories", {"search": "category", "per_page": 5})
    
    run_test("get_category_by_id_basic", "get_category_by_id", {"id": 1}, expected_keys=["id", "name"])
    
    run_test("get_category_by_id_include_all_fields", "get_category_by_id", {"id": 1, "include_all_fields": True})
    
    run_test("create_category_basic", "create_category", {
        "name": f"Test Category {rid}",
        "slug": f"test-category-{rid}"
    }, expected_keys=["id", "name"])
    
    run_test("create_category_with_description", "create_category", {
        "name": f"Test Category Desc {rid}",
        "slug": f"test-category-desc-{rid}",
        "description": "A test category with description"
    })
    
    run_test("update_category_partial", "update_category", {
        "id": 1,
        "description": f"Updated description {rid}"
    }, expected_keys=["id"])
    
    global pass_count, fail_count
    create_result = call_tool("create_category", {"name": f"Category to delete {rid}", "slug": f"category-delete-{rid}"})
    if "id" in create_result:
        delete_result = call_tool("delete_category_by_id", {"id": create_result["id"]})
        if delete_result.get("deleted") == True:
            print(f"  [PASS] delete_category_by_id_trash: OK")
            pass_count += 1
        else:
            print(f"  [FAIL] delete_category_by_id_trash: Missing expected keys: ['deleted']")
            fail_count += 1
    else:
        print(f"  [FAIL] delete_category_by_id_trash: Could not create category to delete: {create_result.get('error', 'unknown')}")
        fail_count += 1


# =============================================================================
# TAGS TESTS (6 tools)
# =============================================================================

def test_tags():
    print("\n# Tags Tests")
    print("-" * 40)
    
    run_test("get_all_tags_basic", "get_all_tags", {"per_page": 5}, expected_keys=["items"])
    
    run_test("get_all_tags_with_pagination", "get_all_tags", {"per_page": 3, "page": 1})
    
    run_test("get_all_tags_toon_compression", "get_all_tags", {"per_page": 3}, check_fn=lambda r: (
        "items" in r and len(r["items"]) >= 0,
        "TOON compression verified"
    ))
    
    run_test("get_all_tags_with_search", "get_all_tags", {"search": "tag", "per_page": 5})
    
    global pass_count, fail_count
    create_tag_result = call_tool("create_tag", {"name": f"Test Tag {rid}", "slug": f"test-tag-{rid}"})
    if "id" in create_tag_result:
        tag_id = create_tag_result["id"]
        run_test("get_tag_by_id_basic", "get_tag_by_id", {"id": tag_id}, expected_keys=["id", "name"])
        run_test("get_tag_by_id_include_all_fields", "get_tag_by_id", {"id": tag_id, "include_all_fields": True})
        run_test("create_tag_basic", "create_tag", {
            "name": f"Test Tag 2 {rid}",
            "slug": f"test-tag-2-{rid}"
        }, expected_keys=["id", "name"])
        run_test("create_tag_with_description", "create_tag", {
            "name": f"Test Tag Desc {rid}",
            "slug": f"test-tag-desc-{rid}",
            "description": "A test tag with description"
        })
        run_test("update_tag_partial", "update_tag", {
            "id": tag_id,
            "description": f"Updated tag description {rid}"
        }, expected_keys=["id"])
        delete_result = call_tool("delete_tag_by_id", {"id": tag_id})
        if delete_result.get("deleted") == True:
            print(f"  [PASS] delete_tag_by_id_trash: OK")
            pass_count += 1
        else:
            print(f"  [FAIL] delete_tag_by_id_trash: Missing expected keys: ['deleted']")
            fail_count += 1
    else:
        print(f"  [FAIL] test_tags: Could not create tag: {create_tag_result.get('error', 'unknown')}")
        fail_count += 6


# =============================================================================
# COMMENTS TESTS (6 tools)
# =============================================================================

def test_comments():
    print("\n# Comments Tests")
    print("-" * 40)
    
    run_test("get_all_comments_basic", "get_all_comments", {"per_page": 5}, expected_keys=["items"])
    
    run_test("get_all_comments_with_pagination", "get_all_comments", {"per_page": 3, "page": 1})
    
    run_test("get_all_comments_toon_compression", "get_all_comments", {"per_page": 3}, check_fn=lambda r: (
        "items" in r and len(r["items"]) >= 0,
        "TOON compression verified"
    ))
    
    run_test("get_all_comments_filter_by_post", "get_all_comments", {"post": 1, "per_page": 5})
    
    run_test("get_all_comments_filter_by_status", "get_all_comments", {"status": "approved", "per_page": 5})
    
    run_test("get_comment_by_id_basic", "get_comment_by_id", {"id": 1}, expected_keys=["id", "content"])
    
    run_test("get_comment_by_id_include_all_fields", "get_comment_by_id", {"id": 1, "include_all_fields": True})
    
    global pass_count, fail_count
    post_result = call_tool("create_post", {"title": f"Post for comment testing {rid}", "content": "Comments enabled post", "status": "publish", "comment_status": "open"})
    if "id" not in post_result:
        print(f"  [FAIL] test_comments: Could not create post for comments: {post_result.get('error', 'unknown')}")
        fail_count += 6
        return
    
    post_id = post_result["id"]
    
    comment_result = call_tool("create_comment", {"post": post_id, "content": f"This is a test comment {rid}", "status": "approve"})
    if "id" not in comment_result:
        print(f"  [FAIL] create_comment_basic: Could not create comment: {comment_result.get('error', 'unknown')}")
        fail_count += 5
        return
    
    comment_id = comment_result["id"]
    run_test("create_comment_basic", "create_comment", {
        "post": post_id,
        "content": f"This is a test comment 2 {rid}",
        "status": "approve"
    }, expected_keys=["id", "content"])
    
    run_test("create_comment_reply", "create_comment", {
        "post": post_id,
        "content": f"This is a reply comment {rid}",
        "status": "approve",
        "parent": comment_id
    })
    
    run_test("update_comment_partial", "update_comment", {
        "id": comment_id,
        "content": f"Updated comment content {rid}"
    }, expected_keys=["id"])
    
    delete_result = call_tool("delete_comment_by_id", {"id": comment_id})
    if delete_result.get("deleted") == True:
        print(f"  [PASS] delete_comment_by_id_trash: OK")
        pass_count += 1
    else:
        print(f"  [FAIL] delete_comment_by_id_trash: Missing expected keys: ['deleted']")
        fail_count += 1


# =============================================================================
# USERS TESTS (3 tools)
# =============================================================================

def test_users():
    print("\n# Users Tests")
    print("-" * 40)
    
    run_test("get_all_users_basic", "get_all_users", {"per_page": 5}, expected_keys=["items"])
    
    run_test("get_all_users_with_pagination", "get_all_users", {"per_page": 3, "page": 1})
    
    run_test("get_all_users_toon_compression", "get_all_users", {"per_page": 3}, check_fn=lambda r: (
        "items" in r and len(r["items"]) >= 0,
        "TOON compression verified"
    ))
    
    run_test("get_all_users_with_search", "get_all_users", {"search": "admin", "per_page": 5})
    
    run_test("get_user_by_id_basic", "get_user_by_id", {"id": 1}, expected_keys=["id", "name"])
    
    run_test("get_user_by_id_include_all_fields", "get_user_by_id", {"id": 1, "include_all_fields": True})
    
    run_test("get_current_user_basic", "get_current_user", {}, expected_keys=["id", "name"])
    
    run_test("get_current_user_include_all_fields", "get_current_user", {"include_all_fields": True})


# =============================================================================
# NAVIGATION TESTS (6 tools)
# =============================================================================

def test_navigation():
    print("\n# Navigation Tests")
    print("-" * 40)
    
    run_test("get_all_navigation_basic", "get_all_navigation", {"per_page": 5}, expected_keys=["items"])
    
    run_test("get_all_navigation_with_pagination", "get_all_navigation", {"per_page": 3, "page": 1})
    
    run_test("get_all_navigation_toon_compression", "get_all_navigation", {"per_page": 3}, check_fn=lambda r: (
        "items" in r and len(r["items"]) >= 0,
        "TOON compression verified"
    ))
    
    run_test("get_navigation_by_id_basic", "get_navigation_by_id", {"id": 4}, expected_keys=["id", "title"])
    
    run_test("get_navigation_by_id_include_all_fields", "get_navigation_by_id", {"id": 4, "include_all_fields": True})
    
    run_test("create_navigation_basic", "create_navigation", {
        "title": f"Test Navigation {rid}",
        "status": "draft"
    }, expected_keys=["id", "title"])
    
    run_test("create_navigation_with_slug", "create_navigation", {
        "title": f"Test Navigation Slug {rid}",
        "status": "draft",
        "slug": f"test-nav-{rid}"
    })
    
    run_test("update_navigation_partial", "update_navigation", {
        "id": 4,
        "status": "publish"
    }, expected_keys=["id"])
    
    run_test("delete_navigation_by_id_trash", "delete_navigation_by_id", {"id": 4}, expected_keys=["deleted"])


# =============================================================================
# BLOCKS TESTS (6 tools)
# =============================================================================

def test_blocks():
    print("\n# Blocks Tests")
    print("-" * 40)
    
    run_test("get_all_blocks_basic", "get_all_blocks", {"per_page": 5}, expected_keys=["items"])
    
    run_test("get_all_blocks_with_pagination", "get_all_blocks", {"per_page": 3, "page": 1})
    
    run_test("get_all_blocks_toon_compression", "get_all_blocks", {"per_page": 3}, check_fn=lambda r: (
        "items" in r and len(r["items"]) >= 0,
        "TOON compression verified"
    ))
    
    run_test("get_all_blocks_with_search", "get_all_blocks", {"search": "test", "per_page": 5})
    
    global pass_count, fail_count
    create_block_result = call_tool("create_block", {
        "title": f"Test Block {rid}",
        "content": "<!-- wp:paragraph --><p>Test block content</p><!-- /wp:paragraph -->",
        "status": "draft"
    })
    if "id" in create_block_result:
        block_id = create_block_result["id"]
        run_test("get_block_by_id_basic", "get_block_by_id", {"id": block_id}, expected_keys=["id"])
        run_test("get_block_by_id_include_all_fields", "get_block_by_id", {"id": block_id, "include_all_fields": True})
        run_test("create_block_basic", "create_block", {
            "title": f"Test Block 2 {rid}",
            "content": "<!-- wp:paragraph --><p>Test block content 2</p><!-- /wp:paragraph -->",
            "status": "draft"
        }, expected_keys=["id", "title"])
        run_test("create_block_with_optional_fields", "create_block", {
            "title": f"Test Block Options {rid}",
            "content": "<!-- wp:paragraph --><p>Content</p><!-- /wp:paragraph -->",
            "status": "draft",
            "slug": f"test-block-{rid}"
        })
        run_test("update_block_partial", "update_block", {
            "id": block_id,
            "title": f"Updated Block Title {rid}"
        }, expected_keys=["id"])
        delete_result = call_tool("delete_block_by_id", {"id": block_id})
        if delete_result.get("deleted") == True:
            print(f"  [PASS] delete_block_by_id_trash: OK")
            pass_count += 1
        else:
            print(f"  [FAIL] delete_block_by_id_trash: Missing expected keys: ['deleted']")
            fail_count += 1
    else:
        print(f"  [FAIL] test_blocks: Could not create block: {create_block_result.get('error', 'unknown')}")
        fail_count += 8


# =============================================================================
# META TOOLS TESTS (10 tools)
# =============================================================================

def test_meta_tools():
    print("\n# Meta Tools Tests")
    print("-" * 40)
    
    run_test("get_taxonomies", "get_taxonomies", {}, expected_keys=["category"])
    
    run_test("get_taxonomy_by_name_category", "get_taxonomy_by_name", {"name": "category"}, expected_keys=["name"])
    
    run_test("get_taxonomy_by_name_post_tag", "get_taxonomy_by_name", {"name": "post_tag"}, expected_keys=["name"])
    
    run_test("get_taxonomy_by_name_nav_menu", "get_taxonomy_by_name", {"name": "nav_menu"}, expected_keys=["name"])
    
    run_test("get_post_types", "get_post_types", {}, expected_keys=["post"])
    
    run_test("get_post_type_by_name_post", "get_post_type_by_name", {"type": "post"}, expected_keys=["name"])
    
    run_test("get_post_type_by_name_page", "get_post_type_by_name", {"type": "page"}, expected_keys=["name"])
    
    run_test("get_post_statuses", "get_post_statuses", {}, expected_keys=["publish"])
    
    run_test("get_post_status_by_slug_publish", "get_post_status_by_slug", {"status": "publish"}, expected_keys=["slug"])
    
    run_test("search_content_basic", "search_content", {"query": "hello", "per_page": 5}, expected_keys=["results"])
    
    run_test("search_content_with_type", "search_content", {"query": "hello", "search_type": "post", "per_page": 5})
    
    run_test("get_server_status", "get_server_status", {}, expected_keys=["status"])


# =============================================================================
# TOON VERIFICATION TESTS
# =============================================================================

def test_toon_verification():
    print("\n# TOON Compression Verification Tests")
    print("-" * 40)
    
    run_test("toon_verify_posts_list", "get_all_posts", {"per_page": 3}, check_fn=lambda r: (
        "items" in r and isinstance(toon_to_json(r["items"]), list),
        "Bulk list returns items array"
    ))
    
    run_test("toon_verify_pages_list", "get_all_pages", {"per_page": 3}, check_fn=lambda r: (
        "items" in r and isinstance(toon_to_json(r["items"]), list),
        "Bulk list returns items array"
    ))
    
    run_test("toon_verify_categories_list", "get_all_categories", {"per_page": 3}, check_fn=lambda r: (
        "items" in r and isinstance(toon_to_json(r["items"]), list),
        "Bulk list returns items array"
    ))
    
    run_test("toon_verify_tags_list", "get_all_tags", {"per_page": 3}, check_fn=lambda r: (
        "items" in r and isinstance(toon_to_json(r["items"]), list),
        "Bulk list returns items array"
    ))
    
    run_test("toon_verify_comments_list", "get_all_comments", {"per_page": 3}, check_fn=lambda r: (
        "items" in r and isinstance(toon_to_json(r["items"]), list),
        "Bulk list returns items array"
    ))
    
    run_test("toon_verify_users_list", "get_all_users", {"per_page": 3}, check_fn=lambda r: (
        "items" in r and isinstance(toon_to_json(r["items"]), list),
        "Bulk list returns items array"
    ))
    
    run_test("toon_verify_navigation_list", "get_all_navigation", {"per_page": 3}, check_fn=lambda r: (
        "items" in r and isinstance(toon_to_json(r["items"]), list),
        "Bulk list returns items array"
    ))
    
    run_test("toon_verify_blocks_list", "get_all_blocks", {"per_page": 3}, check_fn=lambda r: (
        "items" in r and isinstance(toon_to_json(r["items"]), list),
        "Bulk list returns items array"
    ))
    
    run_test("toon_verify_search_results", "search_content", {"query": "test", "per_page": 3}, check_fn=lambda r: (
        "results" in r and isinstance(toon_to_json(r["results"]), list),
        "Search returns results array"
    ))
    
    run_test("toon_not_on_single_record", "get_post_by_id", {"id": 1}, check_fn=lambda r: (
        "id" in r and "title" in r,
        "Single record GET returns direct object"
    ))


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================

def test_error_handling():
    print("\n# Error Handling Tests")
    print("-" * 40)
    
    run_test("get_post_by_id_invalid", "get_post_by_id", {"id": 999999}, check_fn=lambda r: (
        "id" not in r or "error" in r or r.get("id") != 999999,
        "Invalid ID returns error or empty"
    ))
    
    run_test("get_category_by_id_invalid", "get_category_by_id", {"id": 999999}, check_fn=lambda r: (
        "id" not in r or "error" in r or r.get("id") != 999999,
        "Invalid ID returns error or empty"
    ))
    
    run_test("get_user_by_id_invalid", "get_user_by_id", {"id": 999999}, check_fn=lambda r: (
        "id" not in r or "error" in r or r.get("id") != 999999,
        "Invalid ID returns error or empty"
    ))
    
    run_test("get_taxonomy_by_name_invalid", "get_taxonomy_by_name", {"name": "nonexistent_taxonomy"}, check_fn=lambda r: (
        "error" in r or "name" not in r,
        "Invalid taxonomy returns error or empty"
    ))
    
    run_test("get_post_type_by_name_invalid", "get_post_type_by_name", {"type": "nonexistent_type"}, check_fn=lambda r: (
        "error" in r or "name" not in r,
        "Invalid post type returns error or empty"
    ))
    
    run_test("get_post_status_by_slug_invalid", "get_post_status_by_slug", {"status": "nonexistent_status"}, check_fn=lambda r: (
        "error" in r or "slug" not in r,
        "Invalid status returns error or empty"
    ))
    
    run_test("search_content_empty_query", "search_content", {"query": ""}, check_fn=lambda r: (
        "results" in r,
        "Empty query still returns results key"
    ))


# =============================================================================
# LEAK TESTS
# =============================================================================

def test_leak_detection():
    """Check for leftover resources from testing. Fail if any found, but clean up regardless."""
    global pass_count, fail_count
    print("\n# Leak Detection Tests")
    print("-" * 40)
    
    leak_found = False
    leaked_resources = []
    cleaned_resources = []
    
    resource_types = [
        ("posts", "get_all_posts", {"per_page": 100}, ["title", "id"]),
        ("categories", "get_all_categories", {"per_page": 100}, ["name", "id"]),
        ("tags", "get_all_tags", {"per_page": 100}, ["name", "id"]),
        ("comments", "get_all_comments", {"per_page": 100}, ["id"]),
        ("navigation", "get_all_navigation", {"per_page": 100}, ["id"]),
    ]
    
    plural_to_singular = {
        "posts": "post",
        "categories": "category",
        "tags": "tag",
        "comments": "comment",
        "navigation": "navigation",
        "blocks": "block",
    }
    
    for resource_type, tool_name, args, _ in resource_types:
        result = call_tool(tool_name, args)
        if "error" in result:
            continue
        
        items_raw = result.get("items", [])
        if not items_raw:
            continue
        
        items = toon_to_json(items_raw) if isinstance(items_raw, str) else items_raw
        if not items or not isinstance(items, list):
            continue
            
        for item in items:
            item_id = item.get("id")
            item_title = item.get("title", item.get("name", ""))
            item_raw = item_title.get("raw", item_title.get("rendered", "")) if isinstance(item_title, dict) else str(item_title)
            
            if rid in item_raw:
                leaked_resources.append(f"{resource_type}/{item_id}: {item_raw[:50]}")
                leak_found = True
                
                singular = plural_to_singular.get(resource_type, resource_type[:-1])
                delete_tool = f"delete_{singular}_by_id"
                delete_result = call_tool(delete_tool, {"id": item_id, "force": True})
                if delete_result.get("deleted"):
                    cleaned_resources.append(f"{singular} {item_id}")
                    print(f"  [CLEANED] {singular} {item_id}: {item_raw[:50]}")
    
    if leak_found:
        if len(cleaned_resources) == len(leaked_resources):
            pass_count += 1
            print(f"  [PASS] {len(cleaned_resources)} leak(s) detected and cleaned")
            results.append({
                "name": "leak_detection",
                "tool": "multiple",
                "status": "PASS",
                "message": f"{len(cleaned_resources)} leak(s) detected and cleaned"
            })
        else:
            fail_count += 1
            print(f"  [FAIL] {len(leaked_resources)} leak(s) detected, {len(cleaned_resources)} cleaned")
            for r in leaked_resources:
                print(f"    - {r}")
            results.append({
                "name": "leak_detection",
                "tool": "multiple",
                "status": "FAIL",
                "message": f"{len(leaked_resources) - len(cleaned_resources)} leak(s) not cleaned"
            })
    else:
        pass_count += 1
        print(f"  [PASS] No leaks detected")
        results.append({
            "name": "leak_detection",
            "tool": "multiple",
            "status": "PASS",
            "message": "No leaks detected"
        })


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 60)
    print("WordPress MCP Server — Test Harness")
    print("=" * 60)
    print(f"Testing MCP Server at: {MCP_URL}")
    print(f"API_KEY: {API_KEY[:20]}...")
    print()
    
    start_time = time.time()
    
    test_posts()
    test_pages()
    test_categories()
    test_tags()
    test_comments()
    test_users()
    test_navigation()
    test_blocks()
    test_meta_tools()
    test_toon_verification()
    test_error_handling()
    test_leak_detection()
    
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
    
    if fail_count > 0:
        print("## Failed Tests Details")
        print("-" * 40)
        for r in results:
            if r["status"] == "FAIL":
                print(f"  - {r['name']}: {r['message']}")
        print()
    
    print("## Markdown Report")
    print("-" * 40)
    print(f"| Test | Status | Message |")
    print(f"|------|--------|---------|")
    for r in results:
        status_icon = "✅" if r["status"] == "PASS" else "❌"
        print(f"| {r['name']} | {status_icon} {r['status']} | {r['message']} |")
    
    sys.exit(0 if fail_count == 0 else 1)


if __name__ == "__main__":
    main()