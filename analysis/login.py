import time
import requests
from urllib.parse import urlencode
from hashlib import md5
import qrcode
import os
import json
from datetime import datetime


APPKEY = "4409e2ce8ffd12b8"
APPSEC = "59b43e04ad6965f34319062b478f83dd"

# 添加必要的请求头，避免被B站安全策略拦截
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.bilibili.com/',
    'Origin': 'https://www.bilibili.com',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Content-Type': 'application/x-www-form-urlencoded',
}


def get_sign(params):
    items = sorted(params.items())
    return md5(f"{urlencode(items)}{APPSEC}".encode('utf-8')).hexdigest()


def qr_login():
    params = {
        'appkey': APPKEY,
        'local_id': 0,
        'ts': int(time.time())
    }
    params['sign'] = get_sign(params)
    url = f"https://passport.bilibili.com/x/passport-tv-login/qrcode/auth_code"
    
    try:
        r = requests.post(url, params=params, headers=HEADERS, timeout=10)
        print(f"状态码: {r.status_code}")
        print(f"响应内容: {r.text[:500]}")  # 只打印前500字符
        
        # 检查状态码
        if r.status_code != 200:
            print(f"错误: 请求失败，状态码 {r.status_code}")
            return
        
        # 检查响应是否为JSON
        try:
            data = r.json()
        except ValueError as e:
            print(f"错误: 响应不是有效的JSON格式 - {e}")
            print(f"响应内容: {r.text}")
            return
        
        # 检查API返回码
        if data.get('code') != 0:
            print(f"错误: API返回错误码 {data.get('code')}, 消息: {data.get('message', '未知错误')}")
            return
        
        if 'data' not in data or 'url' not in data['data']:
            print(f"错误: 响应数据格式不正确")
            print(f"响应数据: {data}")
            return
        
        qr_url = data['data']['url']
        auth_code = data['data']['auth_code']
        
        print(f"\n二维码URL: {qr_url}")
        print(f"授权码: {auth_code}\n")
        
        # 生成二维码
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=2,
            border=2,
        )
        qr.add_data(qr_url)
        qr.make(fit=True)
        
        # 方式1: 在终端打印ASCII二维码
        print("=" * 50)
        print("二维码 (ASCII):")
        print("=" * 50)
        qr.print_ascii(invert=True)
        print("=" * 50)
        
        # 方式2: 保存为图片文件
        img = qr.make_image(fill_color="black", back_color="white")
        qr_file = "bilibili_qrcode.png"
        img.save(qr_file)
        print(f"\n二维码已保存到文件: {os.path.abspath(qr_file)}")
        
        # 方式3: 尝试用系统默认程序打开（Windows）
        try:
            if os.name == 'nt':  # Windows
                os.startfile(qr_file)
            else:  # macOS/Linux
                os.system(f'open {qr_file}' if os.uname().sysname == 'Darwin' else f'xdg-open {qr_file}')
            print("已尝试用系统默认程序打开二维码图片")
        except Exception as e:
            print(f"无法自动打开图片: {e}")
            print(f"请手动打开文件: {os.path.abspath(qr_file)}")
        
        print("\n请使用B站APP扫描二维码登录...")
        print("等待扫码中...\n")

        # 轮询登录状态
        poll_params = {
            'appkey': APPKEY,
            'local_id': 0,
            'ts': int(time.time()),
            'auth_code': auth_code
        }
        poll_params['sign'] = get_sign(poll_params)
        poll_url = f"https://passport.bilibili.com/x/passport-tv-login/qrcode/poll"
        
        while True:
            poll_r = requests.post(poll_url, params=poll_params, headers=HEADERS, timeout=10)
            print(f"轮询响应: {poll_r.text[:200]}")
            
            try:
                poll_data = poll_r.json()
            except ValueError:
                print("错误: 轮询响应不是有效的JSON")
                time.sleep(2)
                continue
            
            if poll_data.get('code') == 0:
                print("\n" + "=" * 50)
                print("登录成功!")
                print("=" * 50)
                
                # 提取关键信息
                data = poll_data.get('data', {})
                token_info = data.get('token_info', {})
                cookie_info = data.get('cookie_info', {})
                
                access_token = token_info.get('access_token')
                refresh_token = token_info.get('refresh_token')
                
                # 查找SESSDATA和bili_jct
                sessdata = None
                bili_jct = None
                for cookie in cookie_info.get('cookies', []):
                    cookie_name = cookie.get('name')
                    if cookie_name == 'SESSDATA':
                        sessdata = cookie.get('value')
                    elif cookie_name == 'bili_jct':
                        bili_jct = cookie.get('value')
                
                print(f"\n用户ID: {data.get('mid')}")
                print(f"Access Token: {access_token[:20]}...")
                print(f"Refresh Token: {refresh_token[:20]}...")
                print(f"SESSDATA: {sessdata}")
                print(f"bili_jct: {bili_jct[:20] if bili_jct else '未找到'}...")
                
                # 保存token信息到文件
                tokens_file = "tokens.json"
                tokens_data = {
                    'access_token': access_token,
                    'refresh_token': refresh_token,
                    'sessdata': sessdata,
                    'bili_jct': bili_jct,  # 保存CSRF token用于刷新
                    'mid': data.get('mid'),
                    'expires_in': token_info.get('expires_in'),
                    'obtained_at': datetime.now().isoformat()
                }
                
                with open(tokens_file, 'w', encoding='utf-8') as f:
                    json.dump(tokens_data, f, indent=2, ensure_ascii=False)
                
                print(f"\n✅ Token信息已保存到: {os.path.abspath(tokens_file)}")
                print("\n下一步操作:")
                print("1. 运行 setup_github.py 自动更新 GitHub Secrets")
                print("2. 或者手动在 GitHub 仓库设置中添加 Secrets")
                print("3. GitHub Actions 会自动在每天 00:00 刷新 SESSDATA")
                
                # 询问是否立即更新 GitHub Secrets
                print("\n" + "=" * 50)
                update_github = input("是否立即运行 setup_github.py 更新 GitHub Secrets? (y/n): ").strip().lower()
                if update_github == 'y':
                    print("\n正在运行 setup_github.py...")
                    try:
                        import subprocess
                        subprocess.run(['python', 'setup_github.py'], check=True)
                    except FileNotFoundError:
                        print("⚠️  未找到 setup_github.py，请手动运行")
                    except subprocess.CalledProcessError:
                        print("⚠️  setup_github.py 执行失败，请手动运行")
                    except Exception as e:
                        print(f"⚠️  运行 setup_github.py 时出错: {e}")
                        print("请手动运行: python setup_github.py")
                else:
                    print("\n稍后可以运行以下命令更新 GitHub Secrets:")
                    print("  python setup_github.py")
                
                break
            elif poll_data.get('code') == 86101:
                print("等待扫码...")
            elif poll_data.get('code') == 86090:
                print("二维码已扫描，等待确认...")
            else:
                print(f"状态: {poll_data.get('message', '未知状态')}")
            
            time.sleep(2)
            
    except requests.exceptions.RequestException as e:
        print(f"网络请求错误: {e}")
    except Exception as e:
        print(f"发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    qr_login()