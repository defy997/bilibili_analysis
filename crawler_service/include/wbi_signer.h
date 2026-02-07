#pragma once
#include <string>
#include <map>
#include <ctime>
#include <mutex>
#include <curl/curl.h>
#include <iostream>
#include <iomanip>
#include <sstream>
#include <openssl/md5.h>
#include "json.hpp"

// 使用 nlohmann::json 简写
using json = nlohmann::json;

// ============================================================
// Wbi 签名模块
// B站 API 认证核心算法
// ============================================================

class WbiSigner {
public:
    // 获取单例实例
    static WbiSigner& get_instance() {
        static WbiSigner instance;
        return instance;
    }

    // 初始化：从 B站 nav 接口获取密钥
    void init() {
        std::lock_guard<std::mutex> lock(mutex_);
        
        if (is_valid()) {
            std::cout << "[Wbi] Keys already valid, skip init" << std::endl;
            return;
        }
        
        fetch_wbi_keys();
    }

    // 检查密钥是否有效
    bool is_valid() const {
        return !img_key_.empty() && !sub_key_.empty();
    }

    // 生成带签名的请求参数
    // params: 原始参数列表
    // 返回: 添加了 wts 和 w_rid 的新参数列表
    std::map<std::string, std::string> sign_params(const std::map<std::string, std::string>& params) {
        std::lock_guard<std::mutex> lock(mutex_);
        
        if (!is_valid()) {
            std::cout << "[Wbi] Keys invalid, re-fetching..." << std::endl;
            fetch_wbi_keys();
        }
        
        // 1. 生成 w_rid (基于原始参数，不含 wts 和 w_rid)
        std::string w_rid = generate_wrid(params);
        
        // 2. 添加时间戳
        int64_t wts = get_current_timestamp();
        
        // 3. 构建最终参数（先排序好的参数，再添加 wts 和 w_rid）
        std::map<std::string, std::string> signed_params = params;
        signed_params["wts"] = std::to_string(wts);
        signed_params["w_rid"] = w_rid;
        
        return signed_params;
    }

    // 将参数列表转换为 URL 查询字符串
    static std::string map_to_query(const std::map<std::string, std::string>& params) {
        std::string query;
        bool first = true;
        for (const auto& [key, value] : params) {
            if (!first) query += "&";
            first = false;
            
            // URL 编码
            query += key + "=" + url_encode(value);
        }
        return query;
    }

private:
    WbiSigner() = default;
    ~WbiSigner() = default;
    WbiSigner(const WbiSigner&) = delete;
    WbiSigner& operator=(const WbiSigner&) = delete;

    // 固定的打乱顺序索引表
    static constexpr int MIXIN_TABLE[64] = {
        46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
        33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
        61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
        36, 20, 34, 44, 52
    };

    std::string img_key_;
    std::string sub_key_;
    int64_t last_fetch_time_ = 0;
    std::mutex mutex_;
    static constexpr int KEY_EXPIRY_SECONDS = 6 * 3600;  // 6小时过期

    // 获取当前时间戳（秒）
    static int64_t get_current_timestamp() {
        return std::time(nullptr);
    }

    // 从 nav 接口获取 wbi 密钥
    void fetch_wbi_keys() {
        CURL* curl = curl_easy_init();
        if (!curl) {
            std::cout << "[Wbi] Failed to init curl" << std::endl;
            return;
        }

        std::string response;
        curl_easy_setopt(curl, CURLOPT_URL, "https://api.bilibili.com/x/web-interface/nav");
        curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
        curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response);
        curl_easy_setopt(curl, CURLOPT_TIMEOUT, 10L);
        curl_easy_setopt(curl, CURLOPT_COOKIE, "SESSDATA=55d2ed48%2C1785846835%2Cd80a0*22CjDxZL1htFveMUpzPXZrxp6zwh1K5neWuRyhGlZxWZ1A3xBGw6NIs8AhnyqkO5tfmBgSVmhQTHVlNDNaMzlENjNqYjQwcGNPRzN5T05YcTN3SFRLT2ZvOW9sZHFvS295WmdRdW1YQXZzc01GMEdBek1YTGZTajNINW1jdmhRaUN4MWV6QnFLcGh3IIEC");
        
        // 必要的请求头
        struct curl_slist* headers = nullptr;
        headers = curl_slist_append(headers, "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36");
        headers = curl_slist_append(headers, "Referer: https://www.bilibili.com/");
        curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);

        CURLcode res = curl_easy_perform(curl);
        
        long http_code = 0;
        curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
        
        curl_slist_free_all(headers);
        curl_easy_cleanup(curl);

        if (res != CURLE_OK || http_code != 200) {
            std::cout << "[Wbi] Failed to fetch keys, HTTP " << http_code << std::endl;
            return;
        }

        // 使用 nlohmann/json 解析响应（新版格式）
        try {
            auto response_json = json::parse(response);
            auto data = response_json.value("data", json::object());
            auto wbi_img = data.value("wbi_img", json::object());
            
            std::string img_url = wbi_img.value("img_url", "");
            std::string sub_url = wbi_img.value("sub_url", "");
            
            if (img_url.empty() || sub_url.empty()) {
                std::cout << "[Wbi] Empty wbi_img URLs, trying old format..." << std::endl;
                // 兼容旧格式：直接包含 URL
                std::string wbi_img_str = data.value("wbi_img", "");
                if (!wbi_img_str.empty()) {
                    // 旧格式可能是逗号分隔的 URL
                    size_t comma = wbi_img_str.find(',');
                    if (comma != std::string::npos) {
                        img_url = wbi_img_str.substr(0, comma);
                        sub_url = wbi_img_str.substr(comma + 1);
                    } else {
                        img_url = wbi_img_str;
                        sub_url = "";
                    }
                }
            }
            
            if (img_url.empty()) {
                std::cout << "[Wbi] Failed to parse img URLs, response preview: " << response.substr(0, 200) << std::endl;
                return;
            }
            
            // 提取文件名（去除路径和扩展名）
            img_key_ = extract_filename(img_url);
            sub_key_ = extract_filename(sub_url);

            last_fetch_time_ = get_current_timestamp();
            
            std::cout << "[Wbi] Keys fetched: img_key=" << img_key_.substr(0, 12) << "... sub_key=" << sub_key_.substr(0, 12) << "..." << std::endl;
        } catch (const std::exception& e) {
            std::cout << "[Wbi] JSON parse error: " << e.what() << std::endl;
            return;
        }
    }

    // 从 URL 提取文件名（不含扩展名）
    std::string extract_filename(const std::string& url) {
        size_t slash_pos = url.find_last_of('/');
        size_t dot_pos = url.find_last_of('.');
        
        std::string filename = (slash_pos != std::string::npos) ? url.substr(slash_pos + 1) : url;
        if (dot_pos != std::string::npos && dot_pos > slash_pos) {
            filename = filename.substr(0, dot_pos - slash_pos - 1);
        }
        return filename;
    }

    // 生成 mixin key（核心算法）
    std::string get_mixin_key() {
        std::string s = img_key_ + sub_key_;
        std::string key;
        for (int i = 0; i < 64; ++i) {
            if (MIXIN_TABLE[i] < static_cast<int>(s.length())) {
                key += s[MIXIN_TABLE[i]];
            }
        }
        return key.substr(0, 32);
    }

    // 生成 w_rid (MD5签名)
    std::string generate_wrid(const std::map<std::string, std::string>& params) {
        // 1. 按 key 的 ASCII 升序排序
        std::string query;
        for (const auto& [key, value] : params) {
            if (!query.empty()) query += "&";
            query += key + "=" + value;
        }
        
        // 2. 拼接 mixin key
        std::string mixin = get_mixin_key();
        query += mixin;
        
        // 3. MD5 签名
        return md5_hash(query);
    }

    // MD5 哈希（使用 OpenSSL）
    std::string md5_hash(const std::string& input) {
        unsigned char md5[MD5_DIGEST_LENGTH];
        MD5(reinterpret_cast<const unsigned char*>(input.c_str()), input.length(), md5);
        
        std::stringstream ss;
        for (int i = 0; i < MD5_DIGEST_LENGTH; i++) {
            ss << std::hex << std::setw(2) << std::setfill('0') << static_cast<int>(md5[i]);
        }
        return ss.str();
    }

    // URL 编码
    static std::string url_encode(const std::string& value) {
        CURL* curl = curl_easy_init();
        if (!curl) return value;
        
        char* encoded = curl_easy_escape(curl, value.c_str(), value.length());
        std::string result(encoded);
        curl_free(encoded);
        curl_easy_cleanup(curl);
        
        return result;
    }

    // curl write callback
    static size_t write_callback(char* ptr, size_t size, size_t nmemb, void* userdata) {
        auto* buf = static_cast<std::string*>(userdata);
        buf->append(ptr, size * nmemb);
        return size * nmemb;
    }
};
