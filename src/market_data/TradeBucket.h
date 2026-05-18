#pragma once
#include "events/TradeTick.h"
#include "events/FeatureBar.h"
#include <vector>

class TradeBucket
{
public:
    void add();
    void clear();
    void isEmpty();

private:
    std::vector<TradeTick> ticks_;
    FeatureBar bucketFeatures_;
};