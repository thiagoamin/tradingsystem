#include "BarBuilder.h"

BarBuilder::BarBuilder(int64_t interval_ns) : interval_ns_(interval_ns) {}

BarBuilder::~BarBuilder()
{
}

void BarBuilder::onTick(TickEvent tick)
{
}