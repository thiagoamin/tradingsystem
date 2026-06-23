#pragma once

#include <format>
#include <filesystem>
#include <spdlog/async.h>
#include <spdlog/spdlog.h>
#include <spdlog/sinks/rotating_file_sink.h>

#include "utils/TimeUtils.h"

inline bool initLogger(const std::string &name = "orion")
{
    try
    {
        int maxFileSize = 1024 * 1024 * 10; // 10MB
        int maxFiles    = 99999;
        spdlog::init_thread_pool(8192, 1);
        std::filesystem::create_directories("logs");
        std::string log_path = std::format("logs/{}_{}.log", name, TimeUtils::getCurrentDate());

        auto logger = spdlog::create_async<spdlog::sinks::rotating_file_sink_mt>(
            "orion", log_path, maxFileSize, maxFiles); // mutex but not on hot path, runs async
        spdlog::set_default_logger(logger);

        return true;
    }
    catch (spdlog::spdlog_ex &exception)
    {
        printf("Logger init fail: %s\n", exception.what());
        return false;
    }
}