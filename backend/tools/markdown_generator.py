"""CityFlow Markdown 文档生成工具。

提供 Markdown 内容的构建块，包括表格、代码块、目录、
列表等常用结构的生成方法。

设计为无状态工具类，所有方法均为纯函数，便于组合使用。
"""

from __future__ import annotations

from typing import Any


class MarkdownGenerator:
    """Markdown 内容生成器。

    提供生成常见 Markdown 结构的工具方法，
    所有方法返回纯字符串，可直接拼接使用。

    Examples
    --------
    >>> md = MarkdownGenerator()
    >>> table = md.generate_table(
    ...     headers=["名称", "值"],
    ...     rows=[["A", "1"], ["B", "2"]],
    ... )
    >>> print(table)
    | 名称 | 值 |
    | --- | --- |
    | A | 1 |
    | B | 2 |
    """

    # ------------------------------------------------------------------
    # 表格
    # ------------------------------------------------------------------

    def generate_table(
        self,
        headers: list[str],
        rows: list[list[str]],
        *,
        align: str = "left",
    ) -> str:
        """生成 Markdown 表格。

        Parameters
        ----------
        headers : list[str]
            表头列表。
        rows : list[list[str]]
            数据行列表，每行长度应与 headers 一致。
        align : str
            列对齐方式，可选 ``"left"``/``"center"``/``"right"``，默认 ``"left"``。

        Returns
        -------
        str
            Markdown 表格字符串。

        Examples
        --------
        >>> md = MarkdownGenerator()
        >>> print(md.generate_table(["Name", "Age"], [["Alice", "30"]]))
        | Name | Age |
        | --- | --- |
        | Alice | 30 |
        """
        if not headers:
            return ""

        # 对齐符号
        align_map = {
            "left": ":---",
            "center": ":---:",
            "right": "---:",
        }
        separator = align_map.get(align, ":---")

        lines: list[str] = []

        # 表头
        lines.append("| " + " | ".join(headers) + " |")

        # 分隔行
        lines.append("| " + " | ".join([separator] * len(headers)) + " |")

        # 数据行
        for row in rows:
            # 补齐列数
            padded_row = list(row) + [""] * (len(headers) - len(row))
            lines.append("| " + " | ".join(padded_row[: len(headers)]) + " |")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 代码块
    # ------------------------------------------------------------------

    def generate_code_block(
        self,
        code: str,
        language: str = "python",
    ) -> str:
        """生成带语法高亮标记的代码块。

        Parameters
        ----------
        code : str
            代码内容。
        language : str
            编程语言标识，默认 ``"python"``。

        Returns
        -------
        str
            Markdown 代码块字符串。

        Examples
        --------
        >>> md = MarkdownGenerator()
        >>> print(md.generate_code_block("print('hi')", "python"))
        ```python
        print('hi')
        ```
        """
        return f"```{language}\n{code}\n```"

    def generate_inline_code(self, text: str) -> str:
        """生成行内代码标记。

        Parameters
        ----------
        text : str
            代码文本。

        Returns
        -------
        str
            带反引号的行内代码。
        """
        return f"`{text}`"

    # ------------------------------------------------------------------
    # 目录
    # ------------------------------------------------------------------

    def generate_toc(
        self,
        headings: list[dict[str, Any]],
        *,
        max_depth: int = 3,
    ) -> str:
        """生成 Markdown 目录。

        Parameters
        ----------
        headings : list[dict[str, Any]]
            标题列表，每项包含 ``level``（标题级别）和 ``title``（标题文本）。
        max_depth : int
            最大目录深度，默认 ``3``。

        Returns
        -------
        str
            Markdown 目录字符串。

        Examples
        --------
        >>> md = MarkdownGenerator()
        >>> toc = md.generate_toc([
        ...     {"level": 1, "title": "Introduction"},
        ...     {"level": 2, "title": "Getting Started"},
        ... ])
        >>> print(toc)
        - [Introduction](#introduction)
          - [Getting Started](#getting-started)
        """
        lines: list[str] = []

        for heading in headings:
            level = heading.get("level", 1)
            title = heading.get("title", "")

            if level > max_depth or not title:
                continue

            # 生成锚点：小写，空格替换为连字符，移除特殊字符
            anchor = self._slugify(title)
            indent = "  " * (level - 1)
            lines.append(f"{indent}- [{title}](#{anchor})")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 列表
    # ------------------------------------------------------------------

    def generate_unordered_list(
        self,
        items: list[str],
        *,
        marker: str = "-",
    ) -> str:
        """生成无序列表。

        Parameters
        ----------
        items : list[str]
            列表项内容。
        marker : str
            列表标记符，默认 ``"-"``。

        Returns
        -------
        str
            Markdown 无序列表字符串。
        """
        return "\n".join(f"{marker} {item}" for item in items)

    def generate_ordered_list(self, items: list[str]) -> str:
        """生成有序列表。

        Parameters
        ----------
        items : list[str]
            列表项内容。

        Returns
        -------
        str
            Markdown 有序列表字符串。
        """
        return "\n".join(f"{i + 1}. {item}" for i, item in enumerate(items))

    # ------------------------------------------------------------------
    # 标题与分隔
    # ------------------------------------------------------------------

    def generate_heading(self, text: str, level: int = 1) -> str:
        """生成标题。

        Parameters
        ----------
        text : str
            标题文本。
        level : int
            标题级别（1-6），默认 ``1``。

        Returns
        -------
        str
            Markdown 标题字符串。
        """
        level = max(1, min(6, level))
        return f"{'#' * level} {text}"

    def generate_horizontal_rule(self) -> str:
        """生成水平分隔线。

        Returns
        -------
        str
            水平分隔线 ``---``。
        """
        return "---"

    # ------------------------------------------------------------------
    # 链接与引用
    # ------------------------------------------------------------------

    def generate_link(self, text: str, url: str) -> str:
        """生成超链接。

        Parameters
        ----------
        text : str
            链接文本。
        url : str
            链接地址。

        Returns
        -------
        str
            Markdown 链接。
        """
        return f"[{text}]({url})"

    def generate_image(self, alt: str, url: str) -> str:
        """生成图片。

        Parameters
        ----------
        alt : str
            替代文本。
        url : str
            图片地址。

        Returns
        -------
        str
            Markdown 图片。
        """
        return f"![{alt}]({url})"

    def generate_blockquote(self, text: str) -> str:
        """生成引用块。

        Parameters
        ----------
        text : str
            引用文本，支持多行。

        Returns
        -------
        str
            Markdown 引用块。
        """
        lines = text.split("\n")
        return "\n".join(f"> {line}" for line in lines)

    # ------------------------------------------------------------------
    # 混合内容
    # ------------------------------------------------------------------

    def generate_key_value_pairs(
        self,
        data: dict[str, str],
        *,
        separator: str = ":",
    ) -> str:
        """生成键值对列表。

        Parameters
        ----------
        data : dict[str, str]
            键值对数据。
        separator : str
            键值分隔符，默认 ``":"``。

        Returns
        -------
        str
            格式化后的键值对文本。
        """
        lines: list[str] = []
        for key, value in data.items():
            lines.append(f"**{key}**{separator} {value}")
        return "\n".join(lines)

    def generate_details_block(
        self,
        summary: str,
        content: str,
    ) -> str:
        """生成可折叠的详情块（HTML <details> 标签）。

        Parameters
        ----------
        summary : str
            摘要标题。
        content : str
            展开后的内容。

        Returns
        -------
        str
            HTML details 块。
        """
        return f"<details>\n<summary>{summary}</summary>\n\n{content}\n\n</details>"

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    @staticmethod
    def _slugify(text: str) -> str:
        """将文本转换为 URL 友好的锚点格式。

        Parameters
        ----------
        text : str
            原始文本。

        Returns
        -------
        str
            锚点字符串。
        """
        # 转小写
        slug = text.lower()
        # 空格替换为连字符
        slug = slug.replace(" ", "-")
        # 移除非字母数字和连字符的字符
        slug = "".join(c for c in slug if c.isalnum() or c == "-")
        # 合并连续连字符
        while "--" in slug:
            slug = slug.replace("--", "-")
        return slug.strip("-")
