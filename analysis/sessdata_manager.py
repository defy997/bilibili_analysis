"""
B站 SESSDATA 管理模块
负责登录、刷新、验证 SESSDATA

整合了 login.py 和 refresh_local.py 的功能
"""
import json
import time
import requests
import qrcode
import os
from datetime import datetime, timedelta
from django.utils import timezone
from urllib.parse import urlencode
from hashlib import md5
from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA256
import binascii
import urllib.parse
import pytz

# B站公钥
BILIBILI_PUBLIC_KEY = '''-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDLgd2OAkcGVtoE3ThUREbio0Eg
Uc/prcajMKXvkCKFCWhJYJcLkcM2DKKcSeFpD/j6Boy538YXnR6VhcuUJOhH2x71
nzPjfdTcqMz7djHum0qSZA0AyCBDABUqCrfNgCiJ00Ra7GmRj+YCK1NJEuewlb40
JNrRuoEUXpabUzGB8QIDAQAB
-----END PUBLIC KEY-----'''

# 请求头
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.bilibili.com/',
    'Origin': 'https://www.bibili.com',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}

APPKEY = "4409e2ce8ffd12b8"
APPSEC = "59b43e04ad6965f34319062b478f83dd"


def get_sign(params):
    """计算签名"""
    items = sorted(params.items())
    return md5(f"{urlencode(items)}{APPSEC}".encode('utf-8')).hexdigest()


def get_correspond_path(timestamp):
    """生成CorrespondPath签名"""
    key = RSA.importKey(BILIBILI_PUBLIC_KEY)
    cipher = PKCS1_OAEP.new(key, SHA256)
    encrypted = cipher.encrypt(f'refresh_{timestamp}'.encode())
    return binascii.b2a_hex(encrypted).decode()


class SessdataManager:
    """SESSDATA 管理器"""
    
    def __init__(self, user=None):
        """
        初始化管理器
        
        Args:
            user: Django User 实例，如果为 None 则使用默认用户
        """
        self.user = user
    
    def _get_user(self):
        """获取用户实例"""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        if self.user:
            return self.user
        
        # 默认返回第一个有 bilibili 凭证的用户
        return User.objects.filter(
            bilibili_mid__isnull=False
        ).first()
    
    def check_sessdata_valid(self, sessdata=None):
        """
        检查 SESSDATA 是否有效
        
        Returns:
            dict: {'valid': bool, 'message': str, 'need_refresh': bool}
        """
        user = self._get_user()
        if not user:
            return {'valid': False, 'message': '没有找到已登录的用户', 'need_refresh': True}
        
        # 使用提供的 sessdata 或从数据库获取
        if sessdata is None:
            sessdata = user.sessdata
        
        if not sessdata:
            return {'valid': False, 'message': '没有配置 SESSDATA', 'need_refresh': True}
        
        # 构建 Cookie
        cookies = {'SESSDATA': sessdata}
        if user.bili_jct:
            cookies['bili_jct'] = user.bili_jct
        if user.bilibili_mid:
            cookies['DedeUserID'] = str(user.bilibili_mid)
        
        try:
            url = "https://passport.bilibili.com/x/passport-login/web/cookie/info"
            response = requests.get(url, cookies=cookies, headers=HEADERS, timeout=10)
            result = response.json()
            
            if result.get('code') == 0:
                data = result.get('data', {})
                need_refresh = data.get('refresh', False)
                
                if need_refresh:
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
    
    def refresh_sessdata(self):
        """
        刷新 SESSDATA
        
        Returns:
            dict: {'success': bool, 'message': str, 'new_sessdata': str}
        """
        user = self._get_user()
        if not user:
            return {'success': False, 'message': '没有找到已登录的用户', 'new_sessdata': None}
        
        if not user.refresh_token or not user.sessdata or not user.bili_jct:
            return {
                'success': False,
                'message': '缺少必要的登录凭证，请重新扫码登录',
                'new_sessdata': None
            }
        
        # 构建 Cookie
        cookies = {
            'SESSDATA': user.sessdata,
            'bili_jct': user.bili_jct,
        }
        if user.bilibili_mid:
            cookies['DedeUserID'] = str(user.bilibili_mid)
        
        try:
            # 步骤1: 检查是否需要刷新
            url = "https://passport.bilibili.com/x/passport-login/web/cookie/info"
            response = requests.get(url, cookies=cookies, headers=HEADERS, timeout=10)
            result = response.json()
            
            if result.get('code') == 0:
                data = result.get('data', {})
                timestamp = data.get('timestamp')
            else:
                timestamp = None
            
            # 步骤2: 生成 CorrespondPath
            ts = timestamp or int(time.time() * 1000)
            correspond_path = get_correspond_path(ts)
            
            # 步骤3: 获取 refresh_csrf
            csrf_url = f"https://www.bilibili.com/correspond/1/{correspond_path}"
            csrf_response = requests.get(csrf_url, cookies=cookies, headers=HEADERS, timeout=10)
            
            import re
            match = re.search(r'<div id="1-name">([^<]+)</div>', csrf_response.text)
            refresh_csrf = match.group(1) if match else None
            
            if not refresh_csrf:
                return {
                    'success': False,
                    'message': '获取 refresh_csrf 失败',
                    'new_sessdata': None
                }
            
            # 步骤4: 刷新 Cookie
            refresh_url = "https://passport.bilibili.com/x/passport-login/web/cookie/refresh"
            data = {
                'csrf': user.bili_jct,
                'refresh_csrf': refresh_csrf,
                'source': 'main_web',
                'refresh_token': user.refresh_token
            }
            
            session = requests.Session()
            session.headers.update(HEADERS)
            session.cookies.update(cookies)
            
            refresh_response = session.post(refresh_url, data=data, timeout=10)
            refresh_result = refresh_response.json()
            
            if refresh_result.get('code') == 0:
                # 获取新的 Cookie
                new_cookies = {}
                for cookie in refresh_response.cookies:
                    new_cookies[cookie.name] = cookie.value
                
                new_sessdata = new_cookies.get('SESSDATA', user.sessdata)
                new_refresh_token = refresh_result.get('data', {}).get('refresh_token')
                
                # 更新数据库
                user.sessdata = new_sessdata
                user.refresh_token = new_refresh_token
                user.bili_jct = new_cookies.get('bili_jct', user.bili_jct)
                user.last_refreshed_at = timezone.now()
                
                # 计算新的过期时间（通常 30 天）
                user.sessdata_expires_at = timezone.now() + timedelta(days=30)
                user.save()
                
                return {
                    'success': True,
                    'message': 'SESSDATA 刷新成功',
                    'new_sessdata': new_sessdata
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
                'message': f'刷新过程出错: {str(e)}',
                'new_sessdata': None
            }
    
    def generate_qrcode(self):
        """
        生成登录二维码
        
        Returns:
            dict: {'success': bool, 'qr_url': str, 'auth_code': str, 'qr_image': str}
        """
        try:
            params = {
                'appkey': APPKEY,
                'local_id': 0,
                'ts': int(time.time())
            }
            params['sign'] = get_sign(params)

            # 使用 form 表单格式发送请求
            url = "https://passport.bilibili.com/x/passport-tv-login/qrcode/auth_code"
            headers = dict(HEADERS)
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
            response = requests.post(url, data=params, headers=headers, timeout=10)
            
            if response.status_code != 200:
                return {
                    'success': False,
                    'message': f'请求失败: {response.status_code}',
                    'qr_url': None,
                    'auth_code': None
                }
            
            data = response.json()
            if data.get('code') != 0:
                return {
                    'success': False,
                    'message': f'API错误: {data.get("message")}',
                    'qr_url': None,
                    'auth_code': None
                }
            
            qr_url = data['data']['url']
            auth_code = data['data']['auth_code']
            
            # 生成二维码图片
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=2,
                border=2,
            )
            qr.add_data(qr_url)
            qr.make(fit=True)
            
            # 保存为 base64
            from io import BytesIO
            import base64
            
            img = qr.make_image(fill_color="black", back_color="white")
            buffered = BytesIO()
            img.save(buffered, format="PNG")
            qr_image = buffered.getvalue()
            qr_image_base64 = f"data:image/png;base64,{base64.b64encode(qr_image).decode('utf-8')}"
            
            return {
                'success': True,
                'qr_url': qr_url,
                'auth_code': auth_code,
                'qr_image': qr_image_base64
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'生成二维码失败: {str(e)}',
                'qr_url': None,
                'auth_code': None
            }
    
    def poll_login_status(self, auth_code):
        """
        轮询登录状态
        
        Args:
            auth_code: 授权码
            
        Returns:
            dict: {'success': bool, 'message': str, 'tokens': dict}
        """
        try:
            params = {
                'appkey': APPKEY,
                'local_id': 0,
                'ts': int(time.time()),
                'auth_code': auth_code
            }
            params['sign'] = get_sign(params)

            poll_url = "https://passport.bilibili.com/x/passport-tv-login/qrcode/poll"

            headers = dict(HEADERS)
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
            response = requests.post(poll_url, data=params, headers=headers, timeout=10)
            result = response.json()
            
            if result.get('code') == 0:
                data = result.get('data', {})
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
                
                tokens = {
                    'access_token': token_info.get('access_token'),
                    'refresh_token': token_info.get('refresh_token'),
                    'sessdata': sessdata,
                    'bili_jct': bili_jct,
                    'mid': data.get('mid'),
                    'expires_in': token_info.get('expires_in')
                }
                
                # 保存到数据库
                user = self._get_user()
                if user:
                    user.bilibili_mid = data.get('mid')
                    user.sessdata = sessdata
                    user.bili_jct = bili_jct
                    user.access_token = token_info.get('access_token')
                    user.refresh_token = token_info.get('refresh_token')
                    user.sessdata_expires_at = timezone.now() + timedelta(days=30)
                    user.last_refreshed_at = timezone.now()
                    user.save()
                
                return {
                    'success': True,
                    'message': '登录成功',
                    'tokens': tokens
                }
            elif result.get('code') == 86101:
                return {
                    'success': False,
                    'message': '等待扫码',
                    'status': 'waiting'
                }
            elif result.get('code') == 86090:
                return {
                    'success': False,
                    'message': '已扫码，等待确认',
                    'status': 'confirmed'
                }
            else:
                return {
                    'success': False,
                    'message': result.get('message', '未知状态'),
                    'status': 'error'
                }
        except Exception as e:
            return {
                'success': False,
                'message': f'查询失败: {str(e)}',
                'status': 'error'
            }
    
    def get_sessdata_for_crawler(self):
        """
        获取用于爬虫的 SESSDATA，如果过期则自动刷新
        
        Returns:
            str: SESSDATA 值
        """
        user = self._get_user()
        if not user or not user.sessdata:
            return None
        
        # 检查是否需要刷新
        check_result = self.check_sessdata_valid()
        if check_result.get('need_refresh'):
            refresh_result = self.refresh_sessdata()
            if refresh_result['success']:
                return refresh_result['new_sessdata']
            else:
                return None
        
        return user.sessdata
    
    def get_cookie_header(self):
        """
        获取用于请求头的完整 Cookie 字符串
        
        Returns:
            str: Cookie 字符串
        """
        user = self._get_user()
        if not user or not user.sessdata:
            return ""
        
        cookies = [f"SESSDATA={user.sessdata}"]
        if user.bili_jct:
            cookies.append(f"bili_jct={user.bili_jct}")
        if user.bilibili_mid:
            cookies.append(f"DedeUserID={user.bilibili_mid}")
        
        return "; ".join(cookies)
