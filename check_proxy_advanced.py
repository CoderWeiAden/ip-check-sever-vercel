#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# python check_proxy_advanced.py --proxy http://t5iyoF3CLp1wWx:Ffm70iNo@accel.ipflygates.com:5001 --config vc_test.json
# python check_proxy_advanced.py --proxy http://tDT7pgAqFRl3fQ:q1V5WaK8@accel.ipflygates.com:5001 --config vc_test.json
"""
出口 IP（代理）高级检测脚本 - 支持 robots.txt 连通性 + 302跳转 Location 校验
"""

import argparse
import json
import sys
import time
from typing import List, Dict, Any, Tuple, Optional
import requests
from requests.exceptions import ProxyError, Timeout, ConnectionError, SSLError


class ProxyTester:
    def __init__(self, proxy_url: str, timeout: int = 10):
        self.proxy_url = proxy_url
        self.timeout = timeout
        self.proxies = {
            'http': proxy_url,
            'https': proxy_url,
        }

    def test_url(self,
                 url: str,
                 allowed_status_codes: List[int] = None,
                 must_contain: Optional[str] = None,
                 must_not_contain: Optional[str] = None,
                 location_expected: Optional[str] = None,
                 follow_redirects: bool = False
                 ) -> Tuple[bool, str, float, int, str, Optional[str]]:
        """
        测试单个 URL，根据自定义规则判断是否成功
        返回: (是否成功, 错误信息或成功摘要, 耗时, HTTP状态码, 响应体前300字符, Location头)
        """
        if allowed_status_codes is None:
            allowed_status_codes = [200]

        try:
            start = time.time()
            # 不自动跟随重定向，便于检查 Location
            response = requests.get(
                url,
                proxies=self.proxies,
                timeout=self.timeout,
                verify=False,
                allow_redirects=follow_redirects
            )
            elapsed = time.time() - start
            status = response.status_code
            text_sample = response.text[:300]
            location_header = response.headers.get('Location', '')

            # 1. 状态码检查
            if status not in allowed_status_codes:
                return False, f"状态码不在允许列表 {allowed_status_codes} 中，实际 {status}", elapsed, status, text_sample, location_header

            # 2. Location 头检查（仅当状态码为 3xx 且配置了 location_expected 时检查）
            if location_expected and 300 <= status < 400:
                if location_expected not in location_header:
                    return False, f"Location 头中未找到期望内容: '{location_expected}'，实际 Location: {location_header}", elapsed, status, text_sample, location_header

            # 3. 必须包含检查
            if must_contain and must_contain not in response.text:
                return False, f"响应中未找到期望内容: '{must_contain}'", elapsed, status, text_sample, location_header

            # 4. 禁止包含检查
            if must_not_contain and must_not_contain in response.text:
                return False, f"响应中包含了禁止内容: '{must_not_contain}'", elapsed, status, text_sample, location_header

            return True, "OK", elapsed, status, text_sample, location_header

        except ProxyError as e:
            return False, f"代理错误: {e}", 0, 0, "", ""
        except Timeout:
            return False, f"超时 (>{self.timeout}s)", 0, 0, "", ""
        except ConnectionError as e:
            return False, f"连接错误: {e}", 0, 0, "", ""
        except SSLError as e:
            return False, f"SSL错误: {e}", 0, 0, "", ""
        except Exception as e:
            return False, f"未知错误: {e}", 0, 0, "", ""

    def run_tests(self, test_cases: List[Dict[str, Any]]) -> Dict[str, Any]:
        results = []
        all_passed = True
        for idx, case in enumerate(test_cases):
            url = case.get('url')
            if not url:
                results.append({"description": case.get('description', 'UNKNOWN'), "passed": False, "error": "缺少 url 字段"})
                all_passed = False
                continue

            description = case.get('description', url)
            allowed_codes = case.get('allowed_status_codes', [200])
            must_contain = case.get('must_contain')
            must_not_contain = case.get('must_not_contain')
            location_expected = case.get('location_expected')
            follow_redirects = case.get('follow_redirects', False)

            passed, error_msg, elapsed, status, sample, location = self.test_url(
                url, allowed_codes, must_contain, must_not_contain, location_expected, follow_redirects
            )

            result_item = {
                "description": description,
                "url": url,
                "passed": passed,
                "error": error_msg if not passed else None,
                "elapsed_sec": round(elapsed, 2),
                "http_status": status,
                "location_header": location if location else None,
                "response_sample": sample if not passed else None
            }
            results.append(result_item)
            if not passed:
                all_passed = False

        return {
            "proxy": self.proxy_url,
            "all_passed": all_passed,
            "test_results": results
        }


def load_config(config_file: str) -> List[Dict[str, Any]]:
    with open(config_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    elif isinstance(data, dict) and 'test_cases' in data:
        return data['test_cases']
    else:
        raise ValueError("配置文件格式错误，应为测试用例数组或包含 test_cases 字段的对象")


def main():
    parser = argparse.ArgumentParser(description="出口 IP（代理）高级检测 - 支持连通性 + 302跳转校验")
    parser.add_argument("--proxy", "-p", required=True,
                        help="代理地址，例如 http://user:pass@host:port 或 socks5://host:port")
    parser.add_argument("--timeout", "-t", type=int, default=10,
                        help="请求超时秒数（默认10）")
    parser.add_argument("--config", "-c", required=True,
                        help="JSON 配置文件，包含测试用例（必须）")
    args = parser.parse_args()

    test_cases = load_config(args.config)

    tester = ProxyTester(args.proxy, timeout=args.timeout)
    result = tester.run_tests(test_cases)

    # 打印结果
    print("\n" + "="*70)
    print(f"代理地址: {result['proxy']}")
    print("="*70)
    for tr in result['test_results']:
        status_icon = "✅" if tr['passed'] else "❌"
        print(f"\n{status_icon} {tr['description']}")
        print(f"   URL: {tr['url']}")
        print(f"   耗时: {tr['elapsed_sec']}秒 | HTTP状态: {tr['http_status']}")
        if tr.get('location_header'):
            print(f"   Location: {tr['location_header']}")
        if not tr['passed']:
            print(f"   失败原因: {tr['error']}")
            if tr.get('response_sample'):
                print(f"   响应片段: {tr['response_sample'][:200]}...")
    print("="*70)
    if result['all_passed']:
        print("✅ 最终判定: 出口 IP 有效，所有业务测试通过")
        sys.exit(0)
    else:
        print("❌ 最终判定: 出口 IP 无效，至少一个测试失败")
        sys.exit(1)


if __name__ == "__main__":
    # 禁用 SSL 警告（可选）
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    main()





# description	string	否	测试用例的可读描述，显示在结果报告中。
# url	string	是	要通过代理访问的完整 URL（包含协议，如 https://...）。
# allowed_status_codes	array of int	否	允许的 HTTP 状态码列表，例如 [200, 302]。默认 [200]。
# must_contain	string	否	响应体（HTML/文本）中必须包含的子字符串（区分大小写）。
# must_not_contain	string	否	响应体中不得包含的子字符串。
# location_expected	string	否	仅当状态码为 3xx（重定向）时检查 Location 响应头，要求其值中包含该字符串。
# follow_redirects	boolean	否	是否自动跟随 HTTP 重定向。默认 false（不跟随，便于检查原始状态码和 Location 头）。设为 true 时，最终状态码将变为 200 等，需相应调整 allowed_status_codes。