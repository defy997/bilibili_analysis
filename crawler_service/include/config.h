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

    // 独享代理配置
    std::string proxy_pool_url =
        "https://exclusive.proxy.qg.net/replace?key=6A26857D&num=1&area=&isp=0&format=txt&seq=\\r\\n&distinct=false&keep_alive=1440";
    bool use_proxy = true;
    std::string proxy_user = "6A26857D";  // 独享代理key作为用户名
    std::string proxy_pass = "A86FED6E742B";
    
    // 短效代理配置（备用）
    std::string short_proxy_pool_url = 
        "https://share.proxy.qg.net/get?key=86F2076D&num=5&area=&isp=0&format=txt&seq=\\r\\n&distinct=false";
    std::string short_proxy_user = "86F2076D";
    std::string short_proxy_pass = "8E053A5FB99D";
    
    // 短效代理保存文件
    std::string short_proxy_file = "short_proxies.txt";
    
    // 独享代理保存文件
    std::string exclusive_proxy_file = "exclusive_proxies.txt";
    
    // Django API 服务器地址（用于获取SESSDATA）
    std::string django_api_url = "http://127.0.0.1:8000";
    std::string sessdata_api = "/api/crawler/sessdata/";
};

Config load_config();
