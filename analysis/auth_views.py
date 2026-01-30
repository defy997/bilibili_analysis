"""
用户认证相关视图
注册、登录、验证码
"""

import json
import re
import hashlib
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from .models import User
from .email_utils import send_verification_code, verify_code


def validate_password(password):
    """
    验证密码强度
    要求：至少8位，包含字母
    """
    if len(password) < 8:
        return False, "密码至少需要8位"

    if not re.search(r'[a-zA-Z]', password):
        return False, "密码必须包含字母"

    return True, ""


def hash_password(password):
    """对密码进行哈希"""
    return hashlib.sha256(password.encode()).hexdigest()


@csrf_exempt
def send_code(request):
    """发送验证码"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = data.get('email', '').strip()
            purpose = data.get('purpose', 'register')

            if not email:
                return JsonResponse({
                    'success': False,
                    'message': '请输入邮箱地址'
                })

            # 验证邮箱格式
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, email):
                return JsonResponse({
                    'success': False,
                    'message': '邮箱格式不正确'
                })

            # 如果是注册，检查邮箱是否已注册
            if purpose == 'register':
                if User.objects.filter(email=email).exists():
                    return JsonResponse({
                        'success': False,
                        'message': '该邮箱已被注册'
                    })

            # 发送验证码
            result = send_verification_code(email, purpose)

            return JsonResponse(result)

        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'发送失败: {str(e)}'
            }, status=500)

    return JsonResponse({
        'success': False,
        'message': '仅支持 POST 请求'
    }, status=405)


@csrf_exempt
def register(request):
    """用户注册"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            username = data.get('username', '').strip()
            email = data.get('email', '').strip()
            password = data.get('password', '')
            code = data.get('code', '').strip()

            # 验证必填字段
            if not all([username, email, password, code]):
                return JsonResponse({
                    'success': False,
                    'message': '请填写所有必填字段'
                })

            # 验证用户名长度
            if len(username) < 3 or len(username) > 20:
                return JsonResponse({
                    'success': False,
                    'message': '用户名长度应为3-20个字符'
                })

            # 验证用户名格式（只允许字母、数字、下划线）
            if not re.match(r'^[a-zA-Z0-9_]+$', username):
                return JsonResponse({
                    'success': False,
                    'message': '用户名只能包含字母、数字和下划线'
                })

            # 检查用户名是否已存在
            if User.objects.filter(username=username).exists():
                return JsonResponse({
                    'success': False,
                    'message': '用户名已被使用'
                })

            # 检查邮箱是否已注册
            if User.objects.filter(email=email).exists():
                return JsonResponse({
                    'success': False,
                    'message': '该邮箱已被注册'
                })

            # 验证密码强度
            valid, message = validate_password(password)
            if not valid:
                return JsonResponse({
                    'success': False,
                    'message': message
                })

            # 验证邮箱验证码
            verification_result = verify_code(email, code, 'register')
            if not verification_result['valid']:
                return JsonResponse({
                    'success': False,
                    'message': verification_result['message']
                })

            # 创建用户
            user = User.objects.create(
                username=username,
                email=email,
                password=hash_password(password)
            )

            return JsonResponse({
                'success': True,
                'message': '注册成功',
                'data': {
                    'user_id': user.id,
                    'username': user.username
                }
            })

        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'注册失败: {str(e)}'
            }, status=500)

    return JsonResponse({
        'success': False,
        'message': '仅支持 POST 请求'
    }, status=405)


@csrf_exempt
def login(request):
    """用户登录"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            username_or_email = data.get('username', '').strip()
            password = data.get('password', '')

            if not all([username_or_email, password]):
                return JsonResponse({
                    'success': False,
                    'message': '请输入用户名/邮箱和密码'
                })

            # 查找用户（支持用户名或邮箱登录）
            user = User.objects.filter(
                username=username_or_email
            ).first() or User.objects.filter(
                email=username_or_email
            ).first()

            if not user:
                return JsonResponse({
                    'success': False,
                    'message': '用户名或密码错误'
                })

            # 验证密码
            if user.password != hash_password(password):
                return JsonResponse({
                    'success': False,
                    'message': '用户名或密码错误'
                })

            # 检查账号是否激活
            if not user.is_active:
                return JsonResponse({
                    'success': False,
                    'message': '账号已被禁用'
                })

            # 更新最后登录时间
            user.last_login = timezone.now()
            user.save()

            # 设置会话
            request.session['user_id'] = user.id
            request.session['username'] = user.username

            return JsonResponse({
                'success': True,
                'message': '登录成功',
                'data': {
                    'user_id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'config': user.get_config()  # 返回用户配置
                }
            })

        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'登录失败: {str(e)}'
            }, status=500)

    return JsonResponse({
        'success': False,
        'message': '仅支持 POST 请求'
    }, status=405)


@csrf_exempt
def logout(request):
    """用户登出"""
    try:
        request.session.flush()
        return JsonResponse({
            'success': True,
            'message': '登出成功'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'登出失败: {str(e)}'
        }, status=500)


def check_login(request):
    """检查登录状态"""
    user_id = request.session.get('user_id')
    if user_id:
        try:
            user = User.objects.get(id=user_id)
            return JsonResponse({
                'success': True,
                'logged_in': True,
                'data': {
                    'user_id': user.id,
                    'username': user.username,
                    'email': user.email
                }
            })
        except User.DoesNotExist:
            return JsonResponse({
                'success': True,
                'logged_in': False
            })
    else:
        return JsonResponse({
            'success': True,
            'logged_in': False
        })
