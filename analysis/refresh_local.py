"""
SESSDATA 刷新模块
检测 SESSDATA 是否需要刷新

WBI 签名在爬虫阶段使用，这里只检测 cookie 状态
"""
import time
import requests
from datetime import datetime, timedelta

APPKEY = "4409e2ce8ffd12b8"
APPSEC = "59b43e04ad6965f34319062b478f83dd"

# 请求头
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.bilibili.com/',
    'Accept': 'application/json, text/plain, */*',
}


def check_sessdata(sessdata):
    """
    检查 SESSDATA 是否有效
    
    Args:
        sessdata: SESSDATA 字符串
        
    Returns:
        dict: {'valid': bool, 'message': str}
    """
    if not sessdata:
        return {'valid': False, 'message': 'SESSDATA 为空'}
    
    cookies = {'SESSDATA': sessdata}
    
    try:
        url = "https://passport.bilibili.com/x/passport-login/web/cookie/info"
        response = requests.get(url, cookies=cookies, headers=HEADERS, timeout=10)
        result = response.json()
        
        if result.get('code') == 0:
            data = result.get('data', {})
            refresh = data.get('refresh', False)
            
            if refresh:
                return {
                    'valid': True,
                    'message': 'SESSDATA 有效，但需要刷新',
                    'need_refresh': True
                }
            else:
                return {
                    'valid': True,
                    'message': 'SESSDATA 有效',
                    'need_refresh': False
                }
        else:
            return {
                'valid': False,
                'message': f'SESSDATA 无效: {result.get("message", "未知错误")}',
                'need_refresh': True
            }
            
    except Exception as e:
        return {
            'valid': False,
            'message': f'检查失败: {str(e)}',
            'need_refresh': True
        }


def refresh_sessdata(sessdata, bili_jct):
    """
    刷新 SESSDATA（如果需要的话）
    
    Args:
        sessdata: 当前的 SESSDATA
        bili_jct: CSRF token
        
    Returns:
        dict: {'success': bool, 'new_sessdata': str, 'message': str}
    """
    if not sessdata:
        return {'success': False, 'message': 'SESSDATA 为空', 'new_sessdata': None}
    
    if not bili_jct:
        return {'success': False, 'message': 'bili_jct 为空', 'new_sessdata': None}
    
    cookies = {
        'SESSDATA': sessdata,
        'bili_jct': bili_jct
    }
    
    try:
        # 检查是否需要刷新
        check_url = "https://passport.bilibili.com/x/passport-login/web/cookie/info"
        check_resp = requests.get(check_url, cookies=cookies, headers=HEADERS, timeout=10)
        check_result = check_resp.json()
        
        if check_result.get('code') == 0:
            timestamp = check_result.get('data', {}).get('timestamp')
        else:
            timestamp = None
        
        # 生成刷新签名
        ts = timestamp or int(time.time() * 1000)
        csrf = get_csrf(ts, bili_jct)
        
        # 刷新 cookie
        refresh_url = "https://passport.bilibili.com/x/passport-login/web/cookie/refres"
        refresh_params = {
            'csrf': csrf,
            'ts': ts
        }
        
        refresh_resp = requests.post(refresh_url, params=refresh_params, cookies=cookies, headers=HEADERS, timeout=10)
        refresh_result = refresh_resp.json()
        
        if refresh_result.get('code') == 0:
            # 获取新的 SESSDATA
            new_cookies = refresh_result.get('data', {}).get('cookie_info', {}).get('cookies', [])
            new_sessdata = None
            for cookie in new_cookies:
                if cookie.get('name') == 'SESSDATA':
                    new_sessdata = cookie.get('value')
                    break
            
            if new_sessdata:
                print(f"SESSDATA 刷新成功")
                print(f"新 SESSDATA: {new_sessdata[:30]}...")
                return {
                    'success': True,
                    'new_sessdata': new_sessdata,
                    'message': '刷新成功'
                }
            else:
                return {
                    'success': False,
                    'message': '未获取到新 SESSDATA',
                    'new_sessdata': None
                }
        else:
            return {
                'success': False,
                'message': f'刷新失败: {refresh_result.get("message", "未知错误")}',
                'new_sessdata': None
            }
            
    except Exception as e:
        return {
            'success': False,
            'message': f'刷新失败: {str(e)}',
            'new_sessdata': None
        }


def get_csrf(timestamp, bili_jct):
    """
    生成 CSRF token
    
    Args:
        timestamp: 时间戳
        bili_jct: CSRF secret
        
    Returns:
        str: CSRF token
    """
    import hashlib
    secret_key = "59b43e04ad6965f34319062b478f83dd"
    message = f"refresh_{timestamp}"
    
    # 获取 bili_jct 的前 8 位作为 key
    key = bili_jct[:8] if len(bili_jct) >= 8 else bili_jct
    
    # 简单的 XOR 加密作为 CSRF
    csrf = ""
    for i, char in enumerate(message):
        key_char = key[i % len(key)]
        csrf += chr(ord(char) ^ ord(key_char))
    
    # 转换为 16 进制
    csrf_bytes = csrf.encode('utf-8')
    csrf_hex = csrf_bytes.hex()
    
    return csrf_hex
    

def urlencode(items):
    """URL 编码"""
    return '&'.join(f"{k}={v}" for k, v in items)


def main():
    """主函数 - 从 tokens.json 读取并检查/刷新"""
    import json
    import os
    
    tokens_file = "tokens.json"
    
    if not os.path.exists(tokens_file):
        print("未找到 tokens.json，请先运行 login.py 登录")
        return
    
    with open(tokens_file, 'r', encoding='utf-8') as f:
        tokens = json.load(f)
    
    sessdata = tokens.get('sessdata')
    bili_jct = tokens.get('bili_jct')
    
    print("=" * 50)
    print("SESSDATA 状态检查")
    print("=" * 50)
    
    # 检查是否有效
    check_result = check_sessdata(sessdata)
    print(f"状态: {check_result['message']}")
    
    if check_result['valid']:
        if check_result.get('need_refresh', False):
            print("\n需要刷新 SESSDATA...")
            refresh_result = refresh_sessdata(sessdata, bili_jct)
            
            if refresh_result['success']:
                # 更新 tokens.json
                tokens['sessdata'] = refresh_result['new_sessdata']
                with open(tokens_file, 'w', encoding='utf-8') as f:
                    json.dump(tokens, f, indent=2, ensure_ascii=False)
                
                print("✅ SESSDATA 已更新到 tokens.json")
            else:
                print(f"❌ 刷新失败: {refresh_result['message']}")
        else:
            print("\nSESSDATA 无需刷新")
    else:
        print(f"\n❌ SESSDATA 无效: {check_result['message']}")
        print("请重新运行 login.py 登录")


if __name__ == "__main__":
    main()
