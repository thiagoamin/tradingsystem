#pragma once

/**
 * @file FactorSpec.h
 * @author Phi Lam (lamyenphi14@gmail.com)
 * @brief Per-stock factor assignments used during residualization
 * @version 0.1
 * @date 2026-07-08
 *
 * @copyright Copyright (c) 2026
 *
 */

#include <array>
#include <cstddef>
#include <span>

#include "core/InstrumentId.h"

inline constexpr size_t kMaxFactorsPerStock = 3; // max stocks I'll hedge against

class FactorSpec
{
   public:
    /**
     * @brief One stock's full factor assignment: a fixed-capacity list of
     * factor InstrumentIds plus how many of them are actually in use.
     *
     */
    struct Assignment
    {
        std::array<InstrumentId, kMaxFactorsPerStock>
               factors{}; ///< Factor instruments this stock is hedged against.
        size_t size = 0;  ///< Number of valid entries in factors (<= kMaxFactorsPerStock).
    };

    /**
     * @brief Construct a new Factor Spec object
     *
     * @param assignments Per-stock/instrument factor assignments, indexed by InstrumentId
     *
     */
    explicit FactorSpec(std::array<Assignment, kNumInstruments> assignments)
      : instrAssignments_(assignments)
    {
    }

    /**
     * @brief Return factor tickers for stock
     *
     * @param stock Instrument to look up factor assignments for.
     * @return std::span<const InstrumentId> lightweight sequence of factor tickers
     */
    std::span<const InstrumentId> factorsFor(InstrumentId stock) const
    {
        const auto &assignment = instrAssignments_[static_cast<size_t>(stock)];
        return std::span<const InstrumentId>(assignment.factors.data(), assignment.size);
    }

   private:
    std::array<Assignment, kNumInstruments> instrAssignments_;
};