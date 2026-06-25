import os
import sys
from contextvars import ContextVar
from typing import Any, Optional

from fastmcp import FastMCP, Context
from pydantic import BaseModel, Field
from toon_mcp import json_to_toon

from .client import WordPressClient

_current_user_token: ContextVar[Optional[str]] = ContextVar(
    "current_user_token", default=None
)

ALLOW_ALL_AGGREGATE = os.getenv("ALLOW_ALL_AGGREGATE", "false").lower() in ("true", "1", "yes")


class AuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            auth_header = headers.get(b"authorization", b"").decode()
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
                _current_user_token.set(token)
        await self.app(scope, receive, send)


mcp = FastMCP("wordpress-mcp-server")

_client: Optional[WordPressClient] = None


def get_client() -> WordPressClient:
    global _client
    if _client is None:
        _client = WordPressClient()
    return _client


def get_user_token() -> Optional[str]:
    return _current_user_token.get()


# =============================================================================
# Pydantic Contract Models
# =============================================================================

class CreatePostParam(BaseModel):
    title: str
    content: str
    status: str
    slug: str = ""
    author: int = 0
    categories: list = []
    tags: list = []
    featured_media: int = 0
    comment_status: str = "open"
    ping_status: str = "open"
    format: str = "standard"
    password: str = ""


class UpdatePostParam(BaseModel):
    id: int
    title: Optional[str] = None
    content: Optional[str] = None
    status: Optional[str] = None
    slug: Optional[str] = None
    author: Optional[int] = None
    categories: Optional[list] = None
    tags: Optional[list] = None
    featured_media: Optional[int] = None
    comment_status: Optional[str] = None
    ping_status: Optional[str] = None
    format: Optional[str] = None
    password: Optional[str] = None


class CreatePageParam(BaseModel):
    title: str
    content: str
    status: str
    slug: str = ""
    parent: int = 0
    menu_order: int = 0
    author: int = 0
    featured_media: int = 0
    comment_status: str = "closed"
    ping_status: str = "open"
    template: str = ""
    password: str = ""


class UpdatePageParam(BaseModel):
    id: int
    title: Optional[str] = None
    content: Optional[str] = None
    status: Optional[str] = None
    slug: Optional[str] = None
    parent: Optional[int] = None
    menu_order: Optional[int] = None
    author: Optional[int] = None
    featured_media: Optional[int] = None
    comment_status: Optional[str] = None
    ping_status: Optional[str] = None
    template: Optional[str] = None
    password: Optional[str] = None


class CreateCategoryParam(BaseModel):
    name: str
    slug: str
    description: str = ""
    parent: int = 0


class UpdateCategoryParam(BaseModel):
    id: int
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    parent: Optional[int] = None


class CreateTagParam(BaseModel):
    name: str
    slug: str
    description: str = ""


class UpdateTagParam(BaseModel):
    id: int
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None


class CreateCommentParam(BaseModel):
    post: int
    content: str
    status: str
    parent: int = 0
    author_name: str = ""
    author_url: str = ""


class UpdateCommentParam(BaseModel):
    id: int
    content: Optional[str] = None
    status: Optional[str] = None
    author_name: Optional[str] = None
    author_url: Optional[str] = None


class CreateNavigationParam(BaseModel):
    title: str
    status: str
    slug: str = ""
    content: str = ""
    template: str = ""


class UpdateNavigationParam(BaseModel):
    id: int
    title: Optional[str] = None
    status: Optional[str] = None
    slug: Optional[str] = None
    content: Optional[str] = None
    template: Optional[str] = None


class CreateBlockParam(BaseModel):
    title: str
    content: str
    status: str
    slug: str = ""
    template: str = ""


class UpdateBlockParam(BaseModel):
    id: int
    title: Optional[str] = None
    content: Optional[str] = None
    status: Optional[str] = None
    slug: Optional[str] = None
    template: Optional[str] = None


# =============================================================================
# Posts Tools
# =============================================================================

@mcp.tool()
async def get_all_posts(
    include_all_fields: bool = False,
    status: str = "",
    per_page: int = 10,
    page: int = 1,
    search: str = "",
    author: str = "",
    orderby: str = "date",
    order: str = "desc",
    ctx: Context = None
) -> dict[str, Any]:
    """List all post records.

    Args:
        include_all_fields: When False (default), each post contains only
            commonly used fields (id, title, status, author, categories, tags).
            Set to True to include all available fields.
        status: Filter by post status (publish, draft, private, etc.).
        per_page: Maximum number of posts to return. Defaults to 10.
        page: Page number for pagination. Defaults to 1.
        search: Search keyword.
        author: Filter by author user ID.
        orderby: Sort field (date, modified, id, title, etc.). Defaults to "date".
        order: Sort direction (asc or desc). Defaults to "desc".
    """
    data = await get_client().get_all_posts(
        get_user_token(),
        include_all_fields=include_all_fields if ALLOW_ALL_AGGREGATE else False,
        status=status,
        per_page=per_page,
        page=page,
        search=search,
        author=author,
        orderby=orderby,
        order=order,
    )
    return {"items": json_to_toon(data)}


@mcp.tool()
async def get_post_by_id(
    id: int,
    include_all_fields: bool = False,
    ctx: Context = None
) -> dict[str, Any]:
    """Get a single post by its ID.

    Args:
        id: The unique ID of the post.
        include_all_fields: When False (default), returns only commonly used
            fields. Set to True to retrieve all available fields.
    """
    return await get_client().get_post_by_id(
        id, get_user_token(), include_all_fields=include_all_fields
    )


@mcp.tool()
async def create_post(
    title: str,
    content: str,
    status: str,
    slug: str = "",
    author: int = 0,
    categories: list = None,
    tags: list = None,
    featured_media: int = 0,
    comment_status: str = "open",
    ping_status: str = "open",
    format: str = "standard",
    password: str = "",
    ctx: Context = None
) -> dict[str, Any]:
    """Create a new post.

    Args:
        title: Title of the new post (required).
        content: Content of the post (required).
        status: Post status - publish, draft, private, etc. (required).
        slug: URL-friendly slug. Defaults to empty.
        author: Author user ID. Defaults to 0.
        categories: List of category IDs. Defaults to empty list.
        tags: List of tag IDs. Defaults to empty list.
        featured_media: Featured image media ID. Defaults to 0.
        comment_status: Whether comments are open (open or closed). Defaults to "open".
        ping_status: Whether pings are open (open or closed). Defaults to "open".
        format: Post format (standard, aside, chat, etc.). Defaults to "standard".
        password: Password protection. Defaults to empty.
    """
    if categories is None:
        categories = []
    if tags is None:
        tags = []
    params = CreatePostParam(
        title=title, content=content, status=status,
        slug=slug, author=author, categories=categories,
        tags=tags, featured_media=featured_media,
        comment_status=comment_status, ping_status=ping_status,
        format=format, password=password,
    )
    return await get_client().create_post(
        params.model_dump(exclude_unset=True), get_user_token(),
        include_all_fields=ALLOW_ALL_AGGREGATE
    )


@mcp.tool()
async def update_post(
    id: int,
    title: str = None,
    content: str = None,
    status: str = None,
    slug: str = None,
    author: int = None,
    categories: list = None,
    tags: list = None,
    featured_media: int = None,
    comment_status: str = None,
    ping_status: str = None,
    format: str = None,
    password: str = None,
    ctx: Context = None
) -> dict[str, Any]:
    """Update an existing post.

    Args:
        id: The unique ID of the post to update (required).
        title: New title for the post.
        content: New content for the post.
        status: New status (publish, draft, private, etc.).
        slug: New URL-friendly slug.
        author: New author user ID.
        categories: New list of category IDs.
        tags: New list of tag IDs.
        featured_media: New featured image media ID.
        comment_status: New comment status (open or closed).
        ping_status: New ping status (open or closed).
        format: New post format.
        password: New password protection.
    """
    payload = {}
    if title is not None:
        payload["title"] = title
    if content is not None:
        payload["content"] = content
    if status is not None:
        payload["status"] = status
    if slug is not None:
        payload["slug"] = slug
    if author is not None:
        payload["author"] = author
    if categories is not None:
        payload["categories"] = categories
    if tags is not None:
        payload["tags"] = tags
    if featured_media is not None:
        payload["featured_media"] = featured_media
    if comment_status is not None:
        payload["comment_status"] = comment_status
    if ping_status is not None:
        payload["ping_status"] = ping_status
    if format is not None:
        payload["format"] = format
    if password is not None:
        payload["password"] = password
    return await get_client().update_post(id, payload, get_user_token(), include_all_fields=ALLOW_ALL_AGGREGATE)


@mcp.tool()
async def delete_post_by_id(
    id: int,
    force: bool = False,
    ctx: Context = None
) -> dict[str, Any]:
    """Delete a post by its ID.

    Args:
        id: The unique ID of the post to delete.
        force: When False (default), moves to trash. When True, permanently deletes.
    """
    result = await get_client().delete_post_by_id(id, get_user_token(), force=force)
    if isinstance(result, dict) and result.get("code"):
        raise Exception(result.get("message", f"Delete failed: {result.get('code')}"))
    return {"deleted": True}


# =============================================================================
# Pages Tools
# =============================================================================

@mcp.tool()
async def get_all_pages(
    include_all_fields: bool = False,
    status: str = "",
    per_page: int = 10,
    page: int = 1,
    search: str = "",
    author: str = "",
    parent: int = 0,
    orderby: str = "date",
    order: str = "desc",
    ctx: Context = None
) -> dict[str, Any]:
    """List all page records.

    Args:
        include_all_fields: When False (default), each page contains only
            commonly used fields (id, title, status, author, parent).
            Set to True to include all available fields.
        status: Filter by page status.
        per_page: Maximum number of pages to return. Defaults to 10.
        page: Page number for pagination. Defaults to 1.
        search: Search keyword.
        author: Filter by author user ID.
        parent: Filter by parent page ID.
        orderby: Sort field. Defaults to "date".
        order: Sort direction (asc or desc). Defaults to "desc".
    """
    data = await get_client().get_all_pages(
        get_user_token(),
        include_all_fields=include_all_fields if ALLOW_ALL_AGGREGATE else False,
        status=status,
        per_page=per_page,
        page=page,
        search=search,
        author=author,
        parent=parent,
        orderby=orderby,
        order=order,
    )
    return {"items": json_to_toon(data)}


@mcp.tool()
async def get_page_by_id(
    id: int,
    include_all_fields: bool = False,
    ctx: Context = None
) -> dict[str, Any]:
    """Get a single page by its ID.

    Args:
        id: The unique ID of the page.
        include_all_fields: When False (default), returns only commonly used
            fields. Set to True to retrieve all available fields.
    """
    return await get_client().get_page_by_id(
        id, get_user_token(), include_all_fields=include_all_fields
    )


@mcp.tool()
async def create_page(
    title: str,
    content: str,
    status: str,
    slug: str = "",
    parent: int = 0,
    menu_order: int = 0,
    author: int = 0,
    featured_media: int = 0,
    comment_status: str = "closed",
    ping_status: str = "open",
    template: str = "",
    password: str = "",
    ctx: Context = None
) -> dict[str, Any]:
    """Create a new page.

    Args:
        title: Title of the new page (required).
        content: Content of the page (required).
        status: Page status - publish, draft, private, etc. (required).
        slug: URL-friendly slug. Defaults to empty.
        parent: Parent page ID for hierarchical pages. Defaults to 0 (no parent).
        menu_order: Order for menu placement. Defaults to 0.
        author: Author user ID. Defaults to 0.
        featured_media: Featured image media ID. Defaults to 0.
        comment_status: Whether comments are open. Defaults to "closed".
        ping_status: Whether pings are open. Defaults to "open".
        template: Template file name. Defaults to empty.
        password: Password protection. Defaults to empty.
    """
    params = CreatePageParam(
        title=title, content=content, status=status,
        slug=slug, parent=parent, menu_order=menu_order,
        author=author, featured_media=featured_media,
        comment_status=comment_status, ping_status=ping_status,
        template=template, password=password,
    )
    return await get_client().create_page(
        params.model_dump(exclude_unset=True), get_user_token(),
        include_all_fields=ALLOW_ALL_AGGREGATE
    )


@mcp.tool()
async def update_page(
    id: int,
    title: str = None,
    content: str = None,
    status: str = None,
    slug: str = None,
    parent: int = None,
    menu_order: int = None,
    author: int = None,
    featured_media: int = None,
    comment_status: str = None,
    ping_status: str = None,
    template: str = None,
    password: str = None,
    ctx: Context = None
) -> dict[str, Any]:
    """Update an existing page.

    Args:
        id: The unique ID of the page to update (required).
        title: New title for the page.
        content: New content for the page.
        status: New status.
        slug: New URL-friendly slug.
        parent: New parent page ID.
        menu_order: New menu order.
        author: New author user ID.
        featured_media: New featured image media ID.
        comment_status: New comment status.
        ping_status: New ping status.
        template: New template file name.
        password: New password protection.
    """
    payload = {}
    if title is not None:
        payload["title"] = title
    if content is not None:
        payload["content"] = content
    if status is not None:
        payload["status"] = status
    if slug is not None:
        payload["slug"] = slug
    if parent is not None:
        payload["parent"] = parent
    if menu_order is not None:
        payload["menu_order"] = menu_order
    if author is not None:
        payload["author"] = author
    if featured_media is not None:
        payload["featured_media"] = featured_media
    if comment_status is not None:
        payload["comment_status"] = comment_status
    if ping_status is not None:
        payload["ping_status"] = ping_status
    if template is not None:
        payload["template"] = template
    if password is not None:
        payload["password"] = password
    return await get_client().update_page(id, payload, get_user_token(), include_all_fields=ALLOW_ALL_AGGREGATE)


@mcp.tool()
async def delete_page_by_id(
    id: int,
    force: bool = False,
    ctx: Context = None
) -> dict[str, Any]:
    """Delete a page by its ID.

    Args:
        id: The unique ID of the page to delete.
        force: When False (default), moves to trash. When True, permanently deletes.
    """
    result = await get_client().delete_page_by_id(id, get_user_token(), force=force)
    if isinstance(result, dict) and result.get("code"):
        raise Exception(result.get("message", f"Delete failed: {result.get('code')}"))
    return {"deleted": True}


# =============================================================================
# Categories Tools
# =============================================================================

@mcp.tool()
async def get_all_categories(
    include_all_fields: bool = False,
    per_page: int = 10,
    page: int = 1,
    search: str = "",
    parent: int = 0,
    orderby: str = "name",
    order: str = "asc",
    ctx: Context = None
) -> dict[str, Any]:
    """List all category records.

    Args:
        include_all_fields: When False (default), each category contains only
            commonly used fields (id, name, slug, parent, count).
            Set to True to include all available fields.
        per_page: Maximum number of categories to return. Defaults to 10.
        page: Page number for pagination. Defaults to 1.
        search: Search keyword.
        parent: Filter by parent category ID.
        orderby: Sort field. Defaults to "name".
        order: Sort direction (asc or desc). Defaults to "asc".
    """
    data = await get_client().get_all_categories(
        get_user_token(),
        include_all_fields=include_all_fields if ALLOW_ALL_AGGREGATE else False,
        per_page=per_page,
        page=page,
        search=search,
        parent=parent,
        orderby=orderby,
        order=order,
    )
    return {"items": json_to_toon(data)}


@mcp.tool()
async def get_category_by_id(
    id: int,
    include_all_fields: bool = False,
    ctx: Context = None
) -> dict[str, Any]:
    """Get a single category by its ID.

    Args:
        id: The unique ID of the category.
        include_all_fields: When False (default), returns only commonly used
            fields. Set to True to retrieve all available fields.
    """
    return await get_client().get_category_by_id(
        id, get_user_token(), include_all_fields=include_all_fields
    )


@mcp.tool()
async def create_category(
    name: str,
    slug: str,
    description: str = "",
    parent: int = 0,
    ctx: Context = None
) -> dict[str, Any]:
    """Create a new category.

    Args:
        name: Name of the new category (required).
        slug: URL-friendly slug (required).
        description: Category description. Defaults to empty.
        parent: Parent category ID for hierarchical categories. Defaults to 0.
    """
    params = CreateCategoryParam(
        name=name, slug=slug, description=description, parent=parent,
    )
    return await get_client().create_category(
        params.model_dump(exclude_unset=True), get_user_token(),
        include_all_fields=ALLOW_ALL_AGGREGATE
    )


@mcp.tool()
async def update_category(
    id: int,
    name: str = None,
    slug: str = None,
    description: str = None,
    parent: int = None,
    ctx: Context = None
) -> dict[str, Any]:
    """Update an existing category.

    Args:
        id: The unique ID of the category to update (required).
        name: New name for the category.
        slug: New URL-friendly slug.
        description: New description.
        parent: New parent category ID.
    """
    payload = {}
    if name is not None:
        payload["name"] = name
    if slug is not None:
        payload["slug"] = slug
    if description is not None:
        payload["description"] = description
    if parent is not None:
        payload["parent"] = parent
    return await get_client().update_category(id, payload, get_user_token(), include_all_fields=ALLOW_ALL_AGGREGATE)


@mcp.tool()
async def delete_category_by_id(
    id: int,
    ctx: Context = None
) -> dict[str, Any]:
    """Delete a category by its ID (permanently - categories don't support trash).

    Args:
        id: The unique ID of the category to delete.
    """
    result = await get_client().delete_category_by_id(id, get_user_token())
    if isinstance(result, dict) and result.get("code"):
        raise Exception(result.get("message", f"Delete failed: {result.get('code')}"))
    return {"deleted": True}


# =============================================================================
# Tags Tools
# =============================================================================

@mcp.tool()
async def get_all_tags(
    include_all_fields: bool = False,
    per_page: int = 10,
    page: int = 1,
    search: str = "",
    orderby: str = "name",
    order: str = "asc",
    ctx: Context = None
) -> dict[str, Any]:
    """List all tag records.

    Args:
        include_all_fields: When False (default), each tag contains only
            commonly used fields (id, name, slug, count).
            Set to True to include all available fields.
        per_page: Maximum number of tags to return. Defaults to 10.
        page: Page number for pagination. Defaults to 1.
        search: Search keyword.
        orderby: Sort field. Defaults to "name".
        order: Sort direction (asc or desc). Defaults to "asc".
    """
    data = await get_client().get_all_tags(
        get_user_token(),
        include_all_fields=include_all_fields if ALLOW_ALL_AGGREGATE else False,
        per_page=per_page,
        page=page,
        search=search,
        orderby=orderby,
        order=order,
    )
    return {"items": json_to_toon(data)}


@mcp.tool()
async def get_tag_by_id(
    id: int,
    include_all_fields: bool = False,
    ctx: Context = None
) -> dict[str, Any]:
    """Get a single tag by its ID.

    Args:
        id: The unique ID of the tag.
        include_all_fields: When False (default), returns only commonly used
            fields. Set to True to retrieve all available fields.
    """
    return await get_client().get_tag_by_id(
        id, get_user_token(), include_all_fields=include_all_fields
    )


@mcp.tool()
async def create_tag(
    name: str,
    slug: str,
    description: str = "",
    ctx: Context = None
) -> dict[str, Any]:
    """Create a new tag.

    Args:
        name: Name of the new tag (required).
        slug: URL-friendly slug (required).
        description: Tag description. Defaults to empty.
    """
    params = CreateTagParam(
        name=name, slug=slug, description=description,
    )
    return await get_client().create_tag(
        params.model_dump(exclude_unset=True), get_user_token(),
        include_all_fields=ALLOW_ALL_AGGREGATE
    )


@mcp.tool()
async def update_tag(
    id: int,
    name: str = None,
    slug: str = None,
    description: str = None,
    ctx: Context = None
) -> dict[str, Any]:
    """Update an existing tag.

    Args:
        id: The unique ID of the tag to update (required).
        name: New name for the tag.
        slug: New URL-friendly slug.
        description: New description.
    """
    payload = {}
    if name is not None:
        payload["name"] = name
    if slug is not None:
        payload["slug"] = slug
    if description is not None:
        payload["description"] = description
    return await get_client().update_tag(id, payload, get_user_token(), include_all_fields=ALLOW_ALL_AGGREGATE)


@mcp.tool()
async def delete_tag_by_id(
    id: int,
    ctx: Context = None
) -> dict[str, Any]:
    """Delete a tag by its ID (permanently - tags don't support trash).

    Args:
        id: The unique ID of the tag to delete.
    """
    result = await get_client().delete_tag_by_id(id, get_user_token())
    if isinstance(result, dict) and result.get("code"):
        raise Exception(result.get("message", f"Delete failed: {result.get('code')}"))
    return {"deleted": True}


# =============================================================================
# Comments Tools
# =============================================================================

@mcp.tool()
async def get_all_comments(
    include_all_fields: bool = False,
    status: str = "",
    per_page: int = 10,
    page: int = 1,
    search: str = "",
    post: int = 0,
    parent: int = 0,
    author: str = "",
    ctx: Context = None
) -> dict[str, Any]:
    """List all comment records.

    Args:
        include_all_fields: When False (default), each comment contains only
            commonly used fields (id, post, author_name, status, parent).
            Set to True to include all available fields.
        status: Filter by comment status (approved, hold, spam, trash).
        per_page: Maximum number of comments to return. Defaults to 10.
        page: Page number for pagination. Defaults to 1.
        search: Search keyword.
        post: Filter by post ID.
        parent: Filter by parent comment ID.
        author: Filter by author.
    """
    data = await get_client().get_all_comments(
        get_user_token(),
        include_all_fields=include_all_fields if ALLOW_ALL_AGGREGATE else False,
        status=status,
        per_page=per_page,
        page=page,
        search=search,
        post=post,
        parent=parent,
        author=author,
    )
    return {"items": json_to_toon(data)}


@mcp.tool()
async def get_comment_by_id(
    id: int,
    include_all_fields: bool = False,
    ctx: Context = None
) -> dict[str, Any]:
    """Get a single comment by its ID.

    Args:
        id: The unique ID of the comment.
        include_all_fields: When False (default), returns only commonly used
            fields. Set to True to retrieve all available fields.
    """
    return await get_client().get_comment_by_id(
        id, get_user_token(), include_all_fields=include_all_fields
    )


@mcp.tool()
async def create_comment(
    post: int,
    content: str,
    status: str,
    parent: int = 0,
    author_name: str = "",
    author_url: str = "",
    ctx: Context = None
) -> dict[str, Any]:
    """Create a new comment.

    Args:
        post: The post ID to attach the comment to (required).
        content: Comment content text (required).
        status: Comment status - approved, hold, spam, trash (required).
        parent: Parent comment ID for threaded replies. Defaults to 0.
        author_name: Name of the comment author. Defaults to empty.
        author_url: URL of the comment author. Defaults to empty.
    """
    params = CreateCommentParam(
        post=post, content=content, status=status,
        parent=parent, author_name=author_name, author_url=author_url,
    )
    return await get_client().create_comment(
        params.model_dump(exclude_unset=True), get_user_token(),
        include_all_fields=ALLOW_ALL_AGGREGATE
    )


@mcp.tool()
async def update_comment(
    id: int,
    content: str = None,
    status: str = None,
    author_name: str = None,
    author_url: str = None,
    ctx: Context = None
) -> dict[str, Any]:
    """Update an existing comment.

    Args:
        id: The unique ID of the comment to update (required).
        content: New content for the comment.
        status: New status (approved, hold, spam, trash).
        author_name: New author name.
        author_url: New author URL.
    """
    payload = {}
    if content is not None:
        payload["content"] = content
    if status is not None:
        payload["status"] = status
    if author_name is not None:
        payload["author_name"] = author_name
    if author_url is not None:
        payload["author_url"] = author_url
    return await get_client().update_comment(id, payload, get_user_token(), include_all_fields=ALLOW_ALL_AGGREGATE)


@mcp.tool()
async def delete_comment_by_id(
    id: int,
    ctx: Context = None
) -> dict[str, Any]:
    """Delete a comment by its ID (permanently).

    Args:
        id: The unique ID of the comment to delete.
    """
    result = await get_client().delete_comment_by_id(id, get_user_token())
    if isinstance(result, dict) and result.get("code"):
        raise Exception(result.get("message", f"Delete failed: {result.get('code')}"))
    return {"deleted": True}


# =============================================================================
# Users Tools
# =============================================================================

@mcp.tool()
async def get_all_users(
    include_all_fields: bool = False,
    per_page: int = 10,
    page: int = 1,
    search: str = "",
    roles: str = "",
    orderby: str = "name",
    order: str = "asc",
    ctx: Context = None
) -> dict[str, Any]:
    """List all user records.

    Args:
        include_all_fields: When False (default), each user contains only
            commonly used fields (id, name, slug, link).
            Set to True to include all available fields.
        per_page: Maximum number of users to return. Defaults to 10.
        page: Page number for pagination. Defaults to 1.
        search: Search keyword.
        roles: Filter by role.
        orderby: Sort field. Defaults to "name".
        order: Sort direction (asc or desc). Defaults to "asc".
    """
    data = await get_client().get_all_users(
        get_user_token(),
        include_all_fields=include_all_fields if ALLOW_ALL_AGGREGATE else False,
        per_page=per_page,
        page=page,
        search=search,
        roles=roles,
        orderby=orderby,
        order=order,
    )
    return {"items": json_to_toon(data)}


@mcp.tool()
async def get_user_by_id(
    id: int,
    include_all_fields: bool = False,
    ctx: Context = None
) -> dict[str, Any]:
    """Get a single user by their ID.

    Args:
        id: The unique ID of the user.
        include_all_fields: When False (default), returns only commonly used
            fields. Set to True to retrieve all available fields.
    """
    return await get_client().get_user_by_id(
        id, get_user_token(), include_all_fields=include_all_fields
    )


@mcp.tool()
async def get_current_user(
    include_all_fields: bool = False,
    ctx: Context = None
) -> dict[str, Any]:
    """Get the current authenticated user.

    Args:
        include_all_fields: When False (default), returns only commonly used
            fields. Set to True to retrieve all available fields.
    """
    return await get_client().get_current_user(
        get_user_token(), include_all_fields=include_all_fields
    )


# =============================================================================
# Navigation Tools
# =============================================================================

@mcp.tool()
async def get_all_navigation(
    include_all_fields: bool = False,
    per_page: int = 10,
    page: int = 1,
    search: str = "",
    ctx: Context = None
) -> dict[str, Any]:
    """List all navigation menu records.

    Args:
        include_all_fields: When False (default), each navigation contains only
            commonly used fields (id, title, status, slug).
            Set to True to include all available fields.
        per_page: Maximum number of navigation menus to return. Defaults to 10.
        page: Page number for pagination. Defaults to 1.
        search: Search keyword.
    """
    data = await get_client().get_all_navigation(
        get_user_token(),
        include_all_fields=include_all_fields if ALLOW_ALL_AGGREGATE else False,
        per_page=per_page,
        page=page,
        search=search,
    )
    return {"items": json_to_toon(data)}


@mcp.tool()
async def get_navigation_by_id(
    id: int,
    include_all_fields: bool = False,
    ctx: Context = None
) -> dict[str, Any]:
    """Get a single navigation menu by its ID.

    Args:
        id: The unique ID of the navigation menu.
        include_all_fields: When False (default), returns only commonly used
            fields. Set to True to retrieve all available fields.
    """
    return await get_client().get_navigation_by_id(
        id, get_user_token(), include_all_fields=include_all_fields
    )


@mcp.tool()
async def create_navigation(
    title: str,
    status: str,
    slug: str = "",
    content: str = "",
    template: str = "",
    ctx: Context = None
) -> dict[str, Any]:
    """Create a new navigation menu.

    Args:
        title: Title of the new navigation menu (required).
        status: Navigation status - publish, draft, etc. (required).
        slug: URL-friendly slug. Defaults to empty.
        content: Navigation content (menu items). Defaults to empty.
        template: Template file name. Defaults to empty.
    """
    params = CreateNavigationParam(
        title=title, status=status, slug=slug,
        content=content, template=template,
    )
    return await get_client().create_navigation(
        params.model_dump(exclude_unset=True), get_user_token(),
        include_all_fields=ALLOW_ALL_AGGREGATE
    )


@mcp.tool()
async def update_navigation(
    id: int,
    title: str = None,
    status: str = None,
    slug: str = None,
    content: str = None,
    template: str = None,
    ctx: Context = None
) -> dict[str, Any]:
    """Update an existing navigation menu.

    Args:
        id: The unique ID of the navigation menu to update (required).
        title: New title.
        status: New status.
        slug: New URL-friendly slug.
        content: New navigation content.
        template: New template file name.
    """
    payload = {}
    if title is not None:
        payload["title"] = title
    if status is not None:
        payload["status"] = status
    if slug is not None:
        payload["slug"] = slug
    if content is not None:
        payload["content"] = content
    if template is not None:
        payload["template"] = template
    return await get_client().update_navigation(id, payload, get_user_token(), include_all_fields=ALLOW_ALL_AGGREGATE)


@mcp.tool()
async def delete_navigation_by_id(
    id: int,
    ctx: Context = None
) -> dict[str, Any]:
    """Delete a navigation menu by its ID (permanently).

    Args:
        id: The unique ID of the navigation menu to delete.
    """
    result = await get_client().delete_navigation_by_id(id, get_user_token())
    if isinstance(result, dict) and result.get("code"):
        raise Exception(result.get("message", f"Delete failed: {result.get('code')}"))
    return {"deleted": True}


# =============================================================================
# Blocks Tools
# =============================================================================

@mcp.tool()
async def get_all_blocks(
    include_all_fields: bool = False,
    status: str = "",
    per_page: int = 10,
    page: int = 1,
    search: str = "",
    ctx: Context = None
) -> dict[str, Any]:
    """List all block records.

    Args:
        include_all_fields: When False (default), each block contains only
            commonly used fields (id, title, status, slug).
            Set to True to include all available fields.
        status: Filter by block status.
        per_page: Maximum number of blocks to return. Defaults to 10.
        page: Page number for pagination. Defaults to 1.
        search: Search keyword.
    """
    data = await get_client().get_all_blocks(
        get_user_token(),
        include_all_fields=include_all_fields if ALLOW_ALL_AGGREGATE else False,
        status=status,
        per_page=per_page,
        page=page,
        search=search,
    )
    return {"items": json_to_toon(data)}


@mcp.tool()
async def get_block_by_id(
    id: int,
    include_all_fields: bool = False,
    ctx: Context = None
) -> dict[str, Any]:
    """Get a single block by its ID.

    Args:
        id: The unique ID of the block.
        include_all_fields: When False (default), returns only commonly used
            fields. Set to True to retrieve all available fields.
    """
    return await get_client().get_block_by_id(
        id, get_user_token(), include_all_fields=include_all_fields
    )


@mcp.tool()
async def create_block(
    title: str,
    content: str,
    status: str,
    slug: str = "",
    template: str = "",
    ctx: Context = None
) -> dict[str, Any]:
    """Create a new block.

    Args:
        title: Title of the new block (required).
        content: Block content (required).
        status: Block status - publish, draft, etc. (required).
        slug: URL-friendly slug. Defaults to empty.
        template: Template file name. Defaults to empty.
    """
    params = CreateBlockParam(
        title=title, content=content, status=status,
        slug=slug, template=template,
    )
    return await get_client().create_block(
        params.model_dump(exclude_unset=True), get_user_token(),
        include_all_fields=ALLOW_ALL_AGGREGATE,
    )


@mcp.tool()
async def update_block(
    id: int,
    title: str = None,
    content: str = None,
    status: str = None,
    slug: str = None,
    template: str = None,
    ctx: Context = None
) -> dict[str, Any]:
    """Update an existing block.

    Args:
        id: The unique ID of the block to update (required).
        title: New title.
        content: New block content.
        status: New status.
        slug: New URL-friendly slug.
        template: New template file name.
    """
    payload = {}
    if title is not None:
        payload["title"] = title
    if content is not None:
        payload["content"] = content
    if status is not None:
        payload["status"] = status
    if slug is not None:
        payload["slug"] = slug
    if template is not None:
        payload["template"] = template
    return await get_client().update_block(
        id, payload, get_user_token(), include_all_fields=ALLOW_ALL_AGGREGATE,
    )


@mcp.tool()
async def delete_block_by_id(
    id: int,
    ctx: Context = None
) -> dict[str, Any]:
    """Delete a block by its ID (permanently).

    Args:
        id: The unique ID of the block to delete.
    """
    result = await get_client().delete_block_by_id(id, get_user_token())
    if isinstance(result, dict) and result.get("code"):
        raise Exception(result.get("message", f"Delete failed: {result.get('code')}"))
    return {"deleted": True}


# =============================================================================
# Meta Tools
# =============================================================================

@mcp.tool()
async def get_taxonomies(
    ctx: Context = None
) -> dict[str, Any]:
    """List all registered taxonomies (categories, tags, nav_menu, etc.)."""
    return await get_client().get_taxonomies(get_user_token())


@mcp.tool()
async def get_taxonomy_by_name(
    name: str,
    ctx: Context = None
) -> dict[str, Any]:
    """Get details of a specific taxonomy by its name.

    Args:
        name: The taxonomy name (e.g., category, post_tag, nav_menu).
    """
    return await get_client().get_taxonomy_by_name(name, get_user_token())


@mcp.tool()
async def get_post_types(
    ctx: Context = None
) -> dict[str, Any]:
    """List all registered post types (post, page, attachment, etc.)."""
    return await get_client().get_post_types(get_user_token())


@mcp.tool()
async def get_post_type_by_name(
    type: str,
    ctx: Context = None
) -> dict[str, Any]:
    """Get details of a specific post type.

    Args:
        type: The post type name (e.g., post, page, wp_block).
    """
    return await get_client().get_post_type_by_name(type, get_user_token())


@mcp.tool()
async def get_post_statuses(
    ctx: Context = None
) -> dict[str, Any]:
    """List all registered post statuses (publish, draft, private, etc.)."""
    return await get_client().get_post_statuses(get_user_token())


@mcp.tool()
async def get_post_status_by_slug(
    status: str,
    ctx: Context = None
) -> dict[str, Any]:
    """Get details of a specific post status.

    Args:
        status: The status slug (e.g., publish, draft, private).
    """
    return await get_client().get_post_status_by_slug(status, get_user_token())


@mcp.tool()
async def search_content(
    query: str,
    search_type: str = "post",
    per_page: int = 10,
    page: int = 1,
    ctx: Context = None
) -> dict[str, Any]:
    """Search across WordPress content.

    Args:
        query: Search keyword or phrase (required).
        search_type: Type of content to search (post, page, etc.). Defaults to "post".
        per_page: Maximum number of results. Defaults to 10.
        page: Page number for pagination. Defaults to 1.
    """
    data = await get_client().search_content(
        query, get_user_token(), search_type=search_type,
        per_page=per_page, page=page,
    )
    return {"results": json_to_toon(data)}


@mcp.tool()
async def get_server_status(
    ctx: Context = None
) -> dict[str, Any]:
    """Check connectivity to the WordPress backend API."""
    import httpx
    client = get_client()
    try:
        async with httpx.AsyncClient(timeout=5.0) as http_client:
            response = await http_client.get(
                f"{client.base_url}/index.php?rest_route=/wp/v2",
                headers={"Authorization": f"Basic {get_user_token()}"}
            )
            return {"status": "connected", "backend_response": response.status_code}
    except Exception as e:
        return {"status": "disconnected", "error": str(e)}


# =============================================================================
# Entry Point
# =============================================================================

def main():
    if not os.getenv("WORDPRESS_BASE_URL"):
        print("ERROR: WORDPRESS_BASE_URL environment variable is required", file=sys.stderr)
        print("Example: export WORDPRESS_BASE_URL=http://wordpress-web:80", file=sys.stderr)
        sys.exit(1)

    port_env = os.getenv("MCP_SERVER_PORT")
    if not port_env:
        print("ERROR: MCP_SERVER_PORT environment variable is required", file=sys.stderr)
        print("Example: export MCP_SERVER_PORT=6016", file=sys.stderr)
        sys.exit(1)

    host = "0.0.0.0"
    port = int(port_env)
    path = "/mcp"
    app = mcp.http_app(path=path)
    app = AuthMiddleware(app)
    print(f"Starting WordPress MCP server on http://{host}:{port}{path}")
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()