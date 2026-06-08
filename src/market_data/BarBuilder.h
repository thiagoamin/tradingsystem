#pragma once

#include <cstdint>

#include "events/FeatureBar.h"
#include "events/TradeTick.h"

class BarBuilder
{
   public:
    BarBuilder(int64_t &barId);

    void build();

   private:
    int64_t interval_ns_;
};