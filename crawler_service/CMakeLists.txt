cmake_minimum_required(VERSION 3.15)
project(crawler_service LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_BUILD_TYPE Release)

# Sources
set(SOURCES
    src/main.cpp
    src/server.cpp
    src/crawler.cpp
    src/config.cpp
    third_party/pugixml/pugixml.cpp
)

add_executable(crawler_service ${SOURCES})

target_include_directories(crawler_service PRIVATE
    include
    third_party
    third_party/pugixml
)

# Find libcurl
find_package(CURL REQUIRED)
target_link_libraries(crawler_service PRIVATE CURL::libcurl)

# Find OpenSSL for MD5
find_package(OpenSSL REQUIRED)
target_link_libraries(crawler_service PRIVATE OpenSSL::SSL OpenSSL::Crypto)

# 添加编译定义使用 OpenSSL
target_compile_definitions(crawler_service PRIVATE USE_OPENSSL)

# Platform-specific
if(WIN32)
    target_link_libraries(crawler_service PRIVATE ws2_32)
    target_compile_definitions(crawler_service PRIVATE
        _WIN32_WINNT=0x0A00
        NOMINMAX
        WIN32_LEAN_AND_MEAN
    )
endif()

# Thread support
find_package(Threads REQUIRED)
target_link_libraries(crawler_service PRIVATE Threads::Threads)
