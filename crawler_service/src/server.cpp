#include "server.h"
#include "crawler.h"
#include "httplib.h"
#include <iostream>

static json make_error(const std::string& msg) {
    json resp;
    resp["success"] = false;
    resp["error"] = msg;
    return resp;
}

void start_server(const Config& cfg) {
    httplib::Server svr;
    Crawler crawler(cfg);

    // Health check
    svr.Get("/health", [](const httplib::Request&, httplib::Response& res) {
        res.set_content(R"({"status":"ok"})", "application/json");
    });

    // POST /crawl/video
    svr.Post("/crawl/video", [&crawler](const httplib::Request& req, httplib::Response& res) {
        try {
            auto body = json::parse(req.body);
            std::string bvid = body.value("bvid", "");
            std::string cookie = body.value("cookie", "");

            if (bvid.empty()) {
                res.status = 400;
                res.set_content(make_error("bvid is required").dump(), "application/json");
                return;
            }

            json data = crawler.crawl_video(bvid, cookie);

            json resp;
            resp["success"] = true;
            resp["data"] = data;
            res.set_content(resp.dump(), "application/json");

        } catch (const std::exception& e) {
            res.status = 500;
            res.set_content(make_error(e.what()).dump(), "application/json");
        }
    });

    // POST /crawl/comments
    svr.Post("/crawl/comments", [&crawler](const httplib::Request& req, httplib::Response& res) {
        try {
            auto body = json::parse(req.body);
            int64_t aid = body.value("aid", (int64_t)0);
            std::string cookie = body.value("cookie", "");

            if (aid == 0) {
                res.status = 400;
                res.set_content(make_error("aid is required").dump(), "application/json");
                return;
            }

            json data = crawler.crawl_comments(aid, cookie);

            json resp;
            resp["success"] = true;
            resp["total"] = data["total"];
            resp["data"] = data["data"];
            res.set_content(resp.dump(), "application/json");

        } catch (const std::exception& e) {
            res.status = 500;
            res.set_content(make_error(e.what()).dump(), "application/json");
        }
    });

    // POST /crawl/danmaku
    svr.Post("/crawl/danmaku", [&crawler](const httplib::Request& req, httplib::Response& res) {
        try {
            auto body = json::parse(req.body);
            int64_t cid = body.value("cid", (int64_t)0);
            std::string cookie = body.value("cookie", "");

            if (cid == 0) {
                res.status = 400;
                res.set_content(make_error("cid is required").dump(), "application/json");
                return;
            }

            json data = crawler.crawl_danmaku(cid, cookie);

            json resp;
            resp["success"] = true;
            resp["total"] = data["total"];
            resp["data"] = data["data"];
            res.set_content(resp.dump(), "application/json");

        } catch (const std::exception& e) {
            res.status = 500;
            res.set_content(make_error(e.what()).dump(), "application/json");
        }
    });

    // POST /crawl/audio-url
    svr.Post("/crawl/audio-url", [&crawler](const httplib::Request& req, httplib::Response& res) {
        try {
            auto body = json::parse(req.body);
            std::string bvid = body.value("bvid", "");
            int64_t cid = body.value("cid", (int64_t)0);
            std::string cookie = body.value("cookie", "");

            if (bvid.empty() || cid == 0) {
                res.status = 400;
                res.set_content(make_error("bvid and cid are required").dump(), "application/json");
                return;
            }

            json data = crawler.crawl_audio_url(bvid, cid, cookie);

            json resp;
            resp["success"] = true;
            resp["data"] = data;
            res.set_content(resp.dump(), "application/json");

        } catch (const std::exception& e) {
            res.status = 500;
            res.set_content(make_error(e.what()).dump(), "application/json");
        }
    });

    std::cout << "Crawler service starting on port " << cfg.port << "..." << std::endl;
    svr.listen("0.0.0.0", cfg.port);
}
