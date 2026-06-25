# WordPress MCP Server

This repository contains a Model Context Protocol (MCP) server that acts
as a secure, multi-tenant proxy between an AI Assistant and the WordPress
backend API. It exposes **46 MCP tools** covering 9 resource domains
with full CRUD, search, and relationship management.

## ✨ Features

- **🔑 Identity Passthrough** — Extracts the `Authorization: Bearer <base64>`
  header from incoming HTTP requests, converts it to Basic auth, and forwards
  it to the WordPress API without server-side authentication.
- **👥 Multi-Tenancy** — Uses Python `contextvars` to maintain thread-safe
  user identity isolation, ensuring all AI-driven actions are scoped to
  the authenticated user's permissions.
- **📊 Full WordPress Coverage** — 46 tools mapped to WordPress REST API endpoints
  across 9 resource domains.
- **⚡ TOON Optimization** — Bulk list responses are automatically compressed
  using TOON (Token-Optimized Object Notation) to reduce token consumption
  and maximize context window efficiency.
- **🚀 Efficient Gets** — GET responses return only commonly used fields by
  default. Full objects are available via an `include_all_fields` flag.
- **🧪 Comprehensive Testing** — 108 automated tests covering all tool
  domains, run via the test runner pipeline.

## 🔧 Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `WORDPRESS_BASE_URL` | Yes | Docker-internal URL of the WordPress server (e.g. `http://wordpress-web:80`). |
| `MCP_SERVER_PORT` | Yes | Port number the MCP server listens on |
| `ALLOW_ALL_AGGREGATE` | No | When `true`, aggregate listing tools honor the `include_all_fields` parameter. When `false` (default), the parameter is silently forced to `False` for aggregate list operations. |

## 📦 Installation & Local Development

1. Ensure you have Python 3.12+ installed.
2. Install dependencies:
    ```bash
    pip install fastmcp httpx pydantic uvicorn toon-mcp-server
    ```
3. Run the server:
    ```bash
    export WORDPRESS_BASE_URL=http://wordpress-web:80
    export MCP_SERVER_PORT=80
    python -m src.main
    ```

## 🐳 Docker Deployment

Build and run the server using Docker:

```bash
docker build -t wordpress-mcp:latest .
docker run -d --name wordpress-mcp \
    -e WORDPRESS_BASE_URL="http://wordpress-web:80" \
    -e MCP_SERVER_PORT=80 \
    wordpress-mcp:latest

The MCP server serves at `http://wordpress-mcp:80/mcp` (Streamable HTTP).
```

## ⚠️ Important Notes

- **📋 `include_all_fields`** — The `include_all_fields` parameter (available
  on all `get_*` and `list_*` tools) controls whether all available fields
  are included in responses. Defaults to `False` for performance; set to
  `True` only when additional fields are needed.
- **🔒 `ALLOW_ALL_AGGREGATE`** — Controls whether aggregate listing tools respect the `include_all_fields` parameter. When set to `false` (default), all aggregate list operations silently return only default fields regardless of the caller's request.
- **⚡ TOON Compression** — All bulk list responses are automatically
  compressed using TOON to reduce token consumption by 30–60%.
- **📝 Required Fields & Defaults** — Each `create_*` tool requires specific
  key fields. All other fields default to empty strings or reasonable values.
  The author/owner field is automatically set to the authenticated user for most resources.

## 🛠️ API Tool Mapping

The server implements 46 MCP tools organized into the following categories:

### 📨 Posts (5 tools)

- `get_all_posts` — List all posts with pagination and filters
- `get_post_by_id` — Get a single post by ID
- `create_post` — Create a new post
- `update_post` — Update an existing post
- `delete_post_by_id` — Delete a post

### 📄 Pages (5 tools)

- `get_all_pages` — List all pages with pagination and filters
- `get_page_by_id` — Get a single page by ID
- `create_page` — Create a new page
- `update_page` — Update an existing page
- `delete_page_by_id` — Delete a page

### 📁 Categories (5 tools)

- `get_all_categories` — List all categories with pagination and filters
- `get_category_by_id` — Get a single category by ID
- `create_category` — Create a new category
- `update_category` — Update an existing category
- `delete_category_by_id` — Delete a category

### 🏷️ Tags (5 tools)

- `get_all_tags` — List all tags with pagination and filters
- `get_tag_by_id` — Get a single tag by ID
- `create_tag` — Create a new tag
- `update_tag` — Update an existing tag
- `delete_tag_by_id` — Delete a tag

### 💬 Comments (5 tools)

- `get_all_comments` — List all comments with pagination and filters
- `get_comment_by_id` — Get a single comment by ID
- `create_comment` — Create a new comment
- `update_comment` — Update an existing comment
- `delete_comment_by_id` — Delete a comment

### 👤 Users (3 tools)

- `get_all_users` — List all users with pagination
- `get_user_by_id` — Get a single user by ID
- `get_current_user` — Get the current authenticated user

### 🧭 Navigation (5 tools)

- `get_all_navigation` — List all navigation menus with pagination
- `get_navigation_by_id` — Get a single navigation menu by ID
- `create_navigation` — Create a new navigation menu
- `update_navigation` — Update an existing navigation menu
- `delete_navigation_by_id` — Delete a navigation menu

### 🧱 Blocks (5 tools)

- `get_all_blocks` — List all reusable blocks with pagination and filters
- `get_block_by_id` — Get a single block by ID
- `create_block` — Create a new block
- `update_block` — Update an existing block
- `delete_block_by_id` — Delete a block

### 📋 Meta Tools (8 tools)

- `get_taxonomies` — List all registered taxonomies
- `get_taxonomy_by_name` — Get a specific taxonomy by name
- `get_post_types` — List all post types
- `get_post_type_by_name` — Get a specific post type by name
- `get_post_statuses` — List all post statuses
- `get_post_status_by_slug` — Get a specific post status by slug
- `search_content` — Search across WordPress content
- `get_server_status` — Check backend connectivity