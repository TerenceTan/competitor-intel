"""
Market-level localisation config for APAC competitor scraping.

Two scraping methods per competitor-market pair:
- "url"       — Playwright hits a market-specific URL directly (0 ScraperAPI credits)
- "geo_proxy" — ScraperAPI with country_code param on the global URL (5-10 credits)

Most brokers use URL-path routing, so the majority of requests cost 0 credits.
"""

from typing import Optional

PRIORITY_MARKETS = ["sg", "my", "th", "vn", "id", "hk", "tw", "cn", "mn"]

# Human-readable names for dashboard display
MARKET_NAMES = {
    "sg": "Singapore",
    "my": "Malaysia",
    "th": "Thailand",
    "vn": "Vietnam",
    "id": "Indonesia",
    "hk": "Hong Kong",
    "tw": "Taiwan",
    "cn": "China",
    "mn": "Mongolia",
}

# ScraperAPI country_code mapping (ISO 3166-1 alpha-2)
SCRAPERAPI_COUNTRY_CODES = {
    "sg": "sg",
    "my": "my",
    "th": "th",
    "vn": "vn",
    "id": "id",
    "hk": "hk",
    "tw": "tw",
    "cn": "cn",
    "mn": "mn",
}

# ---------------------------------------------------------------------------
# Market-specific URL overrides per competitor
#
# Structure: MARKET_URLS[competitor_id][market_code] = {
#     "method": "url" | "geo_proxy",
#     "pricing_url": "...",        (optional — override for pricing page)
#     "account_urls": [...],       (optional — override for account pages)
#     "promo_url": "...",          (optional — override for promo page)
# }
#
# If a competitor-market pair is not listed, it falls back to geo_proxy
# with the global URL + ScraperAPI country_code.
# ---------------------------------------------------------------------------

MARKET_URLS: dict[str, dict[str, dict]] = {
    # IC Markets: /global/{lang}/ path routing
    # Language codes from site: en, cn, th, id, vn, my, tw, jp, ko, etc.
    "ic-markets": {
        "sg": {
            "method": "url",
            "pricing_url": "https://www.icmarkets.com/global/en/trading-accounts/overview",
        },
        "my": {
            "method": "url",
            "pricing_url": "https://www.icmarkets.com/global/my/trading-accounts/overview",
        },
        "th": {
            "method": "url",
            "pricing_url": "https://www.icmarkets.com/global/th/trading-accounts/overview",
        },
        "vn": {
            "method": "url",
            "pricing_url": "https://www.icmarkets.com/global/vn/trading-accounts/overview",
        },
        "id": {
            "method": "url",
            "pricing_url": "https://www.icmarkets.com/global/id/trading-accounts/overview",
        },
        "hk": {
            "method": "url",
            "pricing_url": "https://www.icmarkets.com/global/cn/trading-accounts/overview",
        },
        "tw": {
            "method": "url",
            "pricing_url": "https://www.icmarkets.com/global/tw/trading-accounts/overview",
        },
        "cn": {
            "method": "url",
            "pricing_url": "https://www.icmarkets.com/global/cn/trading-accounts/overview",
        },
        "mn": {
            "method": "geo_proxy",
        },
    },

    # Exness: /{lang}/ path routing on main domain
    "exness": {
        "sg": {
            "method": "url",
            "pricing_url": "https://www.exness.com/accounts/",
        },
        "my": {
            "method": "url",
            "pricing_url": "https://www.exness.com/ms/accounts/",
        },
        "th": {
            "method": "url",
            "pricing_url": "https://www.exness.com/th/accounts/",
        },
        "vn": {
            "method": "url",
            "pricing_url": "https://www.exness.com/vi/accounts/",
        },
        "id": {
            "method": "url",
            "pricing_url": "https://www.exness.com/id/accounts/",
        },
        "hk": {
            "method": "url",
            "pricing_url": "https://www.exness.com/zh-hant/accounts/",
        },
        "tw": {
            "method": "url",
            "pricing_url": "https://www.exness.com/zh-hant/accounts/",
        },
        "cn": {
            "method": "url",
            "pricing_url": "https://www.exness.com/zh-hans/accounts/",
        },
        "mn": {
            "method": "geo_proxy",
        },
    },

    # Vantage Markets: separate SEA domain (vantagemarketssea.com) + language paths
    "vantage": {
        "sg": {
            "method": "url",
            "pricing_url": "https://www.vantagemarkets.com/en-sg/trading/accounts/",
        },
        "my": {
            "method": "url",
            "pricing_url": "https://www.vantagemarkets.com/en-my/trading/accounts/",
        },
        "th": {
            "method": "url",
            "pricing_url": "https://www.vantagemarkets.com/th/trading/accounts/",
        },
        "vn": {
            "method": "url",
            "pricing_url": "https://www.vantagemarkets.com/vi/trading/accounts/",
        },
        "id": {
            "method": "url",
            "pricing_url": "https://www.vantagemarkets.com/id/trading/accounts/",
        },
        "hk": {
            "method": "url",
            "pricing_url": "https://www.vantagemarkets.com/zh-hant/trading/accounts/",
        },
        "tw": {
            "method": "url",
            "pricing_url": "https://www.vantagemarkets.com/zh-hant/trading/accounts/",
        },
        "cn": {
            "method": "url",
            "pricing_url": "https://www.vantagemarkets.com/zh-hans/trading/accounts/",
        },
        "mn": {
            "method": "geo_proxy",
        },
    },

    # XM Group: /{lang}/ path routing
    "xm": {
        "sg": {
            "method": "url",
            "pricing_url": "https://www.xm.com/account-types",
        },
        "my": {
            "method": "url",
            "pricing_url": "https://www.xm.com/ms/account-types",
        },
        "th": {
            "method": "url",
            "pricing_url": "https://www.xm.com/th/account-types",
        },
        "vn": {
            "method": "url",
            "pricing_url": "https://www.xm.com/vn/account-types",
        },
        "id": {
            "method": "url",
            "pricing_url": "https://www.xm.com/id/account-types",
        },
        "hk": {
            "method": "url",
            "pricing_url": "https://www.xm.com/cn/account-types",
        },
        "tw": {
            "method": "url",
            "pricing_url": "https://www.xm.com/tw/account-types",
        },
        "cn": {
            "method": "url",
            "pricing_url": "https://www.xm.com/cn/account-types",
        },
        "mn": {
            "method": "geo_proxy",
        },
    },

    # HFM: /int/{lang}/ path routing with regional subdomains
    "hfm": {
        "sg": {
            "method": "url",
            "pricing_url": "https://www.hfm.com/int/en/trading/account-types/",
        },
        "my": {
            "method": "url",
            "pricing_url": "https://www.hfm.com/int/ms/trading/account-types/",
        },
        "th": {
            "method": "url",
            "pricing_url": "https://www.hfm.com/int/th/trading/account-types/",
        },
        "vn": {
            "method": "url",
            "pricing_url": "https://www.hfm.com/int/vi/trading/account-types/",
        },
        "id": {
            "method": "url",
            "pricing_url": "https://www.hfm.com/int/id/trading/account-types/",
        },
        "hk": {
            "method": "url",
            "pricing_url": "https://www.hfm.com/int/cn/trading/account-types/",
        },
        "tw": {
            "method": "url",
            "pricing_url": "https://www.hfm.com/int/tw/trading/account-types/",
        },
        "cn": {
            "method": "url",
            "pricing_url": "https://www.hfm.com/int/cn/trading/account-types/",
        },
        "mn": {
            "method": "geo_proxy",
        },
    },

    # FBS: /{lang}/ path routing — /vi/ and /zh/ return 404, use geo_proxy
    "fbs": {
        "sg": {
            "method": "url",
            "pricing_url": "https://fbs.com/en/account-types",
        },
        "my": {
            "method": "url",
            "pricing_url": "https://fbs.com/ms/account-types",
        },
        "th": {
            "method": "url",
            "pricing_url": "https://fbs.com/th/account-types",
        },
        "vn": {
            "method": "geo_proxy",  # /vi/ returns 404
        },
        "id": {
            "method": "url",
            "pricing_url": "https://fbs.com/id/account-types",
        },
        "hk": {
            "method": "geo_proxy",  # /zh/ returns 404
        },
        "tw": {
            "method": "geo_proxy",  # /zh/ returns 404
        },
        "cn": {
            "method": "geo_proxy",  # /zh/ returns 404
        },
        "mn": {
            "method": "geo_proxy",
        },
    },

    # IUX: separate regional domains for VN/ID + /{lang}/ on main domain
    # /th/ redirects to /en/ — use geo_proxy for TH
    "iux": {
        "sg": {
            "method": "url",
            "pricing_url": "https://www.iux.com/en/trading-accounts",
        },
        "my": {
            "method": "url",
            "pricing_url": "https://www.iux.com/ms/trading-accounts",
        },
        "th": {
            "method": "geo_proxy",  # /th/ redirects to /en/
        },
        "vn": {
            "method": "url",
            "pricing_url": "https://www.iuxvn-trading.com/vi/trading-accounts",
        },
        "id": {
            "method": "url",
            "pricing_url": "https://www.id-iux.com/id/trading-accounts",
        },
        "hk": {
            "method": "url",
            "pricing_url": "https://www.iux.com/zh/trading-accounts",
        },
        "tw": {
            "method": "url",
            "pricing_url": "https://www.iux.com/zh/trading-accounts",
        },
        "cn": {
            "method": "url",
            "pricing_url": "https://www.iux.com/zh/trading-accounts",
        },
        "mn": {
            "method": "geo_proxy",
        },
    },

    # FxPro: uses separate regional domains for some APAC markets, not path-based
    # Path-based /th/, /vi/ on fxpro.com are unverified — use geo_proxy as safe default
    "fxpro": {
        "sg": {
            "method": "url",
            "pricing_url": "https://www.fxpro.com/trading/accounts",
        },
        "my": {
            "method": "geo_proxy",  # no verified path
        },
        "th": {
            "method": "geo_proxy",  # unverified path
        },
        "vn": {
            "method": "url",
            "pricing_url": "https://vietnam-fxpro.com/trading/accounts",
        },
        "id": {
            "method": "geo_proxy",  # unverified path
        },
        "hk": {
            "method": "geo_proxy",  # unverified path
        },
        "tw": {
            "method": "geo_proxy",  # unverified path
        },
        "cn": {
            "method": "geo_proxy",  # unverified path
        },
        "mn": {
            "method": "geo_proxy",
        },
    },

    # Mitrade: /{lang}/ path routing — verified: /my/ (not /ms/), /vn/ (not /vi/),
    # /zh/ (not /zh-hant/), /cn/ (not /zh-hans/)
    "mitrade": {
        "sg": {
            "method": "url",
            "pricing_url": "https://www.mitrade.com/en/trading-accounts",
        },
        "my": {
            "method": "url",
            "pricing_url": "https://www.mitrade.com/my/trading-accounts",
        },
        "th": {
            "method": "url",
            "pricing_url": "https://www.mitrade.com/th/trading-accounts",
        },
        "vn": {
            "method": "url",
            "pricing_url": "https://www.mitrade.com/vn/trading-accounts",
        },
        "id": {
            "method": "url",
            "pricing_url": "https://www.mitrade.com/id/trading-accounts",
        },
        "hk": {
            "method": "url",
            "pricing_url": "https://www.mitrade.com/zh/trading-accounts",
        },
        "tw": {
            "method": "url",
            "pricing_url": "https://www.mitrade.com/zh/trading-accounts",
        },
        "cn": {
            "method": "url",
            "pricing_url": "https://www.mitrade.com/cn/trading-accounts",
        },
        "mn": {
            "method": "geo_proxy",
        },
    },

    # TMGM: /en/ path — /th/ and /id/ verified, /vi/ and /ms/ return English content
    "tmgm": {
        "sg": {
            "method": "url",
            "pricing_url": "https://www.tmgm.com/en/trading/account-types",
        },
        "my": {
            "method": "geo_proxy",  # /ms/ returns English content
        },
        "th": {
            "method": "url",
            "pricing_url": "https://www.tmgm.com/th/trading/account-types",
        },
        "vn": {
            "method": "geo_proxy",  # /vi/ returns English content
        },
        "id": {
            "method": "url",
            "pricing_url": "https://www.tmgm.com/id/trading/account-types",
        },
        "hk": {
            "method": "url",
            "pricing_url": "https://www.tmgm.com/zh-hant/trading/account-types",
        },
        "tw": {
            "method": "url",
            "pricing_url": "https://www.tmgm.com/zh-hant/trading/account-types",
        },
        "cn": {
            "method": "url",
            "pricing_url": "https://www.tmgm.com/zh-hans/trading/account-types",
        },
        "mn": {
            "method": "geo_proxy",
        },
    },

    # Pepperstone: same regulatory licence for SG/MY/ID — /en/ (English), /zh/ (Chinese)
    # HK/TW use /zht/ (Traditional Chinese), CN uses /zh-cn/, plus /th-th/, /vi-vn/, /mn-mn/
    "pepperstone": {
        "sg": {
            "method": "url",
            "pricing_url": "https://pepperstone.com/en/ways-to-trade/trading-accounts/",
        },
        "my": {
            "method": "url",
            "pricing_url": "https://pepperstone.com/zh/ways-to-trade/trading-accounts/",
        },
        "th": {
            "method": "url",
            "pricing_url": "https://pepperstone.com/th-th/ways-to-trade/trading-accounts/",
        },
        "vn": {
            "method": "url",
            "pricing_url": "https://pepperstone.com/vi-vn/ways-to-trade/trading-accounts/",
        },
        "id": {
            "method": "url",
            "pricing_url": "https://pepperstone.com/en/ways-to-trade/trading-accounts/",
        },
        "hk": {
            "method": "url",
            "pricing_url": "https://pepperstone.com/zht/ways-to-trade/trading-accounts/",
        },
        "tw": {
            "method": "url",
            "pricing_url": "https://pepperstone.com/zht/ways-to-trade/trading-accounts/",
        },
        "cn": {
            "method": "url",
            "pricing_url": "https://pepperstone.com/zh-cn/ways-to-trade/trading-accounts/",
        },
        "mn": {
            "method": "url",
            "pricing_url": "https://pepperstone.com/mn-mn/ways-to-trade/trading-accounts/",
        },
    },
}


def get_market_urls(competitor_id: str, market_code: str) -> Optional[dict]:
    """
    Returns market-specific URL config for a competitor in a given market.
    Reads from DB first, falls back to hardcoded MARKET_URLS.

    Returns:
        dict with "method" key ("url" or "geo_proxy") and optional URL overrides,
        or None if no config exists (caller should use geo_proxy fallback).
    """
    # Try DB first
    try:
        from db_utils import get_market_urls_from_db
        db_result = get_market_urls_from_db(competitor_id, market_code)
        if db_result is not None:
            return db_result
    except Exception:
        pass  # fall through to hardcoded config

    # Fallback to hardcoded config
    competitor_config = MARKET_URLS.get(competitor_id)
    if not competitor_config:
        return None
    return competitor_config.get(market_code)


def get_scraperapi_country_code(market_code: str) -> Optional[str]:
    """Returns the ScraperAPI country_code for a given market, or None."""
    return SCRAPERAPI_COUNTRY_CODES.get(market_code)
