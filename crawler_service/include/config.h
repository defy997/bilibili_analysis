#pragma once
#include <string>

struct Config {
    int port = 8081;
    std::string user_agent =
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";
    std::string referer = "https://www.bilibili.com/";
    double min_delay = 3.0;  // 最小延迟（秒）
    double max_delay = 8.0;  // 最大延迟（秒）
    int max_retries = 3;

    // 独享代理配置
    std::string proxy_pool_url =
        "https://exclusive.proxy.qg.net/replace?key=6A26857D&num=1&area=&isp=0&format=txt&seq=\\r\\n&distinct=false&keep_alive=1440";
    bool use_proxy = true;
    std::string proxy_user = "";  // 独享代理无需认证
    std::string proxy_pass = "";
};

Config load_config();
