# Mean Reversion

This package converts a residual-return panel into Ornstein--Uhlenbeck (OU)
parameter and s-score paths.

Implementation map:

- `ou_estimator.py`: fits one OU/AR(1) model from one residual window.
- `model.py`: applies the estimator through time without lookahead.
- `factor_ou_model.py`: fits the paper-style assigned-sector-ETF beta and OU
  signal together on one trailing window for each decision date.

For trailing residual returns $\widetilde{R}_{i,u}$, define the residual level:

$$
X_{i,u} = \sum_v \widetilde{R}_{i,v}.
$$

The fitted discrete OU model is:

$$
X_{i,u+1} = a_i + b_i X_{i,u} + \eta_{i,u+1}.
$$

For $0 < b_i < 1$, the implementation computes:

$$
\widehat{\kappa}_i = -252\log(\widehat{b}_i),
\qquad
\widehat{m}_i = \frac{\widehat{a}_i}{1-\widehat{b}_i},
\qquad
\widehat{\sigma}_{eq,i}
=
\frac{\widehat{\sigma}_{\eta,i}}{\sqrt{1-\widehat{b}_i^2}}.
$$

The terminal s-score is:

$$
s_{i,t}
=
\frac{X_{i,t-1}-\widehat{m}_{i,t}}
{\widehat{\sigma}_{eq,i,t}}.
$$

`RollingOUScoreModel` uses only residual observations ending before each
scored date. The daily paper-replication experiment requires a 60-observation
window and marks a stock eligible only when its estimated mean-reversion time
is less than 30 trading days.

`RollingOUScoreModel` supports residual series already produced by an upstream
transformer. `RollingAssignedEtfOUScoreModel` implements the paper-style ETF
signal directly: at each decision date, it assigns one sector ETF to each
stock, estimates its single ETF beta from the trailing 60 days, constructs
that same trailing residual history, and fits the OU/s-score model. This avoids
mixing residuals constructed under different historical beta estimates.

`OUEstimator` can also be supplied to
`ResidualStateTransformer(..., ou_estimator=...)`. In that mode the residual
state transformer adds `ou_s_score` and `ou_mean_reversion_days` panels to its
output, which can then feed either the regime classifier (as extra features)
or the hybrid strategy (via `mr_score_source="ou_s_score"`). The OU s-score
is the Avellaneda--Lee specification; whether it is empirically better than
the residual-state displacement score is data-dependent (in 2020--2025 tech
the displacement score wins; see the experiment README).
