#pragma once

namespace IbkrErrorCodes
{
// System
constexpr int CONNECTION_LOST          = 1100;
constexpr int CONNECTION_RESTORED_LOST = 1101;
constexpr int CONNECTION_RESTORED_OK   = 1102;
constexpr int PORT_RESET               = 1300;
constexpr int NOT_CONNECTED            = 504;

// Orders
constexpr int ORDER_REJECTED  = 201;
constexpr int ORDER_CANCELLED = 202;

// Market data
constexpr int NOT_SUBSCRIBED       = 354;
constexpr int PARTIAL_SUBSCRIPTION = 10090;
constexpr int DELAYED_NOT_ENABLED  = 10186;

// Informational range
constexpr int INFO_MIN = 2100;
constexpr int INFO_MAX = 2200;
} 