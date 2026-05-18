#include "InstrumentMarketState.h"

InstrumentMarketState::InstrumentMarketState(InstrumentId id) : instrumentId_(id) {}
void InstrumentMarketState::onTick(const TradeTick &tick) {}