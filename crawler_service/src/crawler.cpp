#include "crawler.h"
#include "wbi_signer.h"
#include "pugixml.hpp"
#include <curl/curl.h>
#include <random>
#include <thread>
#include <chrono>
#include <iostream>
#include <sstream>
#include <algorithm>
#include <fstream>

// libcurl write callback
static size_t write_callback(char* ptr, size_t size, size_t nmemb, void* userdata) {
    auto* buf = static_cast<std::string*>(userdata);
    buf->append(ptr, size * nmemb);
    return size * nmemb;
}

Crawler::Crawler(const Config& cfg) : config_(cfg), current_proxy_(""), current_proxy_type_("") {
    curl_global_init(CURL_GLOBAL_DEFAULT);
    
    // 配置 WBI 签名的 SESSDATA API
    WbiSigner& wbi = WbiSigner::get_instance();
    std::string full_api_url = config_.django_api_url + config_.sessdata_api;
    wbi.set_sessdata_api(config_.django_api_url, config_.sessdata_api);
    std::cout << "[Crawler] WBI SESSDATA API: " << full_api_url << std::endl;
    
    // 启动时用本地 IP，412 后再切代理池
    std::cout << "Starting with local IP (proxy on standby)" << std::endl;
}

Crawler::~Crawler() {
    curl_global_cleanup();
}

// ============================================================
// 代理池
// ============================================================

std::string Crawler::http_get_direct(const std::string& url) {
    CURL* curl = curl_easy_init();
    if (!curl) throw std::runtime_error("curl init failed");

    std::string response;
    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 10L);
    curl_easy_setopt(curl, CURLOPT_NOPROXY, "*");
    curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 0L);  // 代理池 API 不验证
    curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);

    CURLcode res = curl_easy_perform(curl);
    curl_easy_cleanup(curl);

    if (res != CURLE_OK) {
        throw std::runtime_error(std::string("proxy pool request failed: ") + curl_easy_strerror(res));
    }
    return response;
}

// 加载已保存的独享代理列表
std::vector<std::string> Crawler::load_saved_proxies() {
    std::vector<std::string> proxies;
    std::ifstream file(config_.exclusive_proxy_file);
    if (file.is_open()) {
        std::string line;
        while (std::getline(file, line)) {
            if (!line.empty() && line[0] != '#') {
                // 去除注释和空白
                size_t pos = line.find('#');
                if (pos != std::string::npos) line = line.substr(0, pos);
                size_t start = line.find_first_not_of(" \t\r\n");
                size_t end = line.find_last_not_of(" \t\r\n");
                if (start != std::string::npos) {
                    line = line.substr(start, end - start + 1);
                    if (!line.empty()) proxies.push_back(line);
                }
            }
        }
        file.close();
    }
    return proxies;
}

// 保存独享代理到文件
void Crawler::save_proxy(const std::string& proxy) {
    std::ofstream file(config_.exclusive_proxy_file, std::ios::app);
    if (file.is_open()) {
        file << proxy << "\n";
        file.close();
        std::cout << "[Proxy] Saved exclusive proxy: " << proxy << std::endl;
    }
}

// 删除失效的独享代理
void Crawler::remove_failed_proxy(const std::string& proxy) {
    auto proxies = load_saved_proxies();
    std::ofstream file(config_.exclusive_proxy_file);
    if (file.is_open()) {
        for (const auto& p : proxies) {
            if (p != proxy) {
                file << p << "\n";
            }
        }
        file.close();
        std::cout << "[Proxy] Removed failed exclusive proxy: " << proxy << std::endl;
    }
}

// 加载已保存的短效代理列表
std::vector<std::string> Crawler::load_short_proxies() {
    std::vector<std::string> proxies;
    std::ifstream file(config_.short_proxy_file);
    if (file.is_open()) {
        std::string line;
        while (std::getline(file, line)) {
            if (!line.empty() && line[0] != '#') {
                size_t pos = line.find('#');
                if (pos != std::string::npos) line = line.substr(0, pos);
                size_t start = line.find_first_not_of(" \t\r\n");
                size_t end = line.find_last_not_of(" \t\r\n");
                if (start != std::string::npos) {
                    line = line.substr(start, end - start + 1);
                    if (!line.empty()) proxies.push_back(line);
                }
            }
        }
        file.close();
    }
    return proxies;
}

// 删除失效的短效代理
void Crawler::remove_failed_short_proxy(const std::string& proxy) {
    auto proxies = load_short_proxies();
    std::ofstream file(config_.short_proxy_file);
    if (file.is_open()) {
        for (const auto& p : proxies) {
            if (p != proxy) {
                file << p << "\n";
            }
        }
        file.close();
        std::cout << "[Proxy] Removed failed short proxy: " << proxy << std::endl;
    }
}

// 尝试获取短效代理（备用）- 支持多个代理
std::string Crawler::fetch_short_proxy() {
    std::string body = http_get_direct(config_.short_proxy_pool_url);
    
    auto trim = [](std::string& s) {
        size_t start = s.find_first_not_of(" \t\r\n");
        size_t end = s.find_last_not_of(" \t\r\n");
        if (start == std::string::npos) { s.clear(); return; }
        s = s.substr(start, end - start + 1);
    };
    trim(body);
    
    if (body.empty()) {
        throw std::runtime_error("Short proxy returned empty");
    }
    
    std::vector<std::string> proxies;
    
    // 如果是JSON格式，解析获取多个proxy
    if (body[0] == '{') {
        try {
            json j = json::parse(body);
            if (j.contains("data") && j["data"].contains("ips") && 
                !j["data"]["ips"].empty()) {
                for (const auto& ip : j["data"]["ips"]) {
                    std::string proxy = ip.contains("server") ? ip["server"].get<std::string>() : "";
                    if (!proxy.empty()) {
                        proxies.push_back(proxy);
                    }
                }
                std::cout << "[Fallback] Parsed " << proxies.size() << " short proxies from JSON" << std::endl;
            }
            
            if (proxies.empty()) {
                throw std::runtime_error("JSON missing ips field");
            }
            
            // 保存到文件
            std::ofstream file(config_.short_proxy_file);
            if (file.is_open()) {
                for (const auto& p : proxies) {
                    file << p << "\n";
                }
                file.close();
                std::cout << "[Fallback] Saved " << proxies.size() << " short proxies to " << config_.short_proxy_file << std::endl;
            }
            
            // 返回第一个
            std::cout << "[Fallback] Using short proxy: " << proxies[0] << std::endl;
            return proxies[0];
            
        } catch (const json::exception& e) {
            throw std::runtime_error("Failed to parse short proxy JSON: " + std::string(e.what()));
        }
    }
    
    // 原有纯文本格式 - 可能返回多个（用换行分隔）
    if (body[0] == '{' || body[0] == '<') {
        throw std::runtime_error("Short proxy returned error: " + body.substr(0, 200));
    }
    
    // 尝试解析多行格式
    std::istringstream iss(body);
    std::string line;
    while (std::getline(iss, line)) {
        trim(line);
        if (!line.empty() && line.find(':') != std::string::npos) {
            if (std::isdigit(static_cast<unsigned char>(line[0]))) {
                proxies.push_back(line);
            }
        }
    }
    
    if (proxies.empty()) {
        throw std::runtime_error("Invalid short proxy format: " + body.substr(0, 100));
    }
    
    // 保存到文件
    std::ofstream file(config_.short_proxy_file);
    if (file.is_open()) {
        for (const auto& p : proxies) {
            file << p << "\n";
        }
        file.close();
    }
    
    std::cout << "[Fallback] Fetched " << proxies.size() << " short proxies" << std::endl;
    return proxies[0];
}

std::string Crawler::fetch_proxy() {
    // 1. 先尝试加载已保存的独享代理
    auto saved_proxies = load_saved_proxies();
    if (!saved_proxies.empty()) {
        // 随机选择一个
        std::random_device rd;
        std::mt19937 gen(rd());
        std::uniform_int_distribution<> dis(0, saved_proxies.size() - 1);
        std::string proxy = saved_proxies[dis(gen)];
        std::cout << "[Proxy] Using saved exclusive proxy: " << proxy << std::endl;
        return proxy;
    }
    
    // 2. 获取新的独享代理
    try {
        std::string body = http_get_direct(config_.proxy_pool_url);

        // 去除首尾空白和换行
        auto trim = [](std::string& s) {
            size_t start = s.find_first_not_of(" \t\r\n");
            size_t end = s.find_last_not_of(" \t\r\n");
            if (start == std::string::npos) { s.clear(); return; }
            s = s.substr(start, end - start + 1);
        };
        trim(body);

        // 检查是否是JSON格式
        if (!body.empty() && body[0] == '{') {
            try {
                json j = json::parse(body);
                // 检查是否是错误响应
                if (j.contains("code")) {
                    int code = j["code"].get<int>();
                    if (code != 0 && code != 200) {
                        std::string msg = j.contains("message") ? j["message"].get<std::string>() : "unknown";
                        if (msg.find("DELETE_LIMIT_EXCEEDED") != std::string::npos) {
                            std::cout << "[Proxy] Exclusive proxy rate limited, trying short proxy..." << std::endl;
                            return fetch_short_proxy();
                        }
                        throw std::runtime_error("Proxy API error: " + msg);
                    }
                }
                // 解析JSON获取代理
                if (j.contains("data") && j["data"].contains("ips") && 
                    !j["data"]["ips"].empty()) {
                    std::string proxy = j["data"]["ips"][0]["server"];
                    std::cout << "Fetched exclusive proxy (JSON): " << proxy << std::endl;
                    save_proxy(proxy);
                    return proxy;
                }
                throw std::runtime_error("JSON missing ips field: " + body.substr(0, 100));
            } catch (const json::exception& e) {
                throw std::runtime_error("Failed to parse proxy JSON: " + std::string(e.what()));
            }
        }

        // 原有纯文本格式处理
        if (body.empty() || body[0] == '<') {
            throw std::runtime_error("Proxy pool returned error: " + body.substr(0, 200));
        }

        // 简单校验 ip:port 格式
        auto colon_pos = body.find(':');
        if (colon_pos == std::string::npos || colon_pos == 0 || colon_pos == body.size() - 1) {
            throw std::runtime_error("Invalid proxy format: " + body.substr(0, 100));
        }

        // 检查冒号前是否像 IP（以数字开头）
        if (!std::isdigit(static_cast<unsigned char>(body[0]))) {
            throw std::runtime_error("Proxy pool returned non-IP: " + body.substr(0, 100));
        }

        std::cout << "Fetched exclusive proxy: " << body << std::endl;
        
        // 保存到文件
        save_proxy(body);
        
        return body;  // "ip:port"
    } catch (const std::exception& e) {
        std::string err_msg = e.what();
        // 如果是限速错误，尝试短效代理
        if (err_msg.find("DELETE_LIMIT_EXCEEDED") != std::string::npos || 
            err_msg.find("rate limited") != std::string::npos) {
            std::cout << "[Proxy] Exclusive proxy failed: " << err_msg << std::endl;
            std::cout << "[Proxy] Trying short proxy as fallback..." << std::endl;
            try {
                return fetch_short_proxy();
            } catch (...) {
                throw std::runtime_error("Both exclusive and short proxy failed");
            }
        }
        throw;
    }
}

std::string Crawler::get_proxy() {
    std::lock_guard<std::mutex> lock(proxy_mutex_);
    return current_proxy_;
}

void Crawler::rotate_proxy() {
    std::lock_guard<std::mutex> lock(proxy_mutex_);
    
    // 如果当前代理失效，先从保存的列表中移除
    if (!current_proxy_.empty()) {
        std::cout << "[Proxy] Removing failed proxy: " << current_proxy_ << std::endl;
        // 判断是独享代理还是短效代理
        auto saved_exclusive = load_saved_proxies();
        bool is_exclusive = false;
        for (const auto& p : saved_exclusive) {
            if (p == current_proxy_) {
                is_exclusive = true;
                break;
            }
        }
        
        if (is_exclusive) {
            remove_failed_proxy(current_proxy_);
        } else {
            remove_failed_short_proxy(current_proxy_);
        }
    }

    // 1. 尝试从已保存的短效代理中获取
    auto short_proxies = load_short_proxies();
    if (!short_proxies.empty()) {
        std::random_device rd;
        std::mt19937 gen(rd());
        std::uniform_int_distribution<> dis(0, short_proxies.size() - 1);
        std::string new_proxy = short_proxies[dis(gen)];
        current_proxy_ = new_proxy;
        current_proxy_type_ = "short";  // 短效代理
        std::cout << "[Proxy] Switched to saved short proxy: " << current_proxy_ << std::endl;
        return;
    }
    
    // 2. 获取新的短效代理
    try {
        std::string new_proxy = fetch_short_proxy();
        current_proxy_ = new_proxy;
        current_proxy_type_ = "short";  // 短效代理
        std::cout << "[Proxy] Switched to new short proxy: " << current_proxy_ << std::endl;
        return;
    } catch (const std::exception& e) {
        std::cout << "[Proxy] Failed to get short proxy: " << e.what() << std::endl;
    }
    
    // 3. 尝试独享代理
    try {
        std::string new_proxy = fetch_proxy();
        current_proxy_ = new_proxy;
        current_proxy_type_ = "exclusive";  // 独享代理
        std::cout << "[Proxy] Switched to exclusive proxy: " << current_proxy_ << std::endl;
    } catch (const std::exception& e) {
        std::cout << "[Proxy] All proxy methods failed: " << e.what() << ", staying on local IP" << std::endl;
        current_proxy_.clear();  // 切换回直连
        current_proxy_type_.clear();
    }
}

void Crawler::reset_to_direct() {
    std::lock_guard<std::mutex> lock(proxy_mutex_);
    if (!current_proxy_.empty()) {
        std::cout << "[Reset] Video finished, resetting to direct connection" << std::endl;
        current_proxy_.clear();
        current_proxy_type_.clear();
    }
}

// ============================================================
// HTTP 请求（自动挂代理）
// ============================================================

std::string Crawler::http_get(const std::string& url, const std::string& cookie) {
    CURL* curl = curl_easy_init();
    if (!curl) {
        throw std::runtime_error("Failed to init curl");
    }

    std::string response;

    // B站要求的请求头
    struct curl_slist* headers = nullptr;
    headers = curl_slist_append(headers, "authority: api.bilibili.com");
    headers = curl_slist_append(headers, "accept: application/json, text/plain, */*");
    headers = curl_slist_append(headers, "accept-language: zh-CN,zh;q=0.9");
    headers = curl_slist_append(headers, "origin: https://www.bilibili.com");
    headers = curl_slist_append(headers, "sec-fetch-dest: empty");
    headers = curl_slist_append(headers, "sec-fetch-mode: cors");
    headers = curl_slist_append(headers, "sec-fetch-site: same-site");
    // 设备指纹（关键！）
    headers = curl_slist_append(headers, "buvid3: XY1234567890ABCDEF");
    std::string ua_header = "user-agent: " + config_.user_agent;
    headers = curl_slist_append(headers, ua_header.c_str());
    std::string ref_header = "referer: " + config_.referer;
    headers = curl_slist_append(headers, ref_header.c_str());

    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response);
    curl_easy_setopt(curl, CURLOPT_ACCEPT_ENCODING, "");  // 自动解压 deflate/gzip
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 15L);
    curl_easy_setopt(curl, CURLOPT_TCP_KEEPALIVE, 1L);
    curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);

    // 禁用环境变量代理
    curl_easy_setopt(curl, CURLOPT_NOPROXY, "*");

    // 挂代理池的代理（根据代理类型使用不同账密）
    std::string proxy = get_proxy();
    if (!proxy.empty()) {
        std::string proxy_url = "http://" + proxy;
        curl_easy_setopt(curl, CURLOPT_PROXY, proxy_url.c_str());
        
        // 根据代理类型选择正确的账密
        if (current_proxy_type_ == "short") {
            // 短效代理
            if (!config_.short_proxy_user.empty()) {
                std::string auth = config_.short_proxy_user + ":" + config_.short_proxy_pass;
                curl_easy_setopt(curl, CURLOPT_PROXYUSERPWD, auth.c_str());
            }
        } else {
            // 独享代理或其他
            if (!config_.proxy_user.empty()) {
                std::string auth = config_.proxy_user + ":" + config_.proxy_pass;
                curl_easy_setopt(curl, CURLOPT_PROXYUSERPWD, auth.c_str());
            }
        }
    }

    if (!cookie.empty()) {
        curl_easy_setopt(curl, CURLOPT_COOKIE, cookie.c_str());
    }

    if (!proxy.empty()) {
        // 通过代理隧道时放宽 SSL 校验
        curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 0L);
        curl_easy_setopt(curl, CURLOPT_SSL_VERIFYHOST, 0L);
        curl_easy_setopt(curl, CURLOPT_HTTPPROXYTUNNEL, 1L);
    } else {
        curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 1L);
        curl_easy_setopt(curl, CURLOPT_SSL_VERIFYHOST, 2L);
    }

    CURLcode res = curl_easy_perform(curl);

    long http_code = 0;
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);

    curl_slist_free_all(headers);
    curl_easy_cleanup(curl);

    if (res != CURLE_OK) {
        throw std::runtime_error(std::string("curl error: ") + curl_easy_strerror(res));
    }

    if (http_code == 412) {
        throw AntiCrawlException("HTTP 412");
    }
    if (http_code != 200) {
        throw std::runtime_error("HTTP " + std::to_string(http_code));
    }

    return response;
}

// ============================================================
// 工具函数
// ============================================================

void Crawler::random_delay() {
    static thread_local std::mt19937 rng(std::random_device{}());
    std::uniform_real_distribution<double> dist(config_.min_delay, config_.max_delay);
    double seconds = dist(rng);
    std::this_thread::sleep_for(
        std::chrono::milliseconds(static_cast<int>(seconds * 1000)));
}

void Crawler::backoff_delay(int retry) {
    static thread_local std::mt19937 rng(std::random_device{}());
    std::uniform_real_distribution<double> jitter(1.0, 3.0);
    double seconds = (retry + 1) * 5.0 + jitter(rng);
    std::this_thread::sleep_for(
        std::chrono::milliseconds(static_cast<int>(seconds * 1000)));
}

// ============================================================
// 爬取：视频信息
// ============================================================

json Crawler::crawl_video(const std::string& bvid, const std::string& cookie) {
    // 每个视频开始时重置为直连模式
    reset_to_direct();

    // Wbi 签名
    WbiSigner& wbi = WbiSigner::get_instance();
    wbi.init();

    std::map<std::string, std::string> params;
    params["bvid"] = bvid;

    auto signed_params = wbi.sign_params(params);
    std::string query = WbiSigner::map_to_query(signed_params);

    std::string url = "https://api.bilibili.com/x/web-interface/view?" + query;
    std::string body = http_get(url, cookie);
    json resp = json::parse(body);

    if (resp["code"].get<int>() != 0) {
        std::string msg = resp.value("message", "unknown error");
        throw std::runtime_error("Video API error: " + msg);
    }

    auto& d = resp["data"];
    auto& stat = d["stat"];

    json result;
    result["aid"] = d["aid"];
    result["cid"] = d["cid"];
    result["title"] = d["title"];
    result["pubdate_ts"] = d.value("pubdate", 0);
    result["reply_count"] = stat.value("reply", 0);
    // 新增：视频统计数据
    result["view"] = stat.value("view", 0);
    result["like"] = stat.value("like", 0);
    result["coin"] = stat.value("coin", 0);
    result["favorite"] = stat.value("favorite", 0);
    result["share"] = stat.value("share", 0);
    return result;
}

// ============================================================
// 爬取：评论（412 时换代理继续）
// ============================================================

json Crawler::crawl_comments(int64_t aid, const std::string& cookie) {
    // 每个视频开始时重置为直连模式
    reset_to_direct();

    // Wbi 签名
    WbiSigner& wbi = WbiSigner::get_instance();
    wbi.init();

    json all_comments = json::array();
    int64_t next_cursor = 0;
    int page = 0;
    int anti_crawl_hits = 0;
    const int max_anti_crawl = 5;  // 代理池模式下可以多试几次

    while (true) {
        page++;

        // Wbi 签名参数
        std::map<std::string, std::string> params;
        params["type"] = "1";
        params["oid"] = std::to_string(aid);
        params["mode"] = "3";
        params["next"] = std::to_string(next_cursor);

        auto signed_params = wbi.sign_params(params);
        std::string query = WbiSigner::map_to_query(signed_params);

        std::string url = "https://api.bilibili.com/x/v2/reply/main?" + query;

        for (int retry = 0; retry < config_.max_retries; retry++) {
            try {
                std::string body = http_get(url, cookie);
                json resp = json::parse(body);

                if (resp["code"].get<int>() != 0) {
                    std::cout << "Comment API error code: " << resp["code"] << std::endl;
                    json result;
                    result["total"] = all_comments.size();
                    result["data"] = all_comments;
                    return result;
                }

                auto& data = resp["data"];
                auto replies = data.value("replies", json::array());
                if (replies.is_null() || replies.empty()) {
                    std::cout << "Comments done: " << all_comments.size() << " total" << std::endl;
                    json result;
                    result["total"] = all_comments.size();
                    result["data"] = all_comments;
                    return result;
                }

                for (auto& r : replies) {
                    json comment;
                    comment["rpid"] = r["rpid"];
                    comment["mid"] = r.value("mid", 0);
                    comment["parent"] = r.value("parent", 0);
                    comment["like"] = r.value("like", 0);
                    comment["rcount"] = r.value("rcount", 0);
                    comment["ctime"] = r.value("ctime", 0);
                    comment["uname"] = r.value("member", json::object())
                                        .value("uname", "");
                    comment["message"] = r.value("content", json::object())
                                          .value("message", "");
                    auto member = r.value("member", json::object());
                    auto vip = member.value("vip", json::object());
                    comment["vip_type"] = vip.value("vipType", 0);
                    comment["vip_label"] = vip.value("label", json::object())
                                            .value("text", "");
                    // 提取用户等级
                    comment["user_level"] = member.value("level", 0);
                    auto reply_ctrl = r.value("reply_control", json::object());
                    comment["location"] = reply_ctrl.value("location", "");
                    all_comments.push_back(std::move(comment));
                }

                auto cursor = data.value("cursor", json::object());
                bool is_end = cursor.value("is_end", true);
                next_cursor = cursor.value("next", 0);

                std::cout << "Page " << page << ": " << replies.size()
                          << " comments, total " << all_comments.size() << std::endl;

                if (is_end) {
                    json result;
                    result["total"] = all_comments.size();
                    result["data"] = all_comments;
                    return result;
                }

                // 成功后重置 412 计数
                anti_crawl_hits = 0;
                random_delay();
                break;  // 当前页成功，进入下一页

            } catch (const AntiCrawlException&) {
                anti_crawl_hits++;
                std::cout << "Page " << page << " -> 412 (" << anti_crawl_hits
                          << "/" << max_anti_crawl << "), keeping current proxy..." << std::endl;

                // 失败3次再换代理，避免频繁切换
                if (anti_crawl_hits >= 3) {
                    rotate_proxy();
                    std::cout << "Too many 412s, switching proxy..." << std::endl;
                }

                if (anti_crawl_hits >= max_anti_crawl) {
                    std::cout << "Max 412s reached, returning " << all_comments.size()
                              << " comments" << std::endl;
                    json result;
                    result["total"] = all_comments.size();
                    result["data"] = all_comments;
                    return result;
                }

                // 换完代理等 3 秒再试
                std::this_thread::sleep_for(std::chrono::seconds(3));
                retry--;  // 不消耗 retry 次数
                continue;

            } catch (const std::exception& e) {
                std::cout << "Page " << page << " error (retry "
                          << (retry + 1) << "/" << config_.max_retries << "): "
                          << e.what() << std::endl;
                if (retry < config_.max_retries - 1) {
                    backoff_delay(retry);
                } else {
                    std::cout << "Retries exhausted, got " << all_comments.size()
                              << " comments" << std::endl;
                    json result;
                    result["total"] = all_comments.size();
                    result["data"] = all_comments;
                    return result;
                }
            }
        }
    }

    json result;
    result["total"] = all_comments.size();
    result["data"] = all_comments;
    return result;
}

// ============================================================
// 爬取：音频流URL
// ============================================================

json Crawler::crawl_audio_url(const std::string& bvid, int64_t cid, const std::string& cookie) {
    // 每个视频开始时重置为直连模式
    reset_to_direct();

    // Wbi 签名
    WbiSigner& wbi = WbiSigner::get_instance();
    wbi.init();

    std::map<std::string, std::string> params;
    params["bvid"] = bvid;
    params["cid"] = std::to_string(cid);
    params["fnval"] = "16";
    params["fnver"] = "0";
    params["fourk"] = "1";

    auto signed_params = wbi.sign_params(params);
    std::string query = WbiSigner::map_to_query(signed_params);

    std::string url = "https://api.bilibili.com/x/player/playurl?" + query;
    std::string body = http_get(url, cookie);
    json resp = json::parse(body);

    if (resp["code"].get<int>() != 0) {
        std::string msg = resp.value("message", "unknown error");
        throw std::runtime_error("playurl API error: " + msg);
    }

    auto& dash = resp["data"]["dash"];
    auto& audio_list = dash["audio"];

    if (!audio_list.is_array() || audio_list.empty()) {
        throw std::runtime_error("No audio streams found");
    }

    // Find highest bandwidth audio
    int best_idx = 0;
    int64_t best_bw = 0;
    for (size_t i = 0; i < audio_list.size(); i++) {
        int64_t bw = audio_list[i].value("bandwidth", (int64_t)0);
        if (bw > best_bw) {
            best_bw = bw;
            best_idx = static_cast<int>(i);
        }
    }

    auto& best = audio_list[best_idx];
    json result;
    result["audio_url"] = best.value("baseUrl", "");
    result["codec"] = best.value("codecs", "");
    result["bandwidth"] = best.value("bandwidth", 0);
    return result;
}

// ============================================================
// 爬取：弹幕
// ============================================================

json Crawler::crawl_danmaku(int64_t cid, const std::string& cookie) {
    // 每个视频开始时重置为直连模式
    reset_to_direct();

    json danmaku_list = json::array();

    try {
        std::string url = "https://api.bilibili.com/x/v1/dm/list.so?oid=" + std::to_string(cid);

        std::string body;
        for (int attempt = 0; attempt < 3; attempt++) {
            try {
                body = http_get(url, cookie);
                break;
            } catch (const AntiCrawlException&) {
                std::cout << "Danmaku 412, rotating proxy..." << std::endl;
                rotate_proxy();
                std::this_thread::sleep_for(std::chrono::seconds(2));
                if (attempt == 2) {
                    json result;
                    result["total"] = 0;
                    result["data"] = danmaku_list;
                    return result;
                }
            }
        }

        pugi::xml_document doc;
        pugi::xml_parse_result parse_result = doc.load_buffer(body.data(), body.size());

        if (!parse_result) {
            std::cout << "XML parse error: " << parse_result.description() << std::endl;
            json result;
            result["total"] = 0;
            result["data"] = danmaku_list;
            return result;
        }

        for (auto node : doc.child("i").children("d")) {
            std::string text = node.child_value();
            size_t start = text.find_first_not_of(" \t\n\r");
            size_t end = text.find_last_not_of(" \t\n\r");
            if (start != std::string::npos && end != std::string::npos) {
                std::string trimmed = text.substr(start, end - start + 1);
                if (!trimmed.empty()) {
                    // 从 p 属性中提取时间信息
                    // p 格式: "时间,模式,字号,颜色,时间戳,弹幕池,用户hash,弹幕ID"
                    std::string p_attr = node.attribute("p").as_string();
                    double video_time = 0.0;
                    int64_t send_timestamp = 0;
                    std::string user_hash;

                    if (!p_attr.empty()) {
                        std::istringstream iss(p_attr);
                        std::string part;
                        int part_idx = 0;
                        while (std::getline(iss, part, ',')) {
                            if (part_idx == 0) {
                                // 视频内时间
                                video_time = std::stod(part);
                            } else if (part_idx == 4) {
                                // 发送时间戳
                                send_timestamp = std::stoll(part);
                            } else if (part_idx == 6) {
                                // 用户Hash
                                user_hash = part;
                                break;
                            }
                            part_idx++;
                        }
                    }

                    json danmaku_item;
                    danmaku_item["content"] = trimmed;
                    danmaku_item["video_time"] = video_time;
                    danmaku_item["send_time"] = send_timestamp;
                    danmaku_item["user_hash"] = user_hash;
                    danmaku_list.push_back(danmaku_item);
                }
            }
        }

        std::cout << "Got " << danmaku_list.size() << " danmaku" << std::endl;

    } catch (const std::exception& e) {
        std::cout << "Danmaku error: " << e.what() << std::endl;
    }

    json result;
    result["total"] = danmaku_list.size();
    result["data"] = danmaku_list;
    return result;
}
