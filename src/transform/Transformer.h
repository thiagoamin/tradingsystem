#pragma once

#include <concepts>
#include <span>

#include "events/FeatureBar.h"

namespace transform
{
template<typename T> // becomes the contract
concept Transformer = requires(T t, std::span<const FeatureBar> bars) {
    t.transform(bars); // not including fit and fit transform from python base.py
};
}; // namespace transform

// namespace transform