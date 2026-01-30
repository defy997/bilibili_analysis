"""
邮箱工具模块
发送验证码邮件
"""

import random
import string
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from .models import EmailVerificationCode


def generate_code(length=6):
    """生成随机验证码"""
    return ''.join(random.choices(string.digits, k=length))


def send_verification_code(email, purpose='register'):
    """
    发送验证码到邮箱

    Args:
        email: 邮箱地址
        purpose: 用途 (register/reset_password)

    Returns:
        dict: {'success': bool, 'message': str, 'code': str (仅测试环境)}
    """
    try:
        # 生成6位数字验证码
        code = generate_code(6)

        # 设置过期时间（5分钟）
        expires_at = timezone.now() + timedelta(minutes=5)

        # 保存验证码到数据库
        EmailVerificationCode.objects.create(
            email=email,
            code=code,
            purpose=purpose,
            expires_at=expires_at
        )

        # 邮件主题和内容
        if purpose == 'register':
            subject = 'BiliMood - 注册验证码'
            message = f'''
您好！

您正在注册 BiliMood 账号，验证码为：

{code}

验证码有效期为 5 分钟，请尽快完成注册。

如果这不是您的操作，请忽略此邮件。

---
BiliMood Team
            '''
        else:
            subject = 'BiliMood - 密码重置验证码'
            message = f'''
您好！

您正在重置 BiliMood 账号密码，验证码为：

{code}

验证码有效期为 5 分钟。

如果这不是您的操作，请忽略此邮件。

---
BiliMood Team
            '''

        # 发送邮件
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )

        # 开发环境下返回验证码（生产环境删除）
        if settings.DEBUG:
            return {
                'success': True,
                'message': '验证码已发送',
                'code': code  # 仅用于测试
            }
        else:
            return {
                'success': True,
                'message': '验证码已发送到您的邮箱'
            }

    except Exception as e:
        return {
            'success': False,
            'message': f'发送失败: {str(e)}'
        }


def verify_code(email, code, purpose='register'):
    """
    验证验证码是否正确

    Args:
        email: 邮箱地址
        code: 验证码
        purpose: 用途

    Returns:
        dict: {'valid': bool, 'message': str}
    """
    try:
        # 查找最新的未使用验证码
        verification = EmailVerificationCode.objects.filter(
            email=email,
            code=code,
            purpose=purpose,
            is_used=False
        ).order_by('-created_at').first()

        if not verification:
            return {'valid': False, 'message': '验证码错误'}

        if not verification.is_valid():
            return {'valid': False, 'message': '验证码已过期'}

        # 标记为已使用
        verification.is_used = True
        verification.save()

        return {'valid': True, 'message': '验证成功'}

    except Exception as e:
        return {'valid': False, 'message': f'验证失败: {str(e)}'}
