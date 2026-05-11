#!/usr/bin/env python3
"""
Hunter鹰图平台 - ICP备案资产采集工具
用于实战攻防演练中的信息同步、资产同步、攻击价值信息同步。
输入目标公司ICP备案主体名称，输出去重/去CDN/去蜜罐/去泛解析后的资产CSV。
"""

import argparse
import base64
import csv
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

import requests

# ============================================================
# 配置
# ============================================================
API_KEY = "0ba2fa5b65bd2bd794cbea57460e2910585eeddfc7785ca5efa03ecabfa376cd"
BASE_URL = "https://hunter.qianxin.com/openApi/search"
PAGE_SIZE = 100  # 每页最大条数
REQUEST_INTERVAL = 2.1  # 接口限速 2s，留余量

# 需要导出的全部字段
ALL_FIELDS = (
    "ip,port,domain,ip_tag,url,web_title,is_risk_protocol,protocol,"
    "base_protocol,status_code,os,company,number,icp_exception,"
    "country,province,city,is_web,isp,as_org,cert_sha256,"
    "ssl_certificate,component,asset_tag,updated_at,header,"
    "header_server,banner,whois,body,vul_list"
)

# 已知CDN IP段（常见CDN厂商的公开网段，按需扩充）
CDN_AS_ORG_KEYWORDS = [
    "cloudflare", "akamai", "fastly", "cdn", "cloudfront",
    "incapsula", "sucuri", "stackpath", "imperva", "maxcdn",
    "keycdn", "cloudflare", "quadranet", "alibaba cloud",
    "tencent cloud", "baidu cloud", "huawei cloud",
    "wangsu", "cdnetworks",
]

# 蜜罐判定关键词
HONEYPOT_KEYWORDS = [
    "honeypot", "honeypot", "蜜罐",
    "cowrie", "dionaea", "kippo", "conpot",
    "amun", "glastopf", "honeyd", "snare",
    "t-pot", "mhn",
]

# 泛解析常见占位符子域名
WILDCARD_INDICATORS = [
    "wildcard", "*.",
]


def build_search_query(icp_name: str) -> str:
    """构造ICP名称搜索语法"""
    if "ICP备" in icp_name or "ICP证" in icp_name:
        return f'icp.number=="{icp_name}"'
    return f'icp.name=="{icp_name}"'


MAX_RETRIES = 3
RETRY_BACKOFF = [3, 6, 12]  # 每次重试的等待秒数


def fetch_page(
    query: str, page: int, fields: str = ALL_FIELDS
) -> dict:
    """请求Hunter API获取单页数据，含自动重试和退避"""
    search_encoded = base64.urlsafe_b64encode(
        query.encode("utf-8")
    ).decode("utf-8")

    params = {
        "api-key": API_KEY,
        "search": search_encoded,
        "page": page,
        "page_size": PAGE_SIZE,
        "fields": fields,
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(BASE_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            code = data.get("code")
            if code == 200:
                return data

            # 限速类错误，自动重试
            if code in (429, 1302):
                wait = RETRY_BACKOFF[min(attempt - 1, len(RETRY_BACKOFF) - 1)]
                print(
                    f"    [限速] 第{attempt}次被限速，{wait}s后重试..."
                )
                time.sleep(wait)
                continue

            # 其他API错误
            raise RuntimeError(
                f"API返回错误: code={code}, "
                f"message={data.get('message', '未知错误')}"
            )

        except requests.exceptions.Timeout:
            print(
                f"    [超时] 第{attempt}次请求超时，"
                f"{RETRY_BACKOFF[min(attempt - 1, len(RETRY_BACKOFF) - 1)]}s后重试..."
            )
            time.sleep(RETRY_BACKOFF[min(attempt - 1, len(RETRY_BACKOFF) - 1)])
            continue

        except requests.exceptions.ConnectionError:
            print(
                f"    [连接] 第{attempt}次连接失败，"
                f"{RETRY_BACKOFF[min(attempt - 1, len(RETRY_BACKOFF) - 1)]}s后重试..."
            )
            time.sleep(RETRY_BACKOFF[min(attempt - 1, len(RETRY_BACKOFF) - 1)])
            continue

    raise RuntimeError(
        f"连续{MAX_RETRIES}次请求失败，放弃第{page}页"
    )


def fetch_total(icp_number: str) -> tuple[int, list[dict], str]:
    """首次查询，同时获取总数和首页数据，避免重复调用被限速"""
    query = build_search_query(icp_number)
    print(f"[*] 查询语法: {query}")

    result = fetch_page(query, page=1)
    total = result.get("data", {}).get("total", 0)
    assets = result.get("data", {}).get("arr", []) or []
    return total, assets, query


def fetch_assets(
    query: str, first_page: list[dict], total: int, limit: int
) -> list[dict]:
    """基于首页数据继续分页拉取，跳过已获取的第一页"""
    fetch_limit = min(limit, total)
    assets = list(first_page)
    fetched = len(assets)

    print(f"[*] 总资产: {total}, 目标拉取: {fetch_limit}, 首页已获取: {fetched}")

    if fetched >= fetch_limit:
        return assets[:fetch_limit]

    total_pages = math.ceil(fetch_limit / PAGE_SIZE)

    failed_pages = []
    for page in range(2, total_pages + 1):
        time.sleep(REQUEST_INTERVAL)
        print(f"[*] 正在拉取第 {page}/{total_pages} 页...")
        try:
            result = fetch_page(query, page=page)
            page_assets = result.get("data", {}).get("arr", []) or []
            assets.extend(page_assets)
            fetched += len(page_assets)
            print(f"    获取 {len(page_assets)} 条，累计 {fetched}/{fetch_limit}")
        except RuntimeError as e:
            failed_pages.append(page)
            print(f"    [跳过] 第{page}页失败: {e}")
        if fetched >= fetch_limit:
            break

    if failed_pages:
        print(
            f"[警告] {len(failed_pages)} 页拉取失败 "
            f"(页码: {failed_pages})，实际获取 {fetched}/{fetch_limit} 条"
        )

    return assets[:fetch_limit]


def deduplicate(assets: list[dict]) -> list[dict]:
    """基于 ip+port+domain+url 去重"""
    seen = set()
    unique = []
    for item in assets:
        key = (
            item.get("ip", ""),
            item.get("port", ""),
            item.get("domain", ""),
            item.get("url", ""),
        )
        if key not in seen:
            seen.add(key)
            unique.append(item)
    print(f"[去重] {len(assets)} -> {len(unique)} 条")
    return unique


def remove_cdn(assets: list[dict]) -> list[dict]:
    """根据 ip_tag 标记和 as_org 关键词去除CDN资产"""
    filtered = []
    for item in assets:
        ip_tag = (item.get("ip_tag") or "").lower()
        as_org = (item.get("as_org") or "").lower()

        # ip_tag 包含 CDN 标记
        if "cdn" in ip_tag:
            continue

        # as_org 匹配已知CDN厂商
        if any(kw in as_org for kw in CDN_AS_ORG_KEYWORDS):
            continue

        filtered.append(item)

    removed = len(assets) - len(filtered)
    print(f"[去CDN] {len(assets)} -> {len(filtered)} 条 (移除 {removed} 条)")
    return filtered


def remove_honeypots(assets: list[dict]) -> list[dict]:
    """根据风险协议标记、ip_tag、banner、body等字段识别并去除蜜罐"""
    filtered = []
    for item in assets:
        ip_tag = (item.get("ip_tag") or "").lower()
        is_risk = str(item.get("is_risk_protocol", "")).lower()
        banner = (item.get("banner") or "").lower()
        body = (item.get("body", "") or "").lower()
        component = json.dumps(
            item.get("component", ""), ensure_ascii=False
        ).lower()

        # ip_tag 包含蜜罐标记
        if "蜜罐" in ip_tag or "honeypot" in ip_tag:
            continue

        # 风险协议标记
        if is_risk in ("1", "true", "yes"):
            continue

        # banner / body / component 中包含蜜罐关键词
        combined = f"{banner} {body} {component}"
        if any(kw in combined for kw in HONEYPOT_KEYWORDS):
            continue

        filtered.append(item)

    removed = len(assets) - len(filtered)
    print(f"[去蜜罐] {len(assets)} -> {len(filtered)} 条 (移除 {removed} 条)")
    return filtered


def remove_wildcard_dns(assets: list[dict]) -> list[dict]:
    """
    去泛解析：对同一IP上挂载大量不同子域名的场景进行过滤。
    如果某个IP关联的域名数量超过阈值，且这些域名呈现明显的
    泛解析特征（如随机前缀），则剔除这些泛解析记录。
    """
    DOMAIN_PER_IP_THRESHOLD = 20

    # 按IP分组
    ip_domains: dict[str, set[str]] = defaultdict(set)
    for item in assets:
        ip = item.get("ip", "")
        domain = item.get("domain", "")
        if ip and domain:
            ip_domains[ip].add(domain)

    # 找出疑似泛解析的IP
    wildcard_ips = set()
    for ip, domains in ip_domains.items():
        if len(domains) <= DOMAIN_PER_IP_THRESHOLD:
            continue

        # 检查子域名是否看起来随机（泛解析特征）
        prefixes = [d.split(".")[0] for d in domains if "." in d]
        if not prefixes:
            continue

        # 计算前缀平均长度，泛解析通常生成随机长短不一的前缀
        avg_len = sum(len(p) for p in prefixes) / len(prefixes)

        # 检查是否大量前缀看起来像随机字符串
        random_count = 0
        for p in prefixes:
            # 随机字符串特征：包含数字和字母的混合，长度较长
            has_digit = any(c.isdigit() for c in p)
            has_alpha = any(c.isalpha() for c in p)
            if has_digit and has_alpha and len(p) >= 8:
                random_count += 1

        random_ratio = random_count / len(prefixes) if prefixes else 0
        if random_ratio > 0.5 or avg_len > 15:
            wildcard_ips.add(ip)

    if wildcard_ips:
        print(f"[泛解析] 发现 {len(wildcard_ips)} 个疑似泛解析IP")

    filtered = []
    for item in assets:
        ip = item.get("ip", "")
        if ip in wildcard_ips:
            # 泛解析IP上的资产只保留有明确子域名的（非随机的）
            domain = item.get("domain", "")
            if domain and "." in domain:
                prefix = domain.split(".")[0]
                has_digit = any(c.isdigit() for c in prefix)
                has_alpha = any(c.isalpha() for c in prefix)
                if has_digit and has_alpha and len(prefix) >= 8:
                    continue
        filtered.append(item)

    removed = len(assets) - len(filtered)
    print(f"[去泛解析] {len(assets)} -> {len(filtered)} 条 (移除 {removed} 条)")
    return filtered


def export_csv(assets: list[dict], icp_number: str) -> str:
    """将资产列表导出为CSV文件"""
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    safe_name = icp_number.replace("/", "_").replace("\\", "_")
    filename = output_dir / f"{safe_name}_assets.csv"

    if not assets:
        print("[!] 无资产可导出")
        return ""

    # 收集所有字段名（保持顺序）
    fieldnames = []
    for item in assets:
        for key in item.keys():
            if key not in fieldnames:
                fieldnames.append(key)

    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f, fieldnames=fieldnames, extrasaction="ignore"
        )
        writer.writeheader()
        for item in assets:
            # component 和 vul_list 可能是列表/字典，序列化为JSON
            for key in ("component", "vul_list", "ssl_certificate"):
                val = item.get(key)
                if isinstance(val, (list, dict)):
                    item[key] = json.dumps(val, ensure_ascii=False)
            writer.writerow(item)

    print(f"[导出] CSV已保存: {filename} ({len(assets)} 条记录)")
    return str(filename)


def run_collection(icp_number: str, limit: int = 100) -> str:
    """
    提供给外部程序调用的资产采集方法，不含交互式确认。
    :param icp_number: 备案主体名称或备案号
    :param limit: 最大采集数量（-1 表示全部导出，0 表示默认 100）
    :return: 生成的 CSV 文件绝对路径，如果未生成则返回空字符串
    """
    print(f"\n{'='*60}")
    print(f"[*] ICP备案主体: {icp_number}")
    print(f"{'='*60}")

    try:
        total, first_page, query = fetch_total(icp_number)
    except Exception as e:
        print(f"[!] 查询失败: {e}")
        return ""

    if total == 0:
        print("[!] 未找到任何资产")
        return ""

    default_limit = 100
    print(f"\n[*] 该备案主体共 {total} 条资产")

    if limit == 0:
        limit = default_limit
    elif limit == -1:
        limit = total

    limit = min(limit, total)
    print(f"[*] 将拉取 {limit} 条资产\n")

    try:
        assets = fetch_assets(query, first_page, total, limit)
    except Exception as e:
        print(f"[!] 采集失败: {e}")
        return ""

    if not assets:
        print("[!] 拉取到0条资产")
        return ""

    print(f"\n[*] 原始资产: {len(assets)} 条")
    assets = deduplicate(assets)
    assets = remove_cdn(assets)
    assets = remove_honeypots(assets)
    assets = remove_wildcard_dns(assets)

    output = export_csv(assets, icp_number)
    if output:
        print(f"\n[完成] 最终有效资产: {len(assets)} 条")
        print(f"[完成] 导出文件: {output}")
        return output
    return ""

def main():
    parser = argparse.ArgumentParser(
        description="Hunter鹰图平台 - ICP备案资产采集工具"
    )
    parser.add_argument(
        "icp",
        nargs="+",
        help="ICP备案主体名称，支持多个（空格分隔）",
    )
    parser.add_argument(
        "-n", "--limit",
        type=int,
        default=0,
        help="导出资产数量上限（默认100，0表示全部导出）",
    )
    args = parser.parse_args()

    for icp_number in args.icp:
        print(f"\n{'='*60}")
        print(f"[*] ICP备案主体: {icp_number}")
        print(f"{'='*60}")

        # 1. 首次查询：同时获取总数和首页数据
        try:
            total, first_page, query = fetch_total(icp_number)
        except Exception as e:
            print(f"[!] 查询失败: {e}")
            continue

        if total == 0:
            print("[!] 未找到任何资产")
            continue

        # 2. 回显总数，确认导出数量
        default_limit = 100
        print(f"\n[*] 该备案主体共 {total} 条资产")

        limit = args.limit
        if limit == 0:
            # 未指定 -n，交互式确认
            if total <= default_limit:
                limit = total
                print(f"[*] 资产数 <= {default_limit}，将全部导出")
            else:
                print(f"[*] 默认导出前 {default_limit} 条")
                user_input = input(
                    f"    输入要导出的数量（直接回车={default_limit}，"
                    f"all={total}全量导出）: "
                ).strip()
                if user_input.lower() == "all":
                    limit = total
                elif user_input:
                    try:
                        limit = int(user_input)
                        limit = max(1, min(limit, total))
                    except ValueError:
                        limit = default_limit
                else:
                    limit = default_limit
        elif limit == -1:
            limit = total

        limit = min(limit, total)
        print(f"[*] 将拉取 {limit} 条资产\n")

        # 3. 拉取资产
        try:
            assets = fetch_assets(query, first_page, total, limit)
        except Exception as e:
            print(f"[!] 采集失败: {e}")
            continue

        if not assets:
            print("[!] 拉取到0条资产")
            continue

        print(f"\n[*] 原始资产: {len(assets)} 条")

        # 4. 清洗
        assets = deduplicate(assets)
        assets = remove_cdn(assets)
        assets = remove_honeypots(assets)
        assets = remove_wildcard_dns(assets)

        # 5. 导出CSV
        output = export_csv(assets, icp_number)
        if output:
            print(f"\n[完成] 最终有效资产: {len(assets)} 条")
            print(f"[完成] 导出文件: {output}")

    print("\n[*] 全部任务完成")


if __name__ == "__main__":
    main()
