import json
import os
import sys

# Ensure project root is in sys.path (needed for local dev; Vercel handles this automatically)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request, render_template, jsonify
from check_proxy_advanced import ProxyTester

app = Flask(__name__, template_folder=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates'))

@app.route('/')
def index():
    default_config = {
        "test_cases": [
            {
                "description": "robots.txt 连通性（必须返回200）",
                "url": "https://vendorcentral.amazon.com/robots.txt",
                "allowed_status_codes": [200],
                "follow_redirects": False
            },
            {
                "description": "VC 首页 302 跳转检测（期望 Location 包含 /ap/signin）",
                "url": "https://vendorcentral.amazon.com/",
                "allowed_status_codes": [302],
                "location_expected": "/ap/signin",
                "follow_redirects": False
            },
            {
                "description": "robots.txt 连通性（必须返回200）",
                "url": "https://vendorcentral.amazon.de/robots.txt",
                "allowed_status_codes": [200],
                "follow_redirects": False
            },
            {
                "description": "VC 首页 302 跳转检测（期望 Location 包含 /ap/signin）",
                "url": "https://vendorcentral.amazon.de/",
                "allowed_status_codes": [302],
                "location_expected": "/ap/signin",
                "follow_redirects": False
            }
        ]
    }
    return render_template('index.html', default_config=json.dumps(default_config, indent=2))

@app.route('/test', methods=['POST'])
def run_test():
    data = request.get_json()
    proxy = data.get('proxy')
    config_json = data.get('config')
    timeout = data.get('timeout', 10)

    if not proxy:
        return jsonify({'error': '代理地址不能为空'}), 400
    if not config_json:
        return jsonify({'error': '测试配置不能为空'}), 400

    try:
        config_data = json.loads(config_json)
        if isinstance(config_data, list):
            test_cases = config_data
        elif isinstance(config_data, dict) and 'test_cases' in config_data:
            test_cases = config_data['test_cases']
        else:
            return jsonify({'success': False, 'output': '', 'error': '配置文件格式错误'}), 400

        tester = ProxyTester(proxy, timeout=timeout)
        result = tester.run_tests(test_cases)

        lines = []
        lines.append("")
        lines.append("=" * 70)
        lines.append(f"代理地址: {result['proxy']}")
        lines.append("=" * 70)
        for tr in result['test_results']:
            status_icon = "PASS" if tr['passed'] else "FAIL"
            lines.append(f"\n[{status_icon}] {tr['description']}")
            lines.append(f"   URL: {tr['url']}")
            lines.append(f"   耗时: {tr['elapsed_sec']}秒 | HTTP状态: {tr['http_status']}")
            if tr.get('location_header'):
                lines.append(f"   Location: {tr['location_header']}")
            if not tr['passed']:
                lines.append(f"   失败原因: {tr['error']}")
                if tr.get('response_sample'):
                    lines.append(f"   响应片段: {tr['response_sample'][:200]}...")
        lines.append("=" * 70)
        if result['all_passed']:
            lines.append("PASS: 出口 IP 有效，所有业务测试通过")
        else:
            lines.append("FAIL: 出口 IP 无效，至少一个测试失败")

        output = "\n".join(lines)
        success = result['all_passed']
        return jsonify({
            'success': success,
            'output': output,
            'error': '' if success else '至少一个测试失败'
        })
    except json.JSONDecodeError as e:
        return jsonify({'success': False, 'output': '', 'error': f'JSON 解析错误: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'success': False, 'output': '', 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8081)