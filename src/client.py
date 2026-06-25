import os
import datetime as dt
import re
from typing import Any, Optional

import httpx


def _normalize_datetime(value: str) -> str:
    if re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$', value):
        parsed = dt.datetime.fromisoformat(value)
        parsed = parsed.astimezone(dt.timezone.utc)
        return parsed.strftime('%Y-%m-%d %H:%M:%S')
    if re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', value):
        raise ValueError(
            f"Invalid datetime: {value}. Timezone offset is required. "
            "Must use format: 2026-06-22T15:00:00-04:00"
        )
    return value


class WordPressClient:
    """Client for WordPress API with Basic auth passthrough."""

    def __init__(
        self,
        base_url: Optional[str] = None,
    ):
        self.base_url = (base_url or os.getenv("WORDPRESS_BASE_URL", "")).rstrip("/")

        if not self.base_url:
            raise ValueError(
                "WordPress URL required. Set WORDPRESS_BASE_URL env var "
                "or pass base_url."
            )

    def _get_headers(self, api_key: Optional[str] = None) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
        }
        if api_key:
            headers["Authorization"] = f"Basic {api_key}"
        return headers

    def _normalize_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            k: _normalize_datetime(v) if isinstance(v, str) else v
            for k, v in payload.items()
        }

    async def request(
        self,
        method: str,
        path: str,
        api_key: Optional[str] = None,
        **kwargs: Any,
    ) -> Any:
        url = f"{self.base_url}/index.php"
        headers = self._get_headers(api_key)

        params = kwargs.pop("params", {})
        params["rest_route"] = path

        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            response = await client.request(
                method,
                url,
                headers=headers,
                params=params,
                **kwargs,
            )
            response.raise_for_status()

            if response.status_code == 204:
                return {}
            if response.headers.get("content-type", "").startswith("application/json"):
                return response.json()
            return {"text": response.text}

    async def get(self, path: str, api_key: Optional[str] = None, **kwargs: Any) -> Any:
        return await self.request("GET", path, api_key, **kwargs)

    async def post(self, path: str, api_key: Optional[str] = None, **kwargs: Any) -> Any:
        return await self.request("POST", path, api_key, **kwargs)

    async def put(self, path: str, api_key: Optional[str] = None, **kwargs: Any) -> Any:
        return await self.request("PUT", path, api_key, **kwargs)

    async def patch(self, path: str, api_key: Optional[str] = None, **kwargs: Any) -> Any:
        return await self.request("PATCH", path, api_key, **kwargs)

    async def delete(self, path: str, api_key: Optional[str] = None, **kwargs: Any) -> Any:
        return await self.request("DELETE", path, api_key, **kwargs)

    # =========================================================================
    # Posts
    # =========================================================================

    async def get_all_posts(
        self,
        api_key: Optional[str] = None,
        include_all_fields: bool = False,
        status: str = "",
        per_page: int = 10,
        page: int = 1,
        search: str = "",
        author: str = "",
        orderby: str = "date",
        order: str = "desc",
    ) -> Any:
        params = {"per_page": per_page, "page": page, "orderby": orderby, "order": order}
        if status:
            params["status"] = status
        if search:
            params["search"] = search
        if author:
            params["author"] = author
        if include_all_fields:
            params["context"] = "edit"
        else:
            params["context"] = "embed"
        return await self.get("/wp/v2/posts", api_key, params=params or None)

    async def get_post_by_id(
        self,
        post_id: int,
        api_key: Optional[str] = None,
        include_all_fields: bool = False,
    ) -> Any:
        params = {}
        if include_all_fields:
            params["context"] = "edit"
        else:
            params["context"] = "embed"
        return await self.get(f"/wp/v2/posts/{post_id}", api_key, params=params or None)

    async def create_post(
        self,
        payload: dict[str, Any],
        api_key: Optional[str] = None,
    ) -> Any:
        normalized = self._normalize_payload(payload)
        return await self.post("/wp/v2/posts", api_key, json=normalized)

    async def update_post(
        self,
        post_id: int,
        payload: dict[str, Any],
        api_key: Optional[str] = None,
    ) -> Any:
        normalized = self._normalize_payload(payload)
        return await self.put(f"/wp/v2/posts/{post_id}", api_key, json=normalized)

    async def delete_post_by_id(
        self,
        post_id: int,
        api_key: Optional[str] = None,
        force: bool = False,
    ) -> Any:
        params = {"force": "true" if force else "false"}
        return await self.delete(f"/wp/v2/posts/{post_id}", api_key, params=params)

    # =========================================================================
    # Pages
    # =========================================================================

    async def get_all_pages(
        self,
        api_key: Optional[str] = None,
        include_all_fields: bool = False,
        status: str = "",
        per_page: int = 10,
        page: int = 1,
        search: str = "",
        author: str = "",
        parent: int = 0,
        orderby: str = "date",
        order: str = "desc",
    ) -> Any:
        params = {"per_page": per_page, "page": page, "orderby": orderby, "order": order}
        if status:
            params["status"] = status
        if search:
            params["search"] = search
        if author:
            params["author"] = author
        if parent:
            params["parent"] = parent
        if include_all_fields:
            params["context"] = "edit"
        else:
            params["context"] = "embed"
        return await self.get("/wp/v2/pages", api_key, params=params or None)

    async def get_page_by_id(
        self,
        page_id: int,
        api_key: Optional[str] = None,
        include_all_fields: bool = False,
    ) -> Any:
        params = {}
        if include_all_fields:
            params["context"] = "edit"
        else:
            params["context"] = "embed"
        return await self.get(f"/wp/v2/pages/{page_id}", api_key, params=params or None)

    async def create_page(
        self,
        payload: dict[str, Any],
        api_key: Optional[str] = None,
    ) -> Any:
        normalized = self._normalize_payload(payload)
        return await self.post("/wp/v2/pages", api_key, json=normalized)

    async def update_page(
        self,
        page_id: int,
        payload: dict[str, Any],
        api_key: Optional[str] = None,
    ) -> Any:
        normalized = self._normalize_payload(payload)
        return await self.put(f"/wp/v2/pages/{page_id}", api_key, json=normalized)

    async def delete_page_by_id(
        self,
        page_id: int,
        api_key: Optional[str] = None,
        force: bool = False,
    ) -> Any:
        params = {"force": "true" if force else "false"}
        return await self.delete(f"/wp/v2/pages/{page_id}", api_key, params=params)

    # =========================================================================
    # Categories
    # =========================================================================

    async def get_all_categories(
        self,
        api_key: Optional[str] = None,
        include_all_fields: bool = False,
        per_page: int = 10,
        page: int = 1,
        search: str = "",
        parent: int = 0,
        orderby: str = "name",
        order: str = "asc",
    ) -> Any:
        params = {"per_page": per_page, "page": page, "orderby": orderby, "order": order}
        if search:
            params["search"] = search
        if parent:
            params["parent"] = parent
        if include_all_fields:
            params["context"] = "edit"
        else:
            params["context"] = "embed"
        return await self.get("/wp/v2/categories", api_key, params=params or None)

    async def get_category_by_id(
        self,
        category_id: int,
        api_key: Optional[str] = None,
        include_all_fields: bool = False,
    ) -> Any:
        params = {}
        if include_all_fields:
            params["context"] = "edit"
        else:
            params["context"] = "embed"
        return await self.get(f"/wp/v2/categories/{category_id}", api_key, params=params or None)

    async def create_category(
        self,
        payload: dict[str, Any],
        api_key: Optional[str] = None,
    ) -> Any:
        normalized = self._normalize_payload(payload)
        return await self.post("/wp/v2/categories", api_key, json=normalized)

    async def update_category(
        self,
        category_id: int,
        payload: dict[str, Any],
        api_key: Optional[str] = None,
    ) -> Any:
        normalized = self._normalize_payload(payload)
        return await self.put(f"/wp/v2/categories/{category_id}", api_key, json=normalized)

    async def delete_category_by_id(
        self,
        category_id: int,
        api_key: Optional[str] = None,
        force: bool = False,
    ) -> Any:
        params = {"force": "true" if force else "false"}
        return await self.delete(f"/wp/v2/categories/{category_id}", api_key, params=params)

    # =========================================================================
    # Tags
    # =========================================================================

    async def get_all_tags(
        self,
        api_key: Optional[str] = None,
        include_all_fields: bool = False,
        per_page: int = 10,
        page: int = 1,
        search: str = "",
        orderby: str = "name",
        order: str = "asc",
    ) -> Any:
        params = {"per_page": per_page, "page": page, "orderby": orderby, "order": order}
        if search:
            params["search"] = search
        if include_all_fields:
            params["context"] = "edit"
        else:
            params["context"] = "embed"
        return await self.get("/wp/v2/tags", api_key, params=params or None)

    async def get_tag_by_id(
        self,
        tag_id: int,
        api_key: Optional[str] = None,
        include_all_fields: bool = False,
    ) -> Any:
        params = {}
        if include_all_fields:
            params["context"] = "edit"
        else:
            params["context"] = "embed"
        return await self.get(f"/wp/v2/tags/{tag_id}", api_key, params=params or None)

    async def create_tag(
        self,
        payload: dict[str, Any],
        api_key: Optional[str] = None,
    ) -> Any:
        normalized = self._normalize_payload(payload)
        return await self.post("/wp/v2/tags", api_key, json=normalized)

    async def update_tag(
        self,
        tag_id: int,
        payload: dict[str, Any],
        api_key: Optional[str] = None,
    ) -> Any:
        normalized = self._normalize_payload(payload)
        return await self.put(f"/wp/v2/tags/{tag_id}", api_key, json=normalized)

    async def delete_tag_by_id(
        self,
        tag_id: int,
        api_key: Optional[str] = None,
        force: bool = False,
    ) -> Any:
        params = {"force": "true" if force else "false"}
        return await self.delete(f"/wp/v2/tags/{tag_id}", api_key, params=params)

    # =========================================================================
    # Comments
    # =========================================================================

    async def get_all_comments(
        self,
        api_key: Optional[str] = None,
        include_all_fields: bool = False,
        status: str = "",
        per_page: int = 10,
        page: int = 1,
        search: str = "",
        post: int = 0,
        parent: int = 0,
        author: str = "",
    ) -> Any:
        params = {"per_page": per_page, "page": page}
        if status:
            params["status"] = status
        if search:
            params["search"] = search
        if post:
            params["post"] = post
        if parent:
            params["parent"] = parent
        if author:
            params["author"] = author
        if include_all_fields:
            params["context"] = "edit"
        else:
            params["context"] = "embed"
        return await self.get("/wp/v2/comments", api_key, params=params or None)

    async def get_comment_by_id(
        self,
        comment_id: int,
        api_key: Optional[str] = None,
        include_all_fields: bool = False,
    ) -> Any:
        params = {}
        if include_all_fields:
            params["context"] = "edit"
        else:
            params["context"] = "embed"
        return await self.get(f"/wp/v2/comments/{comment_id}", api_key, params=params or None)

    async def create_comment(
        self,
        payload: dict[str, Any],
        api_key: Optional[str] = None,
    ) -> Any:
        normalized = self._normalize_payload(payload)
        return await self.post("/wp/v2/comments", api_key, json=normalized)

    async def update_comment(
        self,
        comment_id: int,
        payload: dict[str, Any],
        api_key: Optional[str] = None,
    ) -> Any:
        normalized = self._normalize_payload(payload)
        return await self.put(f"/wp/v2/comments/{comment_id}", api_key, json=normalized)

    async def delete_comment_by_id(
        self,
        comment_id: int,
        api_key: Optional[str] = None,
        force: bool = False,
    ) -> Any:
        params = {"force": "true" if force else "false"}
        return await self.delete(f"/wp/v2/comments/{comment_id}", api_key, params=params)

    # =========================================================================
    # Users
    # =========================================================================

    async def get_all_users(
        self,
        api_key: Optional[str] = None,
        include_all_fields: bool = False,
        per_page: int = 10,
        page: int = 1,
        search: str = "",
        roles: str = "",
        orderby: str = "name",
        order: str = "asc",
    ) -> Any:
        params = {"per_page": per_page, "page": page, "orderby": orderby, "order": order}
        if search:
            params["search"] = search
        if roles:
            params["roles"] = roles
        if include_all_fields:
            params["context"] = "edit"
        else:
            params["context"] = "embed"
        return await self.get("/wp/v2/users", api_key, params=params or None)

    async def get_user_by_id(
        self,
        user_id: int,
        api_key: Optional[str] = None,
        include_all_fields: bool = False,
    ) -> Any:
        params = {}
        if include_all_fields:
            params["context"] = "edit"
        else:
            params["context"] = "embed"
        return await self.get(f"/wp/v2/users/{user_id}", api_key, params=params or None)

    async def get_current_user(
        self,
        api_key: Optional[str] = None,
        include_all_fields: bool = False,
    ) -> Any:
        params = {}
        if include_all_fields:
            params["context"] = "edit"
        else:
            params["context"] = "embed"
        return await self.get("/wp/v2/users/me", api_key, params=params or None)

    # =========================================================================
    # Navigation
    # =========================================================================

    async def get_all_navigation(
        self,
        api_key: Optional[str] = None,
        include_all_fields: bool = False,
        per_page: int = 10,
        page: int = 1,
        search: str = "",
    ) -> Any:
        params = {"per_page": per_page, "page": page}
        if search:
            params["search"] = search
        if include_all_fields:
            params["context"] = "edit"
        else:
            params["context"] = "embed"
        return await self.get("/wp/v2/navigation", api_key, params=params or None)

    async def get_navigation_by_id(
        self,
        navigation_id: int,
        api_key: Optional[str] = None,
        include_all_fields: bool = False,
    ) -> Any:
        params = {}
        if include_all_fields:
            params["context"] = "edit"
        else:
            params["context"] = "embed"
        return await self.get(f"/wp/v2/navigation/{navigation_id}", api_key, params=params or None)

    async def create_navigation(
        self,
        payload: dict[str, Any],
        api_key: Optional[str] = None,
    ) -> Any:
        normalized = self._normalize_payload(payload)
        return await self.post("/wp/v2/navigation", api_key, json=normalized)

    async def update_navigation(
        self,
        navigation_id: int,
        payload: dict[str, Any],
        api_key: Optional[str] = None,
    ) -> Any:
        normalized = self._normalize_payload(payload)
        return await self.put(f"/wp/v2/navigation/{navigation_id}", api_key, json=normalized)

    async def delete_navigation_by_id(
        self,
        navigation_id: int,
        api_key: Optional[str] = None,
        force: bool = False,
    ) -> Any:
        params = {"force": "true" if force else "false"}
        return await self.delete(f"/wp/v2/navigation/{navigation_id}", api_key, params=params)

    # =========================================================================
    # Blocks
    # =========================================================================

    async def get_all_blocks(
        self,
        api_key: Optional[str] = None,
        include_all_fields: bool = False,
        status: str = "",
        per_page: int = 10,
        page: int = 1,
        search: str = "",
    ) -> Any:
        params = {"per_page": per_page, "page": page}
        if status:
            params["status"] = status
        if search:
            params["search"] = search
        if include_all_fields:
            params["context"] = "edit"
        else:
            params["context"] = "embed"
        return await self.get("/wp/v2/blocks", api_key, params=params or None)

    async def get_block_by_id(
        self,
        block_id: int,
        api_key: Optional[str] = None,
        include_all_fields: bool = False,
    ) -> Any:
        params = {}
        if include_all_fields:
            params["context"] = "edit"
        else:
            params["context"] = "embed"
        return await self.get(f"/wp/v2/blocks/{block_id}", api_key, params=params or None)

    async def create_block(
        self,
        payload: dict[str, Any],
        api_key: Optional[str] = None,
    ) -> Any:
        normalized = self._normalize_payload(payload)
        return await self.post("/wp/v2/blocks", api_key, json=normalized)

    async def update_block(
        self,
        block_id: int,
        payload: dict[str, Any],
        api_key: Optional[str] = None,
    ) -> Any:
        normalized = self._normalize_payload(payload)
        return await self.put(f"/wp/v2/blocks/{block_id}", api_key, json=normalized)

    async def delete_block_by_id(
        self,
        block_id: int,
        api_key: Optional[str] = None,
        force: bool = False,
    ) -> Any:
        params = {"force": "true" if force else "false"}
        return await self.delete(f"/wp/v2/blocks/{block_id}", api_key, params=params)

    # =========================================================================
    # Meta Tools
    # =========================================================================

    async def get_taxonomies(
        self,
        api_key: Optional[str] = None,
    ) -> Any:
        return await self.get("/wp/v2/taxonomies", api_key)

    async def get_taxonomy_by_name(
        self,
        taxonomy: str,
        api_key: Optional[str] = None,
    ) -> Any:
        return await self.get(f"/wp/v2/taxonomies/{taxonomy}", api_key)

    async def get_post_types(
        self,
        api_key: Optional[str] = None,
    ) -> Any:
        return await self.get("/wp/v2/types", api_key)

    async def get_post_type_by_name(
        self,
        post_type: str,
        api_key: Optional[str] = None,
    ) -> Any:
        return await self.get(f"/wp/v2/types/{post_type}", api_key)

    async def get_post_statuses(
        self,
        api_key: Optional[str] = None,
    ) -> Any:
        return await self.get("/wp/v2/statuses", api_key)

    async def get_post_status_by_slug(
        self,
        status: str,
        api_key: Optional[str] = None,
    ) -> Any:
        return await self.get(f"/wp/v2/statuses/{status}", api_key)

    async def search_content(
        self,
        query: str,
        api_key: Optional[str] = None,
        search_type: str = "post",
        per_page: int = 10,
        page: int = 1,
    ) -> Any:
        params = {"search": query, "type": search_type, "per_page": per_page, "page": page}
        return await self.get("/wp/v2/search", api_key, params=params)

    async def get_server_status(
        self,
        api_key: Optional[str] = None,
    ) -> Any:
        return await self.get("/wp/v2", api_key)