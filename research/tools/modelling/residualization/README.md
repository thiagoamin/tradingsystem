# Residualization

This package estimates per-stock factor exposures and then removes the factor-explained component of returns.

Implementation map:

- `spec.py`: stock-to-factor assignments via `FactorSpec`
- `estimators.py`: exposure estimators such as `OLSExposureEstimator`, `RidgeExposureEstimator`, and `ElasticNetExposureEstimator`
- `model.py`: orchestration in `FactorResidualizationModel`

## General Model

At the highest level, residualization assumes

$$
r_i(t) = f_{\theta}\!\left(x_i(t)\right) + \epsilon_i(t)
$$

where:

- $r_i(t)$ is the stock return
- $x_i(t)$ is the vector of factor returns assigned to stock $i$
- $f_{\theta}$ is the exposure model
- $\theta$ are the model parameters estimated from data
- $\epsilon_i(t)$ is the residual return

This package currently implements linear exposure models, so $f_{\theta}$ is specialized to a linear map with coefficient vector $\beta_i$.

## Estimation Sample

For each stock, `FactorResidualizationModel.fit(...)` in `model.py` does the following through the configured estimator:

1. Build $y$, the vector of stock returns.
2. Build $X$, the matrix of assigned factor returns.
3. Drop any row where $y$ or any factor column in $X$ is missing.
4. Require at least `min_obs_per_factor * n_factors` valid rows.

If the sample is too small or degenerate, the estimator returns `NaN` betas for that stock.

## Residual Construction

Once betas are estimated, `FactorResidualizationModel.transform(...)` in `model.py` computes explained returns as

$$
\hat{r}_i(t) = \sum_f \beta_{i,f} r_f(t)
$$

and residual returns as

$$
\epsilon_i(t) = r_i(t) - \hat{r}_i(t)
$$

If a stock's beta estimation failed, its residual series is returned as all `NaN`.

## Linear Special Case

For the linear estimators in `estimators.py`, the model becomes

$$
r_i(t) = \sum_f \beta_{i,f} r_f(t) + \epsilon_i(t)
$$

where:

- $r_i(t)$ is the stock return
- $r_f(t)$ is the return of factor $f$
- $\beta_{i,f}$ is the stock's exposure to factor $f$
- $\epsilon_i(t)$ is the residual return

There is no intercept term. By design, anything not explained by the factor span stays in the residual.

### OLS

`OLSExposureEstimator` in `estimators.py` solves the no-intercept least-squares problem

$$
\min_{\beta} \lVert y - X\beta \rVert_2^2
$$

This is ordinary linear regression without a constant. The implementation rejects rank-deficient `X` because the beta vector is not uniquely identified in that case.

### Ridge

`RidgeExposureEstimator` in `estimators.py` solves

$$
\min_{\beta} \lVert y - X\beta \rVert_2^2 + \alpha \lVert \beta \rVert_2^2
$$

The $L_2$ penalty shrinks coefficients toward zero and stabilizes the fit when factors are highly correlated.

### Elastic Net

`ElasticNetExposureEstimator` in `estimators.py` solves

$$
\min_{\beta}
\frac{1}{2n}\lVert y - X\beta \rVert_2^2
+ \alpha \cdot \text{l1\_ratio} \cdot \lVert \beta \rVert_1
+ \frac{1}{2}\alpha(1-\text{l1\_ratio})\lVert \beta \rVert_2^2
$$

where:

- $\alpha$ controls total regularization strength
- $\text{l1\_ratio} = 1$ is lasso-like
- $\text{l1\_ratio} = 0$ is ridge-like in penalty shape

Elastic net is useful when factors are correlated and you still want some sparsity.

### Scaling for `RidgeExposureEstimator` and `ElasticNetExposureEstimator`

Raw intraday returns are very small numbers, and factor columns can have different variances. Penalized regression is sensitive to scale, so `RidgeExposureEstimator` and `ElasticNetExposureEstimator` in `estimators.py` are fit on variance-scaled data:

$$
X^{\text{scaled}}_{:,j} = \frac{X_{:,j}}{s_{x,j}},
\qquad
y^{\text{scaled}} = \frac{y}{s_y}
$$

with no mean-centering. Mean-centering is intentionally skipped because the estimators are configured with `fit_intercept=False`.

After fitting on scaled data and obtaining $\beta^{\text{scaled}}$, the code maps coefficients back to the original return units:

$$
\beta_j = \beta^{\text{scaled}}_j \cdot \frac{s_y}{s_{x,j}}
$$

That gives coefficients that can be used directly in the original return equation.


