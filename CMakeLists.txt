cmake_minimum_required(VERSION 3.16)

message(STATUS "⚙️ Configuring Live Testing")

project(projectorion LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(IBKR_CLIENT_DIR
   "${CMAKE_SOURCE_DIR}/third_party/ibkr_10.37/source/cppclient/client"
   "${CMAKE_SOURCE_DIR}/third_party/ibkr_10.37/source/cppclient/client/protobufUnix"
)

file(GLOB IBKR_CLIENT_SOURCES
    "${IBKR_CLIENT_DIR}/*.cpp"
)

add_executable(ibkr_smoke_test
    "${CMAKE_SOURCE_DIR}/src/ibkr_smoke_test.cpp"
    ${IBKR_CLIENT_SOURCES}
)

target_include_directories(ibkr_smoke_test PRIVATE
    ${IBKR_INCLUDE_DIRS}
)

