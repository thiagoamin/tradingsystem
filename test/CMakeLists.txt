cmake_minimum_required(VERSION 3.20)

include(FetchContent)

FetchContent_Declare(
    googletest
    URL https://github.com/google/googletest/archive/refs/tags/v1.14.0.tar.gz
    DOWNLOAD_EXTRACT_TIMESTAMP TRUE
)
set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(googletest)

add_executable(unit_tests
    unit/test_market_bucket.cpp
    unit/test_instrument_market_state.cpp
)

target_link_libraries(unit_tests PRIVATE trading_lib GTest::gtest_main)

add_executable(integration_tests
    integration/test_market_data_engine.cpp
)

target_link_libraries(integration_tests PRIVATE trading_lib GTest::gtest_main)

include(GoogleTest)
gtest_discover_tests(unit_tests)
gtest_discover_tests(integration_tests)
