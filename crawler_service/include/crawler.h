#pragma once
#include <string>
#include <stdexcept>
#include <mutex>
#include <vector>
#include "json.hpp"
#include "config.h"

using json = nlohmann::json;

// 412 专用异常
class AntiCrawlException : public std::runtime_error {
public:
    explicit AntiCrawlException(const std::string& msg) : std::runtime_error(msg) {}
};

class Crawler {
public:
    explicit Crawler(const Config& cfg);
    ~Crawler();

    json crawl_video(const std::string& bvid, const std::string& cookie);
    json crawl_comments(int64_t aid, const std::string& cookie);
    json crawl_danmaku(int64_t cid, const std::string& cookie);
    json crawl_audio_url(const std::string& bvid, int64_t cid, const std::string& cookie);

private:
    Config config_;

    // 当前代理 IP:Port，空字符串表示直连
    std::string current_proxy_;
    std::mutex proxy_mutex_;

    // 从代理池获取新代理，返回 "ip:port"
    std::string fetch_proxy();
    
    // 获取短效代理（备用）
    std::string fetch_short_proxy();
    
    // 加载/保存/删除已保存的独享代理
    std::vector<std::string> load_saved_proxies();
    void save_proxy(const std::string& proxy);
    void remove_failed_proxy(const std::string& proxy);
    
    // 短效代理相关
    std::vector<std::string> load_short_proxies();
    void remove_failed_short_proxy(const std::string& proxy);

    // 获取当前代理（线程安全）
    std::string get_proxy();

    // 412 时刷新代理
    void rotate_proxy();

    // 重置为直连模式（每个视频开始时调用）
    void reset_to_direct();

    // HTTP GET，自动挂代理
    std::string http_get(const std::string& url, const std::string& cookie);

    // 无代理的 HTTP GET（用于请求代理池 API 本身）
    std::string http_get_direct(const std::string& url);

    void random_delay();
    void backoff_delay(int retry);
};
