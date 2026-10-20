"""Lấy OHLCV lịch sử và chuẩn hóa thành adjusted close có provenance."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
import logging
import time
from typing import Any


logger = logging.getLogger(__name__)


def _fetch_ohlcv_with_retry(fetcher: Any, **kwargs: Any) -> Any:
    """Retry only Vnstock's transient policy/network failure, with a short bound.

    Vnstock 5.x exposes this failure as ``NetworkError`` from its private
    ``_core`` module. Checking the exception class name keeps this adapter
    compatible with patch releases while avoiding retries for data/schema bugs.
    """
    delays = (2, 5)
    for attempt in range(len(delays) + 1):
        try:
            return fetcher.ohlcv(**kwargs)
        except Exception as exc:
            is_vnstock_network_error = (
                type(exc).__name__ == "NetworkError"
                and type(exc).__module__.endswith("_core")
            )
            if not is_vnstock_network_error or attempt == len(delays):
                raise
            delay = delays[attempt]
            logger.warning(
                "Vnstock network/policy request failed; retry %s/%s in %s seconds: %s",
                attempt + 1,
                len(delays),
                delay,
                exc,
            )
            time.sleep(delay)


def _iso_value(value: Any) -> str:
    """Đổi ngày/giờ do pandas trả về thành chuỗi ISO để ghi JSON."""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def collect(
    stock_symbols: tuple[str, ...],
    benchmark_index: str,
    date_from: str,
    date_to: str,
    source: str = "kbs",
) -> list[dict[str, object]]:
    """Crawl OHLCV qua Vnstock, giữ raw rows và tạo quan sát đã chuẩn hóa.

    Giá đóng cửa cổ phiếu từ Vnstock đã điều chỉnh theo sự kiện quyền và được
    trả bằng nghìn đồng. Hàm đổi sang đồng, tính lợi suất từ hai phiên liên tiếp,
    đồng thời giữ một phiên đệm trước date_from để tính lợi suất phiên đầu.
    """
    try:
        from vnstock import Market
    except ImportError as exc:
        raise RuntimeError(
            "Thiếu vnstock. Cài theo requirements-market.txt trước khi crawl."
        ) from exc

    start_day = date.fromisoformat(date_from)
    end_day = date.fromisoformat(date_to)
    if start_day > end_day:
        raise ValueError("market_observation_date_from phải trước hoặc bằng date_to.")

    # Yêu cầu lùi một ngày lịch để lấy phiên gần nhất làm mốc lợi suất đầu kỳ.
    request_start = (start_day.fromordinal(start_day.toordinal() - 7)).isoformat()
    market = Market()
    instruments = [(symbol, "equity") for symbol in stock_symbols]
    instruments.append((benchmark_index, "index"))
    collected: list[dict[str, object]] = []

    for symbol, instrument_type in instruments:
        fetcher = getattr(market, instrument_type)(symbol)
        frame = _fetch_ohlcv_with_retry(
            fetcher,
            start=request_start,
            end=date_to,
            interval="1D",
            source=source,
        )
        required_columns = {"time", "close"}
        if instrument_type == "equity":
            required_columns.add("volume")
        missing = required_columns.difference(frame.columns)
        if missing or frame.empty:
            raise RuntimeError(f"{symbol}: Vnstock trả dữ liệu rỗng hoặc thiếu cột {sorted(missing)}.")

        attrs = dict(frame.attrs)
        actual_source = str(attrs.get("source", "")).lower()
        if actual_source != source.lower():
            raise RuntimeError(f"{symbol}: backend trả {actual_source!r}, cần {source!r}.")

        # Lưu nguyên các dòng Vnstock trả về trước khi loại trùng/chuẩn hóa.
        raw_rows = []
        for row in frame.to_dict(orient="records"):
            raw_rows.append({key: _iso_value(value) for key, value in row.items()})

        by_day: dict[str, dict[str, Any]] = {}
        for row in frame.to_dict(orient="records"):
            trading_day = _iso_value(row["time"])[:10]
            close = Decimal(str(row["close"]))
            previous = by_day.get(trading_day)
            # Dòng VNINDEX cuối kỳ có thể lặp với OHLCV khác; chỉ chấp nhận nếu close giống nhau.
            if previous is not None:
                if Decimal(str(previous["close"])) != close:
                    raise RuntimeError(f"{symbol} {trading_day}: các dòng trùng có close khác nhau.")
                continue
            by_day[trading_day] = row

        ordered_days = sorted(by_day)
        if not any(day < date_from for day in ordered_days):
            raise RuntimeError(f"{symbol}: thiếu phiên đệm trước {date_from} để tính returnValue.")

        domain_values = attrs.get("access_domain", [])
        if isinstance(domain_values, str):
            domain_values = [domain_values]
        provider_domain = str(domain_values[0]) if domain_values else ""
        if not provider_domain:
            raise RuntimeError(f"{symbol}: Vnstock không trả access_domain để ghi provenance.")
        provider_url = f"https://{provider_domain.strip('/')}/"
        retrieved_at = datetime.now(timezone.utc).isoformat()
        provider_name = str(attrs.get("source_name", source.upper()))

        observations: list[dict[str, object]] = []
        previous_close: Decimal | None = None
        for trading_day in ordered_days:
            row = by_day[trading_day]
            raw_close = Decimal(str(row["close"]))
            # Cổ phiếu trả nghìn đồng; chỉ số trả điểm nên không nhân hệ số.
            adjusted_close = raw_close * 1000 if instrument_type == "equity" else raw_close
            if trading_day >= date_from and trading_day <= date_to:
                if previous_close is None:
                    raise RuntimeError(f"{symbol} {trading_day}: không có close phiên trước để tính return.")
                return_value = adjusted_close / previous_close - Decimal(1)
                observation: dict[str, object] = {
                    "observationId": f"MARKET:{symbol}:{trading_day}",
                    "instrumentCode": symbol,
                    "tradingDate": trading_day,
                    "adjustedClose": float(adjusted_close),
                    "returnValue": float(return_value),
                    "availableAt": retrieved_at,
                    "sourceReference": provider_url,
                }
                if instrument_type == "equity":
                    observation["volume"] = int(row["volume"])
                observations.append(observation)
            previous_close = adjusted_close

        if not observations:
            raise RuntimeError(f"{symbol}: không có phiên nào trong khoảng {date_from}–{date_to}.")

        source_metadata = {
            key: attrs.get(key)
            for key in (
                "source", "source_name", "organisation", "route", "access_domain",
                "access_method", "access_protocol", "requested_at", "terms_url", "is_tool_only",
            )
            if key in attrs
        }
        collected.append(
            {
                "instrumentCode": symbol,
                "instrumentType": instrument_type,
                "dateFrom": date_from,
                "dateTo": date_to,
                "requestStartWithBuffer": request_start,
                "firstTradingDate": observations[0]["tradingDate"],
                "lastTradingDate": observations[-1]["tradingDate"],
                "count": len(observations),
                "source": "Vnstock",
                "sourceCode": source,
                "providerName": provider_name,
                "sourceReference": provider_url,
                "documentationUrl": "https://vnstocks.com/docs/vnstock/thi-truong-market",
                "retrievedAt": retrieved_at,
                "sourceMetadata": source_metadata,
                "rawRows": raw_rows,
                "observations": observations,
            }
        )

    return collected
