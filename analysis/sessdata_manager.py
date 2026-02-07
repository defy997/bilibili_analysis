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
import threading

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


# ============================================================
# WBI 签名模块（移植自 C++ crawler_service）
# ============================================================

# 固定的打乱顺序索引表
MIXIN_TABLE = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
    61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
    36, 20, 34, 44, 52
]


class WbiSigner:
    """WBI 签名器（单例模式）"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.img_key = ""
        self.sub_key = ""
        self.last_fetch_time = 0
        self._initialized = True

    def is_valid(self):
        """检查密钥是否有效"""
        return bool(self.img_key and self.sub_key)

    def is_expired(self):
        """检查密钥是否过期（6小时）"""
        if not self.last_fetch_time:
            return True
        return (time.time() - self.last_fetch_time) > (6 * 3600)

    def fetch_wbi_keys(self, sessdata=None):
        """从 nav 接口获取 WBI 密钥"""
        if sessdata is None:
            # 尝试从 views 导入（避免循环导入）
            try:
                from .views import BILI_COOKIE
                sessdata = BILI_COOKIE
            except (ImportError, AttributeError):
                # 如果无法导入，使用默认值
                sessdata = "SESSDATA=55d2ed48%2C1785846835%2Cd80a0%2A22CjDxZL1htFveMUpzPXZrxp6zwh1K5neWuRyhGlZxWZ1A3xBGw6NIs8AhnyqkO5tfmBgSVmhQTHVlNDNaMzlENjNqYjQwcGNPRzN5T05YcTN3SFRLT2ZvOW9sZHFvS295WmdRdW1YQXZzc01GMEdBek1YTGZTajNINW1jdmhRaUN4MWV6QnFLcGh3IIEC"

        url = "https://api.bilibili.com/x/web-interface/nav"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.bilibili.com/',
            'Cookie': sessdata or ''
        }

        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                print(f"[Wbi] Failed to fetch keys, HTTP {resp.status_code}")
                return False

            data = resp.json()
            if data.get('code') != 0:
                print(f"[Wbi] API error: {data.get('message')}")
                return False

            # 解析 wbi_img 字段（新版格式是对象）
            wbi_img = data.get('data', {}).get('wbi_img', {})
            if not wbi_img:
                print("[Wbi] No wbi_img in response")
                return False

            # 新版格式: {"img_url": "...", "sub_url": "..."}
            if isinstance(wbi_img, dict):
                img_url = wbi_img.get('img_url', '')
                sub_url = wbi_img.get('sub_url', '')
                if img_url and sub_url:
                    self.img_key = self._extract_filename(img_url)
                    self.sub_key = self._extract_filename(sub_url)
                    self.last_fetch_time = time.time()
                    print(f"[Wbi] Keys fetched: img_key={self.img_key[:12]}... sub_key={self.sub_key[:12]}...")
                    return True
                else:
                    print(f"[Wbi] Incomplete wbi_img data: {wbi_img}")
                    return False
            else:
                # 旧版格式：直接是字符串
                import re
                urls = re.findall(r'https://[^"\']+', wbi_img)
                if len(urls) >= 2:
                    self.img_key = self._extract_filename(urls[0])
                    self.sub_key = self._extract_filename(urls[1])
                    self.last_fetch_time = time.time()
                    print(f"[Wbi] Keys fetched: img_key={self.img_key[:12]}... sub_key={self.sub_key[:12]}...")
                    return True
                else:
                    print(f"[Wbi] Failed to parse img URLs: {wbi_img}")
                    return False

        except Exception as e:
            print(f"[Wbi] Exception: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _extract_filename(self, url):
        """从 URL 提取文件名（不含扩展名）"""
        import os
        filename = os.path.basename(url)
        # 去除扩展名
        if '.' in filename:
            filename = filename.rsplit('.', 1)[0]
        return filename

    def get_mixin_key(self):
        """生成 mixin key（核心算法）"""
        if not self.is_valid():
            self.fetch_wbi_keys()

        s = self.img_key + self.sub_key
        key = ''.join(s[MIXIN_TABLE[i]] for i in range(64) if MIXIN_TABLE[i] < len(s))
        return key[:32]

    def sign_params(self, params, sessdata=None):
        """
        生成带签名的请求参数

        Args:
            params: 原始参数字典
            sessdata: 可选的 SESSDATA 用于获取密钥

        Returns:
            dict: 添加了 wts 和 w_rid 的参数
        """
        with threading.Lock():
            if not self.is_valid() or self.is_expired():
                self.fetch_wbi_keys(sessdata)

            signed_params = dict(params)

            # 1. 添加时间戳
            wts = int(time.time())
            signed_params['wts'] = str(wts)

            # 2. 生成 w_rid (MD5签名)
            w_rid = self._generate_wrid(signed_params)
            signed_params['w_rid'] = w_rid

            return signed_params

    def _generate_wrid(self, params):
        """生成 w_rid (MD5签名)"""
        # 1. 按 key 的 ASCII 升序排序并拼接
        sorted_items = sorted(params.items())
        query = '&'.join(f"{k}={v}" for k, v in sorted_items)

        # 2. 拼接 mixin key
        mixin = self.get_mixin_key()
        query += mixin

        # 3. MD5 签名
        return md5(query.encode('utf-8')).hexdigest()


def get_wbi_signed_params(params, sessdata=None):
    """便捷函数：获取 WBI 签名参数"""
    signer = WbiSigner()
    return signer.sign_params(params, sessdata)


def get_sign(params):
    """计算签名（旧版，已废弃，使用 WBI 签名）"""
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
        生成登录二维码（用于前端显示）

        Returns:
            dict: {'success': bool, 'qr_url': str, 'auth_code': str, 'qr_image': str, 'message': str}
        """
        try:
            # 使用旧的 MD5 签名（登录阶段不需要 WBI 签名）
            from .login import get_sign as login_get_sign
            
            params = {
                'appkey': APPKEY,
                'local_id': 0,
                'ts': int(time.time())
            }
            params['sign'] = login_get_sign(params)

            url = "https://passport.bilibili.com/x/passport-tv-login/qrcode/auth_code"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://www.bilibili.com/',
                'Origin': 'https://www.bilibili.com',
                'Accept': 'application/json, text/plain, */*',
                'Content-Type': 'application/x-www-form-urlencoded',
            }

            # 使用 params 作为 URL 参数（与 login.py 一致）
            response = requests.post(url, params=params, headers=headers, timeout=10)

            if response.status_code != 200:
                return {
                    'success': False,
                    'message': f'请求失败: {response.status_code}',
                    'qr_url': None,
                    'auth_code': None,
                    'qr_image': None
                }

            data = response.json()
            if data.get('code') != 0:
                return {
                    'success': False,
                    'message': f'API错误: {data.get("message")}',
                    'qr_url': None,
                    'auth_code': None,
                    'qr_image': None
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
                'qr_image': qr_image_base64,
                'message': '请使用B站APP扫描二维码'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'生成二维码失败: {str(e)}',
                'qr_url': None,
                'auth_code': None,
                'qr_image': None
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
            # 使用旧的 MD5 签名（登录阶段不需要 WBI 签名）
            from .login import get_sign as login_get_sign
            
            params = {
                'appkey': APPKEY,
                'local_id': 0,
                'ts': int(time.time()),
                'auth_code': auth_code
            }
            params['sign'] = login_get_sign(params)

            poll_url = "https://passport.bilibili.com/x/passport-tv-login/qrcode/poll"

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://www.bilibili.com/',
                'Accept': 'application/json, text/plain, */*',
            }

            # 使用 params 作为 URL 参数（与 login.py 一致）
            response = requests.post(poll_url, params=params, headers=headers, timeout=10)
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
                    'sessdata': sessdata,
                    'bili_jct': bili_jct,
                    'mid': data.get('mid')
                }

                # 保存到数据库（不保存 refresh_token）
                user = self._get_user()
                if user:
                    user.bilibili_mid = data.get('mid')
                    user.sessdata = sessdata
                    user.bili_jct = bili_jct
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
