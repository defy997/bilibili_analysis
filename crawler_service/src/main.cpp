#include "config.h"
#include "server.h"
#include <iostream>

int main() {
    std::cout << "=== Bilibili Crawler Service ===" << std::endl;
    Config cfg = load_config();
    std::cout << "Port: " << cfg.port << std::endl;
    start_server(cfg);
    return 0;
}
