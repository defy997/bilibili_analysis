"""
B站扫码登录模块
生成二维码并获取 SESSDATA

WBI 签名在爬虫阶段使用，登录阶段主要用于获取 SESSDATA
"""
import time
import requests
import qrcode
import os
import json
from datetime import datetime
from hashlib import md5

APPKEY = "4409e2ce8ffd12b8"
APPSEC = "59b43e04ad6965f34319062b478f83dd"

# 添加必要的请求头
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.bilibili.com/',
    'Origin': 'https://www.bilibili.com',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Content-Type': 'application/x-www-form-urlencoded',
}


def qr_login():
    """
    扫码登录，获取 SESSDATA
    
    Returns:
        dict: {'success': bool, 'sessdata': str, 'bili_jct': str, 'mid': int}
    """
    # 第一步：获取二维码和授权码
    params = {
        'appkey': APPKEY,
        'local_id': 0,
        'ts': int(time.time())
    }
    params['sign'] = get_sign(params)
    
    url = "https://passport.bilibili.com/x/passport-tv-login/qrcode/auth_code"
    
    try:
        r = requests.post(url, params=params, headers=HEADERS, timeout=10)
        print(f"状态码: {r.status_code}")
        
        if r.status_code != 200:
            return {'success': False, 'error': f'请求失败: {r.status_code}'}
        
        data = r.json()
        if data.get('code') != 0:
            return {'success': False, 'error': data.get('message', '未知错误')}
        
        if 'data' not in data or 'url' not in data['data']:
            return {'success': False, 'error': '响应数据格式不正确'}
        
        qr_url = data['data']['url']
        auth_code = data['data']['auth_code']
        
        print(f"二维码URL: {qr_url}")
        print(f"授权码: {auth_code}")
        
        # 生成二维码图片
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=2,
            border=2,
        )
        qr.add_data(qr_url)
        qr.make(fit=True)
        
        # 保存为图片文件
        img = qr.make_image(fill_color="black", back_color="white")
        qr_file = "bilibili_qrcode.png"
        img.save(qr_file)
        print(f"\n二维码已保存到: {os.path.abspath(qr_file)}")
        print("\n请使用B站APP扫描二维码登录...")
        print("等待扫码中...\n")
        
        # 第二步：轮询登录状态
        poll_params = {
            'appkey': APPKEY,
            'local_id': 0,
            'ts': int(time.time()),
            'auth_code': auth_code
        }
        poll_params['sign'] = get_sign(poll_params)
        poll_url = "https://passport.bilibili.com/x/passport-tv-login/qrcode/poll"
        
        max_retries = 60  # 最多等待 2 分钟
        retries = 0
        
        while retries < max_retries:
            poll_r = requests.post(poll_url, params=poll_params, headers=HEADERS, timeout=10)
            
            try:
                poll_data = poll_r.json()
            except ValueError:
                print("响应不是有效的JSON")
                time.sleep(2)
                retries += 1
                continue
            
            if poll_data.get('code') == 0:
                print("\n登录成功!")
                
                data = poll_data.get('data', {})
                token_info = data.get('token_info', {})
                cookie_info = data.get('cookie_info', {})
                
                # 提取 SESSDATA 和 bili_jct
                sessdata = None
                bili_jct = None
                for cookie in cookie_info.get('cookies', []):
                    name = cookie.get('name')
                    if name == 'SESSDATA':
                        sessdata = cookie.get('value')
                    elif name == 'bili_jct':
                        bili_jct = cookie.get('value')
                
                mid = data.get('mid')
                
                print(f"\n用户ID: {mid}")
                print(f"SESSDATA: {sessdata[:30]}...")
                print(f"bili_jct: {bili_jct}")
                
                # 保存到文件
                tokens_file = "tokens.json"
                tokens_data = {
                    'sessdata': sessdata,
                    'bili_jct': bili_jct,
                    'mid': mid,
                    'obtained_at': datetime.now().isoformat()
                }
                
                with open(tokens_file, 'w', encoding='utf-8') as f:
                    json.dump(tokens_data, f, indent=2, ensure_ascii=False)
                
                print(f"\n✅ Token信息已保存到: {os.path.abspath(tokens_file)}")
                
                return {
                    'success': True,
                    'sessdata': sessdata,
                    'bili_jct': bili_jct,
                    'mid': mid
                }
                
            elif poll_data.get('code') == 86101:
                print("等待扫码...")
            elif poll_data.get('code') == 86090:
                print("二维码已扫描，等待确认...")
            else:
                print(f"状态: {poll_data.get('message', '未知状态')}")
            
            time.sleep(2)
            retries += 1
        
        return {'success': False, 'error': '扫码超时'}
        
    except Exception as e:
        print(f"错误: {e}")
        return {'success': False, 'error': str(e)}


def get_sign(params):
    """计算签名（登录阶段使用旧的 MD5 签名）"""
    items = sorted(params.items())
    return md5(f"{urlencode(items)}{APPSEC}".encode('utf-8')).hexdigest()


def md5_hash(text):
    """MD5 哈希"""
    return md5(text.encode('utf-8')).hexdigest()


def urlencode(items):
    """URL 编码"""
    return '&'.join(f"{k}={v}" for k, v in items)


if __name__ == "__main__":
    result = qr_login()
    if result['success']:
        print("\n" + "=" * 50)
        print("登录成功！")
        print("=" * 50)
        print(f"SESSDATA: {result['sessdata']}")
        print(f"bili_jct: {result['bili_jct']}")
        print(f"mid: {result['mid']}")
    else:
        print(f"\n登录失败: {result['error']}")
