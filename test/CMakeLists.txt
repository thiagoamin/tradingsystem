cmake_minimum_required(VERSION 3.20)

include(FetchContent)

FetchContent_Declare(
    googletest
    URL https://github.com/google/googletest/archive/refs/tags/v1.14.0.tar.gz
    DOWNLOAD_EXTRACT_TIMESTAMP TRUE
)
set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(googletest)


set(TESTABLE_SOURCES
    ${CMAKE_SOURCE_DIR}/src/market_data/MarketBucket.cpp
    ${CMAKE_SOURCE_DIR}/src/market_data/MarketDataEngine.cpp
    ${CMAKE_SOURCE_DIR}/src/market_data/InstrumentMarketState.cpp
    ${CMAKE_SOURCE_DIR}/src/market_data/BarBuilder.cpp
)

add_library(test_lib STATIC ${TESTABLE_SOURCES})
target_include_directories(test_lib PUBLIC ${CMAKE_SOURCE_DIR}/src)

add_executable(unit_tests
    unit/test_marketBucket.cpp
    unit/test_instrumentMarketState.cpp
)

target_link_libraries(unit_tests PRIVATE test_lib GTest::gtest_main)

add_executable(integration_tests
    integration/test_marketDataEngine.cpp
)

target_link_libraries(integration_tests PRIVATE test_lib GTest::gtest_main)

include(GoogleTest)
gtest_discover_tests(unit_tests)
gtest_discover_tests(integration_tests)
