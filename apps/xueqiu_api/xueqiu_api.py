# -*- coding: utf-8 -*-
"""雪球接口客户端 —— Chrome 作"通行证"，数据走 JSON 接口。

为什么非要浏览器
================
雪球主要接口挂在阿里云 WAF / EdgeOne 风控后面：不带浏览器 JS 算出的指纹 cookie
直接请求，返回的是挑战页而不是 JSON（实测 `requests`、`curl_cffi` 模拟 Chrome TLS
均被拦，只有 `/friendships/friends.json` 这类老接口能匿名通过）。

所以这里的做法是：用 Chrome 打开一次 `xueqiu.com` 过掉风控，然后在**页面上下文**
里 `fetch` 同源接口拿 JSON。浏览器只当传输通道，**不解析任何 DOM**，
因而不受页面改版影响。

用到的接口
==========
* `GET /v4/statuses/user_timeline.json?user_id=&page=&count=&type=0`  帖子列表
    `type=0` 即网站"原发"标签口径（**排除回复/转发**）。
    每项含 `id / user_id / title / description(摘要) / created_at(毫秒) /
    retweeted_status`；长文的 `text` 为空，短帖 `text` 即全文。
* `GET /statuses/show.json?id=`                                单帖全文（`text`）
* `GET /friendships/friends.json?uid=&page=`                   关注列表
* `GET /friendships/groups.json?uid=` / `groups/members.json`  关注分组（分页备用）
* `GET /statuses/original/show.json?user_id=`                  用户资料 / 总帖数

注意：`user_id` 必须是**数字 id**，slug（如 `houqiang`）会返回 400，
需要先用 `resolve_user_id()` 解析。
"""
from __future__ import annotations

import json
import random
import re
import time
from html import unescape
from typing import Any, Dict, Iterator, List, Optional, Tuple
from urllib.parse import urlencode

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

HOME = "https://xueqiu.com"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
DEFAULT_COUNT = 20

# 页面上下文里发请求：同源、自动带 cookie，天然过风控
_FETCH_SCRIPT = """
const url = arguments[0];
const done = arguments[arguments.length - 1];
fetch(url, { credentials: 'include', headers: { 'Accept': 'application/json, text/plain, */*' } })
  .then(function (r) { return r.text().then(function (t) { done({ ok: true, status: r.status, text: t }); }); })
  .catch(function (e) { done({ ok: false, error: String(e) }); });
"""


class XueqiuAPIError(RuntimeError):
    """接口返回非预期内容（含风控拦截、业务错误码）。"""


def _is_waf(text: str) -> bool:
    """是否是风控挑战页（阿里云 WAF / EdgeOne 等），而非正常 JSON。"""
    if not text:
        return False
    head = text.lstrip()[:200]
    if head.startswith("{") or head.startswith("["):
        return False
    markers = ("aliyun_waf", "renderData", "EO_Bot_Ssid", "_0x", "acw_sc__v2", "<script", "<html", "<!doctype")
    return any(m.lower() in head.lower() for m in markers)


def parse_cookie_file(path: str) -> List[Dict[str, Any]]:
    """解析 cookies 文件，兼容两种格式：

    * Netscape（`# Netscape HTTP Cookie File`，curl 导出）
    * 简单格式（`k=v; k=v`，旧版 `xueqiu_cookies.txt`）
    """
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    if content.lstrip().startswith("# Netscape HTTP Cookie File"):
        cookies: List[Dict[str, Any]] = []
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 7:
                cookie: Dict[str, Any] = {
                    "name": parts[5].strip(),
                    "value": parts[6].strip(),
                    "domain": parts[0].strip(),
                    "path": parts[2].strip() or "/",
                }
                try:
                    expiry = int(parts[4])
                    if expiry > 0:
                        cookie["expiry"] = expiry
                except ValueError:
                    pass
                cookies.append(cookie)
        return cookies

    cookies = []
    for part in content.split(";"):
        part = part.strip()
        if "=" not in part:
            continue
        name, value = part.split("=", 1)
        name = name.strip()
        value = value.strip().strip('"').strip("'")
        if name and value:
            cookies.append({"name": name, "value": value, "domain": ".xueqiu.com", "path": "/"})
    return cookies


class BrowserTransport:
    """用 Chrome 过风控，并在页面上下文 fetch 接口。

    生命周期：`start()` → 多次 `fetch_json()` → `close()`（或用 with）。
    """

    # 业务错误码：确定性失败，不重试（交给调用方判断）
    AUTH_ERROR_CODES = {"400016", "10027", "20206"}
    # 触发频率限制：退避后重试
    RATE_LIMIT_CODES = {"31005"}

    def __init__(
        self,
        headless: bool = True,
        home: str = HOME,
        warmup_wait: float = 4.0,
        script_timeout: int = 60,
        page_load_timeout: int = 40,
        user_agent: str = UA,
    ):
        self.headless = headless
        self.home = home
        self.warmup_wait = warmup_wait
        self.script_timeout = script_timeout
        self.page_load_timeout = page_load_timeout
        self.user_agent = user_agent
        self.driver: Optional[webdriver.Chrome] = None

    # ------------------------------------------------------------------ 生命周期
    def _build_options(self) -> Options:
        opts = Options()
        if self.headless:
            opts.add_argument("--headless=new")
        for arg in (
            "--disable-gpu",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
            "--disable-extensions",
            "--disable-plugins",
            "--no-first-run",
            "--no-default-browser-check",
            "--lang=zh-CN",
            "--window-size=1920,1080",
        ):
            opts.add_argument(arg)
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)
        opts.add_argument(f"user-agent={self.user_agent}")
        return opts

    def start(self) -> "BrowserTransport":
        if self.driver is not None:
            return self
        self.driver = webdriver.Chrome(options=self._build_options())
        self.driver.set_script_timeout(self.script_timeout)
        self.driver.set_page_load_timeout(self.page_load_timeout)
        # 抹掉 navigator.webdriver 痕迹（风控会看）
        try:
            self.driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
        except Exception:  # noqa: BLE001 - 尽力而为
            pass
        self._warmup()
        return self

    def _warmup(self) -> None:
        """打开首页让风控下发指纹 cookie。"""
        assert self.driver is not None
        self.driver.get(self.home)
        time.sleep(self.warmup_wait)
        page = self.driver.page_source or ""
        if any(m in page for m in ("aliyun_waf", "EO_Bot_Ssid", "acw_sc__v2")):
            # 挑战页会自行重载，再等一会
            time.sleep(self.warmup_wait)

    def close(self) -> None:
        if self.driver is not None:
            try:
                self.driver.quit()
            finally:
                self.driver = None

    # ------------------------------------------------------------------ cookie
    def load_cookies(self, path: str) -> int:
        """把 cookies 文件注入浏览器（用于"我的关注"等需登录场景）。"""
        assert self.driver is not None, "先调用 start()"
        cookies = parse_cookie_file(path)
        loaded = 0
        for c in cookies:
            try:
                self.driver.add_cookie(c)
                loaded += 1
            except Exception:  # noqa: BLE001 - 个别 cookie 失败不影响整体
                continue
        if loaded:
            self.driver.refresh()
            time.sleep(1.5)
        return loaded

    def dump_cookies(self, path: str) -> int:
        """把当前浏览器里雪球相关 cookie 写到文件（简单格式）。"""
        assert self.driver is not None, "先调用 start()"
        cookies = [
            c
            for c in self.driver.get_cookies()
            if "xueqiu" in (c.get("domain") or "") or "snowball" in (c.get("domain") or "")
        ]
        with open(path, "w", encoding="utf-8") as f:
            f.write("; ".join(f"{c['name']}={c['value']}" for c in cookies))
        return len(cookies)

    def __enter__(self) -> "BrowserTransport":
        return self.start()

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # ------------------------------------------------------------------ 请求
    def fetch_json(self, path: str, params: Optional[Dict[str, Any]] = None, retries: int = 4) -> Any:
        """取接口 JSON。

        先走页面上下文 `fetch`（快）；若命中风控挑战页，则改用**导航兜底**
        （`driver.get(url)`），让浏览器真正执行挑战 JS、拿到放行 cookie，
        再把 JSON 读回来。最后按退避重试若干轮。

        * 返回 JSON 业务错误（含 `error_code`）→ 立即抛出（限流码除外）。
        """
        assert self.driver is not None, "先调用 start()"
        url = path + ("?" + urlencode(params) if params else "")
        abs_url = url if url.startswith("http") else self.home + url
        last_err: Optional[Exception] = None
        for attempt in range(retries + 1):
            # 1) 页面上下文 fetch
            res = self.driver.execute_async_script(_FETCH_SCRIPT, url)
            if res.get("ok"):
                text = res.get("text") or ""
                try:
                    data = json.loads(text)
                except ValueError:
                    last_err = XueqiuAPIError(self._challenge_desc(text))
                else:
                    if isinstance(data, dict) and data.get("error_code"):
                        code = str(data.get("error_code"))
                        if code in self.RATE_LIMIT_CODES:
                            last_err = XueqiuAPIError(
                                f"触发限流 {code}：{data.get('error_description')}"
                            )
                        else:
                            raise XueqiuAPIError(
                                f"接口错误 {code}：{data.get('error_description')}"
                            )
                    else:
                        return data
            else:
                last_err = XueqiuAPIError(f"fetch 失败：{res.get('error')}")

            # 2) 导航兜底：让浏览器执行挑战 JS（注意用绝对 URL）
            try:
                data = self._fetch_via_navigation(abs_url)
            except XueqiuAPIError:
                raise
            except Exception as e:  # noqa: BLE001 - 兜底本身失败不应拖垮作者抓取
                last_err = XueqiuAPIError(f"导航兜底失败：{e}")
                data = None
            if data is not None:
                return data

            if attempt < retries:
                time.sleep(self._retry_wait(attempt, last_err))
                self._warmup()
        raise last_err or XueqiuAPIError("请求失败")

    def _fetch_via_navigation(self, url: str, navigate_wait: float = 2.5) -> Optional[Any]:
        """导航到接口地址取 JSON（风控挑战需要浏览器执行 JS 才能放行）。

        返回解析好的 JSON；若仍是挑战页 / 非 JSON，返回 None（交给上层重试）。
        `url` 必须是绝对地址（相对地址会让 `driver.get` 抛 invalid argument）。
        """
        assert self.driver is not None
        if not url.startswith("http"):
            url = self.home + url
        for i in range(2):
            try:
                self.driver.get(url)
            except Exception:  # noqa: BLE001 - 导航失败交给上层重试
                return None
            time.sleep(navigate_wait)
            body = ""
            try:
                body = self.driver.execute_script(
                    "return (document.body && document.body.innerText) || '';"
                ) or ""
            except Exception:  # noqa: BLE001
                body = ""
            body = body.strip()
            if body.startswith("{") or body.startswith("["):
                try:
                    data = json.loads(body)
                except ValueError:
                    data = None
                if data is not None:
                    if isinstance(data, dict) and data.get("error_code"):
                        code = str(data.get("error_code"))
                        if code in self.RATE_LIMIT_CODES:
                            return None
                        raise XueqiuAPIError(
                            f"接口错误 {code}：{data.get('error_description')}"
                        )
                    return data
            # 还是挑战页：等它设置 cookie 后重载
            time.sleep(1.5)
        return None

    @staticmethod
    def _challenge_desc(text: str) -> str:
        if "aliyun_waf" in text or "renderData" in text:
            kind = "阿里云 WAF"
        elif "EO_Bot_Ssid" in text:
            kind = "EdgeOne 风控"
        else:
            kind = "非 JSON"
        return f"{kind} 页面：{text[:160]!r}"

    @staticmethod
    def _retry_wait(attempt: int, err: Optional[Exception]) -> float:
        """限流/风控时退避更久（后台运行，时间不是问题）。"""
        if err and "限流" in str(err):
            return 20 + attempt * 20
        return 4 + attempt * 5


class XueqiuClient:
    """雪球接口的业务封装（列表分页 / 详情 / 关注 / 用户解析）。"""

    def __init__(self, transport: BrowserTransport, delay: float = 0.8):
        self.transport = transport
        self.delay = delay

    def _pause(self) -> None:
        """请求间隔（带抖动），避免触发风控。"""
        if self.delay > 0:
            time.sleep(self.delay * random.uniform(0.8, 1.4))

    # ------------------------------------------------------------------ 帖子
    def get_timeline(
        self, user_id: str, page: int = 1, count: int = DEFAULT_COUNT, original: bool = True
    ) -> Dict[str, Any]:
        """帖子列表。

        `original=True` 会带上 `type=0`，即网站"原发"标签的口径（**排除回复/转发**）。
        """
        params: Dict[str, Any] = {"user_id": str(user_id), "page": page, "count": count}
        if original:
            params["type"] = 0
        data = self.transport.fetch_json("/v4/statuses/user_timeline.json", params)
        self._pause()
        return data

    def iter_timeline(
        self,
        user_id: str,
        count: int = DEFAULT_COUNT,
        max_pages: Optional[int] = None,
        original: bool = True,
    ) -> Iterator[Dict[str, Any]]:
        """按页产出帖子，直到最后一页（不做时间过滤，过滤交给调用方）。"""
        page = 1
        while True:
            if max_pages is not None and page > max_pages:
                return
            data = self.get_timeline(user_id, page=page, count=count, original=original)
            statuses = data.get("statuses") or []
            for s in statuses:
                yield s
            max_page = data.get("maxPage") or page
            if not statuses or page >= max_page:
                return
            page += 1

    def get_status(self, status_id: str) -> Dict[str, Any]:
        data = self.transport.fetch_json("/statuses/show.json", {"id": str(status_id)})
        self._pause()
        return data

    def get_full_text(self, status: Dict[str, Any]) -> str:
        """列表项 `text` 为空（长文）时才去详情接口取全文。"""
        text = status.get("text") or ""
        if text:
            return text
        detail = self.get_status(status["id"])
        return detail.get("text") or detail.get("description") or ""

    # ------------------------------------------------------------------ 关注
    def get_friends(
        self, uid: Optional[str] = None, page: int = 1, count: int = DEFAULT_COUNT
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"page": page, "count": count}
        if uid:
            params["uid"] = str(uid)
        data = self.transport.fetch_json("/friendships/friends.json", params)
        self._pause()
        return data

    def get_friend_groups(self, uid: str) -> List[Dict[str, Any]]:
        """关注分组（`/friendships/groups.json` 的响应是**裸数组**）。"""
        data = self.transport.fetch_json("/friendships/groups.json", {"uid": str(uid)})
        self._pause()
        if isinstance(data, list):
            return data
        return data.get("groups") or data.get("list") or []

    def get_group_members(
        self, uid: str, gid: Any, page: int = 1, count: int = DEFAULT_COUNT
    ) -> Dict[str, Any]:
        data = self.transport.fetch_json(
            "/friendships/groups/members.json",
            {"uid": str(uid), "gid": gid, "page": page, "count": count},
        )
        self._pause()
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _users_of(data: Dict[str, Any]) -> List[Dict[str, Any]]:
        return data.get("users") or data.get("friends") or data.get("friends_list") or []

    def collect_following(
        self, uid: Optional[str], count: int = DEFAULT_COUNT
    ) -> Tuple[List[Dict[str, Any]], int]:
        """收集某用户的**全部关注**，返回 `(用户列表, 官方总数)`。

        实测雪球各接口的分页能力不同：

        * `/friendships/friends.json` 的 `page` **被忽略**（登录与否都只给第 1 页），
          未登录时第 2 页还会返回 `10022 请登录`；
        * `/friendships/groups/members.json?gid=0`（"全部"分组）的 `page` **有效**，
          且登录后可用 —— 这才是拿全关注的正路。

        策略顺序：先走分组接口（`gid=0` 优先），不够再用 `friends.json` 兜底。
        """
        seen: Dict[str, Dict[str, Any]] = {}
        total = 0

        def absorb(users: List[Dict[str, Any]]) -> int:
            new = 0
            for u in users:
                fid = str(u.get("id") or "").strip()
                if fid and fid not in seen:
                    seen[fid] = u
                    new += 1
            return new

        def page_loop(fetch, extract, *, trust_max_page: bool, count_is_total: bool) -> None:
            nonlocal total
            page = 1
            while page <= 200:
                data = fetch(page)
                if count_is_total:
                    total = total or int(data.get("count") or 0)
                users = extract(data)
                if not users:
                    break
                new = absorb(users)
                max_page = int(data.get("maxPage") or 0)
                # 分组接口的 page 有效：按 maxPage 翻完（即使某页全是重复）；
                # friends.json 的 page 无效：没有新 id 就停，避免死循环。
                if trust_max_page:
                    if max_page and page >= max_page:
                        break
                else:
                    if new == 0:
                        break
                    if max_page and page >= max_page:
                        break
                page += 1

        # 策略 1：分组接口（gid=0 = "全部"，page 有效）
        groups: List[Dict[str, Any]] = []
        if uid:
            try:
                groups = self.get_friend_groups(uid)
            except XueqiuAPIError:
                groups = []
            for g in groups:
                if str(g.get("id")) == "0":
                    total = max(total, int(g.get("member_count") or 0))
        for g in sorted(groups, key=lambda x: 0 if str(x.get("id")) == "0" else 1):
            gid = g.get("id")
            if gid is None:
                continue
            page_loop(
                lambda p, _gid=gid: self.get_group_members(uid, _gid, page=p, count=count),
                self._users_of,
                trust_max_page=True,
                count_is_total=False,
            )
            if total and len(seen) >= total:
                break

        # 策略 2：friends.json（带 uid）
        if not total or len(seen) < total:
            page_loop(
                lambda p: self.get_friends(uid, page=p, count=count),
                lambda d: d.get("friends") or [],
                trust_max_page=False,
                count_is_total=True,
            )
        # 策略 3：friends.json（不带 uid，"我的关注"）
        if total and len(seen) < total:
            page_loop(
                lambda p: self.get_friends(None, page=p, count=count),
                lambda d: d.get("friends") or [],
                trust_max_page=False,
                count_is_total=True,
            )

        return list(seen.values()), total

    def iter_friends(self, uid: Optional[str] = None, count: int = DEFAULT_COUNT) -> Iterator[Dict[str, Any]]:
        """逐条产出关注（内部走 collect_following，保证尽量拿全）。"""
        friends, _total = self.collect_following(uid, count=count)
        yield from friends

    # ------------------------------------------------------------------ 用户
    def get_self(self) -> Optional[Dict[str, Any]]:
        """当前登录用户资料；未登录返回 None。"""
        try:
            data = self.transport.fetch_json("/statuses/original/show.json")
        except XueqiuAPIError:
            return None
        return data.get("user") or None

    def resolve_user_id(self, identifier: str) -> str:
        """把数字 id 或自定义域名（slug）解析成接口需要的**数字 user_id**。"""
        identifier = str(identifier).strip()
        if not identifier:
            raise XueqiuAPIError("空的作者标识")
        if identifier.isdigit():
            return identifier

        driver = self.transport.driver
        assert driver is not None, "先调用 BrowserTransport.start()"
        driver.get(f"{self.transport.home}/{identifier}")
        time.sleep(1.5)
        m = re.search(r"/u/(\d+)", driver.current_url or "")
        if m:
            return m.group(1)
        m = re.search(r'"user_id"\s*:\s*(\d+)', driver.page_source or "")
        if m:
            return m.group(1)
        raise XueqiuAPIError(f"无法把 {identifier!r} 解析成数字 user_id")


# ---------------------------------------------------------------------- 文本清洗
_SENTENCE_END = re.compile(r"[。！？!?…][）)」』】\"]?$")
# 常见的视频播放器/样板噪声
_NOISE_PATTERNS = (
    re.compile(r"^Video Player is loading\.?$"),
    re.compile(r"^(Play|Pause|Replay|Mute|Fullscreen)"),
    re.compile(r"^Current Time\s"),
    re.compile(r"^Duration\s"),
    re.compile(r"^Loaded:\s"),
    re.compile(r"^Remaining Time\s"),
    re.compile(r"^Stream Type\s"),
    re.compile(r"^This is a modal window"),
    re.compile(r"^Beginning of dialog window"),
    re.compile(r"^End of dialog window"),
    re.compile(r"^来源：雪球App"),
    re.compile(r"^查看对话$"),
)


def html_to_text(html_str: str) -> str:
    """正文 HTML → 纯文本（只让 <br> 与块级标签产生换行）。"""
    if not html_str:
        return ""
    s = re.sub(r"(?is)<(script|style)\b[^>]*>.*?</\1>", "", html_str)
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</(p|h[1-6]|blockquote)\s*>", "\n\n", s)
    s = re.sub(r"(?i)</(div|li|tr|section|article|ul|ol)\s*>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = unescape(s)
    s = s.replace("\u200b", "").replace("\ufeff", "").replace("\xa0", " ")
    s = re.sub(r"[ \t\u3000]+", " ", s)
    s = re.sub(r" *\n *", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _merge_fragments(text: str) -> str:
    """把被 DOM 切碎的片段接回同一行（上一行未以句末标点结束就续接）。"""
    if not text:
        return ""
    out: List[str] = []
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            if out and out[-1] != "":
                out.append("")
            continue
        if out and out[-1] and not _SENTENCE_END.search(out[-1]):
            out[-1] += line
        else:
            out.append(line)
    return "\n".join(out).strip()


def clean_article_text(html_str: str) -> str:
    """正文 HTML → 去噪后的纯文本（去掉播放器/样板行）。"""
    text = _merge_fragments(html_to_text(html_str))
    if not text:
        return ""
    lines = []
    for line in text.split("\n"):
        if any(p.search(line) for p in _NOISE_PATTERNS):
            continue
        lines.append(line)
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()
