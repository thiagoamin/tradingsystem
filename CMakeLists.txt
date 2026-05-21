cmake_minimum_required(VERSION 3.16)

message(STATUS "⚙️ Configuring Live Testing")

project(projectorion LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(Protobuf REQUIRED)

message(STATUS "🛜 Protobuf include dirs: ${Protobuf_INCLUDE_DIRS}")
message(STATUS "🛜 Protobuf libraries: ${Protobuf_LIBRARIES}")
message(STATUS "🛜 Protobuf version: ${Protobuf_VERSION}")

set(IBKR_CLIENT_DIR
   "${CMAKE_SOURCE_DIR}/third_party/ibkr_10.37/source/cppclient/client"
)

file(GLOB IBKR_CLIENT_SOURCES
    "${IBKR_CLIENT_DIR}/*.cpp"
)

file(GLOB IBKR_PROTO_SOURCES
    "${CMAKE_SOURCE_DIR}/third_party/ibkr_10.37/source/cppclient/client/protobufUnix/*.cc"
)

file(GLOB_RECURSE PROJECT_SOURCES
    "${CMAKE_SOURCE_DIR}/src/*.cpp"
)

list(FILTER PROJECT_SOURCES EXCLUDE REGEX ".*ibkr_smoke_test\\.cpp$")
list(FILTER PROJECT_SOURCES EXCLUDE REGEX ".*ibkr_connect_test\\.cpp$")

set(IBKR_INCLUDE_DIRS
    "${IBKR_CLIENT_DIR}"
    "${CMAKE_SOURCE_DIR}/third_party/ibkr_10.37/source/cppclient"
    "${CMAKE_SOURCE_DIR}/third_party/ibkr_10.37/source"
    "${CMAKE_SOURCE_DIR}/third_party/ibkr_10.37/source/cppclient/client/protobufUnix"
)

add_executable(projectorion
    "${CMAKE_SOURCE_DIR}/src/main.cpp"
    ${PROJECT_SOURCES}
    ${IBKR_CLIENT_SOURCES}
    ${IBKR_PROTO_SOURCES}
)

target_include_directories(projectorion PRIVATE
    ${CMAKE_SOURCE_DIR}/src
    ${IBKR_INCLUDE_DIRS}
    ${Protobuf_INCLUDE_DIRS}
)

add_executable(ibkr_smoke_test
    "${CMAKE_SOURCE_DIR}/src/ibkr_smoke_test.cpp"
    ${IBKR_CLIENT_SOURCES}
    ${IBKR_PROTO_SOURCES}
)

target_include_directories(ibkr_smoke_test PRIVATE
    ${IBKR_INCLUDE_DIRS}
    ${Protobuf_INCLUDE_DIRS}
)

# target_link_libraries(ibkr_smoke_test PRIVATE
#     ${Protobuf_LIBRARIES}
# )

add_executable(ibkr_connect_test
    "${CMAKE_SOURCE_DIR}/src/ibkr_connect_test.cpp"
    ${IBKR_CLIENT_SOURCES}
    ${IBKR_PROTO_SOURCES}
)

target_include_directories(ibkr_connect_test PRIVATE
    ${IBKR_INCLUDE_DIRS}
    ${Protobuf_INCLUDE_DIRS}
)

# target_link_libraries(ibkr_connect_test PRIVATE
#     ${Protobuf_LIBRARIES}
# )


target_link_directories(ibkr_smoke_test PRIVATE
    "${CMAKE_SOURCE_DIR}/third_party/ibkr_10.37/source/cppclient/client/lib"
)
target_link_directories(ibkr_connect_test PRIVATE
    "${CMAKE_SOURCE_DIR}/third_party/ibkr_10.37/source/cppclient/client/lib"
)
target_link_directories(projectorion PRIVATE
    "${CMAKE_SOURCE_DIR}/third_party/ibkr_10.37/source/cppclient/client/lib"
)

target_link_libraries(ibkr_smoke_test PRIVATE protobuf::libprotobuf bid)
target_link_libraries(ibkr_connect_test PRIVATE protobuf::libprotobuf bid)
target_link_libraries(projectorion PRIVATE protobuf::libprotobuf bid)