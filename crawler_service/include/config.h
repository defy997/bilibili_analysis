#pragma once
#include <string>

struct Config {
    int port = 8081;
    std::string user_agent =
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";
    std::string referer = "https://www.bilibili.com/";
    double min_delay = 8.0;  // 最小延迟（秒）
    double max_delay = 15.0;  // 最大延迟（秒）
    int max_retries = 3;

    // 隧道代理配置（固定地址，无需API获取）
    // 代理服务地址
    std::string proxy_server = "http://tun-oolotr.qg.net:14855";
    bool use_proxy = true;
    // 代理认证信息（HTTP Basic Auth）
    std::string proxy_user = "2D443FF0";  // Authkey
    std::string proxy_pass = "D7C4F61E0E54";  // Authpwd
    
    // 短效代理配置（备用）- 已禁用
    std::string short_proxy_pool_url = 
        "https://share.proxy.qg.net/get?key=86F2076D&num=5&area=&isp=0&format=txt&seq=\\r\\n&distinct=false";
    std::string short_proxy_user = "86F2076D";
    std::string short_proxy_pass = "8E053A5FB99D";
    
    // 是否启用短效代理（false=只用独享代理）
    bool enable_short_proxy = false;
    
    // 短效代理保存文件
    std::string short_proxy_file = "short_proxies.txt";
    
    // 独享代理保存文件
    std::string exclusive_proxy_file = "exclusive_proxies.txt";
    
    // Django API 服务器地址（用于获取SESSDATA）
    std::string django_api_url = "http://127.0.0.1:8000";
    std::string sessdata_api = "/api/crawler/sessdata/";
};

Config load_config();
