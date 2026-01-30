#pragma once
#include <string>

struct Config {
    int port = 8081;
    std::string user_agent =
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";
    std::string referer = "https://www.bilibili.com/";
    double min_delay = 0.5;
    double max_delay = 1.5;
    int max_retries = 3;

    // 代理池配置
    std::string proxy_pool_url =
        "https://share.proxy.qg.net/get?key=86F2076D&num=1&area=&isp=0&format=txt&seq=\\r\\n&distinct=false";
    bool use_proxy = true;
    std::string proxy_user = "86F2076D";
    std::string proxy_pass = "8E053A5FB99D";
};

Config load_config();
