from __future__ import annotations

from datetime import date

from fetchers_new.thetadata.theta_bulk_downloader import ThetaDataBulkDownloader


def main() -> None:

    start_date = date(2019, 1, 1)
    end_date = date(2025, 12, 31)
    symbols = ["AAPL"]

    downloader = ThetaDataBulkDownloader(
        data_root="data_new",
        dataframe_type="polars",
        default_venue="utp_cta",
        max_retries=2,
        retry_sleep_seconds=0.25,
    )

    trade_results = downloader.download_stock_trades(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        overwrite=False,
    )
    trade_summary = downloader.summarize_results(trade_results)

    quote_results = downloader.download_stock_quotes(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        interval="500ms",
        overwrite=False,
    )
    quote_summary = downloader.summarize_results(quote_results)

    print("Trades summary:", trade_summary)
    print("Quotes summary:", quote_summary)


if __name__ == "__main__":
    main()
