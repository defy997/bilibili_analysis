#!/bin/bash
# MySQL 数据库连接修复脚本
# 用于解决 Navicat 等远程工具无法连接数据库的问题

echo "========================================="
echo "   MySQL 数据库连接修复工具"
echo "========================================="

# MySQL 配置信息
MYSQL_USER="root"
MYSQL_PASS="142857"
MYSQL_PORT="3306"

echo ""
echo "检查 MySQL 服务状态..."
systemctl status mysql 2>/dev/null | head -5 || service mysql status 2>/dev/null | head -5

echo ""
echo "========================================="
echo "正在修复数据库连接权限..."
echo "========================================="

# 尝试连接 MySQL 并修复权限
mysql -u${MYSQL_USER} -p${MYSQL_PASS} -e "
-- 允许 root 用户从任何主机连接
GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' IDENTIFIED BY '${MYSQL_PASS}' WITH GRANT OPTION;

-- 刷新权限
FLUSH PRIVILEGES;

-- 显示当前用户权限
SELECT User, Host FROM mysql.user WHERE User='root';
" 2>/dev/null

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ 权限修复成功！"
else
    echo ""
    echo "⚠️ 自动修复失败，尝试手动修复..."
    echo ""
    echo "请在服务器上执行以下命令："
    echo "----------------------------------------"
    echo "1. 登录 MySQL:"
    echo "   mysql -u root -p142857"
    echo ""
    echo "2. 执行以下 SQL:"
    echo "   GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' IDENTIFIED BY '142857' WITH GRANT OPTION;"
    echo "   FLUSH PRIVILEGES;"
    echo

echo ""
echo "----------------------------------------"
fi "========================================="
echo "检查 bind-address 配置..."
echo "========================================="

# 检查 MySQL 配置文件
if [ -f /etc/mysql/mysql.conf.d/mysqld.cnf ]; then
    CONF_FILE="/etc/mysql/mysql.conf.d/mysqld.cnf"
elif [ -f /etc/mysql/my.cnf ]; then
    CONF_FILE="/etc/mysql/my.cnf"
elif [ -f /etc/my.cnf ]; then
    CONF_FILE="/etc/my.cnf"
else
    CONF_FILE=""
fi

if [ -n "$CONF_FILE" ]; then
    echo "配置文件: $CONF_FILE"
    echo "当前 bind-address 设置:"
    grep -i "bind-address" $CONF_FILE 2>/dev/null || echo "  (未找到 bind-address 配置)"
    
    echo ""
    echo "如果显示 127.0.0.1，需要修改为 0.0.0.0"
    echo "修改命令: sudo sed -i 's/bind-address.*=.*127.0.0.1/bind-address=0.0.0.0/' $CONF_FILE"
else
    echo "未找到 MySQL 配置文件"
fi

echo ""
echo "========================================="
echo "检查防火墙状态..."
echo "========================================="

# 检查防火墙
if command -v ufw &> /dev/null; then
    echo "UFW 防火墙状态:"
    ufw status 2>/dev/null | head -5
    echo ""
    echo "如果防火墙开启，需要开放 3306 端口:"
    echo "  sudo ufw allow 3306/tcp"
fi

if command -v firewall-cmd &> /dev/null; then
    echo "Firewalld 防火墙状态:"
    firewall-cmd --list-all 2>/dev/null | head -5
    echo ""
    echo "如果防火墙开启，需要开放 3306 端口:"
    echo "  sudo firewall-cmd --add-port=3306/tcp --permanent"
    echo "  sudo firewall-cmd --reload"
fi

echo ""
echo "========================================="
echo "修复完成！"
echo "========================================="
echo ""
echo "如果仍无法连接，请尝试以下步骤："
echo "1. 重启 MySQL 服务: sudo systemctl restart mysql"
echo "2. 确保 MySQL 监听的地址是 0.0.0.0"
echo "3. 确保防火墙已开放 3306 端口"
echo ""
echo "Navicat 连接信息:"
echo "  主机: 118.25.39.91"
echo "  端口: 3306"
echo "  用户: root"
echo "  密码: 142857"
echo "========================================="
