# -*- coding: utf-8 -*-
"""雪球大V文章抓取 —— 接口版（Chrome 当通行证 + JSON 接口，不解析 DOM）。

与旧版 `apps/xueqiu/` 的关系
============================
* 输出目录、文件布局、汇总文件名保持一致，可**直接接手旧数据**：
    - 目录：`<data_dir>/<作者ID>_<作者名>/<作者ID>_<年月>.html`
    - 索引：`all_authors.json` / `scraped_authors.json` / `update_latest.html`
* 判定"新文章"改用 status **id**（旧版按链接字符串去重，链接一坏就失效）。
* 归档 HTML 增加了**标题**与 `data-status-id`（用于幂等去重）。

抓取流程
========
1. Chrome 打开 `xueqiu.com` 过 WAF；
2. 作者列表：`all_authors.json` 优先，缺失/`--refresh-authors` 时用关注列表接口；
3. 每个作者：`user_timeline` 分页 → 按 `created_at` 过滤当天（或 `--all-history` 全量）
   → 列表 `text` 为空（长文）再取 `show.json` 全文 → 写入归档；
4. 生成 `update_latest.html` 汇总。

用法
====
    python3 xueqiu_scraper.py --mode=full          # 当天更新（默认）
    python3 xueqiu_scraper.py --all-history        # 全量历史
    python3 xueqiu_scraper.py --check              # 连通性自检（不写数据）
    python3 xueqiu_scraper.py --refresh-authors    # 刷新关注列表（需登录）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from config import get_path, setup_logger  # noqa: E402

from xueqiu_api import (  # noqa: E402
    BrowserTransport,
    XueqiuAPIError,
    XueqiuClient,
    clean_article_text,
)

_DEFAULT_DATA_DIR = os.environ.get("XUEQIU_DATA_DIR") or get_path(
    "xueqiu", "data_dir", fallback="/data/xueqiu_data"
)
logger = setup_logger("xueqiu_api", log_file=os.path.join(_DEFAULT_DATA_DIR, "log_api.txt"))

ALL_AUTHORS_FILE = "all_authors.json"
SCRAPED_AUTHORS_FILE = "scraped_authors.json"
AUTHOR_ID_MAP_FILE = "author_id_map.json"
UPDATE_SUMMARY_FILE = "update_latest.html"
PAGE_SIZE = 20
MAX_PAGES = 200  # 安全上限
AUTHOR_DELAY = 4.0  # 作者之间的间隔（秒）
PAGE_DELAY = 2.0  # 翻下一页的间隔（秒）


# ---------------------------------------------------------------------- 参数/工具
def sanitize_filename(name: str) -> str:
    """清理文件名里的非法字符。"""
    cleaned = re.sub(r'[<>:"/\\|?*]', "", str(name))
    cleaned = cleaned.strip()
    return (cleaned or "untitled")[:100]


def status_datetime(status: Dict[str, Any]) -> datetime:
    """帖子发布时间的本地 datetime（`created_at` 是毫秒时间戳）。"""
    return datetime.fromtimestamp(int(status["created_at"]) / 1000)


# ---------------------------------------------------------------------- 归档
_PAGE_CSS = """
    body { font-family: 'Microsoft YaHei','SimHei','Segoe UI',Tahoma,sans-serif;
           line-height: 1.8; margin: 0; padding: 20px;
           background: linear-gradient(135deg,#f5f7fa 0%,#c3cfe2 100%);
           color: #2c3e50; min-height: 100vh; }
    .container { max-width: 1200px; margin: 20px auto; background: #fff;
                 padding: 40px; border-radius: 15px;
                 box-shadow: 0 10px 30px rgba(0,0,0,.15); position: relative; overflow: hidden; }
    .container::before { content: ''; position: absolute; top: 0; left: 0; width: 100%; height: 5px;
                         background: linear-gradient(90deg,#3498db,#2ecc71,#e74c3c,#9b59b6); }
    h1 { text-align: center; color: #2c3e50; border-bottom: 3px solid #3498db;
         padding-bottom: 15px; margin-top: 0; font-size: 2.2em; }
    .article { margin-bottom: 35px; padding: 25px; border-left: 5px solid #3498db;
               background: linear-gradient(to right,#f8f9fa,#fff); border-radius: 0 10px 0;
               box-shadow: 0 4px 8px rgba(0,0,0,.05); }
    .article .title { margin: 0 0 10px; color: #2c3e50; font-size: 1.4em; }
    .meta-info { color: #7f8c8d; font-size: .9em; }
    .publish-time { color: #e74c3c; font-weight: bold; }
    .content { margin-top: 15px; font-size: 1.1em; line-height: 1.8; }
    .divider { border: 0; height: 1px; background: #ddd; margin: 30px 0; }
    a { color: #3498db; text-decoration: none; }
    a:hover { text-decoration: underline; }
"""

_PAGE_HEADER = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{name} - 雪球文章</title>
    <style>{css}</style>
</head>
<body>
    <div class="container">
        <h1>{name} - 雪球文章</h1>
"""

_PAGE_FOOTER = """
    </div>
</body>
</html>
"""


class ArticleStore:
    """按月归档文章到 HTML，并用 `data-status-id` 做幂等去重。"""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def author_dir(self, author: Dict[str, str]) -> Path:
        d = self.output_dir / f"{author['id']}_{sanitize_filename(author['name'])}"
        d.mkdir(exist_ok=True)
        return d

    def month_file(self, author: Dict[str, str], dt: datetime) -> Path:
        return self.author_dir(author) / f"{author['id']}_{dt.strftime('%Y-%m')}.html"

    @staticmethod
    def _marker(status_id: Any) -> str:
        return f"data-status-id='{status_id}'"

    def exists(self, author: Dict[str, str], dt: datetime, status_id: Any) -> bool:
        path = self.month_file(author, dt)
        if not path.exists():
            return False
        try:
            return self._marker(status_id) in path.read_text(encoding="utf-8")
        except OSError:
            return False

    def save(self, author: Dict[str, str], article: Dict[str, str], dt: datetime) -> bool:
        """写入文章；已存在（同 status id）返回 False。"""
        path = self.month_file(author, dt)
        if self.exists(author, dt, article["id"]):
            return False

        content_lines = (
            article["content"].replace("<", "&lt;").replace(">", "&gt;").split("\n")
        )
        formatted = "<br>".join(content_lines)
        block = (
            f"<div class='article' data-status-id='{article['id']}'>\n"
            f"  <div class='header'>\n"
            f"    <h2 class='title'>{article['title']}</h2>\n"
            f"    <div class='meta-info'>\n"
            f"      <span class='author'>作者: {author['name']}</span><br>\n"
            f"      <span class='author-link'>链接: "
            f"<a href='{article['link']}' target='_blank'>{article['link']}</a></span><br>\n"
            f"      <span class='publish-time'>发布时间: {article['time']}</span>\n"
            f"    </div>\n"
            f"  </div>\n"
            f"  <div class='content'>\n    {formatted}\n  </div>\n"
            f"  <hr class='divider'>\n"
            f"</div>\n\n"
        )

        if path.exists():
            existing = path.read_text(encoding="utf-8")
        else:
            existing = _PAGE_HEADER.format(name=author["name"], css=_PAGE_CSS) + _PAGE_FOOTER

        anchor = existing.find("</h1>")
        if anchor == -1:
            raise XueqiuAPIError(f"归档文件缺少 </h1>：{path}")
        insert_at = anchor + len("</h1>")
        combined = existing[:insert_at] + block + existing[insert_at:]
        path.write_text(combined, encoding="utf-8")
        return True


class SummaryWriter:
    """生成当天更新汇总 `update_latest.html`。"""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)

    def write(self, entries: List[Dict[str, str]]) -> Optional[Path]:
        if not entries:
            return None
        rows = []
        for e in entries:
            body = e["content"].replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
            rows.append(
                f"<div class='article'>\n"
                f"  <h2 class='title'>{e['title']}</h2>\n"
                f"  <div class='meta-info'><span class='author'>{e['author']}</span> · "
                f"<span class='publish-time'>{e['time']}</span> · "
                f"<a href='{e['link']}' target='_blank'>{e['link']}</a></div>\n"
                f"  <div class='content'>{body}</div>\n"
                f"  <hr class='divider'>\n"
                f"</div>\n"
            )
        html = _PAGE_HEADER.format(name="雪球更新汇总", css=_PAGE_CSS) + "".join(rows) + _PAGE_FOOTER
        path = self.output_dir / UPDATE_SUMMARY_FILE
        path.write_text(html, encoding="utf-8")
        return path


# ---------------------------------------------------------------------- 作者
class AuthorRepository:
    """作者列表（`all_authors.json`）、已抓记录、slug→数字 id 缓存。"""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _read_json(self, name: str, default: Any) -> Any:
        path = self.output_dir / name
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:  # noqa: BLE001
            logger.warning(f"读取 {name} 失败：{e}")
            return default

    def _write_json(self, name: str, data: Any) -> None:
        (self.output_dir / name).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def load_authors(self) -> List[Dict[str, str]]:
        return self._read_json(ALL_AUTHORS_FILE, []) or []

    def save_authors(self, authors: List[Dict[str, str]]) -> None:
        self._write_json(ALL_AUTHORS_FILE, authors)
        logger.info(f"作者列表已保存到 {self.output_dir / ALL_AUTHORS_FILE}（{len(authors)} 个）")

    def load_scraped(self) -> Dict[str, dict]:
        return self._read_json(SCRAPED_AUTHORS_FILE, {}) or {}

    def save_scraped(self, scraped: Dict[str, dict]) -> None:
        self._write_json(SCRAPED_AUTHORS_FILE, scraped)

    def load_id_map(self) -> Dict[str, str]:
        return self._read_json(AUTHOR_ID_MAP_FILE, {}) or {}

    def save_id_map(self, id_map: Dict[str, str]) -> None:
        self._write_json(AUTHOR_ID_MAP_FILE, id_map)


def fetch_following_authors(client: XueqiuClient) -> Tuple[List[Dict[str, str]], int]:
    """用当前登录账号的关注列表接口拉作者（需登录）。

    返回 `(作者列表, 官方总数)`；`总数>0` 且 `len==总数` 表示拿全了。
    """
    me = client.get_self()
    if not me:
        raise XueqiuAPIError("获取当前登录用户失败：请先在浏览器/容器里登录雪球")
    uid = me.get("id")
    logger.info(f"当前登录：{me.get('screen_name') or me.get('name')}（uid={uid}）")

    friends, total = client.collect_following(str(uid))
    authors: List[Dict[str, str]] = []
    seen = set()
    for f in friends:
        fid = str(f.get("id") or "").strip()
        domain = (f.get("domain") or "").strip()
        name = (f.get("screen_name") or f.get("name") or "").strip()
        if not fid or fid in seen:
            continue
        seen.add(fid)
        authors.append(
            {
                "id": fid,
                "uid": fid,
                "name": name,
                "link": f"https://xueqiu.com/{domain or fid}",
            }
        )
    if total and len(authors) < total:
        logger.warning(f"关注列表可能不完整：拿到 {len(authors)} / 官方 {total}")
    logger.info(f"关注列表获取完成，共 {len(authors)} 个作者（官方 {total}）")
    return authors, total


def merge_authors(
    existing: List[Dict[str, str]], fetched: List[Dict[str, str]]
) -> List[Dict[str, str]]:
    """按 id/uid 合并：保留已有顺序，用新数据补全/更新，追加新作者。"""
    def key(a: Dict[str, str]) -> str:
        return str(a.get("uid") or a.get("id") or "").strip()

    merged: Dict[str, Dict[str, str]] = {}
    order: List[str] = []
    for a in existing + fetched:
        k = key(a)
        if not k:
            continue
        if k not in merged:
            merged[k] = dict(a)
            order.append(k)
        else:
            # 新数据优先补全 name/link/uid
            for field in ("name", "link", "uid"):
                if a.get(field) and not merged[k].get(field):
                    merged[k][field] = a[field]
    return [merged[k] for k in order]


# ---------------------------------------------------------------------- 编排
class XueqiuScraper:
    def __init__(
        self,
        output_dir: str = "",
        headless: bool = True,
        cookies_file: str = "",
        do_login: bool = False,
        request_delay: float = 0.8,
    ):
        self.output_dir = os.environ.get("XUEQIU_DATA_DIR") or get_path(
            "xueqiu", "data_dir", fallback=output_dir or "/data/xueqiu_data"
        )
        self.headless = headless
        self.cookies_file = cookies_file
        self.do_login = do_login
        self.request_delay = request_delay
        self.cookies_path = cookies_file or os.path.join(self.output_dir, "xueqiu_cookies.txt")
        self.store = ArticleStore(self.output_dir)
        self.summary = SummaryWriter(self.output_dir)
        self.repo = AuthorRepository(self.output_dir)
        self.id_map = self.repo.load_id_map()
        self.scraped = self.repo.load_scraped()

    # ------------------------------------------------------------------ 会话
    def _prepare_session(self, transport: BrowserTransport) -> None:
        """登录 / cookies：`--login` 手动登录后保存；否则自动加载已有 cookies。"""
        if self.do_login:
            if self.headless:
                raise XueqiuAPIError("--login 需要可见浏览器，请同时加 --no-headless")
            input("请在打开的浏览器里完成雪球登录，登录成功后回到这里按回车继续...")
            n = transport.dump_cookies(self.cookies_path)
            logger.info(f"已保存 {n} 个 cookies → {self.cookies_path}")
        elif os.path.exists(self.cookies_path):
            n = transport.load_cookies(self.cookies_path)
            logger.info(f"已加载 {n} 个 cookies ← {self.cookies_path}")
        else:
            logger.info("未提供 cookies，使用匿名会话（公开数据可用）")

    # ------------------------------------------------------------------ 作者 id
    def _resolve_uid(self, client: XueqiuClient, author: Dict[str, str]) -> str:
        for key in ("uid", "id"):
            val = str(author.get(key) or "").strip()
            if val.isdigit():
                return val
        key = str(author.get("id") or "").strip()
        if key in self.id_map:
            return self.id_map[key]
        uid = client.resolve_user_id(key)
        self.id_map[key] = uid
        logger.info(f"解析作者 {key!r} → uid={uid}")
        return uid

    # ------------------------------------------------------------------ 单作者
    def _process_author(
        self, client: XueqiuClient, author: Dict[str, str], all_history: bool
    ) -> Tuple[List[Dict[str, str]], int]:
        uid = self._resolve_uid(client, author)
        name = author.get("name") or author.get("id")
        today = date.today()
        logger.info(f"开始抓取作者 {name}（uid={uid}）...")

        new_entries: List[Dict[str, str]] = []
        new_count = 0
        page = 1

        while page <= MAX_PAGES:
            data = client.get_timeline(uid, page=page, count=PAGE_SIZE)
            statuses = data.get("statuses") or []
            if not statuses:
                break
            logger.info(f"  [{name}] 第 {page} 页：{len(statuses)} 条")

            for status in statuses:
                if status.get("blocked"):
                    continue
                dt = status_datetime(status)
                if not all_history and dt.date() != today:
                    continue
                sid = str(status["id"])

                if self.store.exists(author, dt, sid):
                    logger.debug(f"    [跳过] 已存在 {sid}")
                    continue

                text_html = status.get("text") or ""
                if not text_html:
                    text_html = client.get_status(sid).get("text") or ""
                content = clean_article_text(text_html)
                if not content:
                    logger.warning(f"    [空正文] 跳过 {sid}（{status.get('title')!r}）")
                    continue

                link = f"https://xueqiu.com/{status.get('user_id')}/{sid}"
                article = {
                    "id": sid,
                    "title": status.get("title") or "无标题",
                    "content": content,
                    "time": dt.strftime("%Y-%m-%d %H:%M"),
                    "link": link,
                }
                if self.store.save(author, article, dt):
                    new_count += 1
                    logger.info(f"    [保存] {self.store.month_file(author, dt).name} ← {article['title']}")
                    new_entries.append(
                        {
                            "author": author["name"],
                            "title": article["title"],
                            "time": article["time"],
                            "content": content,
                            "link": link,
                        }
                    )

            max_page = data.get("maxPage") or page
            if page >= max_page:
                break
            if not all_history:
                # 列表按时间倒序，末条已不在今天 → 后面的都更旧，收工
                if status_datetime(statuses[-1]).date() != today:
                    break
            logger.debug(f"  翻页间隔 {PAGE_DELAY:.0f}s")
            time.sleep(PAGE_DELAY)
            page += 1

        logger.info(f"作者 {name} 完成，新增 {new_count} 篇")
        return new_entries, new_count

    # ------------------------------------------------------------------ 主流程
    def run(
        self,
        all_history: bool = False,
        test_mode: bool = False,
        refresh_authors: bool = False,
        limit: int = 0,
    ) -> None:
        transport = BrowserTransport(headless=self.headless).start()
        client = XueqiuClient(transport, delay=self.request_delay)
        try:
            self._prepare_session(transport)
            # ---------- 作者列表 ----------
            if refresh_authors:
                existing = self.repo.load_authors()
                fetched, total = fetch_following_authors(client)
                if not fetched:
                    logger.warning("刷新未获取到作者，保留原列表")
                    authors = existing
                elif total and len(fetched) >= total:
                    # 拿全了 → 直接替换，保证与"当前关注"一致
                    authors = fetched
                    self.repo.save_authors(authors)
                else:
                    logger.warning(
                        f"刷新结果不完整（{len(fetched)}/{total or '?'}），与现有列表合并以免丢失"
                    )
                    authors = merge_authors(existing, fetched)
                    self.repo.save_authors(authors)
            else:
                authors = self.repo.load_authors()
                if not authors:
                    logger.info(f"未找到 {ALL_AUTHORS_FILE}，尝试用关注列表接口获取...")
                    authors, _total = fetch_following_authors(client)
                    self.repo.save_authors(authors)

            if limit:
                authors = authors[:limit]
            if test_mode:
                authors = authors[:2]
            logger.info(f"本次处理 {len(authors)} 个作者（all_history={all_history}）")

            # ---------- 抓取 ----------
            all_entries: List[Dict[str, str]] = []
            total = 0
            errors: List[str] = []
            for i, author in enumerate(authors, 1):
                if i > 1:
                    logger.info(f"作者间隔 {AUTHOR_DELAY:.0f}s...")
                    time.sleep(AUTHOR_DELAY)
                logger.info(f"{'='*60}\n处理第 {i}/{len(authors)} 个作者：{author.get('name')}")
                try:
                    entries, cnt = self._process_author(client, author, all_history)
                except Exception as e:  # noqa: BLE001 - 单个作者失败不拖垮整轮
                    logger.error(f"[错误] 处理作者 {author.get('name')} 失败：{e}")
                    if "10022" in str(e):
                        logger.error("  → 该错误表示『需登录才能翻页』，请用 --login 登录后再跑全量")
                    errors.append(f"{author.get('name')}: {e}")
                    continue
                total += cnt
                all_entries.extend(entries)
                self.scraped[str(author.get("id"))] = {
                    "name": author.get("name"),
                    "link": author.get("link"),
                    "article_count": cnt,
                    "last_scraped": datetime.now().isoformat(),
                }

            # ---------- 收尾 ----------
            self.repo.save_scraped(self.scraped)
            self.repo.save_id_map(self.id_map)
            if all_entries:
                path = self.summary.write(all_entries)
                logger.info(f"更新汇总已写入：{path}")

            logger.info(
                f"{'='*60}\n全部完成：{len(authors)} 个作者，成功 {len(authors) - len(errors)} 个，"
                f"新增 {total} 篇，输出目录 {self.output_dir}"
            )
            if errors:
                raise XueqiuAPIError(f"{len(errors)} 个作者抓取失败，首个错误：{errors[0]}")
        finally:
            transport.close()

    # ------------------------------------------------------------------ 自检
    def check(self) -> None:
        """连通性自检：不写数据，只验证接口可用。"""
        transport = BrowserTransport(headless=self.headless).start()
        client = XueqiuClient(transport, delay=self.request_delay)
        try:
            self._prepare_session(transport)
            logger.info("连通性自检...")
            tl = client.get_timeline("3770558188", page=1, count=3)
            logger.info(
                f"  timeline OK：total={tl.get('total')} maxPage={tl.get('maxPage')} "
                f"本页={len(tl.get('statuses') or [])}"
            )
            first = (tl.get("statuses") or [{}])[0]
            full = ""
            for s in (tl.get("statuses") or [])[:5]:
                full = client.get_full_text(s)
                if full:
                    first = s
                    break
            logger.info(f"  详情 OK：id={first.get('id')} 正文字数={len(full)}")
            fr = client.get_friends("3770558188", page=1, count=1)
            logger.info(f"  关注列表 OK：count={fr.get('count')} maxPage={fr.get('maxPage')}")
            me = client.get_self()
            logger.info(f"  当前登录：{me.get('screen_name') if me else '未登录（公开数据仍可用）'}")
            logger.info("自检通过 ✅")
        finally:
            transport.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="雪球大V文章抓取工具（接口版）")
    parser.add_argument("--mode", "-m", choices=["full", "test"], default="full",
                        help="full=全部作者, test=只抓前 2 个作者")
    parser.add_argument("--all-history", action="store_true", help="抓取全部历史（默认只抓当天）")
    parser.add_argument("--refresh-authors", action="store_true", help="刷新关注列表（需登录）")
    parser.add_argument("--limit", type=int, default=0, help="最多处理 N 个作者（0=不限）")
    parser.add_argument("--no-headless", action="store_true", help="显示浏览器窗口")
    parser.add_argument("--cookies", default="", help="cookies 文件路径（默认 <数据目录>/xueqiu_cookies.txt）")
    parser.add_argument("--login", action="store_true", help="打开可见浏览器手动登录并保存 cookies")
    parser.add_argument("--request-delay", type=float, default=0.8,
                        help="每次请求之间的间隔秒数（默认 0.8；后台跑可调大，如 2~3）")
    parser.add_argument("--check", action="store_true", help="仅做连通性自检，不写数据")
    args = parser.parse_args()

    headless = not args.no_headless
    scraper = XueqiuScraper(
        headless=headless,
        cookies_file=args.cookies,
        do_login=args.login,
        request_delay=args.request_delay,
    )

    logger.info("雪球大V文章抓取工具（接口版）")
    logger.info(f"输出目录：{scraper.output_dir}")
    logger.info(f"模式：{args.mode} / all_history={args.all_history} / headless={headless}")

    try:
        if args.check:
            scraper.check()
        else:
            scraper.run(
                all_history=args.all_history,
                test_mode=args.mode == "test",
                refresh_authors=args.refresh_authors,
                limit=args.limit,
            )
    except KeyboardInterrupt:
        logger.info("用户中断")
        sys.exit(130)
    except Exception as e:  # noqa: BLE001
        logger.error(f"运行出错：{e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
