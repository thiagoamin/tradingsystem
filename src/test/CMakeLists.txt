cmake_minimum_required(VERSION 3.20)

include(FetchContent)

FetchContent_Declare(
    googletest
    URL https://github.com/google/googletest/archive/refs/tags/v1.14.0.tar.gz
)
set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(googletest)

set(TESTABLE_SOURCES
    ${CMAKE_SOURCE_DIR}/src/market_data/MarketBucket.cpp
    ${CMAKE_SOURCE_DIR}/src/market_data/MarketDataEngine.cpp
    ${CMAKE_SOURCE_DIR}/src/market_data/InstrumentMarketState.cpp
    ${CMAKE_SOURCE_DIR}/src/market_data/BarBuilder.cpp
)

add_executable(unit_tests
    unit/test_market_bucket.cpp
    unit/test_instrument_market_state.cpp
    ${TESTABLE_SOURCES}
)
target_include_directories(unit_tests PRIVATE ${CMAKE_SOURCE_DIR}/src)
target_link_libraries(unit_tests PRIVATE GTest::gtest_main)

add_executable(e2e_tests
    e2e/test_pipeline.cpp
    ${TESTABLE_SOURCES}
)
target_include_directories(e2e_tests PRIVATE ${CMAKE_SOURCE_DIR}/src)
target_link_libraries(e2e_tests PRIVATE GTest::gtest_main)

include(GoogleTest)
gtest_discover_tests(unit_tests)
gtest_discover_tests(e2e_tests)
