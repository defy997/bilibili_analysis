// welcome.js - 绑定事件，替代 inline script 来满足 CSP 要求
document.addEventListener('DOMContentLoaded', () => {
    // 页面动画
    const featureItems = document.querySelectorAll('.feature-item');
    featureItems.forEach((item, index) => {
        item.style.opacity = '0';
        item.style.transform = 'translateY(20px)';
        setTimeout(() => {
            item.style.transition = 'all 0.5s ease';
            item.style.opacity = '1';
            item.style.transform = 'translateY(0)';
        }, index * 100);
    });

    // 开始按钮
    const startBtn = document.getElementById('startBtn');
    if (startBtn) {
        startBtn.addEventListener('click', () => {
            try {
                window.open('https://www.bilibili.com', '_blank');
                window.close();
            } catch (err) {
                console.error('打开 B 站失败', err);
            }
        });
    }

    // 已移除 SESSDATA 授权逻辑
});


