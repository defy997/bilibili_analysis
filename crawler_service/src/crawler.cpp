#include "crawler.h"
#include "pugixml.hpp"
#include <curl/curl.h>
#include <random>
#include <thread>
#include <chrono>
#include <iostream>
#include <sstream>
#include <algorithm>

// libcurl write callback
static size_t write_callback(char* ptr, size_t size, size_t nmemb, void* userdata) {
    auto* buf = static_cast<std::string*>(userdata);
    buf->append(ptr, size * nmemb);
    return size * nmemb;
}

Crawler::Crawler(const Config& cfg) : config_(cfg) {
    curl_global_init(CURL_GLOBAL_DEFAULT);
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

std::string Crawler::fetch_proxy() {
    std::string body = http_get_direct(config_.proxy_pool_url);

    // 去除首尾空白和换行
    auto trim = [](std::string& s) {
        size_t start = s.find_first_not_of(" \t\r\n");
        size_t end = s.find_last_not_of(" \t\r\n");
        if (start == std::string::npos) { s.clear(); return; }
        s = s.substr(start, end - start + 1);
    };
    trim(body);

    // 校验：必须是 "数字.数字.数字.数字:端口" 格式，不能是 JSON 错误响应
    if (body.empty() || body[0] == '{' || body[0] == '<') {
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

    std::cout << "Fetched proxy: " << body << std::endl;
    return body;  // "ip:port"
}

std::string Crawler::get_proxy() {
    std::lock_guard<std::mutex> lock(proxy_mutex_);
    return current_proxy_;
}

void Crawler::rotate_proxy() {
    std::lock_guard<std::mutex> lock(proxy_mutex_);

    if (!current_proxy_.empty()) {
        // 当前是代理 IP 被封 → 先回退本地 IP
        std::cout << "Proxy " << current_proxy_ << " got 412, falling back to local IP" << std::endl;
        current_proxy_.clear();
        return;
    }

    // 当前是本地 IP 被封 → 从代理池取新 IP
    try {
        std::string new_proxy = fetch_proxy();
        current_proxy_ = new_proxy;
        std::cout << "Local IP got 412, switched to proxy: " << current_proxy_ << std::endl;
    } catch (const std::exception& e) {
        std::cout << "Failed to get proxy: " << e.what() << ", staying on local IP" << std::endl;
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

    // 挂代理池的代理（账密认证）
    std::string proxy = get_proxy();
    if (!proxy.empty()) {
        std::string proxy_url = "http://" + proxy;
        curl_easy_setopt(curl, CURLOPT_PROXY, proxy_url.c_str());
        if (!config_.proxy_user.empty()) {
            std::string auth = config_.proxy_user + ":" + config_.proxy_pass;
            curl_easy_setopt(curl, CURLOPT_PROXYUSERPWD, auth.c_str());
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
    std::string url = "https://api.bilibili.com/x/web-interface/view?bvid=" + bvid;
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
    return result;
}

// ============================================================
// 爬取：评论（412 时换代理继续）
// ============================================================

json Crawler::crawl_comments(int64_t aid, const std::string& cookie) {
    json all_comments = json::array();
    int64_t next_cursor = 0;
    int page = 0;
    int anti_crawl_hits = 0;
    const int max_anti_crawl = 5;  // 代理池模式下可以多试几次

    while (true) {
        page++;
        std::ostringstream url;
        url << "https://api.bilibili.com/x/v2/reply/main"
            << "?type=1&oid=" << aid
            << "&mode=3&next=" << next_cursor;

        for (int retry = 0; retry < config_.max_retries; retry++) {
            try {
                std::string body = http_get(url.str(), cookie);
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
                          << "/" << max_anti_crawl << "), rotating proxy..." << std::endl;

                if (anti_crawl_hits >= max_anti_crawl) {
                    std::cout << "Too many 412s, returning " << all_comments.size()
                              << " comments" << std::endl;
                    json result;
                    result["total"] = all_comments.size();
                    result["data"] = all_comments;
                    return result;
                }

                rotate_proxy();
                // 换完代理等 2 秒再试
                std::this_thread::sleep_for(std::chrono::seconds(2));
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
    std::ostringstream url;
    url << "https://api.bilibili.com/x/player/playurl"
        << "?bvid=" << bvid
        << "&cid=" << cid
        << "&fnval=16&fnver=0&fourk=1";

    std::string body = http_get(url.str(), cookie);
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
                    danmaku_list.push_back(trimmed);
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
