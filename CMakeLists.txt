cmake_minimum_required(VERSION 3.20)

message(STATUS "⚙️  Configuring Trading System — TARGET: ${TARGET}")

project(projectorion LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Debug)
endif()

message(STATUS "🔨 Build type: ${CMAKE_BUILD_TYPE}")

# protobuf - find in system
find_package(Protobuf REQUIRED)

message(STATUS "🛜 Protobuf include dirs: ${Protobuf_INCLUDE_DIRS}")
message(STATUS "🛜 Protobuf libraries: ${Protobuf_LIBRARIES}")
message(STATUS "🛜 Protobuf version: ${Protobuf_VERSION}")

# spdlog - needs to be compiled
add_subdirectory(third_party/spdlog)

message(STATUS "📦 spdlog: ${SPDLOG_VERSION}")

# ibkr - header
set(IBKR_CLIENT_DIR
   "${CMAKE_SOURCE_DIR}/third_party/ibkr_10.37/source/cppclient/client"
)

file(GLOB IBKR_CLIENT_SOURCES
    "${IBKR_CLIENT_DIR}/*.cpp"
)

file(GLOB IBKR_PROTO_SOURCES
    "${IBKR_CLIENT_DIR}/protobufUnix/*.cc"
)

add_library(ibkr_sdk STATIC
    ${IBKR_CLIENT_SOURCES}
    ${IBKR_PROTO_SOURCES}
)

set(IBKR_INCLUDE_DIRS
    "${IBKR_CLIENT_DIR}"
    "${CMAKE_SOURCE_DIR}/third_party/ibkr_10.37/source/cppclient"
    "${CMAKE_SOURCE_DIR}/third_party/ibkr_10.37/source"
    "${IBKR_CLIENT_DIR}/protobufUnix"
)

target_include_directories(ibkr_sdk PUBLIC
    ${IBKR_INCLUDE_DIRS}
    ${Protobuf_INCLUDE_DIRS}
)

target_link_directories(ibkr_sdk PUBLIC
    "${IBKR_CLIENT_DIR}/lib"
)

target_link_libraries(ibkr_sdk PUBLIC
    protobuf::libprotobuf
    bid
)

# project specific
file(GLOB_RECURSE PROJECT_SOURCES
    "${CMAKE_SOURCE_DIR}/src/*.cpp"
)

list(FILTER PROJECT_SOURCES EXCLUDE REGEX ".*main\\.cpp$")
list(FILTER PROJECT_SOURCES EXCLUDE REGEX ".*/bench/.*\\.cpp$")

add_library(trading_lib STATIC ${PROJECT_SOURCES})

# spsc - header only
target_include_directories(trading_lib PUBLIC
    ${CMAKE_SOURCE_DIR}/src
    ${CMAKE_SOURCE_DIR}/third_party/rigtorp/SPSCQueue/include 
)

target_link_libraries(trading_lib PUBLIC
    spdlog::spdlog
    ibkr_sdk
)

if ("${TARGET}" STREQUAL "binary")
    add_executable(projectorion
        "${CMAKE_SOURCE_DIR}/src/main.cpp"
    )

    target_link_libraries(projectorion PRIVATE trading_lib)

    
elseif ("${TARGET}" STREQUAL "bench")
    add_executable(ibkrConnectTest
        "${CMAKE_SOURCE_DIR}/bench/ibkrConnectTest.cpp"
    )

    add_executable(marketBench
        "${CMAKE_SOURCE_DIR}/bench/marketBench.cpp"
    )

    target_compile_definitions(trading_lib PUBLIC BENCH)
    target_compile_definitions(marketBench PRIVATE BENCH)

    target_link_libraries(ibkrConnectTest PRIVATE trading_lib)
    target_link_libraries(marketBench PRIVATE trading_lib)

elseif ("${TARGET}" STREQUAL "test")
    enable_testing()
    add_subdirectory(test)

else()
    message(FATAL_ERROR "❌ Please set TARGET to 'binary' or 'test' using -DTARGET=<target>")
    
endif()