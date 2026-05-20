#pragma once

#include <cstdint>
#include "events/TradeTick.h"
#include "events/FeatureBar.h"

class BarBuilder
{
public:
    BarBuilder(int64_t &barId);

    void build();

private:
    int64_t interval_ns_;
};