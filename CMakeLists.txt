cmake_minimum_required(VERSION 3.20)

message(STATUS "⚙️ Configuring Live Testing")

project(projectorion LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(Protobuf REQUIRED)

message(STATUS "🛜 Protobuf include dirs: ${Protobuf_INCLUDE_DIRS}")
message(STATUS "🛜 Protobuf libraries: ${Protobuf_LIBRARIES}")
message(STATUS "🛜 Protobuf version: ${Protobuf_VERSION}")

# spdlog
add_subdirectory(third_party/spdlog)

set(IBKR_CLIENT_DIR
   "${CMAKE_SOURCE_DIR}/third_party/ibkr_10.37/source/cppclient/client"
)

file(GLOB IBKR_CLIENT_SOURCES
    "${IBKR_CLIENT_DIR}/*.cpp"
)

file(GLOB IBKR_PROTO_SOURCES
    "${IBKR_CLIENT_DIR}/protobufUnix/*.cc"
)

set(IBKR_INCLUDE_DIRS
    "${IBKR_CLIENT_DIR}"
    "${CMAKE_SOURCE_DIR}/third_party/ibkr_10.37/source/cppclient"
    "${CMAKE_SOURCE_DIR}/third_party/ibkr_10.37/source"
    "${IBKR_CLIENT_DIR}/protobufUnix"
)

add_library(ibkr_sdk STATIC
    ${IBKR_CLIENT_SOURCES}
    ${IBKR_PROTO_SOURCES}
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

file(GLOB_RECURSE PROJECT_SOURCES
    "${CMAKE_SOURCE_DIR}/src/*.cpp"
)

list(FILTER PROJECT_SOURCES EXCLUDE REGEX ".*main\\.cpp$")
list(FILTER PROJECT_SOURCES EXCLUDE REGEX ".*ibkr_connect_test\\.cpp$")
list(FILTER PROJECT_SOURCES EXCLUDE REGEX ".*/test/.*\\.cpp$")

if ("${TARGET}" STREQUAL "binary")
    add_executable(projectorion
        "${CMAKE_SOURCE_DIR}/src/main.cpp"
        ${PROJECT_SOURCES}
    )

    target_include_directories(projectorion PRIVATE
        ${CMAKE_SOURCE_DIR}/src
    )

    target_link_libraries(projectorion PRIVATE
        spdlog::spdlog
        ibkr_sdk
    )

    add_executable(ibkr_connect_test
        "${CMAKE_SOURCE_DIR}/src/ibkr_connect_test.cpp"
    )

    target_link_libraries(ibkr_connect_test PRIVATE
        ibkr_sdk
    )

elseif ("${TARGET}" STREQUAL "test")
    enable_testing()
    add_subdirectory(src/test)

else()
    message(FATAL_ERROR "❌ Please set TARGET to 'binary' or 'test' using -DTARGET=<target>")
    
endif()